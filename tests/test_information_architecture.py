"""Pure aggregate reference and navigation validation."""

import pytest

from arch_web import WebContractReferenceError, WebContractValidationError
from conftest import make_ia, make_requirement, make_requirements, make_route, make_surface


def test_valid_information_architecture_resolves_requirement_context() -> None:
    ia = make_ia()
    ia.validate_requirements(make_requirements())
    assert ia.routes[0].surface_ref == ia.surfaces[0].surface_id


def test_duplicate_requirement_ids_are_rejected() -> None:
    duplicate = make_requirement()
    with pytest.raises(WebContractValidationError, match="duplicate IDs"):
        make_requirements(requirements=(duplicate, duplicate))


def test_missing_requirement_dependency_is_rejected() -> None:
    requirement = make_requirement(dependency_refs=("REQ-MISSING",))
    with pytest.raises(WebContractReferenceError, match="missing dependencies"):
        make_requirements(requirements=(requirement,))


def test_self_requirement_dependency_is_rejected() -> None:
    with pytest.raises(WebContractReferenceError, match="itself"):
        make_requirement(dependency_refs=("REQ-001",))


def test_duplicate_surface_and_route_ids_are_rejected() -> None:
    surface = make_surface()
    route = make_route()
    with pytest.raises(WebContractValidationError, match="surface IDs"):
        make_ia(surfaces=(surface, surface))
    with pytest.raises(WebContractValidationError, match="route IDs"):
        make_ia(routes=(route, route))


def test_missing_route_surface_is_rejected() -> None:
    with pytest.raises(WebContractReferenceError, match="missing surface"):
        make_ia(routes=(make_route(surface_ref="missing"),))


def test_missing_surface_route_is_rejected() -> None:
    with pytest.raises(WebContractReferenceError, match="missing routes"):
        make_ia(surfaces=(make_surface(route_refs=("missing",)),))


def test_surface_route_must_point_back_to_same_surface() -> None:
    other = make_surface(surface_id="surface-other", route_refs=())
    route = make_route(surface_ref="surface-other")
    with pytest.raises(WebContractReferenceError, match="another surface"):
        make_ia(surfaces=(make_surface(), other), routes=(route,))


def test_missing_navigation_parent_is_rejected() -> None:
    route = make_route(navigation_parent_ref="missing")
    with pytest.raises(WebContractReferenceError, match="navigation parent"):
        make_ia(routes=(route,))


def test_navigation_cycles_are_rejected() -> None:
    route_a = make_route(route_id="a", path_pattern="/a", navigation_parent_ref="b")
    route_b = make_route(
        route_id="b", path_pattern="/b", navigation_parent_ref="a", requirement_refs=()
    )
    surface = make_surface(route_refs=("a", "b"))
    with pytest.raises(WebContractValidationError, match="cycle"):
        make_ia(surfaces=(surface,), routes=(route_a, route_b))


def test_incompatible_duplicate_paths_are_rejected() -> None:
    route_a = make_route(route_id="a")
    route_b = make_route(route_id="b", requirement_refs=())
    surface = make_surface(route_refs=("a", "b"))
    with pytest.raises(WebContractValidationError, match="incompatible"):
        make_ia(surfaces=(surface,), routes=(route_a, route_b))


@pytest.mark.parametrize("path", ["home", "//home", "/bad path", "/{9id}", "/{id", "/home/"])
def test_malformed_framework_neutral_paths_are_rejected(path: str) -> None:
    with pytest.raises(WebContractValidationError, match="Malformed"):
        make_route(path_pattern=path)


def test_route_parameters_are_exact_and_immutable() -> None:
    parameters = {"project_id": "non-empty string"}
    route = make_route(path_pattern="/projects/{project_id}", parameter_contracts=parameters)
    parameters["other"] = "integer"
    assert route.parameter_contracts == (("project_id", "non-empty string"),)
    with pytest.raises(WebContractValidationError, match="exactly"):
        make_route(path_pattern="/projects/{project_id}", parameter_contracts=())


def test_missing_requirement_reference_and_project_mismatch_are_rejected() -> None:
    ia = make_ia(routes=(make_route(requirement_refs=("REQ-MISSING",)),))
    with pytest.raises(WebContractReferenceError, match="missing requirements"):
        ia.validate_requirements(make_requirements())
    with pytest.raises(WebContractReferenceError, match="different projects"):
        make_ia().validate_requirements(make_requirements(project_id="other"))


def test_container_order_is_normalized_by_identity() -> None:
    route_a = make_route(route_id="a", path_pattern="/a", requirement_refs=())
    route_b = make_route(route_id="b", path_pattern="/b", requirement_refs=())
    surface = make_surface(route_refs=("a", "b"), requirement_refs=())
    left = make_ia(surfaces=(surface,), routes=(route_b, route_a))
    right = make_ia(surfaces=(surface,), routes=(route_a, route_b))
    assert left.canonical_bytes() == right.canonical_bytes()
