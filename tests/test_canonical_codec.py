"""Canonical JSON, round-trip, and integrity evidence tests."""

import json
from dataclasses import replace
from datetime import UTC, datetime, timedelta, timezone

import pytest

from arch_web import (
    DesignReference,
    EvidenceRef,
    WebContractIntegrityError,
    WebContractValidationError,
    WebInformationArchitectureContract,
    WebProjectProfile,
    WebRequirementsContract,
    WebStackProfile,
    canonical_bytes,
    decode_contract,
    encode_contract,
)
from conftest import NOW, make_ia, make_project, make_requirements, make_stack


@pytest.mark.parametrize(
    ("contract_class", "value"),
    [
        (WebStackProfile, make_stack()),
        (WebRequirementsContract, make_requirements()),
        (WebInformationArchitectureContract, make_ia()),
        (WebProjectProfile, make_project()),
        (DesignReference, DesignReference("d1", "tokens", "urn:design:1", captured_at=NOW)),
        (EvidenceRef, EvidenceRef("e1", "report", "urn:evidence:1", created_at=NOW)),
    ],
)
def test_canonical_round_trip(contract_class: type[object], value: object) -> None:
    payload = encode_contract(value)  # type: ignore[arg-type]
    decoded = decode_contract(contract_class, payload)  # type: ignore[type-var]
    assert decoded == value
    assert encode_contract(decoded) == payload  # type: ignore[arg-type]


def test_expected_fingerprint_is_verified_fail_closed() -> None:
    stack = make_stack()
    assert (
        decode_contract(
            WebStackProfile,
            stack.canonical_bytes(),
            expected_fingerprint=stack.canonical_fingerprint(),
        )
        == stack
    )
    with pytest.raises(WebContractIntegrityError, match="fingerprint"):
        decode_contract(WebStackProfile, stack.canonical_bytes(), expected_fingerprint="0" * 64)


def test_noncanonical_json_is_rejected() -> None:
    stack = make_stack()
    pretty = json.dumps(stack.canonical_data(), indent=2).encode()
    with pytest.raises(WebContractIntegrityError, match="not canonical"):
        decode_contract(WebStackProfile, pretty)


@pytest.mark.parametrize("payload", [b"not-json", b"[]", b'"text"', b"\xff"])
def test_invalid_payload_is_rejected(payload: bytes) -> None:
    with pytest.raises(WebContractValidationError):
        decode_contract(WebStackProfile, payload)


def test_canonical_policy_rejects_nonfinite_numbers_and_nonstring_keys() -> None:
    with pytest.raises(WebContractValidationError, match="NaN"):
        canonical_bytes({"score": float("nan")})
    with pytest.raises(WebContractValidationError, match="NaN"):
        canonical_bytes({"score": float("inf")})
    with pytest.raises(WebContractValidationError, match="keys"):
        canonical_bytes({1: "bad"})


def test_canonical_policy_rejects_unsupported_values() -> None:
    with pytest.raises(WebContractValidationError, match="Unsupported"):
        canonical_bytes(object())


def test_datetime_is_timezone_independent_and_uses_one_utc_shape() -> None:
    mexico_offset = timezone(timedelta(hours=-6))
    local = datetime(2026, 8, 19, 6, 30, tzinfo=mexico_offset)
    utc = datetime(2026, 8, 19, 12, 30, tzinfo=UTC)
    left = DesignReference("d1", "tokens", "urn:d", captured_at=local)
    right = DesignReference("d1", "tokens", "urn:d", captured_at=utc)
    assert left.canonical_bytes() == right.canonical_bytes()
    assert b"2026-08-19T12:30:00.000000Z" in left.canonical_bytes()


def test_semantic_change_changes_sha256_fingerprint() -> None:
    project = make_project()
    changed = replace(project, primary_goal="A different goal.")
    assert len(project.canonical_fingerprint()) == 64
    assert project.canonical_fingerprint() != changed.canonical_fingerprint()


def test_contract_reference_fingerprint_participates_in_its_own_content() -> None:
    project = make_project()
    changed_ref = replace(project.stack_profile_ref, fingerprint="f" * 64)
    changed = replace(project, stack_profile_ref=changed_ref)
    assert project.canonical_fingerprint() != changed.canonical_fingerprint()


def test_unknown_decoder_class_is_rejected() -> None:
    class Unknown(WebStackProfile):
        pass

    with pytest.raises(WebContractValidationError, match="No approved decoder"):
        decode_contract(Unknown, make_stack().canonical_bytes())
