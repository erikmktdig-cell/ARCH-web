"""Framework-neutral navigation and journey contracts."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum, unique

from arch_web.domain._base import WebContractRecord, freeze_strings, require_text
from arch_web.domain.errors import WebContractReferenceError, WebContractValidationError


@unique
class NavigationKind(StrEnum):
    PRIMARY = "primary"
    SECONDARY = "secondary"
    CONTEXTUAL = "contextual"
    UTILITY = "utility"
    BREADCRUMB = "breadcrumb"


@unique
class NavigationVisibility(StrEnum):
    PUBLIC = "public"
    AUTHENTICATED = "authenticated"
    INTERNAL = "internal"
    HIDDEN = "hidden"


@unique
class NavigationRelationship(StrEnum):
    HIERARCHY = "hierarchy"
    CONTEXTUAL = "contextual"
    JOURNEY = "journey"


@dataclass(frozen=True, slots=True)
class NavigationNode(WebContractRecord):
    contract_type = "navigation_node"

    node_id: str
    surface_ref: str
    label: str
    navigation_kind: NavigationKind
    visibility: NavigationVisibility
    audience: tuple[str, ...]
    order: int
    route_ref: str | None = None
    parent_node_ref: str | None = None
    requirement_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for field_name in ("node_id", "surface_ref", "label"):
            require_text(getattr(self, field_name), field_name)
        for field_name in ("route_ref", "parent_node_ref"):
            value = getattr(self, field_name)
            if value is not None:
                require_text(value, field_name)
        if self.parent_node_ref == self.node_id:
            raise WebContractValidationError("A navigation node cannot parent itself")
        if self.order < 0:
            raise WebContractValidationError("Navigation order must be non-negative")
        object.__setattr__(self, "audience", freeze_strings(self.audience, "audience", sort=True))
        object.__setattr__(
            self,
            "requirement_refs",
            freeze_strings(self.requirement_refs, "requirement_refs", sort=True),
        )


@dataclass(frozen=True, slots=True)
class NavigationEdge(WebContractRecord):
    contract_type = "navigation_edge"

    edge_id: str
    from_node_ref: str
    to_node_ref: str
    relationship: NavigationRelationship
    condition: str | None = None
    requirement_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for field_name in ("edge_id", "from_node_ref", "to_node_ref"):
            require_text(getattr(self, field_name), field_name)
        if self.from_node_ref == self.to_node_ref:
            raise WebContractValidationError("A navigation edge cannot point to itself")
        if self.condition is not None:
            require_text(self.condition, "condition")
        object.__setattr__(
            self,
            "requirement_refs",
            freeze_strings(self.requirement_refs, "requirement_refs", sort=True),
        )


@dataclass(frozen=True, slots=True)
class UserJourney(WebContractRecord):
    contract_type = "user_journey"

    journey_id: str
    name: str
    actor: str
    surface_refs: tuple[str, ...]
    success_outcome: str
    entry_condition: str = "direct"
    route_refs: tuple[str, ...] = ()
    requirement_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for field_name in ("journey_id", "name", "actor", "entry_condition", "success_outcome"):
            require_text(getattr(self, field_name), field_name)
        object.__setattr__(self, "surface_refs", freeze_strings(self.surface_refs, "surface_refs"))
        if not self.surface_refs:
            raise WebContractValidationError("A user journey requires at least one surface")
        object.__setattr__(self, "route_refs", freeze_strings(self.route_refs, "route_refs"))
        object.__setattr__(
            self,
            "requirement_refs",
            freeze_strings(self.requirement_refs, "requirement_refs", sort=True),
        )


@dataclass(frozen=True, slots=True)
class NavigationModel(WebContractRecord):
    contract_type = "navigation_model"

    navigation_id: str
    project_id: str
    nodes: tuple[NavigationNode, ...]
    edges: tuple[NavigationEdge, ...] = ()
    journeys: tuple[UserJourney, ...] = ()

    def __post_init__(self) -> None:
        require_text(self.navigation_id, "navigation_id")
        require_text(self.project_id, "project_id")
        nodes = tuple(sorted(self.nodes, key=lambda item: (item.order, item.node_id)))
        edges = tuple(sorted(self.edges, key=lambda item: item.edge_id))
        journeys = tuple(sorted(self.journeys, key=lambda item: item.journey_id))
        node_ids = tuple(item.node_id for item in nodes)
        if len(node_ids) != len(set(node_ids)):
            raise WebContractValidationError("Navigation contains duplicate node IDs")
        known = set(node_ids)
        for node in nodes:
            if node.parent_node_ref is not None and node.parent_node_ref not in known:
                raise WebContractReferenceError("Navigation parent reference is missing")
        for edge in edges:
            if edge.from_node_ref not in known or edge.to_node_ref not in known:
                raise WebContractReferenceError("Navigation edge reference is missing")
        self._reject_cycles(nodes)
        object.__setattr__(self, "nodes", nodes)
        object.__setattr__(self, "edges", edges)
        object.__setattr__(self, "journeys", journeys)

    @staticmethod
    def _reject_cycles(nodes: tuple[NavigationNode, ...]) -> None:
        parents = {node.node_id: node.parent_node_ref for node in nodes}
        for start in parents:
            seen: set[str] = set()
            current: str | None = start
            while current is not None:
                if current in seen:
                    raise WebContractValidationError("Navigation parent cycle detected")
                seen.add(current)
                current = parents[current]


__all__ = (
    "NavigationEdge",
    "NavigationKind",
    "NavigationModel",
    "NavigationNode",
    "NavigationRelationship",
    "NavigationVisibility",
    "UserJourney",
)
