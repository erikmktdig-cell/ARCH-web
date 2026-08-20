"""Meaning-preserving W02 intake normalization."""

from __future__ import annotations

from dataclasses import replace

from arch_web.application.requirements.models import (
    RequirementAnswer,
    RequirementIntake,
)


def normalize_text(value: str) -> str:
    return " ".join(value.split())


def _strings(values: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(sorted({normalized for item in values if (normalized := normalize_text(item))}))


def normalize_intake(value: RequirementIntake) -> RequirementIntake:
    answers_by_semantics: dict[tuple[object, ...], RequirementAnswer] = {}
    for answer in value.answers:
        source = replace(
            answer.source,
            source_id=normalize_text(answer.source.source_id),
            label=normalize_text(answer.source.label),
        )
        normalized = replace(
            answer,
            answer_id=normalize_text(answer.answer_id),
            statement=normalize_text(answer.statement),
            source=source,
            acceptance_criteria=_strings(answer.acceptance_criteria),
            dependency_refs=_strings(answer.dependency_refs),
        )
        key = (
            normalized.category,
            normalized.statement.casefold(),
            normalized.priority,
            normalized.acceptance_criteria,
            normalized.source.source_id,
            normalized.dependency_refs,
            normalized.security_relevance,
            normalized.inferred,
        )
        answers_by_semantics[key] = normalized
    refs = {item.evidence_id: item for item in value.source_refs}
    return replace(
        value,
        project_id=normalize_text(value.project_id),
        name=normalize_text(value.name),
        raw_idea=normalize_text(value.raw_idea),
        problem_statement=normalize_text(value.problem_statement),
        primary_goal=normalize_text(value.primary_goal),
        value_proposition=normalize_text(value.value_proposition),
        delivery_mode=normalize_text(value.delivery_mode),
        answers=tuple(
            sorted(
                answers_by_semantics.values(),
                key=lambda item: (item.category.value, item.answer_id),
            )
        ),
        source_refs=tuple(sorted(refs.values(), key=lambda item: item.evidence_id)),
        target_users=_strings(value.target_users),
        core_capabilities=_strings(value.core_capabilities),
        content_needs=_strings(value.content_needs),
        data_needs=_strings(value.data_needs),
        integrations=_strings(value.integrations),
        auth_security_needs=_strings(value.auth_security_needs),
        responsive_expectations=_strings(value.responsive_expectations),
        accessibility_expectations=_strings(value.accessibility_expectations),
        performance_expectations=_strings(value.performance_expectations),
        operational_expectations=_strings(value.operational_expectations),
        constraints=_strings(value.constraints),
        assumptions=_strings(value.assumptions),
        exclusions=_strings(value.exclusions),
        unresolved_questions=_strings(value.unresolved_questions),
    )


__all__ = ("normalize_intake",)
