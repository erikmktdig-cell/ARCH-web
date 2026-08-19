"""Shared immutable W01 contract fixtures."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest

from arch_web import (
    CURRENT_WEB_CONTRACT_VERSION,
    ArchitectureChoice,
    ContractRef,
    ProjectKind,
    RequirementCategory,
    RequirementPriority,
    RequirementStatus,
    RouteVisibility,
    SurfaceType,
    WebInformationArchitectureContract,
    WebLifecycleStatus,
    WebProjectProfile,
    WebRequirement,
    WebRequirementsContract,
    WebRoute,
    WebRouteContract,
    WebStackProfile,
    WebSurface,
)

VERSION = "0.1.0"
NOW = datetime(2026, 8, 19, 12, 30, tzinfo=UTC)


def make_stack(**changes: object) -> WebStackProfile:
    values: dict[str, object] = {
        "contract_version": VERSION,
        "profile_id": "stack-main",
        "language": "python",
        "frontend_framework": ArchitectureChoice.UNSPECIFIED,
        "rendering_mode": ArchitectureChoice.UNSPECIFIED,
        "package_manager": ArchitectureChoice.UNSPECIFIED,
        "backend_model": ArchitectureChoice.NONE,
        "database_provider": ArchitectureChoice.NONE,
        "auth_provider": ArchitectureChoice.NONE,
        "unit_test_runner": ArchitectureChoice.UNSPECIFIED,
        "e2e_test_runner": ArchitectureChoice.UNSPECIFIED,
        "deployment_target": ArchitectureChoice.UNSPECIFIED,
        "runtime_requirement": ArchitectureChoice.UNSPECIFIED,
        "constraints": ("offline-capable", "reproducible"),
    }
    values.update(changes)
    return WebStackProfile(**values)  # type: ignore[arg-type]


def make_requirement(requirement_id: str = "REQ-001", **changes: object) -> WebRequirement:
    values: dict[str, object] = {
        "requirement_id": requirement_id,
        "category": RequirementCategory.FUNCTIONAL,
        "statement": "Visitors can inspect the product offer.",
        "priority": RequirementPriority.MUST,
        "source": "product-owner",
        "acceptance_criteria": ("Offer is visible without authentication.",),
        "route_requirement": WebRoute.QUICK,
        "security_relevance": False,
        "status": RequirementStatus.PROPOSED,
        "dependency_refs": (),
    }
    values.update(changes)
    return WebRequirement(**values)  # type: ignore[arg-type]


def make_requirements(**changes: object) -> WebRequirementsContract:
    values: dict[str, object] = {
        "contract_version": VERSION,
        "contract_id": "requirements-main",
        "project_id": "project-001",
        "route": WebRoute.QUICK,
        "requirements": (make_requirement(),),
        "assumptions": ("English content is supplied.",),
        "exclusions": ("No checkout.",),
        "unresolved_items": (),
    }
    values.update(changes)
    return WebRequirementsContract(**values)  # type: ignore[arg-type]


def make_surface(**changes: object) -> WebSurface:
    values: dict[str, object] = {
        "surface_id": "surface-home",
        "name": "Home",
        "surface_type": SurfaceType.PAGE,
        "audience": ("visitor",),
        "requirement_refs": ("REQ-001",),
        "route_refs": ("route-home",),
        "data_dependencies": (),
        "auth_requirement": "none",
        "responsive_requirement": "required",
    }
    values.update(changes)
    return WebSurface(**values)  # type: ignore[arg-type]


def make_route(**changes: object) -> WebRouteContract:
    values: dict[str, object] = {
        "route_id": "route-home",
        "path_pattern": "/",
        "surface_ref": "surface-home",
        "visibility": RouteVisibility.PUBLIC,
        "auth_requirement": "none",
        "rendering_requirement": "unspecified",
        "navigation_parent_ref": None,
        "parameter_contracts": (),
        "requirement_refs": ("REQ-001",),
    }
    values.update(changes)
    return WebRouteContract(**values)  # type: ignore[arg-type]


def make_ia(**changes: object) -> WebInformationArchitectureContract:
    values: dict[str, object] = {
        "contract_version": VERSION,
        "contract_id": "ia-main",
        "project_id": "project-001",
        "surfaces": (make_surface(),),
        "routes": (make_route(),),
    }
    values.update(changes)
    return WebInformationArchitectureContract(**values)  # type: ignore[arg-type]


def make_ref(target: Any, contract_id: str) -> ContractRef:
    return ContractRef(
        target_contract_type=target.contract_type,
        contract_id=contract_id,
        contract_version=getattr(target, "contract_version", CURRENT_WEB_CONTRACT_VERSION),
        fingerprint=target.canonical_fingerprint(),
    )


def make_project(**changes: object) -> WebProjectProfile:
    stack = make_stack()
    values: dict[str, object] = {
        "contract_version": VERSION,
        "project_id": "project-001",
        "name": "Example Web Project",
        "route": WebRoute.QUICK,
        "project_kind": ProjectKind.STATIC_SITE,
        "primary_goal": "Explain the product clearly.",
        "target_users": ("buyer", "visitor"),
        "delivery_mode": "public-web",
        "locale": "en-US",
        "status": WebLifecycleStatus.DRAFT,
        "stack_profile_ref": make_ref(stack, stack.profile_id),
        "created_at": NOW,
    }
    values.update(changes)
    return WebProjectProfile(**values)  # type: ignore[arg-type]


@pytest.fixture
def stack() -> WebStackProfile:
    return make_stack()


@pytest.fixture
def requirements() -> WebRequirementsContract:
    return make_requirements()


@pytest.fixture
def information_architecture() -> WebInformationArchitectureContract:
    return make_ia()
