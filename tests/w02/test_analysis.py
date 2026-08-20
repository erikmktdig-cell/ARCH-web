"""Gap, conflict, and route recommendation matrices."""

from dataclasses import replace

import pytest

from arch_web import (
    FindingCode,
    PrepareRequirementsCommand,
    RequirementCategory,
    RequirementsReadiness,
    WebRoute,
    prepare_requirements,
)
from w02.factories import answer, intake


def _codes(**changes: object) -> set[FindingCode]:
    result = prepare_requirements(PrepareRequirementsCommand(intake(**changes)))  # type: ignore[arg-type]
    return {item.code for item in result.review_package.gap_findings}


@pytest.mark.parametrize(
    ("changes", "expected"),
    [
        ({"responsive_expectations": ()}, FindingCode.MISSING_RESPONSIVE_REQUIREMENT),
        ({"accessibility_expectations": ()}, FindingCode.MISSING_ACCESSIBILITY_REQUIREMENT),
        (
            {"answers": (answer("x", RequirementCategory.FUNCTIONAL, "X", criteria=()),)},
            FindingCode.MISSING_ACCEPTANCE_CRITERIA,
        ),
    ],
)
def test_quick_gap_matrix(changes: dict[str, object], expected: FindingCode) -> None:
    assert expected in _codes(**changes)


@pytest.mark.parametrize(
    ("category", "expected"),
    [
        (RequirementCategory.NAVIGATION, FindingCode.MISSING_NAVIGATION_REQUIREMENT),
        (RequirementCategory.PERFORMANCE, FindingCode.MISSING_PERFORMANCE_REQUIREMENT),
        (RequirementCategory.OPERATIONAL, FindingCode.MISSING_OPERATIONAL_REQUIREMENT),
    ],
)
def test_standard_route_requires_route_specific_categories(
    category: RequirementCategory, expected: FindingCode
) -> None:
    value = intake(WebRoute.STANDARD)
    answers = tuple(item for item in value.answers if item.category is not category)
    result = prepare_requirements(PrepareRequirementsCommand(replace(value, answers=answers)))
    assert expected in {item.code for item in result.review_package.gap_findings}


def test_standard_data_auth_and_integration_gaps_are_explicit() -> None:
    value = intake(
        WebRoute.STANDARD,
        data_needs=("Customer records",),
        integrations=("Unresolved CRM provider",),
        auth_security_needs=("Unspecified",),
    )
    value = replace(
        value,
        answers=tuple(
            item for item in value.answers if item.category is not RequirementCategory.SECURITY
        ),
    )
    codes = {
        item.code
        for item in prepare_requirements(
            PrepareRequirementsCommand(value)
        ).review_package.gap_findings
    }
    assert FindingCode.UNRESOLVED_DATA_OWNERSHIP in codes
    assert FindingCode.UNRESOLVED_INTEGRATION_DEPENDENCY in codes
    assert FindingCode.UNRESOLVED_AUTH in codes
    assert FindingCode.MISSING_SECURITY_REQUIREMENT in codes


@pytest.mark.parametrize(
    ("changes", "expected"),
    [
        ({"auth_security_needs": ()}, FindingCode.UNRESOLVED_AUTH),
        (
            {"operational_expectations": ("Failure recovery is defined.",)},
            FindingCode.MISSING_AUDITABILITY_INTENT,
        ),
        (
            {"operational_expectations": ("Auditability is defined.",)},
            FindingCode.MISSING_FAILURE_RECOVERY_INTENT,
        ),
    ],
)
def test_critical_route_gap_matrix(changes: dict[str, object], expected: FindingCode) -> None:
    value = intake(WebRoute.CRITICAL, **changes)
    result = prepare_requirements(PrepareRequirementsCommand(value))
    assert expected in {item.code for item in result.review_package.gap_findings}


def test_critical_requires_security_relevance() -> None:
    value = intake(WebRoute.CRITICAL)
    answers = tuple(replace(item, security_relevance=False) for item in value.answers)
    result = prepare_requirements(PrepareRequirementsCommand(replace(value, answers=answers)))
    assert FindingCode.MISSING_SECURITY_REQUIREMENT in {
        item.code for item in result.review_package.gap_findings
    }


@pytest.mark.parametrize(
    ("constraints", "capabilities", "auth", "integrations", "expected"),
    [
        (
            (),
            ("Public access",),
            ("Mandatory authentication",),
            (),
            FindingCode.PUBLIC_AUTH_CONFLICT,
        ),
        (
            ("No persistence",),
            ("Durable user state",),
            (),
            (),
            FindingCode.PERSISTENCE_CONFLICT,
        ),
        (
            ("Static-only",),
            ("Server capability required",),
            (),
            (),
            FindingCode.STATIC_SERVER_CONFLICT,
        ),
        (
            ("No third-party services",),
            (),
            (),
            ("Mandatory external integration",),
            FindingCode.THIRD_PARTY_INTEGRATION_CONFLICT,
        ),
    ],
)
def test_explicit_conflict_matrix(
    constraints: tuple[str, ...],
    capabilities: tuple[str, ...],
    auth: tuple[str, ...],
    integrations: tuple[str, ...],
    expected: FindingCode,
) -> None:
    value = intake(
        constraints=constraints,
        core_capabilities=capabilities,
        auth_security_needs=auth,
        integrations=integrations,
    )
    review = prepare_requirements(PrepareRequirementsCommand(value)).review_package
    assert expected in {item.code for item in review.conflict_findings}
    assert review.readiness is RequirementsReadiness.NOT_READY


def test_conflicting_acceptance_criteria_are_not_arbitrated() -> None:
    contradictory = answer(
        "visibility",
        RequirementCategory.FUNCTIONAL,
        "Control access to the offer.",
        criteria=("It must be visible.", "It must not be visible."),
    )
    review = prepare_requirements(
        PrepareRequirementsCommand(intake(answers=(contradictory,)))
    ).review_package
    assert FindingCode.ACCEPTANCE_CRITERIA_CONFLICT in {
        item.code for item in review.conflict_findings
    }


@pytest.mark.parametrize(
    ("route", "changes", "recommended"),
    [
        (WebRoute.QUICK, {}, WebRoute.QUICK),
        (WebRoute.STANDARD, {}, WebRoute.STANDARD),
        (
            WebRoute.CRITICAL,
            {"problem_statement": "A regulated health and financial workflow."},
            WebRoute.CRITICAL,
        ),
    ],
)
def test_route_recommendation_examples(
    route: WebRoute, changes: dict[str, object], recommended: WebRoute
) -> None:
    result = prepare_requirements(PrepareRequirementsCommand(intake(route, **changes)))
    assert result.review_package.route_recommendation.recommended_route is recommended
    assert result.product_brief.route is route


def test_premature_stack_decision_is_advisory_not_silent_architecture() -> None:
    result = prepare_requirements(PrepareRequirementsCommand(intake(constraints=("Use Next.js",))))
    finding = next(
        item
        for item in result.review_package.gap_findings
        if item.code is FindingCode.PREMATURE_STACK_DECISION
    )
    assert finding.severity.value == "advisory"
    assert result.review_package.readiness is RequirementsReadiness.READY_FOR_REVIEW
