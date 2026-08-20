"""Product Brief, derivation, normalization, and review tests."""

from dataclasses import FrozenInstanceError, replace

import pytest

from arch_web import (
    EvidenceRef,
    FindingCode,
    PrepareRequirementsCommand,
    ProjectKind,
    RequirementCategory,
    RequirementSource,
    RequirementSourceKind,
    RequirementsReadiness,
    RequirementStatus,
    WebProductBrief,
    WebRoute,
    decode_contract,
    prepare_requirements,
)
from w02.factories import answer, intake, source


@pytest.mark.parametrize("route", list(WebRoute))
def test_complete_route_briefs_are_ready_for_review(route: WebRoute) -> None:
    result = prepare_requirements(PrepareRequirementsCommand(intake(route)))
    assert result.product_brief.route is route
    assert result.requirements_contract.route is route
    assert result.review_package.readiness is RequirementsReadiness.READY_FOR_REVIEW
    assert result.review_package.gap_findings == ()


def test_missing_goal_and_ambiguous_users_are_structured_gaps() -> None:
    result = prepare_requirements(
        PrepareRequirementsCommand(intake(primary_goal="", target_users=("everyone",)))
    )
    codes = {item.code for item in result.review_package.gap_findings}
    assert FindingCode.MISSING_PRIMARY_GOAL in codes
    assert FindingCode.AMBIGUOUS_TARGET_USERS in codes
    assert result.review_package.readiness is RequirementsReadiness.NOT_READY


def test_intake_and_product_brief_are_defensively_immutable() -> None:
    users = ["visitor"]
    value = intake(target_users=users)
    users.append("operator")
    result = prepare_requirements(PrepareRequirementsCommand(value))
    assert result.product_brief.target_users == ("visitor",)
    with pytest.raises(FrozenInstanceError):
        result.product_brief.name = "changed"  # type: ignore[misc]


def test_normalized_equivalent_intakes_produce_identical_evidence() -> None:
    left = intake(
        primary_goal="Explain   the offer and enable the intended workflow.",
        target_users=("prospective customer", "prospective customer"),
    )
    right = intake(target_users=("prospective customer",))
    left_result = prepare_requirements(PrepareRequirementsCommand(left))
    right_result = prepare_requirements(PrepareRequirementsCommand(right))
    assert left_result.product_brief == right_result.product_brief
    assert left_result.requirements_contract == right_result.requirements_contract
    assert left_result.review_package == right_result.review_package


def test_semantic_duplicate_answers_are_collapsed_without_merging_distinct_items() -> None:
    duplicate = answer(
        "duplicate", RequirementCategory.FUNCTIONAL, "Visitors can inspect the offer."
    )
    distinct = answer(
        "distinct",
        RequirementCategory.FUNCTIONAL,
        "Visitors can inspect pricing.",
    )
    result = prepare_requirements(
        PrepareRequirementsCommand(intake(answers=(*intake().answers, duplicate, distinct)))
    )
    assert len(result.requirements_contract.requirements) == 2


def test_provenance_and_inferred_assumptions_are_preserved() -> None:
    inferred = answer(
        "assumption",
        RequirementCategory.CONTENT,
        "Marketing copy will be supplied.",
        inferred=True,
    )
    result = prepare_requirements(
        PrepareRequirementsCommand(intake(answers=(*intake().answers, inferred)))
    )
    derived = next(
        item
        for item in result.requirements_contract.requirements
        if item.category is RequirementCategory.CONTENT
    )
    assert derived.source == source().source_id
    assert derived.status is RequirementStatus.PROPOSED
    assert inferred.statement in result.product_brief.assumptions


def test_research_evidence_source_is_preserved_without_remote_fetch() -> None:
    evidence = EvidenceRef("research-1", "market-research", "urn:research:1")
    research_source = RequirementSource(
        "source:research",
        RequirementSourceKind.RESEARCH_EVIDENCE,
        "Validated research note",
        evidence,
    )
    researched = replace(
        answer("research", RequirementCategory.CONTENT, "Show validated market evidence."),
        source=research_source,
    )
    result = prepare_requirements(
        PrepareRequirementsCommand(
            intake(answers=(*intake().answers, researched), source_refs=(evidence, evidence))
        )
    )
    assert {item.source for item in result.requirements_contract.requirements} >= {
        "source:research"
    }
    assert result.product_brief.source_refs == (evidence,)


def test_no_answers_means_no_silent_requirement_invention() -> None:
    result = prepare_requirements(PrepareRequirementsCommand(intake(answers=())))
    assert result.requirements_contract.requirements == ()
    assert FindingCode.MISSING_MATERIAL_REQUIREMENT in {
        item.code for item in result.review_package.gap_findings
    }


def test_answer_dependencies_resolve_to_deterministic_requirement_ids() -> None:
    base = answer("base", RequirementCategory.FUNCTIONAL, "User can start.")
    child = answer(
        "child",
        RequirementCategory.CONTENT,
        "User sees confirmation.",
        dependency_refs=("base",),
    )
    result = prepare_requirements(PrepareRequirementsCommand(intake(answers=(child, base))))
    requirements = {item.statement: item for item in result.requirements_contract.requirements}
    assert requirements[child.statement].dependency_refs == (
        requirements[base.statement].requirement_id,
    )


def test_unknown_answer_dependency_becomes_a_blocking_review_gap() -> None:
    broken = answer(
        "child",
        RequirementCategory.CONTENT,
        "User sees confirmation.",
        dependency_refs=("missing",),
    )
    result = prepare_requirements(PrepareRequirementsCommand(intake(answers=(broken,))))
    assert FindingCode.UNRESOLVED_REQUIREMENT_DEPENDENCY in {
        item.code for item in result.review_package.gap_findings
    }
    assert result.review_package.readiness is RequirementsReadiness.NOT_READY


def test_product_brief_and_review_round_trip_canonically() -> None:
    result = prepare_requirements(PrepareRequirementsCommand(intake()))
    brief = decode_contract(WebProductBrief, result.product_brief.canonical_bytes())
    assert brief == result.product_brief
    from arch_web import RequirementsReviewPackage

    review = decode_contract(RequirementsReviewPackage, result.review_package.canonical_bytes())
    assert review == result.review_package


def test_route_recommendation_does_not_mutate_authoritative_route() -> None:
    result = prepare_requirements(
        PrepareRequirementsCommand(
            intake(
                WebRoute.QUICK,
                project_kind_hypothesis=ProjectKind.STATIC_SITE,
                auth_security_needs=("Financial data is security-critical.",),
            )
        )
    )
    assert result.product_brief.route is WebRoute.QUICK
    assert result.review_package.route_recommendation.recommended_route is WebRoute.CRITICAL
    assert result.review_package.route_recommendation.requires_human_confirmation


def test_semantic_change_changes_review_fingerprint() -> None:
    first = prepare_requirements(PrepareRequirementsCommand(intake()))
    changed = prepare_requirements(
        PrepareRequirementsCommand(intake(value_proposition="A materially different promise."))
    )
    assert (
        first.review_package.canonical_fingerprint()
        != changed.review_package.canonical_fingerprint()
    )
