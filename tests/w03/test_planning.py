"""Surface, route, navigation, and coverage behavior."""

from __future__ import annotations

from dataclasses import replace

import pytest

from arch_web import (
    ArchitectureFindingCode,
    ArchitecturePreparationError,
    ArchitectureReadiness,
    CoverageDisposition,
    NavigationKind,
    NavigationModel,
    NavigationNode,
    NavigationVisibility,
    PrepareRequirementsCommand,
    RequirementCategory,
    RouteVisibility,
    SurfaceType,
    WebContractReferenceError,
    WebContractValidationError,
    WebLifecycleStatus,
    WebRoute,
    WebRouteContract,
    WebSurface,
    analyze_architecture,
    normalize_route_path,
    prepare_architecture,
    prepare_requirements,
)
from w02.factories import answer, intake
from w03.factories import architecture_command


@pytest.mark.parametrize("route", list(WebRoute))
def test_route_depths_can_produce_reviewable_architecture(route: WebRoute) -> None:
    result = prepare_architecture(architecture_command(route))
    assert result.review_package.readiness is ArchitectureReadiness.READY_FOR_REVIEW
    assert result.information_architecture.routes[0].path_pattern == "/"
    assert len(result.review_package.coverage) == len(
        architecture_command(route).requirements_contract.requirements
    )


def test_equivalent_inputs_are_byte_identical() -> None:
    first = prepare_architecture(architecture_command(WebRoute.STANDARD))
    second = prepare_architecture(architecture_command(WebRoute.STANDARD))
    assert first.canonical_bytes() == second.canonical_bytes()
    assert first.canonical_fingerprint() == second.canonical_fingerprint()


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("/", "/"),
        ("//About//Team/", "/about/team"),
        ("/Products/{Product_ID}", "/products/{product_id}"),
    ],
)
def test_route_path_normalization(raw: str, expected: str) -> None:
    assert normalize_route_path(raw) == expected


@pytest.mark.parametrize(
    "raw",
    ["about", "/products/[id]", "/products/{id}/{id}", "/bad path", "/a?x=1", "/a#x"],
)
def test_route_path_rejects_ambiguous_or_framework_specific_identity(raw: str) -> None:
    with pytest.raises(ValueError, match=r"Route|route|parameter|segment"):
        normalize_route_path(raw)


@pytest.mark.parametrize(
    ("statement", "surface_type", "has_route"),
    [
        ("Users inspect a dashboard of metrics.", SurfaceType.DASHBOARD, True),
        ("Users edit settings and preferences.", SurfaceType.SETTINGS, True),
        ("Users confirm in a modal dialog.", SurfaceType.MODAL_FLOW, False),
        ("Administrators manage approved records.", SurfaceType.ADMIN, True),
    ],
)
def test_surface_semantics_are_not_equivalent_to_urls(
    statement: str, surface_type: SurfaceType, has_route: bool
) -> None:
    prepared = prepare_requirements(
        PrepareRequirementsCommand(
            intake(answers=(answer("capability", RequirementCategory.FUNCTIONAL, statement),))
        )
    )
    command = architecture_command(
        requirements_contract=prepared.requirements_contract,
        requirements_review=prepared.review_package,
        approved_requirements_fingerprint=(prepared.requirements_contract.canonical_fingerprint()),
        approved_requirements_review_fingerprint=(prepared.review_package.canonical_fingerprint()),
    )
    result = prepare_architecture(command)
    surface = result.information_architecture.surfaces[0]
    assert surface.surface_type is surface_type
    assert bool(surface.route_refs) is has_route


def test_admin_and_auth_are_not_invented() -> None:
    result = prepare_architecture(architecture_command())
    assert all(
        surface.surface_type is not SurfaceType.ADMIN
        for surface in result.information_architecture.surfaces
    )
    assert all(
        route.visibility is RouteVisibility.PUBLIC
        for route in result.information_architecture.routes
    )


def test_dynamic_route_is_explicit_and_requires_data_justification() -> None:
    prepared = prepare_requirements(
        PrepareRequirementsCommand(
            intake(
                answers=(
                    answer(
                        "product-detail",
                        RequirementCategory.FUNCTIONAL,
                        "Visitors inspect an individual product detail.",
                    ),
                    answer(
                        "product-data",
                        RequirementCategory.DATA,
                        "Product data is selected by product_id.",
                    ),
                )
            )
        )
    )
    result = prepare_architecture(
        architecture_command(
            requirements_contract=prepared.requirements_contract,
            requirements_review=prepared.review_package,
            approved_requirements_fingerprint=(
                prepared.requirements_contract.canonical_fingerprint()
            ),
            approved_requirements_review_fingerprint=(
                prepared.review_package.canonical_fingerprint()
            ),
        )
    )
    route = result.information_architecture.routes[0]
    assert route.path_pattern == "/products/{product_id}"
    assert route.parameter_contracts == (("product_id", "string"),)
    assert ArchitectureFindingCode.UNJUSTIFIED_DYNAMIC_PARAMETER not in {
        item.code for item in result.review_package.findings
    }


