"""Date parsing for the formats seen in the discovery samples."""

import re
from datetime import date, datetime

_FORMATS = ("%Y-%m-%d", "%m/%d/%Y", "%B %d %Y", "%b %d %Y", "%d %B %Y")
_ORDINAL = re.compile(r"(\d{1,2})(st|nd|rd|th)\b", re.IGNORECASE)


def parse_date(text: str) -> date | None:
    """Return a date for '1985-03-14', '03/14/1985', 'March 14, 1985',
    '14 March 1985' or '14th of March 1985'; None otherwise.

    US month-first order for slashes: Northwind is US-only (A-4 in
    requirements.md). An ambiguous format is an assumption to log,
    not a detail to hide.
    """
    cleaned = _ORDINAL.sub(r"\1", text.strip().rstrip("."))
    cleaned = re.sub(r"\bof\b", " ", cleaned, flags=re.IGNORECASE)
    cleaned = " ".join(cleaned.replace(",", " ").split())
    for fmt in _FORMATS:
        try:
            return datetime.strptime(cleaned, fmt).date()
        except ValueError:
            continue
    return None
