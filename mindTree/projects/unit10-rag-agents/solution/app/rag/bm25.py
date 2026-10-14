"""Okapi BM25 keyword index in pure Python."""

from __future__ import annotations

import math
from collections import Counter
from collections.abc import Collection, Sequence

from app.rag.documents import Chunk
from app.rag.text import chunk_text_for_index, tokenize


class BM25Index:
    """score(q, d) = sum over query terms t of
    idf(t) * tf * (k1 + 1) / (tf + k1 * (1 - b + b * |d| / avgdl))"""

    def __init__(
        self, chunks: Sequence[Chunk], k1: float = 1.5, b: float = 0.75
    ) -> None:
        self.k1, self.b = k1, b
        self.chunks = list(chunks)
        self._tf = [
            Counter(
                tokenize(chunk_text_for_index(c.title, c.heading, c.text))
            )
            for c in self.chunks
        ]
        self._len = [sum(tf.values()) for tf in self._tf]
        n = len(self.chunks)
        self._avgdl = (sum(self._len) / n) if n else 0.0
        df: Counter[str] = Counter()
        for tf in self._tf:
            df.update(tf.keys())
        # BM25+ style idf that is never negative for common terms.
        self._idf = {
            t: math.log(1 + (n - f + 0.5) / (f + 0.5))
            for t, f in df.items()
        }

    def search(
        self,
        query: str,
        k: int,
        allowed: Collection[str] | None = None,
    ) -> list[tuple[Chunk, float]]:
        """Top-k chunks with score > 0. `allowed` is a pre-filter of
        chunk ids: filtered-out chunks never compete for top-k."""
        terms = tokenize(query)
        scored: list[tuple[Chunk, float]] = []
        for i, chunk in enumerate(self.chunks):
            if allowed is not None and chunk.chunk_id not in allowed:
                continue
            tf, dl = self._tf[i], self._len[i]
            score = 0.0
            for t in terms:
                f = tf.get(t, 0)
                if not f:
                    continue
                norm = self.k1 * (1 - self.b + self.b * dl / self._avgdl)
                score += self._idf[t] * f * (self.k1 + 1) / (f + norm)
            if score > 0:
                scored.append((chunk, score))
        scored.sort(key=lambda pair: (-pair[1], pair[0].chunk_id))
        return scored[:k]
