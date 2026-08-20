"""Explicit contradiction detection without autonomous arbitration."""

from __future__ import annotations

from arch_web.domain.product_brief import WebProductBrief
from arch_web.domain.requirements import WebRequirementsContract
from arch_web.domain.requirements_review import FindingCode, FindingSeverity, RequirementFinding


def _has(text: str, *phrases: str) -> bool:
    return any(phrase in text for phrase in phrases)


class RequirementsConflictAnalyzer:
    def analyze(
        self, brief: WebProductBrief, requirements: WebRequirementsContract
    ) -> tuple[RequirementFinding, ...]:
        brief_text = " ".join(
            (
                *brief.core_capabilities,
                *brief.data_needs,
                *brief.integrations,
                *brief.auth_security_needs,
                *brief.constraints,
                *brief.exclusions,
            )
        ).casefold()
        requirement_text = " ".join(
            f"{item.statement} {' '.join(item.acceptance_criteria)}"
            for item in requirements.requirements
        ).casefold()
        text = f"{brief_text} {requirement_text}"
        findings: list[RequirementFinding] = []
        checks = (
            (
                FindingCode.PUBLIC_AUTH_CONFLICT,
                _has(text, "public access", "without authentication")
                and _has(text, "mandatory authentication", "authentication required"),
                "Public access conflicts with mandatory authentication.",
            ),
            (
                FindingCode.PERSISTENCE_CONFLICT,
                _has(text, "no persistence", "no stored data")
                and _has(text, "durable user state", "persist user", "saved user state"),
                "No-persistence intent conflicts with durable state.",
            ),
            (
                FindingCode.STATIC_SERVER_CONFLICT,
                _has(text, "static-only", "static only")
                and _has(text, "server capability", "server-side", "backend required"),
                "Static-only delivery conflicts with a required server capability.",
            ),
            (
                FindingCode.THIRD_PARTY_INTEGRATION_CONFLICT,
                _has(text, "no third-party", "no external services")
                and _has(text, "mandatory external integration", "external integration required"),
                "Third-party exclusion conflicts with a mandatory integration.",
            ),
        )
        for code, conflict, message in checks:
            if conflict:
                findings.append(RequirementFinding(code, FindingSeverity.BLOCKING, message))
        for requirement in requirements.requirements:
            criteria = " ".join(requirement.acceptance_criteria).casefold()
            if _has(criteria, "must be visible") and _has(criteria, "must not be visible"):
                findings.append(
                    RequirementFinding(
                        FindingCode.ACCEPTANCE_CRITERIA_CONFLICT,
                        FindingSeverity.BLOCKING,
                        "Acceptance criteria explicitly contradict each other.",
                        (requirement.requirement_id,),
                    )
                )
        return tuple(sorted(findings, key=lambda item: (item.code.value, item.requirement_refs)))


__all__ = ("RequirementsConflictAnalyzer",)
