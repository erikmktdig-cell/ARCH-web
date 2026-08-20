"""Deterministic Product Brief and requirement derivation."""

from __future__ import annotations

import hashlib

from arch_web.application.requirements.models import RequirementIntake
from arch_web.application.requirements.normalize import normalize_intake
from arch_web.contracts.canonical import canonical_bytes
from arch_web.contracts.versions import CURRENT_WEB_CONTRACT_VERSION
from arch_web.domain.enums import RequirementStatus
from arch_web.domain.product_brief import WebProductBrief
from arch_web.domain.requirements import WebRequirement, WebRequirementsContract


def _semantic_id(prefix: str, value: object) -> str:
    digest = hashlib.sha256(canonical_bytes(value)).hexdigest()[:16].upper()
    return f"{prefix}-{digest}"


def build_product_brief(intake: RequirementIntake) -> WebProductBrief:
    value = normalize_intake(intake)
    identity_data = {
        "project_id": value.project_id,
        "name": value.name,
        "raw_idea": value.raw_idea,
        "route": value.route.value,
    }
    assumptions = set(value.assumptions)
    assumptions.update(answer.statement for answer in value.answers if answer.inferred)
    return WebProductBrief(
        contract_version=CURRENT_WEB_CONTRACT_VERSION,
        brief_id=_semantic_id("BRF", identity_data),
        project_id=value.project_id,
        name=value.name,
        problem_statement=value.problem_statement,
        primary_goal=value.primary_goal,
        target_users=value.target_users,
        value_proposition=value.value_proposition,
        project_kind_hypothesis=value.project_kind_hypothesis,
        delivery_mode=value.delivery_mode,
        core_capabilities=value.core_capabilities,
        content_needs=value.content_needs,
        data_needs=value.data_needs,
        integrations=value.integrations,
        auth_security_needs=value.auth_security_needs,
        responsive_expectations=value.responsive_expectations,
        accessibility_expectations=value.accessibility_expectations,
        performance_expectations=value.performance_expectations,
        operational_expectations=value.operational_expectations,
        constraints=value.constraints,
        assumptions=tuple(assumptions),
        exclusions=value.exclusions,
        unresolved_questions=value.unresolved_questions,
        source_refs=value.source_refs,
        route=value.route,
    )


def derive_requirements(intake: RequirementIntake) -> WebRequirementsContract:
    value = normalize_intake(intake)
    derived: list[WebRequirement] = []
    unresolved_dependencies: list[str] = []
    answer_to_requirement: dict[str, str] = {}
    for answer in value.answers:
        semantic = {
            "category": answer.category.value,
            "statement": answer.statement.casefold(),
            "acceptance_criteria": answer.acceptance_criteria,
            "source": answer.source.source_id,
            "route": value.route.value,
        }
        answer_to_requirement[answer.answer_id] = _semantic_id("WREQ", semantic)
    for answer in value.answers:
        known_dependencies = tuple(
            sorted(
                answer_to_requirement[item]
                for item in answer.dependency_refs
                if item in answer_to_requirement
            )
        )
        unresolved_dependencies.extend(
            f"requirement_dependency:{answer.answer_id}:{item}"
            for item in answer.dependency_refs
            if item not in answer_to_requirement
        )
        derived.append(
            WebRequirement(
                requirement_id=answer_to_requirement[answer.answer_id],
                category=answer.category,
                statement=answer.statement,
                priority=answer.priority,
                source=answer.source.source_id,
                acceptance_criteria=answer.acceptance_criteria,
                route_requirement=value.route,
                security_relevance=answer.security_relevance,
                status=RequirementStatus.PROPOSED,
                dependency_refs=known_dependencies,
            )
        )
    contract_identity = {
        "project_id": value.project_id,
        "route": value.route.value,
        "requirement_ids": tuple(item.requirement_id for item in derived),
    }
    return WebRequirementsContract(
        contract_version=CURRENT_WEB_CONTRACT_VERSION,
        contract_id=_semantic_id("WRC", contract_identity),
        project_id=value.project_id,
        route=value.route,
        requirements=tuple(derived),
        assumptions=tuple(answer.statement for answer in value.answers if answer.inferred),
        exclusions=value.exclusions,
        unresolved_items=(*value.unresolved_questions, *unresolved_dependencies),
    )


__all__ = ("build_product_brief", "derive_requirements")
