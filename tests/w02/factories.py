"""W02 test factories with complete route-aware examples."""

from __future__ import annotations

from arch_web import (
    ProjectKind,
    RequirementAnswer,
    RequirementCategory,
    RequirementIntake,
    RequirementPriority,
    RequirementSource,
    RequirementSourceKind,
    WebRoute,
)

PROJECT_ID = "PRJ-01HZX7M3FQ1T2Q9V8Y6K4C2B1B"
REQUEST_ID = "CHG-01HZX7M3FQ1T2Q9V8Y6K4C2R06"


def source(source_id: str = "source:user") -> RequirementSource:
    return RequirementSource(source_id, RequirementSourceKind.USER, "Product owner")


def answer(
    answer_id: str,
    category: RequirementCategory,
    statement: str,
    *,
    criteria: tuple[str, ...] = ("The behavior is observable in an acceptance test.",),
    security: bool = False,
    inferred: bool = False,
    dependency_refs: tuple[str, ...] = (),
) -> RequirementAnswer:
    return RequirementAnswer(
        answer_id=answer_id,
        statement=statement,
        category=category,
        priority=RequirementPriority.MUST,
        source=source(),
        acceptance_criteria=criteria,
        security_relevance=security,
        inferred=inferred,
        dependency_refs=dependency_refs,
    )


def route_answers(route: WebRoute) -> tuple[RequirementAnswer, ...]:
    values = [
        answer("functional", RequirementCategory.FUNCTIONAL, "Visitors can inspect the offer."),
    ]
    if route in {WebRoute.STANDARD, WebRoute.CRITICAL}:
        values.extend(
            (
                answer(
                    "navigation", RequirementCategory.NAVIGATION, "Users can navigate sections."
                ),
                answer("data", RequirementCategory.DATA, "The product reads owned account data."),
                answer(
                    "integration",
                    RequirementCategory.INTEGRATION,
                    "The product uses a confirmed billing integration.",
                ),
                answer(
                    "performance",
                    RequirementCategory.PERFORMANCE,
                    "Primary views meet the agreed response target.",
                ),
                answer(
                    "operational",
                    RequirementCategory.OPERATIONAL,
                    "Operators can observe service health.",
                ),
                answer(
                    "security-baseline",
                    RequirementCategory.SECURITY,
                    "Authentication follows the confirmed session policy.",
                ),
            )
        )
    if route is WebRoute.CRITICAL:
        values.append(
            answer(
                "security",
                RequirementCategory.SECURITY,
                "Sensitive financial data requires authorization controls.",
                security=True,
            )
        )
    return tuple(values)


def intake(route: WebRoute = WebRoute.QUICK, **changes: object) -> RequirementIntake:
    values: dict[str, object] = {
        "project_id": PROJECT_ID,
        "name": "Governed Web Product",
        "raw_idea": "Build a clear product experience.",
        "problem_statement": "Customers cannot inspect the offer clearly.",
        "primary_goal": "Explain the offer and enable the intended workflow.",
        "target_users": ("prospective customer",),
        "value_proposition": "A trustworthy, accessible experience.",
        "project_kind_hypothesis": (
            ProjectKind.STATIC_SITE if route is WebRoute.QUICK else ProjectKind.FRONTEND_APP
        ),
        "delivery_mode": "public-web",
        "route": route,
        "answers": route_answers(route),
        "responsive_expectations": ("Works from 320px through desktop.",),
        "accessibility_expectations": ("WCAG 2.2 AA baseline.",),
        "exclusions": ("No unapproved scope.",),
        "data_needs": (() if route is WebRoute.QUICK else ("Account data owned by product.",)),
        "integrations": (() if route is WebRoute.QUICK else ("Confirmed billing provider.",)),
        "performance_expectations": (() if route is WebRoute.QUICK else ("LCP target defined.",)),
        "operational_expectations": (
            ()
            if route is WebRoute.QUICK
            else (
                "Health monitoring and alerts.",
                "Audit trail and failure recovery runbook."
                if route is WebRoute.CRITICAL
                else "Failure alerts.",
            )
        ),
        "auth_security_needs": (
            ()
            if route is WebRoute.QUICK
            else (
                "Authorization for sensitive financial data."
                if route is WebRoute.CRITICAL
                else "Session authentication is confirmed.",
            )
        ),
        "constraints": (),
        "assumptions": (),
        "unresolved_questions": (),
        "source_refs": (),
    }
    values.update(changes)
    return RequirementIntake(**values)  # type: ignore[arg-type]
