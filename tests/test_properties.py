"""Generative evidence for deterministic contracts."""

import pytest
from hypothesis import given
from hypothesis import strategies as st

from arch_web import (
    UnsupportedWebContractVersionError,
    WebContractReferenceError,
    WebContractValidationError,
    WebStackProfile,
    decode_contract,
)
from conftest import (
    make_ia,
    make_requirement,
    make_requirements,
    make_route,
    make_stack,
    make_surface,
)


@pytest.mark.property
@given(
    st.lists(
        st.text(min_size=1).filter(lambda value: value == value.strip()), unique=True, max_size=8
    )
)
def test_constraint_order_does_not_change_canonical_evidence(values: list[str]) -> None:
    left = make_stack(constraints=tuple(values))
    right = make_stack(constraints=tuple(reversed(values)))
    assert left.canonical_bytes() == right.canonical_bytes()
    assert left.canonical_fingerprint() == right.canonical_fingerprint()


@pytest.mark.property
@given(st.text(min_size=1).filter(lambda value: value == value.strip()))
def test_semantic_stack_mutation_changes_fingerprint(runtime: str) -> None:
    baseline = make_stack(runtime_requirement="node>=22")
    changed = make_stack(runtime_requirement=runtime)
    if runtime != "node>=22":
        assert baseline.canonical_fingerprint() != changed.canonical_fingerprint()


@pytest.mark.property
@given(st.sampled_from(["0.0.1", "0.2.0", "1.0.0", "999.0.0"]))
def test_arbitrary_unsupported_versions_fail(version: str) -> None:
    with pytest.raises(UnsupportedWebContractVersionError):
        make_stack(contract_version=version)


@pytest.mark.property
@given(st.text(min_size=1).filter(lambda value: value == value.strip()))
def test_missing_requirement_references_fail(reference: str) -> None:
    if reference != "REQ-001":
        ia = make_ia(routes=(make_route(requirement_refs=(reference,)),))
        with pytest.raises(WebContractReferenceError):
            ia.validate_requirements(make_requirements())


@pytest.mark.property
@given(st.text(min_size=1).filter(lambda value: value == value.strip()))
def test_canonical_stack_round_trip(runtime: str) -> None:
    if runtime not in {"none", "unspecified"}:
        stack = make_stack(runtime_requirement=runtime)
        assert decode_contract(WebStackProfile, stack.canonical_bytes()) == stack


@pytest.mark.property
@given(st.text(min_size=1).filter(lambda value: value == value.strip()))
def test_duplicate_ids_always_fail(identifier: str) -> None:
    requirement = make_requirement(identifier)
    with pytest.raises(WebContractValidationError):
        make_requirements(requirements=(requirement, requirement))


@pytest.mark.property
@given(st.text(min_size=1).filter(lambda value: value == value.strip()))
def test_broken_surface_references_always_fail(surface_id: str) -> None:
    if surface_id != "surface-home":
        surface = make_surface()
        with pytest.raises(WebContractReferenceError):
            make_ia(surfaces=(surface,), routes=(make_route(surface_ref=surface_id),))
