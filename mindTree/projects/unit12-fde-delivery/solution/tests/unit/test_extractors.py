from datetime import date

import pytest

from app.extraction.dates import parse_date
from app.extraction.deterministic import extract_deterministic
from app.extraction.llm import FakeExtractor
from app.fields import ALL_FIELDS, Field
from tests.conftest import sample


@pytest.mark.parametrize(
    "text",
    [
        "1985-03-14",
        "03/14/1985",
        "March 14, 1985",
        "14 March 1985",
        "14th of March 1985",
    ],
)
def test_parse_date_formats_from_discovery(text: str) -> None:
    assert parse_date(text) == date(1985, 3, 14)


def test_parse_date_rejects_garbage() -> None:
    assert parse_date("next Tuesday") is None
    assert parse_date("13/45/2020") is None


@pytest.mark.parametrize(
    "raw",
    [
        "555-010-1111",
        "(555) 010-1111",
        "555.010.1111",
        "555 010 1111",
        "+1 555 010 1111",
    ],
)
def test_phone_formats_normalize_to_e164(raw: str) -> None:
    found = extract_deterministic(f"Phone: {raw}")
    assert found[Field.PHONE].value == "+15550101111"


def test_deterministic_extracts_formatted_fields_only() -> None:
    found = extract_deterministic(sample("02_web_form.txt"))
    assert found[Field.EMAIL].value == "j.okafor@example.org"
    assert found[Field.POLICY_NUMBER].value == "NWH-7654321"
    assert found[Field.DATE_OF_BIRTH].value == "1990-04-22"
    assert found[Field.PREFERRED_DATE].value == "2026-10-28"
    # Name and reason need language understanding: not regex work.
    assert Field.PATIENT_NAME not in found
    assert Field.REASON not in found


def test_unlabeled_date_is_not_guessed_by_regex() -> None:
    found = extract_deterministic("i was born on 3rd of March 1978")
    assert Field.DATE_OF_BIRTH not in found


def test_fake_extractor_scores_guesses_lower_than_labels() -> None:
    fake = FakeExtractor()
    labeled = fake.extract("Name: James Okafor", ALL_FIELDS)
    signed = fake.extract("thanks\n> ana silva", ALL_FIELDS)
    assert labeled[Field.PATIENT_NAME].confidence == 0.95
    assert signed[Field.PATIENT_NAME].value == "Ana Silva"
    assert signed[Field.PATIENT_NAME].confidence < 0.85


def test_fake_extractor_only_returns_requested_fields() -> None:
    out = FakeExtractor().extract(
        sample("01_clean_email.txt"), [Field.REASON]
    )
    assert set(out) == {Field.REASON}
