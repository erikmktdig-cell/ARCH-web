"""Deterministic surface, route, and navigation planning."""

from __future__ import annotations

import hashlib
import re

from arch_web.contracts.canonical import canonical_bytes
from arch_web.contracts.versions import CURRENT_WEB_CONTRACT_VERSION
from arch_web.domain.enums import RequirementCategory, RouteVisibility, SurfaceType
from arch_web.domain.information_architecture import WebInformationArchitectureContract
from arch_web.domain.navigation import (
    NavigationEdge,
    NavigationKind,
    NavigationModel,
    NavigationNode,
    NavigationRelationship,
    NavigationVisibility,
    UserJourney,
)
from arch_web.domain.requirements import WebRequirement, WebRequirementsContract
from arch_web.domain.surfaces import WebRouteContract, WebSurface

_PARAM = re.compile(r"\{([A-Za-z_][A-Za-z0-9_]*)\}")


def semantic_id(prefix: str, value: object) -> str:
    return f"{prefix}-{hashlib.sha256(canonical_bytes(value)).hexdigest()[:16].upper()}"


def normalize_route_path(value: str) -> str:
    """Normalize safe separator/case variants into the W01 brace grammar."""
    if "?" in value or "#" in value or "[" in value or "]" in value:
        raise ValueError("Route identity cannot contain query, fragment, or framework syntax")
    path = value.strip()
    if not path.startswith("/"):
        raise ValueError("Route path must begin with /")
    path = re.sub(r"/+", "/", path)
    if len(path) > 1:
        path = path.rstrip("/")
    normalized: list[str] = []
    parameters: set[str] = set()
    for segment in path.split("/")[1:]:
        if not segment:
            continue
        match = _PARAM.fullmatch(segment)
        if match:
            name = match.group(1).lower()
            if name in parameters:
                raise ValueError("Dynamic route parameter names must be unique")
            parameters.add(name)
            normalized.append(f"{{{name}}}")
        elif re.fullmatch(r"[A-Za-z0-9._~-]+", segment):
            normalized.append(segment.lower())
        else:
            raise ValueError("Malformed framework-neutral route segment")
    return "/" + "/".join(normalized) if normalized else "/"


def _surface_kind(requirement: WebRequirement) -> tuple[str, str, SurfaceType, bool]:
    text = requirement.statement.lower()
    if any(term in text for term in ("product detail", "individual product")):
        return "Product detail", "products/{product_id}", SurfaceType.PAGE, True
    if any(term in text for term in ("modal", "dialog", "overlay")):
        return "Interaction", "interaction", SurfaceType.MODAL_FLOW, False
    if any(term in text for term in ("admin", "administrator")):
        return "Administration", "admin", SurfaceType.ADMIN, True
    if any(term in text for term in ("settings", "preferences")):
        return "Settings", "settings", SurfaceType.SETTINGS, True
    if any(term in text for term in ("dashboard", "metrics", "analytics")):
        return "Dashboard", "dashboard", SurfaceType.DASHBOARD, True
    if any(term in text for term in ("workspace", "account")):
        return "Workspace", "workspace", SurfaceType.WORKSPACE, True
    return "Landing", "", SurfaceType.PAGE, True


