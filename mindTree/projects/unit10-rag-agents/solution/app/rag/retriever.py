"""Hybrid retrieval: permission pre-filter, BM25 + vectors, RRF."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from app.rag.bm25 import BM25Index
from app.rag.documents import Audience, Chunk
from app.rag.embeddings import Embedder, VectorIndex
from app.rag.text import chunk_text_for_index, tokenize
from app.roles import Role


@dataclass(frozen=True)
class Hit:
    chunk: Chunk
    fused: float  # RRF score: rank-based, NOT a relevance measure
    relevance: float  # rerank score in [0, 1]: used to abstain
    bm25_rank: int | None
    vector_rank: int | None


def rrf(
    rankings: Sequence[Sequence[str]], k: int = 60
) -> list[tuple[str, float]]:
    """Reciprocal Rank Fusion: score(d) = sum_i 1 / (k + rank_i(d)),
    ranks start at 1. Ties break by id so results are deterministic."""
    scores: dict[str, float] = {}
    for ranking in rankings:
        for rank, item in enumerate(ranking, start=1):
            scores[item] = scores.get(item, 0.0) + 1.0 / (k + rank)
    return sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))


def allowed_audiences(role: Role) -> frozenset[Audience]:
    """Which documents a role may ever see. Enforced in code, before
    retrieval, never by asking the model to keep secrets."""
    if role is Role.AGENT:
        return frozenset({Audience.PUBLIC, Audience.INTERNAL})
    return frozenset({Audience.PUBLIC})


class HybridRetriever:
    def __init__(self, chunks: Sequence[Chunk], embedder: Embedder):
        self.chunks = list(chunks)
        self.embedder = embedder
        self.bm25 = BM25Index(self.chunks)
        self.vectors = VectorIndex(self.chunks, embedder)
        self._by_id = {c.chunk_id: c for c in self.chunks}

    def allowed_ids(self, role: Role) -> set[str]:
        audiences = allowed_audiences(role)
        return {c.chunk_id for c in self.chunks if c.audience in audiences}

    def search(
        self, query: str, role: Role, k: int = 4, candidates: int = 10
    ) -> list[Hit]:
        allowed = self.allowed_ids(role)  # 1. filter BEFORE ranking
        keyword = self.bm25.search(query, candidates, allowed)
        semantic = self.vectors.search(query, candidates, allowed)
        kw_ids = [c.chunk_id for c, _ in keyword]
        vec_ids = [c.chunk_id for c, _ in semantic]
        hits = []
        for cid, fused in rrf([kw_ids, vec_ids])[:k]:  # 2. fuse
            chunk = self._by_id[cid]
            if chunk.chunk_id not in allowed:  # 3. defense in depth
                continue
            hits.append(
                Hit(
                    chunk=chunk,
                    fused=fused,
                    relevance=coverage(query, chunk),
                    bm25_rank=_rank(kw_ids, cid),
                    vector_rank=_rank(vec_ids, cid),
                )
            )
        # 4. rerank: best evidence first (stable for equal scores)
        hits.sort(key=lambda h: -h.relevance)
        return hits


def coverage(query: str, chunk: Chunk) -> float:
    """Share of distinct query terms that appear in the chunk.
    A cheap, explainable stand-in for a cross-encoder reranker."""
    terms = set(tokenize(query))
    if not terms:
        return 0.0
    text = chunk_text_for_index(chunk.title, chunk.heading, chunk.text)
    return len(terms & set(tokenize(text))) / len(terms)


def _rank(ids: list[str], cid: str) -> int | None:
    return ids.index(cid) + 1 if cid in ids else None
