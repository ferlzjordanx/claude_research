"""Tokenization shared by BM25 and the hashing embedder."""

from __future__ import annotations

import re

TOKEN = re.compile(r"[a-z0-9]+")
STOPWORDS = frozenset(
    "a an and are as at be by can do does for from how i if in is it "
    "my of on or our the to we what when where which who will with "
    "you your this that me".split()
)


def stem(token: str) -> str:
    """Crude suffix stripping so "refunds"/"refunded" match "refund".
    Real systems use a proper stemmer or a learned embedding."""
    for suffix, min_len in (("ing", 6), ("ed", 5), ("es", 5), ("s", 4)):
        if token.endswith(suffix) and len(token) >= min_len:
            token = token[: -len(suffix)]
            break
    if len(token) > 3 and token[-1] == token[-2]:
        token = token[:-1]  # "shipp" -> "ship", "cancell" -> "cancel"
    return token


def tokenize(text: str) -> list[str]:
    """Lowercase, split, drop stopwords, stem."""
    return [
        stem(t) for t in TOKEN.findall(text.lower()) if t not in STOPWORDS
    ]


def chunk_text_for_index(title: str, heading: str, text: str) -> str:
    """Prefix the chunk with its title and heading so a chunk that
    says "within 30 days" still matches a query about refunds."""
    return f"{title}. {heading}. {text}"
