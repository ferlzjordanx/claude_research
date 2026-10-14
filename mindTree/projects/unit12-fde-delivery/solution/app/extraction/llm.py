"""LLM extraction behind a Protocol, plus a deterministic fake.

A real adapter (Anthropic or OpenAI, built in Unit 9) implements the
same method: send the text and the field list, ask for structured
JSON output, validate it with Pydantic, retry once on invalid JSON,
and return Candidates. Nothing else in the app changes.
"""

import re
from collections.abc import Sequence
from typing import Protocol

from app.extraction.dates import parse_date
from app.extraction.deterministic import PHONE_RE, normalize_phone
from app.fields import Field
from app.models import Candidate


class LLMExtractor(Protocol):
    def extract(
        self, text: str, fields: Sequence[Field]
    ) -> dict[Field, Candidate]:
        """Return a Candidate for each requested field it can fill.

        Contract: dates as ISO 8601, phones as +1XXXXXXXXXX,
        confidence in [0, 1]. Omit a field rather than invent it.
        """
        ...


_NAME_PATTERNS = (
    (re.compile(r"^\s*(?:patient\s+)?name\s*:\s*(.+)$", re.I | re.M), 0.95),
    (
        re.compile(r"\b(?i:my name is) ([A-Z][\w'-]+(?: [A-Z][\w'-]+)+)"),
        0.9,
    ),
    (
        re.compile(
            r"^(?:thanks|thank you|regards|best),?\s*\n\s*"
            r"([A-Za-z][\w'-]+(?: [A-Za-z][\w'-]+)+)\s*$",
            re.I | re.M,
        ),
        0.6,
    ),
)
_REASON_LABEL = re.compile(
    r"^\s*reason(?: for visit)?\s*:\s*(.+)$", re.I | re.M
)
_REASON_SENTENCE = re.compile(
    r"\b((?:i need|i'd like|i would like|appointment for)\b[^.]*)",
    re.I,
)
_BORN = re.compile(
    r"\bborn (?:on )?("
    r"\d{1,2}(?:st|nd|rd|th)? (?:of )?[A-Za-z]+ \d{4}"
    r"|[A-Za-z]+ \d{1,2},? \d{4}"
    r"|\d{1,2}/\d{1,2}/\d{4}"
    r"|\d{4}-\d{2}-\d{2})",
    re.I,
)
_QUOTE_MARK = re.compile(r"^[ \t]*>[ \t]?", re.M)
_BEST_PHONE = re.compile(
    r"(?:best number is|call me at|reach me at)\s*([^\n]+)", re.I
)


class FakeExtractor:
    """Stands in for the model in dev, tests and demos.

    Heuristics plus honest confidences: a labeled value scores high,
    a guess from a sign-off line scores low. Same input, same output,
    so tests and the demo are repeatable.
    """

    def extract(
        self, text: str, fields: Sequence[Field]
    ) -> dict[Field, Candidate]:
        out: dict[Field, Candidate] = {}
        wanted = set(fields)
        # Models read through "> " quoting; the fake does it here.
        text = _QUOTE_MARK.sub("", text)
        if Field.PATIENT_NAME in wanted:
            for pattern, conf in _NAME_PATTERNS:
                if m := pattern.search(text):
                    name = m.group(1).strip().title()
                    out[Field.PATIENT_NAME] = Candidate(
                        value=name, confidence=conf
                    )
                    break
        if Field.REASON in wanted:
            if m := _REASON_LABEL.search(text):
                out[Field.REASON] = Candidate(
                    value=m.group(1).strip(), confidence=0.95
                )
            elif m := _REASON_SENTENCE.search(text):
                out[Field.REASON] = Candidate(
                    value=" ".join(m.group(1).split()), confidence=0.7
                )
        if Field.DATE_OF_BIRTH in wanted and (m := _BORN.search(text)):
            if d := parse_date(m.group(1)):
                out[Field.DATE_OF_BIRTH] = Candidate(
                    value=d.isoformat(), confidence=0.6
                )
        if Field.PHONE in wanted and (m := _BEST_PHONE.search(text)):
            if p := PHONE_RE.search(m.group(1)):
                out[Field.PHONE] = Candidate(
                    value=normalize_phone(*p.groups()), confidence=0.9
                )
        return out
