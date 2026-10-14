"""Ingestion: load markdown docs with front matter, chunk by heading."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

import yaml


class Audience(StrEnum):
    PUBLIC = "public"
    INTERNAL = "internal"


@dataclass(frozen=True)
class Document:
    doc_id: str
    title: str
    audience: Audience
    body: str
    updated: str = ""


@dataclass(frozen=True)
class Chunk:
    chunk_id: str  # "<doc_id>#<n>": the citation key
    doc_id: str
    title: str
    heading: str
    text: str
    audience: Audience


FRONT_MATTER = re.compile(r"\A---\n(.*?)\n---\n", re.DOTALL)
HEADING = re.compile(r"^(#{1,6})\s+(.*)$")


def parse_document(raw: str, fallback_id: str) -> Document:
    """Split YAML front matter from the markdown body."""
    meta: dict[str, object] = {}
    body = raw
    match = FRONT_MATTER.match(raw)
    if match:
        loaded = yaml.safe_load(match.group(1)) or {}
        if not isinstance(loaded, dict):
            raise ValueError(f"{fallback_id}: front matter not a map")
        meta = loaded
        body = raw[match.end() :]
    # Fail closed: a doc without an audience is treated as internal.
    audience = Audience(str(meta.get("audience", "internal")))
    return Document(
        doc_id=str(meta.get("id", fallback_id)),
        title=str(meta.get("title", fallback_id)),
        audience=audience,
        body=body.strip(),
        updated=str(meta.get("updated", "")),
    )


def load_kb(directory: Path) -> list[Document]:
    docs = [
        parse_document(p.read_text(encoding="utf-8"), p.stem)
        for p in sorted(directory.glob("*.md"))
    ]
    ids = [d.doc_id for d in docs]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate document ids in knowledge base")
    return docs


def _sections(body: str) -> list[tuple[str, str]]:
    """Group lines under their nearest heading: (heading, text)."""
    sections: list[tuple[str, list[str]]] = [("", [])]
    for line in body.splitlines():
        match = HEADING.match(line)
        if match:
            sections.append((match.group(2).strip(), []))
        else:
            sections[-1][1].append(line)
    out = []
    for heading, lines in sections:
        text = " ".join(" ".join(lines).split())
        if text:
            out.append((heading, text))
    return out


def _windows(text: str, max_chars: int, overlap: int) -> list[str]:
    """Split long text on word boundaries with a character overlap."""
    if len(text) <= max_chars:
        return [text]
    words = text.split()
    pieces: list[str] = []
    start = 0
    while start < len(words):
        end, size = start, 0
        while end < len(words) and size + len(words[end]) + 1 <= max_chars:
            size += len(words[end]) + 1
            end += 1
        end = max(end, start + 1)  # always make progress
        pieces.append(" ".join(words[start:end]))
        if end >= len(words):
            break
        # Step back far enough to repeat ~overlap characters.
        back, kept = end, 0
        while back > start + 1 and kept < overlap:
            back -= 1
            kept += len(words[back]) + 1
        start = back
    return pieces


def chunk_document(
    doc: Document, max_chars: int = 600, overlap: int = 80
) -> list[Chunk]:
    """Chunk by structure first (headings), then by size."""
    chunks: list[Chunk] = []
    for heading, text in _sections(doc.body):
        for piece in _windows(text, max_chars, overlap):
            n = len(chunks)
            chunks.append(
                Chunk(
                    chunk_id=f"{doc.doc_id}#{n}",
                    doc_id=doc.doc_id,
                    title=doc.title,
                    heading=heading,
                    text=piece,
                    audience=doc.audience,
                )
            )
    return chunks


def chunk_all(
    docs: list[Document], max_chars: int = 600, overlap: int = 80
) -> list[Chunk]:
    return [c for d in docs for c in chunk_document(d, max_chars, overlap)]
