"""Information architecture container and pure cross-reference validation."""

from __future__ import annotations

from dataclasses import dataclass

from arch_web.contracts.versions import require_supported_version
from arch_web.domain._base import WebContractRecord, require_text
from arch_web.domain.errors import WebContractReferenceError, WebContractValidationError
from arch_web.domain.requirements import WebRequirementsContract
from arch_web.domain.surfaces import WebRouteContract, WebSurface


@dataclass(frozen=True, slots=True)
class WebInformationArchitectureContract(WebContractRecord):
    contract_type = "web_information_architecture_contract"

    contract_version: str
    contract_id: str
    project_id: str
    surfaces: tuple[WebSurface, ...]
    routes: tuple[WebRouteContract, ...]

    def __post_init__(self) -> None:
        require_supported_version(self.contract_version)
        require_text(self.contract_id, "contract_id")
        require_text(self.project_id, "project_id")
        surfaces = tuple(sorted(self.surfaces, key=lambda item: item.surface_id))
        routes = tuple(sorted(self.routes, key=lambda item: item.route_id))
        surface_ids = tuple(item.surface_id for item in surfaces)
        route_ids = tuple(item.route_id for item in routes)
        self._reject_duplicates(surface_ids, "surface")
        self._reject_duplicates(route_ids, "route")
        known_surfaces = set(surface_ids)
        known_routes = set(route_ids)
        for route in routes:
            if route.surface_ref not in known_surfaces:
                raise WebContractReferenceError(
                    f"Route {route.route_id!r} references missing surface {route.surface_ref!r}"
                )
            if route.navigation_parent_ref not in known_routes | {None}:
                raise WebContractReferenceError(
                    f"Route {route.route_id!r} references missing navigation parent"
                )
        for surface in surfaces:
            missing_routes = set(surface.route_refs) - known_routes
            if missing_routes:
                raise WebContractReferenceError(
                    f"Surface {surface.surface_id!r} references missing routes: "
                    f"{sorted(missing_routes)!r}"
                )
            for route_id in surface.route_refs:
                route = next(item for item in routes if item.route_id == route_id)
                if route.surface_ref != surface.surface_id:
                    raise WebContractReferenceError(
                        "Surface route reference points to another surface"
                    )
        self._reject_incompatible_paths(routes)
        self._reject_navigation_cycles(routes)
        object.__setattr__(self, "surfaces", surfaces)
        object.__setattr__(self, "routes", routes)

    @staticmethod
    def _reject_duplicates(values: tuple[str, ...], kind: str) -> None:
        if len(values) != len(set(values)):
            raise WebContractValidationError(
                f"Information architecture contains duplicate {kind} IDs"
            )

    @staticmethod
    def _reject_incompatible_paths(routes: tuple[WebRouteContract, ...]) -> None:
        by_path: dict[str, WebRouteContract] = {}
        for route in routes:
            previous = by_path.get(route.path_pattern)
            if previous is not None and previous != route:
                raise WebContractValidationError(
                    f"Path {route.path_pattern!r} has incompatible route contracts"
                )
            by_path[route.path_pattern] = route

    @staticmethod
    def _reject_navigation_cycles(routes: tuple[WebRouteContract, ...]) -> None:
        parents = {route.route_id: route.navigation_parent_ref for route in routes}
        for route_id in parents:
            visited: set[str] = set()
            current: str | None = route_id
            while current is not None:
                if current in visited:
                    raise WebContractValidationError(
                        "Navigation parent relationships contain a cycle"
                    )
                visited.add(current)
                current = parents[current]

    def validate_requirements(self, requirements: WebRequirementsContract) -> None:
        if requirements.project_id != self.project_id:
            raise WebContractReferenceError("Requirements and IA belong to different projects")
        known = {requirement.requirement_id for requirement in requirements.requirements}
        refs = {ref for surface in self.surfaces for ref in surface.requirement_refs} | {
            ref for route in self.routes for ref in route.requirement_refs
        }
        missing = refs - known
        if missing:
            raise WebContractReferenceError(
                f"IA references missing requirements: {sorted(missing)!r}"
            )


__all__ = ("WebInformationArchitectureContract",)
