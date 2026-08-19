"""Web product surfaces and navigable route contracts."""

from __future__ import annotations

import re
from dataclasses import dataclass

from arch_web.domain._base import WebContractRecord, freeze_string_map, freeze_strings, require_text
from arch_web.domain.enums import RouteVisibility, SurfaceType
from arch_web.domain.errors import WebContractValidationError

_PATH = re.compile(
    r"^/(?:[A-Za-z0-9._~-]+|\{[A-Za-z_][A-Za-z0-9_]*\})(?:/(?:[A-Za-z0-9._~-]+|\{[A-Za-z_][A-Za-z0-9_]*\}))*$|^/$"
)


@dataclass(frozen=True, slots=True)
class WebSurface(WebContractRecord):
    contract_type = "web_surface"

    surface_id: str
    name: str
    surface_type: SurfaceType
    audience: tuple[str, ...]
    requirement_refs: tuple[str, ...] = ()
    route_refs: tuple[str, ...] = ()
    data_dependencies: tuple[str, ...] = ()
    auth_requirement: str = "unspecified"
    responsive_requirement: str = "unspecified"

    def __post_init__(self) -> None:
        require_text(self.surface_id, "surface_id")
        require_text(self.name, "name")
        for field_name in (
            "audience",
            "requirement_refs",
            "route_refs",
            "data_dependencies",
        ):
            object.__setattr__(
                self, field_name, freeze_strings(getattr(self, field_name), field_name, sort=True)
            )
        require_text(self.auth_requirement, "auth_requirement")
        require_text(self.responsive_requirement, "responsive_requirement")


@dataclass(frozen=True, slots=True)
class WebRouteContract(WebContractRecord):
    contract_type = "web_route_contract"

    route_id: str
    path_pattern: str
    surface_ref: str
    visibility: RouteVisibility
    auth_requirement: str
    rendering_requirement: str
    navigation_parent_ref: str | None = None
    parameter_contracts: tuple[tuple[str, str], ...] = ()
    requirement_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        require_text(self.route_id, "route_id")
        require_text(self.surface_ref, "surface_ref")
        require_text(self.auth_requirement, "auth_requirement")
        require_text(self.rendering_requirement, "rendering_requirement")
        if not _PATH.fullmatch(self.path_pattern):
            raise WebContractValidationError(
                f"Malformed framework-neutral route path: {self.path_pattern!r}"
            )
        if self.navigation_parent_ref is not None:
            require_text(self.navigation_parent_ref, "navigation_parent_ref")
            if self.navigation_parent_ref == self.route_id:
                raise WebContractValidationError("A route cannot be its own navigation parent")
        object.__setattr__(
            self,
            "parameter_contracts",
            freeze_string_map(self.parameter_contracts, "parameter_contracts"),
        )
        object.__setattr__(
            self,
            "requirement_refs",
            freeze_strings(self.requirement_refs, "requirement_refs", sort=True),
        )
        path_parameters = {
            segment[1:-1] for segment in self.path_pattern.split("/") if segment.startswith("{")
        }
        declared_parameters = {name for name, _ in self.parameter_contracts}
        if path_parameters != declared_parameters:
            raise WebContractValidationError(
                "Route parameters must exactly match path placeholders"
            )


__all__ = ("WebRouteContract", "WebSurface")
