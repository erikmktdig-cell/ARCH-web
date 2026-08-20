"""Pure requirements preparation orchestration."""

from __future__ import annotations

import hashlib

from arch_web.application.requirements.conflicts import RequirementsConflictAnalyzer
from arch_web.application.requirements.derive import build_product_brief, derive_requirements
from arch_web.application.requirements.gaps import RequirementsGapAnalyzer
from arch_web.application.requirements.models import (
    PrepareRequirementsCommand,
    PrepareRequirementsResult,
)
from arch_web.application.requirements.route import recommend_route
from arch_web.contracts.canonical import canonical_bytes
from arch_web.contracts.versions import CURRENT_WEB_CONTRACT_VERSION
from arch_web.domain.product_brief import WebProductBrief
from arch_web.domain.references import ContractRef
from arch_web.domain.requirements import WebRequirementsContract
from arch_web.domain.requirements_review import (
    FindingSeverity,
    RequirementsReadiness,
    RequirementsReviewPackage,
)


def _ref(target: WebProductBrief | WebRequirementsContract, contract_id: str) -> ContractRef:
    return ContractRef(
        target_contract_type=target.contract_type,
        contract_id=contract_id,
        contract_version=target.contract_version,
        fingerprint=target.canonical_fingerprint(),
    )


def prepare_requirements(command: PrepareRequirementsCommand) -> PrepareRequirementsResult:
    brief = build_product_brief(command.intake)
    requirements = derive_requirements(command.intake)
    gaps = RequirementsGapAnalyzer().analyze(brief, requirements)
    conflicts = RequirementsConflictAnalyzer().analyze(brief, requirements)
    blockers = any(item.severity is FindingSeverity.BLOCKING for item in (*gaps, *conflicts))
    recommendation = recommend_route(brief, requirements)
    review_identity = {
        "brief": brief.canonical_fingerprint(),
        "requirements": requirements.canonical_fingerprint(),
        "gaps": gaps,
        "conflicts": conflicts,
    }
    review_id = f"RRV-{hashlib.sha256(canonical_bytes(review_identity)).hexdigest()[:16].upper()}"
    review = RequirementsReviewPackage(
        contract_version=CURRENT_WEB_CONTRACT_VERSION,
        review_id=review_id,
        project_id=brief.project_id,
        product_brief_ref=_ref(brief, brief.brief_id),
        requirements_contract_ref=_ref(requirements, requirements.contract_id),
        gap_findings=gaps,
        conflict_findings=conflicts,
        assumptions=brief.assumptions,
        exclusions=brief.exclusions,
        unresolved_items=brief.unresolved_questions,
        route_recommendation=recommendation,
        readiness=(
            RequirementsReadiness.NOT_READY if blockers else RequirementsReadiness.READY_FOR_REVIEW
        ),
        source_evidence_refs=brief.source_refs,
    )
    return PrepareRequirementsResult(brief, requirements, review)


__all__ = ("prepare_requirements",)
