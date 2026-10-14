"""Knowledge base: section chunks + BM25 keyword search (see Unit 10).

Small and deterministic on purpose. Production would add embeddings
and hybrid ranking; the interface (search -> cited chunks) stays.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

TOKEN = re.compile(r"[a-z0-9]+")
STOP = frozenset(
    "a an and are be by for from i if in is it my of on or the to was"
    " what when where who why with you your".split()
)


def tokenize(text: str) -> list[str]:
    return [t for t in TOKEN.findall(text.lower()) if t not in STOP]


@dataclass(frozen=True, slots=True)
class Chunk:
    id: str  # "<doc>#<section>", the citation format
    title: str
    text: str


@dataclass(frozen=True, slots=True)
class Hit:
    chunk: Chunk
    score: float


def _chunks_of(path: Path) -> list[Chunk]:
    """One chunk per "## " section; the "# " heading is the doc title."""
    doc_title, out = path.stem, []
    sections: list[tuple[str, list[str]]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("# "):
            doc_title = line[2:].strip()
        elif line.startswith("## "):
            sections.append((line[3:].strip(), []))
        elif line.strip() and sections:
            sections[-1][1].append(line.strip())
    for n, (section, lines) in enumerate(sections, start=1):
        if lines:
            out.append(
                Chunk(
                    f"{path.stem}#{n}",
                    f"{doc_title} > {section}",
                    " ".join(lines),
                )
            )
    return out


def load_chunks(directory: Path) -> list[Chunk]:
    return [
        c for p in sorted(directory.glob("*.md")) for c in _chunks_of(p)
    ]


class KnowledgeBase:
    def __init__(
        self, chunks: list[Chunk], k1: float = 1.5, b: float = 0.75
    ) -> None:
        self.chunks = chunks
        self._k1, self._b = k1, b
        self._tf = [
            Counter(tokenize(c.title + " " + c.text)) for c in chunks
        ]
        self._len = [sum(tf.values()) for tf in self._tf]
        self._avg = sum(self._len) / max(len(chunks), 1)
        df: Counter[str] = Counter()
        for tf in self._tf:
            df.update(tf.keys())
        n = len(chunks)
        self._idf = {
            t: math.log(1 + (n - d + 0.5) / (d + 0.5))
            for t, d in df.items()
        }

    @classmethod
    def from_dir(cls, directory: str | Path) -> KnowledgeBase:
        return cls(load_chunks(Path(directory)))

    def search(self, query: str, k: int = 3) -> list[Hit]:
        terms = tokenize(query)
        hits = []
        for chunk, tf, length in zip(
            self.chunks, self._tf, self._len, strict=True
        ):
            score = 0.0
            for t in terms:
                if t not in tf:
                    continue
                f = tf[t]
                norm = 1 - self._b + self._b * length / self._avg
                score += (
                    self._idf[t]
                    * f
                    * (self._k1 + 1)
                    / (f + self._k1 * norm)
                )
            if score > 0:
                hits.append(Hit(chunk, round(score, 3)))
        hits.sort(key=lambda h: h.score, reverse=True)
        return hits[:k]

    def get(self, chunk_id: str) -> Chunk | None:
        return next((c for c in self.chunks if c.id == chunk_id), None)