def plan_information_architecture(
    requirements: WebRequirementsContract,
) -> tuple[WebInformationArchitectureContract, NavigationModel]:
    material = tuple(
        item
        for item in requirements.requirements
        if item.category
        in {
            RequirementCategory.FUNCTIONAL,
            RequirementCategory.CONTENT,
            RequirementCategory.NAVIGATION,
        }
    )
    groups: dict[tuple[str, str, SurfaceType, bool], list[WebRequirement]] = {}
    for requirement in material:
        groups.setdefault(_surface_kind(requirement), []).append(requirement)
    if not groups:
        groups[("Landing", "", SurfaceType.PAGE, True)] = []

    auth_approved = any(
        item.category is RequirementCategory.SECURITY
        and any(term in item.statement.lower() for term in ("auth", "session", "protected"))
        for item in requirements.requirements
    )
    rows: list[tuple[WebSurface, WebRouteContract | None]] = []
    protected_types = {
        SurfaceType.ADMIN,
        SurfaceType.SETTINGS,
        SurfaceType.WORKSPACE,
        SurfaceType.DASHBOARD,
    }
    for (name, slug, surface_type, routed), refs in sorted(
        groups.items(), key=lambda item: item[0][1]
    ):
        requirement_refs = tuple(sorted(item.requirement_id for item in refs))
        surface_id = semantic_id(
            "SFC",
            {"project": requirements.project_id, "kind": surface_type.value, "slug": slug},
        )
        route: WebRouteContract | None = None
        route_refs: tuple[str, ...] = ()
        protected = surface_type in protected_types and auth_approved
        if routed:
            path = normalize_route_path(f"/{slug}" if slug else "/")
            route_id = semantic_id("RTE", {"project": requirements.project_id, "path": path})
            route = WebRouteContract(
                route_id=route_id,
                path_pattern=path,
                surface_ref=surface_id,
                visibility=(RouteVisibility.AUTHENTICATED if protected else RouteVisibility.PUBLIC),
                auth_requirement="required" if protected else "none",
                rendering_requirement="unspecified",
                parameter_contracts=tuple((name, "string") for name in _PARAM.findall(path)),
                requirement_refs=requirement_refs,
            )
            route_refs = (route_id,)
        surface = WebSurface(
            surface_id=surface_id,
            name=name,
            surface_type=surface_type,
            audience=("approved users",),
            requirement_refs=requirement_refs,
            route_refs=route_refs,
            auth_requirement="required" if protected else "none",
        )
        rows.append((surface, route))

    surfaces = tuple(row[0] for row in rows)
    routes = tuple(row[1] for row in rows if row[1] is not None)
    ia = WebInformationArchitectureContract(
        contract_version=CURRENT_WEB_CONTRACT_VERSION,
        contract_id=semantic_id(
            "WIA", {"project": requirements.project_id, "surfaces": surfaces, "routes": routes}
        ),
        project_id=requirements.project_id,
        surfaces=surfaces,
        routes=routes,
    )
    nodes: list[NavigationNode] = []
    for order, (surface, route) in enumerate(rows):
        if route is None:
            continue
        nodes.append(
            NavigationNode(
                node_id=semantic_id(
                    "NAV", {"surface": surface.surface_id, "route": route.route_id}
                ),
                surface_ref=surface.surface_id,
                route_ref=route.route_id,
                label=surface.name,
                navigation_kind=NavigationKind.PRIMARY,
                visibility=NavigationVisibility(route.visibility.value),
                audience=surface.audience,
                order=order,
                requirement_refs=surface.requirement_refs,
            )
        )
    edges = (
        tuple(
            NavigationEdge(
                edge_id=semantic_id("NED", {"from": nodes[0].node_id, "to": node.node_id}),
                from_node_ref=nodes[0].node_id,
                to_node_ref=node.node_id,
                relationship=NavigationRelationship.JOURNEY,
                requirement_refs=node.requirement_refs,
            )
            for node in nodes[1:]
        )
        if nodes
        else ()
    )
    journeys = (
        (
            UserJourney(
                journey_id=semantic_id("JNY", {"nodes": tuple(n.node_id for n in nodes)}),
                name="Primary user journey",
                actor="approved user",
                surface_refs=tuple(node.surface_ref for node in nodes),
                route_refs=tuple(node.route_ref for node in nodes if node.route_ref is not None),
                success_outcome="The approved capability is reachable.",
                requirement_refs=tuple(
                    sorted({ref for node in nodes for ref in node.requirement_refs})
                ),
            ),
        )
        if nodes
        else ()
    )
    navigation = NavigationModel(
        navigation_id=semantic_id(
            "NVM",
            {
                "project": requirements.project_id,
                "nodes": nodes,
                "edges": edges,
                "journeys": journeys,
            },
        ),
        project_id=requirements.project_id,
        nodes=tuple(nodes),
        edges=edges,
        journeys=journeys,
    )
    return ia, navigation


__all__ = ("normalize_route_path", "plan_information_architecture", "semantic_id")
