"""Embedder protocol, a deterministic stand-in, and a vector index.

HashingEmbedder is NOT semantic: it maps words to buckets (feature
hashing), so "refund" and "money back" do not match. Real systems call
a provider embedding model behind the same Embedder protocol and store
vectors in pgvector, OpenSearch, Pinecone or similar (ANN/HNSW).
"""

from __future__ import annotations

import hashlib
import math
from collections.abc import Collection, Sequence
from typing import Protocol

from app.rag.documents import Chunk
from app.rag.text import chunk_text_for_index, tokenize

Vector = list[float]


class Embedder(Protocol):
    dim: int

    def embed(self, texts: Sequence[str]) -> list[Vector]: ...


def _bucket(feature: str, dim: int) -> tuple[int, float]:
    # hashlib, not hash(): Python's hash() is salted per process, so
    # vectors would change between runs and the index would break.
    digest = hashlib.blake2b(feature.encode(), digest_size=8).digest()
    value = int.from_bytes(digest, "big")
    sign = 1.0 if value & 1 else -1.0  # signed hashing reduces bias
    return (value >> 1) % dim, sign


def l2_normalize(vec: Vector) -> Vector:
    norm = math.sqrt(sum(x * x for x in vec))
    return [x / norm for x in vec] if norm else vec


class HashingEmbedder:
    """Bag of words + bigrams, feature-hashed, L2-normalized."""

    def __init__(self, dim: int = 4096) -> None:
        self.dim = dim

    def embed(self, texts: Sequence[str]) -> list[Vector]:
        return [self._embed_one(t) for t in texts]

    def _embed_one(self, text: str) -> Vector:
        vec = [0.0] * self.dim
        tokens = tokenize(text)
        features = tokens + [
            f"{a}_{b}" for a, b in zip(tokens, tokens[1:], strict=False)
        ]
        for feature in features:
            index, sign = _bucket(feature, self.dim)
            vec[index] += sign
        return l2_normalize(vec)


def cosine(a: Vector, b: Vector) -> float:
    """Dot product: both vectors are already unit length."""
    return sum(x * y for x, y in zip(a, b, strict=True))


class VectorIndex:
    """Exact (brute-force) cosine search. Fine for thousands of
    chunks; use an ANN index such as HNSW beyond that."""

    def __init__(self, chunks: Sequence[Chunk], embedder: Embedder):
        self.chunks = list(chunks)
        self.embedder = embedder
        self._vectors = embedder.embed(
            [
                chunk_text_for_index(c.title, c.heading, c.text)
                for c in self.chunks
            ]
        )

    def search(
        self,
        query: str,
        k: int,
        allowed: Collection[str] | None = None,
    ) -> list[tuple[Chunk, float]]:
        [q] = self.embedder.embed([query])
        scored = [
            (chunk, cosine(q, vec))
            for chunk, vec in zip(self.chunks, self._vectors, strict=True)
            if allowed is None or chunk.chunk_id in allowed
        ]
        scored.sort(key=lambda pair: (-pair[1], pair[0].chunk_id))
        return [pair for pair in scored[:k] if pair[1] > 0]
