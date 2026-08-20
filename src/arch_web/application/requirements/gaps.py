"""Route-aware, deterministic requirements completeness analysis."""

from __future__ import annotations

from arch_web.domain.enums import ProjectKind, RequirementCategory, WebRoute
from arch_web.domain.product_brief import WebProductBrief
from arch_web.domain.requirements import WebRequirementsContract
from arch_web.domain.requirements_review import FindingCode, FindingSeverity, RequirementFinding


def _finding(code: FindingCode, message: str, *refs: str) -> RequirementFinding:
    return RequirementFinding(code, FindingSeverity.BLOCKING, message, tuple(refs))


def _contains(values: tuple[str, ...], *terms: str) -> bool:
    text = " ".join(values).casefold()
    return any(term in text for term in terms)


class RequirementsGapAnalyzer:
    """Evaluate only explicit W02 completeness evidence."""

    def analyze(
        self, brief: WebProductBrief, requirements: WebRequirementsContract
    ) -> tuple[RequirementFinding, ...]:
        findings: list[RequirementFinding] = []
        categories = {item.category for item in requirements.requirements}
        if not brief.primary_goal:
            findings.append(_finding(FindingCode.MISSING_PRIMARY_GOAL, "Primary goal is missing."))
        if not brief.target_users or _contains(brief.target_users, "everyone", "all users"):
            findings.append(
                _finding(
                    FindingCode.AMBIGUOUS_TARGET_USERS, "Target users are missing or ambiguous."
                )
            )
        if not categories.intersection(
            {RequirementCategory.FUNCTIONAL, RequirementCategory.CONTENT}
        ):
            findings.append(
                _finding(
                    FindingCode.MISSING_MATERIAL_REQUIREMENT,
                    "At least one functional or content requirement is required.",
                )
            )
        for requirement in requirements.requirements:
            if not requirement.acceptance_criteria:
                findings.append(
                    _finding(
                        FindingCode.MISSING_ACCEPTANCE_CRITERIA,
                        "Material requirement has no explicit acceptance criteria.",
                        requirement.requirement_id,
                    )
                )
        if any(
            item.startswith("requirement_dependency:") for item in requirements.unresolved_items
        ):
            findings.append(
                _finding(
                    FindingCode.UNRESOLVED_REQUIREMENT_DEPENDENCY,
                    "At least one answer references an unresolved requirement dependency.",
                )
            )
            missing = set(requirement.dependency_refs) - {
                item.requirement_id for item in requirements.requirements
            }
            if missing:
                findings.append(
                    _finding(
                        FindingCode.UNRESOLVED_REQUIREMENT_DEPENDENCY,
                        "Requirement dependency is unresolved.",
                        requirement.requirement_id,
                    )
                )
        if not brief.responsive_expectations and RequirementCategory.RESPONSIVE not in categories:
            findings.append(
                _finding(
                    FindingCode.MISSING_RESPONSIVE_REQUIREMENT,
                    "Responsive baseline is not explicit.",
                )
            )
        if (
            not brief.accessibility_expectations
            and RequirementCategory.ACCESSIBILITY not in categories
        ):
            findings.append(
                _finding(
                    FindingCode.MISSING_ACCESSIBILITY_REQUIREMENT,
                    "Accessibility baseline is not explicit.",
                )
            )
        if brief.route in {WebRoute.STANDARD, WebRoute.CRITICAL}:
            self._standard_gaps(brief, categories, findings)
        if brief.route is WebRoute.CRITICAL:
            self._critical_gaps(brief, requirements, categories, findings)
        if brief.project_kind_hypothesis is ProjectKind.STATIC_SITE and (
            brief.data_needs or _contains(brief.core_capabilities, "server", "durable state")
        ):
            findings.append(
                _finding(
                    FindingCode.PROJECT_KIND_INCONSISTENCY,
                    "Static-site hypothesis conflicts with stateful/server requirements.",
                )
            )
        if _contains(brief.constraints, "react", "next.js", "vue", "angular", "svelte"):
            findings.append(
                RequirementFinding(
                    FindingCode.PREMATURE_STACK_DECISION,
                    FindingSeverity.ADVISORY,
                    "A framework choice appears before architecture approval.",
                )
            )
        return tuple(sorted(findings, key=lambda item: (item.code.value, item.requirement_refs)))

    @staticmethod
    def _standard_gaps(
        brief: WebProductBrief,
        categories: set[RequirementCategory],
        findings: list[RequirementFinding],
    ) -> None:
        required = (
            (RequirementCategory.NAVIGATION, FindingCode.MISSING_NAVIGATION_REQUIREMENT),
            (RequirementCategory.PERFORMANCE, FindingCode.MISSING_PERFORMANCE_REQUIREMENT),
            (RequirementCategory.OPERATIONAL, FindingCode.MISSING_OPERATIONAL_REQUIREMENT),
        )
        for category, code in required:
            if category not in categories:
                findings.append(_finding(code, f"{category.value} requirements are not explicit."))
        if brief.data_needs and not _contains(
            brief.data_needs, "owner", "owned by", "source of truth"
        ):
            findings.append(
                _finding(FindingCode.UNRESOLVED_DATA_OWNERSHIP, "Data ownership is unresolved.")
            )
        if brief.integrations and any(
            "unresolved" in item.casefold() for item in brief.integrations
        ):
            findings.append(
                _finding(
                    FindingCode.UNRESOLVED_INTEGRATION_DEPENDENCY,
                    "An integration dependency remains unresolved.",
                )
            )
        if brief.auth_security_needs and _contains(
            brief.auth_security_needs, "unspecified", "unresolved"
        ):
            findings.append(_finding(FindingCode.UNRESOLVED_AUTH, "Auth intent is unresolved."))
        if brief.auth_security_needs and RequirementCategory.SECURITY not in categories:
            findings.append(
                _finding(
                    FindingCode.MISSING_SECURITY_REQUIREMENT,
                    "Applicable security/auth intent lacks a security requirement.",
                )
            )

    @staticmethod
    def _critical_gaps(
        brief: WebProductBrief,
        requirements: WebRequirementsContract,
        categories: set[RequirementCategory],
        findings: list[RequirementFinding],
    ) -> None:
        if RequirementCategory.SECURITY not in categories or not any(
            item.security_relevance for item in requirements.requirements
        ):
            findings.append(
                _finding(
                    FindingCode.MISSING_SECURITY_REQUIREMENT,
                    "Critical route requires explicit security-relevant requirements.",
                )
            )
        if not brief.auth_security_needs or _contains(
            brief.auth_security_needs, "unspecified", "unresolved"
        ):
            findings.append(
                _finding(FindingCode.UNRESOLVED_AUTH, "Auth/authz intent is unresolved.")
            )
        if not _contains(brief.operational_expectations, "audit", "auditability"):
            findings.append(
                _finding(
                    FindingCode.MISSING_AUDITABILITY_INTENT,
                    "Critical route requires auditability intent.",
                )
            )
        if not _contains(brief.operational_expectations, "recover", "failure", "rollback"):
            findings.append(
                _finding(
                    FindingCode.MISSING_FAILURE_RECOVERY_INTENT,
                    "Critical route requires failure and recovery intent.",
                )
            )


__all__ = ("RequirementsGapAnalyzer",)
