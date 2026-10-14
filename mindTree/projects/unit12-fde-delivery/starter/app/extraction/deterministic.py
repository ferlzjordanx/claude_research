"""Deterministic extraction: patterns we can test exhaustively.

Rule of thumb from the ADR: use code for anything with a format
(email, phone, labeled dates, policy numbers); use the LLM only for
fields that need language understanding (name, reason).
"""

import re

from app.extraction.dates import parse_date
from app.fields import Field
from app.models import Candidate

# A regex match is certain about the *format*. It can still be the
# wrong phone number (see the two-phones sample); merge flags that.
CONFIDENCE = 1.0

EMAIL_RE = re.compile(r"\b[\w.+-]+@[\w-]+(?:\.[\w-]+)+\b")
PHONE_RE = re.compile(
    r"(?<!\d)(?:\+?1[\s.-]?)?\(?(\d{3})\)?[\s.-]?(\d{3})[\s.-]?(\d{4})"
    r"(?!\d)"
)
POLICY_RE = re.compile(r"\b([A-Z]{3})[- ]?(\d{7})\b")
DOB_RE = re.compile(
    r"^\s*(?:dob|d\.o\.b\.?|date of birth)\s*[:\-]\s*(.+)$",
    re.IGNORECASE | re.MULTILINE,
)
PREFERRED_RE = re.compile(
    r"^\s*preferred (?:appointment )?date\s*[:\-]\s*(.+)$",
    re.IGNORECASE | re.MULTILINE,
)


def normalize_phone(area: str, exchange: str, line: str) -> str:
    return f"+1{area}{exchange}{line}"


def extract_deterministic(text: str) -> dict[Field, Candidate]:
    """Return only what the patterns found. Never guesses."""
    found: dict[Field, Candidate] = {}

    if m := EMAIL_RE.search(text):
        found[Field.EMAIL] = _c(m.group(0).lower())
    if m := PHONE_RE.search(text):
        found[Field.PHONE] = _c(normalize_phone(*m.groups()))
    if m := POLICY_RE.search(text):
        found[Field.POLICY_NUMBER] = _c(f"{m.group(1)}-{m.group(2)}")
    if (m := DOB_RE.search(text)) and (d := parse_date(m.group(1))):
        found[Field.DATE_OF_BIRTH] = _c(d.isoformat())
    if (m := PREFERRED_RE.search(text)) and (d := parse_date(m.group(1))):
        found[Field.PREFERRED_DATE] = _c(d.isoformat())
    return found


def _c(value: str) -> Candidate:
    return Candidate(value=value, confidence=CONFIDENCE)
