"""Property evidence for W02 normalization and readiness."""

from dataclasses import replace

from hypothesis import given
from hypothesis import strategies as st

from arch_web import (
    PrepareRequirementsCommand,
    RequirementCategory,
    RequirementsReadiness,
    prepare_requirements,
)
from w02.factories import answer, intake


@given(st.lists(st.sampled_from(["alpha", "beta", "gamma", "delta"]), min_size=1))
def test_collection_order_and_duplicates_are_semantically_invariant(values: list[str]) -> None:
    first = prepare_requirements(PrepareRequirementsCommand(intake(constraints=tuple(values))))
    second = prepare_requirements(
        PrepareRequirementsCommand(intake(constraints=tuple(reversed(values))))
    )
    assert (
        first.product_brief.canonical_fingerprint() == second.product_brief.canonical_fingerprint()
    )
    assert (
        first.review_package.canonical_fingerprint()
        == second.review_package.canonical_fingerprint()
    )


@given(
    st.text(alphabet=st.characters(min_codepoint=32, max_codepoint=126), min_size=1, max_size=40)
)
def test_whitespace_normalization_is_deterministic(text: str) -> None:
    normalized = " ".join(text.split())
    if not normalized:
        return
    left = prepare_requirements(
        PrepareRequirementsCommand(intake(value_proposition=f"  {normalized}  "))
    )
    right = prepare_requirements(PrepareRequirementsCommand(intake(value_proposition=normalized)))
    assert left.product_brief == right.product_brief


@given(st.sampled_from(["Goal A", "Goal B", "Goal C"]))
def test_semantic_mutation_changes_review_fingerprint(goal: str) -> None:
    baseline = prepare_requirements(PrepareRequirementsCommand(intake(primary_goal="Baseline")))
    changed = prepare_requirements(PrepareRequirementsCommand(intake(primary_goal=goal)))
    assert (
        baseline.review_package.canonical_fingerprint()
        != changed.review_package.canonical_fingerprint()
    )


@given(st.booleans())
def test_any_blocking_gap_prevents_ready_state(remove_criteria: bool) -> None:
    base = answer("x", RequirementCategory.FUNCTIONAL, "A material behavior.")
    broken = replace(base, acceptance_criteria=()) if remove_criteria else base
    value = intake(answers=(broken,), primary_goal="" if not remove_criteria else "Goal")
    review = prepare_requirements(PrepareRequirementsCommand(value)).review_package
    assert review.readiness is RequirementsReadiness.NOT_READY


@given(st.integers(min_value=1, max_value=8))
def test_duplicate_answer_input_is_idempotent(count: int) -> None:
    item = answer("same", RequirementCategory.FUNCTIONAL, "One exact behavior.")
    result = prepare_requirements(
        PrepareRequirementsCommand(intake(answers=tuple(item for _ in range(count))))
    )
    assert len(result.requirements_contract.requirements) == 1
