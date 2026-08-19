"""Construction, immutability, version, and reference tests."""

from dataclasses import FrozenInstanceError
from datetime import datetime

import pytest

from arch_web import (
    ArchitectureChoice,
    ContractRef,
    DesignReference,
    EvidenceRef,
    ProjectKind,
    UnsupportedWebContractVersionError,
    WebContractReferenceError,
    WebContractValidationError,
    WebLifecycleStatus,
    WebRoute,
)
from conftest import NOW, make_ia, make_project, make_ref, make_requirements, make_stack


@pytest.mark.parametrize("kind", list(ProjectKind))
def test_each_project_kind_is_supported(kind: ProjectKind) -> None:
    assert make_project(project_kind=kind).project_kind is kind


@pytest.mark.parametrize("route", list(WebRoute))
def test_each_arch_route_is_supported(route: WebRoute) -> None:
    assert make_project(route=route).route is route


def test_lifecycle_values_are_closed_without_transition_behavior() -> None:
    values = tuple(item.value for item in WebLifecycleStatus)
    assert values[0] == "DRAFT"
    assert values[-1] == "DEPLOYED"


def test_stack_distinguishes_none_from_unspecified() -> None:
    stack = make_stack()
    assert stack.backend_model is ArchitectureChoice.NONE
    assert stack.frontend_framework is ArchitectureChoice.UNSPECIFIED


@pytest.mark.parametrize("value", ["none", "unspecified"])
def test_stack_requires_explicit_choice_enum(value: str) -> None:
    with pytest.raises(ValueError, match="ArchitectureChoice"):
        make_stack(frontend_framework=value)


def test_records_and_nested_collections_are_immutable() -> None:
    users = ["visitor", "buyer"]
    project = make_project(target_users=users)
    users.append("operator")
    assert project.target_users == ("buyer", "visitor")
    with pytest.raises(FrozenInstanceError):
        project.name = "Changed"  # type: ignore[misc]
    with pytest.raises(AttributeError):
        project.target_users.append("operator")  # type: ignore[attr-defined]


def test_empty_and_non_normalized_identifiers_fail() -> None:
    with pytest.raises(WebContractValidationError, match="empty"):
        make_project(project_id="")
    with pytest.raises(WebContractValidationError, match="normalized"):
        make_project(project_id=" project-001 ")


@pytest.mark.parametrize("version", ["0.0.9", "0.2.0", "1.0.0"])
def test_unsupported_versions_fail_closed(version: str) -> None:
    with pytest.raises(UnsupportedWebContractVersionError):
        make_stack(contract_version=version)


def test_naive_injected_datetime_is_rejected() -> None:
    with pytest.raises(WebContractValidationError, match="timezone-aware"):
        make_project(created_at=datetime(2026, 1, 1))


def test_contract_reference_verifies_identity_version_and_fingerprint() -> None:
    stack = make_stack()
    reference = make_ref(stack, stack.profile_id)
    reference.verify(stack, stack.profile_id)
    with pytest.raises(WebContractReferenceError, match="identity"):
        reference.verify(stack, "other")
    changed = make_stack(constraints=("different",))
    with pytest.raises(WebContractReferenceError, match="fingerprint"):
        reference.verify(changed, changed.profile_id)


def test_contract_reference_rejects_invalid_digest() -> None:
    with pytest.raises(WebContractReferenceError, match="SHA-256"):
        ContractRef("web_stack_profile", "stack", "0.1.0", "ABC")


def test_project_rejects_wrong_reference_type() -> None:
    wrong = ContractRef("web_requirements_contract", "x", "0.1.0", "a" * 64)
    with pytest.raises(WebContractReferenceError, match="stack_profile_ref"):
        make_project(stack_profile_ref=wrong)


def test_project_verifies_project_bound_contracts() -> None:
    requirements = make_requirements()
    project = make_project(requirements_ref=make_ref(requirements, requirements.contract_id))
    project.verify_requirements(requirements)
    with pytest.raises(WebContractReferenceError, match="different project"):
        project.verify_requirements(make_requirements(project_id="other"))


def test_missing_optional_project_references_fail_when_verified() -> None:
    project = make_project()
    with pytest.raises(WebContractReferenceError, match="no requirements"):
        project.verify_requirements(make_requirements())
    with pytest.raises(WebContractReferenceError, match="no information"):
        project.verify_information_architecture(make_ia())


def test_stack_reference_can_be_verified_from_project() -> None:
    stack = make_stack()
    project = make_project(stack_profile_ref=make_ref(stack, stack.profile_id))
    project.verify_stack(stack)


def test_design_and_evidence_are_passive_references() -> None:
    design = DesignReference(
        "design-1", "figma", "https://example.test/design", "a" * 64, captured_at=NOW
    )
    evidence = EvidenceRef("ev-1", "test-report", "urn:evidence:1", "b" * 64, created_at=NOW)
    assert design.uri.startswith("https://")
    assert evidence.producer is None


def test_project_design_reference_verification() -> None:
    design = DesignReference("design-1", "tokens", "urn:design:1")
    project = make_project(design_system_ref=make_ref(design, design.design_ref_id))
    project.verify_design(design)
    with pytest.raises(WebContractReferenceError, match="no design"):
        make_project().verify_design(design)


def test_contract_and_package_versions_are_conceptually_separate() -> None:
    from arch_web import CURRENT_WEB_CONTRACT_VERSION, __version__

    assert CURRENT_WEB_CONTRACT_VERSION == "0.1.0"
    assert __version__ == "0.1.0"
