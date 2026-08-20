"""Non-authoritative ARCH route recommendation."""

from __future__ import annotations

from arch_web.domain.enums import ProjectKind, WebRoute
from arch_web.domain.product_brief import WebProductBrief
from arch_web.domain.requirements import WebRequirementsContract
from arch_web.domain.requirements_review import RouteRecommendation


def recommend_route(
    brief: WebProductBrief, requirements: WebRequirementsContract
) -> RouteRecommendation:
    text = " ".join(
        (
            brief.problem_statement,
            brief.primary_goal,
            *brief.core_capabilities,
            *brief.data_needs,
            *brief.integrations,
            *brief.auth_security_needs,
            *(item.statement for item in requirements.requirements),
        )
    ).casefold()
    critical_terms = (
        "financial",
        "health data",
        "healthcare",
        "regulated",
        "sensitive data",
        "payment",
        "security-critical",
    )
    if any(term in text for term in critical_terms) or any(
        item.security_relevance for item in requirements.requirements
    ):
        return RouteRecommendation(
            WebRoute.CRITICAL,
            ("Security, regulatory, financial, health, or sensitive-data evidence is present.",),
            "high",
        )
    if (
        brief.project_kind_hypothesis is not ProjectKind.STATIC_SITE
        or brief.data_needs
        or brief.integrations
        or brief.auth_security_needs
    ):
        return RouteRecommendation(
            WebRoute.STANDARD,
            ("Application, data, auth, or integration complexity is present.",),
            "medium",
        )
    return RouteRecommendation(
        WebRoute.QUICK,
        ("The current evidence describes a small, low-risk static web slice.",),
        "medium",
    )


__all__ = ("recommend_route",)