def test_coverage_defers_design_and_implementation_explicitly() -> None:
    prepared = prepare_requirements(
        PrepareRequirementsCommand(
            intake(
                answers=(
                    answer(
                        "functional", RequirementCategory.FUNCTIONAL, "Visitors inspect the offer."
                    ),
                    answer("responsive", RequirementCategory.RESPONSIVE, "The layout adapts."),
                    answer(
                        "performance",
                        RequirementCategory.PERFORMANCE,
                        "The build meets its budget.",
                    ),
                )
            )
        )
    )
    result = prepare_architecture(
        architecture_command(
            requirements_contract=prepared.requirements_contract,
            requirements_review=prepared.review_package,
            approved_requirements_fingerprint=prepared.requirements_contract.canonical_fingerprint(),
            approved_requirements_review_fingerprint=prepared.review_package.canonical_fingerprint(),
        )
    )
    categories = {
        item.requirement_id: item.category for item in prepared.requirements_contract.requirements
    }
    by_category = {
        categories[item.requirement_ref]: item for item in result.review_package.coverage
    }
    assert (
        by_category[RequirementCategory.RESPONSIVE].disposition
        is CoverageDisposition.DEFERRED_TO_W04
    )
    assert (
        by_category[RequirementCategory.PERFORMANCE].disposition
        is CoverageDisposition.DEFERRED_TO_W06_W07
    )
    by_ref = {item.requirement_ref: item for item in result.review_package.coverage}
    assert all(item.disposition is not CoverageDisposition.UNRESOLVED for item in by_ref.values())


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("project_status", WebLifecycleStatus.DRAFT, "REQUIREMENTS_APPROVED"),
        ("project_id", "different-project", "identity"),
        ("approved_requirements_fingerprint", "0" * 64, "fingerprint"),
        ("approved_requirements_review_fingerprint", "0" * 64, "review fingerprint"),
        ("route", WebRoute.CRITICAL, "route mismatch"),
    ],
)
def test_preparation_fails_closed(field: str, value: object, message: str) -> None:
    command = architecture_command()
    changed = replace(command, **{field: value})  # type: ignore[arg-type]
    with pytest.raises(ArchitecturePreparationError, match=message):
        prepare_architecture(changed)


def test_navigation_rejects_missing_parent_and_cycle() -> None:
    node = NavigationNode(
        "node-a",
        "surface-a",
        "A",
        NavigationKind.PRIMARY,
        NavigationVisibility.PUBLIC,
        ("user",),
        0,
        parent_node_ref="missing",
    )
    with pytest.raises(WebContractReferenceError):
        NavigationModel("navigation", "project", (node,))
    node_a = replace(node, parent_node_ref="node-b")
    node_b = replace(node, node_id="node-b", surface_ref="surface-b", parent_node_ref="node-a")
    with pytest.raises(WebContractValidationError, match="cycle"):
        NavigationModel("navigation", "project", (node_a, node_b))


def test_analysis_detects_public_protected_mismatch_and_unreachable_route() -> None:
    command = architecture_command(WebRoute.STANDARD)
    result = prepare_architecture(command)
    route = replace(
        result.information_architecture.routes[0],
        visibility=RouteVisibility.AUTHENTICATED,
        auth_requirement="required",
    )
    ia = replace(result.information_architecture, routes=(route,))
    public_node = replace(result.navigation_model.nodes[0], visibility=NavigationVisibility.PUBLIC)
    navigation = replace(result.navigation_model, nodes=(public_node,))
    _, findings = analyze_architecture(
        command.requirements_contract,
        ia,
        navigation,
        expected_requirements_fingerprint=command.approved_requirements_fingerprint,
    )
    codes = {item.code for item in findings}
    assert ArchitectureFindingCode.PUBLIC_PROTECTED_MISMATCH in codes


def test_contracts_reject_duplicate_paths_and_parameter_mismatch() -> None:
    surface = WebSurface(
        "surface", "Page", SurfaceType.PAGE, ("user",), route_refs=("route-a", "route-b")
    )
    with pytest.raises(WebContractValidationError, match="parameters"):
        WebRouteContract(
            "route", "/items/{item_id}", "surface", RouteVisibility.PUBLIC, "none", "unspecified"
        )
    first = WebRouteContract(
        "route-a", "/", "surface", RouteVisibility.PUBLIC, "none", "unspecified"
    )
    second = replace(first, route_id="route-b", auth_requirement="different")
    from arch_web import WebInformationArchitectureContract

    with pytest.raises(WebContractValidationError, match="incompatible"):
        WebInformationArchitectureContract("0.1.0", "ia", "project", (surface,), (first, second))
