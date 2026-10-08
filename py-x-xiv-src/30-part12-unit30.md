# Part XII — Embeddings and RAG

**What this part teaches.** How to ground model answers in your own data. Unit 30 teaches embeddings and vector search: what an embedding is, how similarity works, how chunking and metadata shape retrieval, and how to store and query vectors in PostgreSQL with pgvector. Unit 31 builds a complete retrieval-augmented generation (RAG) service from scratch: ingestion, retrieval, context construction, generation with citations, and an evaluation dataset that separates retrieval failures from generation failures. Unit 32 adds production techniques: authorization-aware filtering, query rewriting, hybrid search, reranking, compression, hierarchical chunks, index migrations and retrieval regression tests.

**Why it matters.** Most enterprise AI value comes from answering questions over private, changing data (policies, manuals, tickets, contracts). Fine-tuning doesn't solve that well, and stuffing everything into a prompt doesn't scale. RAG is the default architecture, and its quality depends almost entirely on retrieval engineering, which is measurable, debuggable classical engineering.

**Where it appears.** Support assistants over help-center articles, internal knowledge search, contract Q&A, developer docs bots, and the "retrieve evidence" step of agents in Part XIV.

**Connections.** Uses the LLM client (Unit 29), PostgreSQL and SQLAlchemy 2.x, FastAPI, Docker Compose (pgvector image, Unit 25) and pytest. Feeds tool calling (Unit 34: knowledge search tool) and agents (Units 35–39).

## Unit 30 — Embeddings and Vector Search

### 1. Learning Objectives

By the end of this unit you will be able to:

1. **Explain** what an embedding model produces, what the dimensions of a vector space represent (and don't), and why semantically similar texts land near each other.
2. **Compute** cosine similarity, dot product and Euclidean distance with NumPy, **explain** their relationship for normalized vectors, and **choose** the right pgvector operator and index operator class.
3. **Distinguish** tokens from embeddings, and embedding models from generative models.
4. **Design** chunking strategies (fixed-size with overlap, structure-aware, sentence-based) and metadata schemas (tenant, document, section, version, ACL, language, timestamps).
5. **Implement** embedding generation behind a provider-neutral interface with batching, retries and caching.
6. **Implement** vector storage and top-k similarity search in PostgreSQL with pgvector and SQLAlchemy 2.x, including HNSW/IVFFlat indexes, query tuning and filtered search.
7. **Evaluate** chunk size and top-k choices experimentally with recall@k and MRR on a labelled query set.
8. **Explain** hybrid search and reranking at a conceptual level (implemented in Unit 32), and when a dedicated vector database is warranted.

### 2. Prerequisite Knowledge

- **Linear algebra basics:** vectors, dot product, norm (length), angle between vectors.
- **PostgreSQL:** tables, indexes, `EXPLAIN ANALYZE`, extensions, transactions.
- **SQLAlchemy 2.x:** declarative models with `Mapped[...]`, `select()`, async sessions.
- **Unit 29:** LLM client patterns (retries, budgets, adapters). Embedding calls are model calls too.
- **NumPy:** arrays, vectorized operations.

**Refresher: dot product and cosine.** For vectors a and b: `a·b = Σ aᵢbᵢ`, `‖a‖ = √(a·a)`, `cos(a,b) = a·b / (‖a‖‖b‖)` ∈ [−1, 1]. If both are unit-normalized (‖a‖ = ‖b‖ = 1), then `cos(a,b) = a·b` and `‖a−b‖² = 2 − 2·cos(a,b)`. So for normalized vectors, ranking by cosine, by dot product, or by Euclidean distance gives the **same order**.

### 3. Mental Model

An embedding model is **a function that maps text to a point in a high-dimensional space, trained so that texts with similar meaning map to nearby points**.

```
"Where is my parcel?"          ─┐
"Track my order shipment"      ─┼─▶ embedding model ─▶ points close together
"My package hasn't arrived"    ─┘
"How do I reset my password?"  ─────▶ embedding model ─▶ point far away from the cluster above
```

Vector search is then **nearest-neighbor lookup**: embed the query, find the k stored points closest to it, and return their source text and metadata.

```
documents ─▶ chunk ─▶ embed ─▶ (pgvector: id, tenant_id, doc_id, chunk_text, metadata, embedding)
query     ─▶ embed ─▶ ORDER BY embedding <=> :query_vector LIMIT k  (+ WHERE tenant/ACL filters)
```

Three cautions:

1. "Near" means *similar according to the model's training*, not "correct" or "answers the question". A chunk can be similar but irrelevant, or relevant but phrased differently.
2. Individual dimensions have **no human-interpretable meaning**. Only distances and directions matter.
3. Vectors from different embedding models (or versions) are **not comparable**. Switching models means re-embedding everything.

### 4. Comprehensive Theory

#### 4.1 Embedding Models and Vector Spaces

**Definition.** An embedding model (typically a transformer encoder trained with contrastive objectives) maps an input (text, sometimes images or code) to a fixed-length vector of floats, for example 384, 768, 1024 or 3072 dimensions.

**How they're trained (intuition).** On pairs of related texts (question/answer, title/body, paraphrases) and unrelated texts, the model learns to pull related pairs together and push unrelated ones apart. This gives *semantic* similarity: synonyms and paraphrases match even without shared words.

**Model choices (October 2026 landscape, verify current options).** [Version-dependent]

| Option | Examples | Notes |
|---|---|---|
| Hosted APIs | Voyage AI (`voyage-3.5`-family; recommended by Anthropic, which doesn't offer its own embedding model), OpenAI `text-embedding-3-small/large`, Cohere Embed, Google Gemini embeddings | Easy, scalable; data leaves your infra; per-token cost |
| Cloud-managed | Amazon Bedrock (Titan Text Embeddings V2, Cohere Embed) | IAM, VPC endpoints, region control |
| Self-hosted open models | `sentence-transformers` models (e.g., `all-MiniLM-L6-v2` 384-d, BGE/E5/GTE families, multilingual variants) | Free per call, needs CPU/GPU capacity, version pinning is yours |

**Selection criteria:** retrieval quality on *your* data (measure it, since public leaderboards like MTEB are only a starting point), languages, max input length (tokens), dimension (storage and speed), cost, latency, data governance, and asymmetric query/document modes (some models use different prefixes or `input_type` for queries vs documents. Use them correctly or quality drops).

**Dimensions and storage.** A 1024-d float32 vector is 4 KB. 10M chunks means ~40 GB of raw vectors before index overhead. Options: smaller models, **Matryoshka**-trained models that allow truncating dimensions with graceful quality loss, `halfvec` (16-bit floats in pgvector), and binary quantization with re-ranking.

**Normalization.** Many models output unit-normalized vectors; some don't. Normalize at write time if you'll use dot product or rely on cosine/L2 equivalence.

#### 4.2 Cosine Similarity and Distance

| Measure | Formula | pgvector operator | Index opclass | Notes |
|---|---|---|---|---|
| Cosine distance | `1 − cos(a,b)` | `<=>` | `vector_cosine_ops` | Default choice for text embeddings |
| Negative inner product | `−(a·b)` | `<#>` | `vector_ip_ops` | Fastest if vectors normalized; equals cosine ranking then |
| Euclidean (L2) | `‖a−b‖` | `<->` | `vector_l2_ops` | Equivalent ranking for normalized vectors |
| L1 (Manhattan) | `Σ|aᵢ−bᵢ|` | `<+>` | `vector_l1_ops` | Rare for text |

Use the metric the embedding model was trained for (documented by the provider), and keep the operator in queries consistent with the index opclass, or the index won't be used.

**Similarity scores aren't calibrated probabilities.** A cosine of 0.82 doesn't mean "82% relevant", and the score distribution differs across models. Thresholds must be tuned per model on labelled data.

#### 4.3 Embeddings vs Tokens

- **Tokens** are discrete units of text processed by models (Unit 28). A generative model's input is a token sequence.
- **Embeddings** are dense vectors. Inside a transformer, every token gets an internal embedding, but an **embedding model's output** is typically *one vector per input text* (pooled), designed for similarity.
- Embedding APIs bill per input token and have max token limits per input. Chunks longer than the limit get truncated, often silently.

#### 4.4 Chunking and Metadata

**Why chunk.** Embedding models have input limits, and one vector per long document blurs many topics together ("average meaning"). Retrieval needs units small enough to be specific and large enough to be self-contained.

**Strategies.**

| Strategy | How | Pros | Cons |
|---|---|---|---|
| Fixed-size tokens + overlap | e.g., 400 tokens, 50 overlap | Simple, predictable | Splits mid-sentence/table |
| Sentence/paragraph packing | Pack sentences up to a token budget | Coherent units | Variable sizes |
| Structure-aware | Split by headings/sections (Markdown/HTML), keep heading path | Preserves context and citations | Needs parsing per format |
| Semantic | Split where embedding similarity between adjacent sentences drops | Topic-coherent | Costlier, less predictable |
| Hierarchical (parent-child) | Small chunks for matching, larger parent for context | Precision + context | More storage/logic (Unit 32) |

**Practical defaults for support docs:** structure-aware splitting by headings, then packing paragraphs to ~300–500 tokens with ~10–15% overlap. Prefix each chunk with its title and heading path ("Shipping Policy › International › Delays") so it is self-describing, and keep tables intact (or convert them to text rows).

**Metadata (store alongside each chunk):**

```
tenant_id, document_id, document_version, chunk_index, title, heading_path,
source_uri, language, content_type, acl_groups[], created_at, updated_at,
embedding_model, embedding_dim, content_hash
```

Metadata enables **filtering** (tenant, ACL, language, freshness), **citations** (document, section, URI), **dedupe and incremental updates** (content hash), and **migrations** (embedding model/version).

**Common mistakes.** Chunks without titles ("It must be returned within 30 days" — *what* must?), tables split across chunks, no tenant/ACL metadata (making secure filtering impossible later), and storing only vectors without source text.

#### 4.5 Top-k Similarity Search

**Exact (brute force) search** computes distance to every vector: O(N·d), with perfect recall. It's fine up to ~100k vectors with filtering, and is the ground truth for measuring ANN recall.

**Approximate nearest neighbor (ANN)** indexes trade a little recall for big speedups.

- **HNSW** (Hierarchical Navigable Small World): a multi-layer proximity graph. Queries greedily walk from coarse to fine layers. Build parameters: `m` (links per node, default 16) and `ef_construction` (default 64). Query parameter: `hnsw.ef_search` (default 40), where a higher value means better recall and slower queries. Good recall and speed, slower builds and more memory. Supports incremental inserts. Usually the default choice.
- **IVFFlat**: clusters vectors into `lists` (k-means). A query searches the nearest `ivfflat.probes` lists. Faster build and less memory, needs data present before building (to train centroids), and recall depends on `probes`. Rebuild after large data changes.

**Choosing k.** Too small, and you miss relevant chunks (low recall). Too large, and you get noise, cost (tokens in the prompt) and distraction. Typical: retrieve 20–50 candidates, rerank to 5–8 for the prompt (Unit 32). Without reranking, k = 4–8 is common. **Measure** recall@k on your data.

**Filtered search and the "overfiltering" problem.** With ANN, `WHERE tenant_id = :t ORDER BY embedding <=> :q LIMIT 10` may return fewer than 10 rows: the index scan finds the nearest candidates first, then the filter removes most of them. Mitigations:

- pgvector **0.8 iterative index scans** (`SET hnsw.iterative_scan = relaxed_order` or `strict_order`): the index scan continues until enough rows pass the filter (bounded by `hnsw.max_scan_tuples`). [Version-dependent]
- Partial indexes per large tenant or category, or partitioning by tenant.
- Increase `ef_search`.
- For small filtered sets, exact search on the filtered subset can be both faster and perfectly accurate (the planner may choose this when a B-tree filter is selective).

#### 4.6 Vector Stores and pgvector

**pgvector** adds `vector(n)`, `halfvec(n)`, `sparsevec(n)` and `bit(n)` types, distance operators, and HNSW/IVFFlat indexes to PostgreSQL.

**Why pgvector first.** One database for vectors **and** relational data: joins, transactions, ACL metadata, filtering with SQL, backups, and existing operational skills. It fits most applications up to tens of millions of vectors with tuning.

**When a dedicated vector database** (Qdrant, Weaviate, Milvus, Pinecone, OpenSearch k-NN, and others): very large scale (hundreds of millions to billions), very high QPS, built-in multi-tenancy and sharding for vectors, advanced features (multi-vector, sparse+dense native fusion), or when the team prefers a managed vector service. The cost: another system to sync, secure and operate, plus consistency between your relational source of truth and the vector store.

**Schema (SupportDesk).**

```sql
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE kb_document (
    id            uuid PRIMARY KEY,
    tenant_id     text        NOT NULL,
    title         text        NOT NULL,
    source_uri    text        NOT NULL,
    version       integer     NOT NULL,
    acl_groups    text[]      NOT NULL DEFAULT '{}',
    language      text        NOT NULL DEFAULT 'en',
    updated_at    timestamptz NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, source_uri, version)
);

CREATE TABLE kb_chunk (
    id              bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    document_id     uuid    NOT NULL REFERENCES kb_document(id) ON DELETE CASCADE,
    tenant_id       text    NOT NULL,             -- denormalized for filtering without joins
    acl_groups      text[]  NOT NULL DEFAULT '{}',
    chunk_index     integer NOT NULL,
    heading_path    text    NOT NULL DEFAULT '',
    content         text    NOT NULL,
    content_hash    char(64) NOT NULL,
    token_count     integer NOT NULL,
    embedding_model text    NOT NULL,
    embedding       vector(1024) NOT NULL,
    UNIQUE (document_id, chunk_index)
);

CREATE INDEX kb_chunk_embedding_hnsw ON kb_chunk
    USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64);
CREATE INDEX kb_chunk_tenant ON kb_chunk (tenant_id);
CREATE INDEX kb_chunk_acl ON kb_chunk USING gin (acl_groups);
```

**Query.**

```sql
SET LOCAL hnsw.ef_search = 100;
SET LOCAL hnsw.iterative_scan = relaxed_order;   -- pgvector ≥ 0.8
SELECT c.id, c.document_id, c.heading_path, c.content,
       1 - (c.embedding <=> $1) AS cosine_similarity
FROM kb_chunk c
WHERE c.tenant_id = $2
  AND c.acl_groups && $3                         -- user's groups overlap chunk ACL
ORDER BY c.embedding <=> $1
LIMIT 10;
```

`SET LOCAL` scopes the setting to the current transaction, which matters with connection pools so settings don't leak to other requests.

#### 4.7 Hybrid Search and Reranking (Concepts)

**Lexical search** (BM25 / PostgreSQL full-text `tsvector`) matches exact terms: order IDs, product codes, error messages and rare names, which embeddings often blur. **Vector search** matches meaning and paraphrase. **Hybrid search** runs both and fuses results, commonly with **Reciprocal Rank Fusion (RRF)**: `score(d) = Σ 1/(k + rank_i(d))` with k ≈ 60. It's robust because it doesn't need comparable score scales.

**Reranking** uses a more expensive model (a **cross-encoder** that reads query and chunk together, or an LLM) to reorder the top 20–100 candidates. It's more accurate than bi-encoder similarity and too slow to run over the whole corpus, so it's always applied to a candidate set. Unit 32 implements both.

### 5. Internal Mechanics

#### 5.1 What happens when you embed text

```
text → tokenizer (model-specific) → token IDs (truncate at max length!) → transformer encoder layers
→ per-token hidden states → pooling (mean / CLS) → (optional) normalization → vector[d]
```

Truncation is silent in many libraries and APIs, so long chunks lose their tails. Check token counts.

#### 5.2 What happens inside an HNSW query

```
start at entry point on top layer → greedy move to closest neighbor until no improvement
→ descend layer → repeat → bottom layer: best-first search keeping a candidate list of size ef_search
→ return top k by distance → (filter applied after candidates are produced, unless iterative scan continues)
```

Recall depends on `m` (graph connectivity), `ef_construction` (build quality) and `ef_search` (query breadth). Latency grows with `ef_search`. HNSW indexes should fit in memory (`shared_buffers`/OS cache) for good performance. Check index size with `pg_relation_size`.

#### 5.3 How PostgreSQL decides to use the vector index

The planner uses the HNSW index only for `ORDER BY embedding <op> constant LIMIT n` where `<op>` matches the index opclass. Expressions such as `ORDER BY 1 - (embedding <=> q) DESC` won't use it. Always order by the distance operator ascending. With selective filters, the planner may prefer a B-tree index plus exact distance computation. Use `EXPLAIN (ANALYZE, BUFFERS)` to see which.

### 6. Implementation Examples

#### Example 1 — Minimal: Embeddings and cosine similarity in NumPy

```python
# examples/cosine_demo.py
import numpy as np
from sentence_transformers import SentenceTransformer   # local model for learning; pin the version

model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")   # 384-d

sentences = [
    "Where is my parcel?",
    "Track my order shipment",
    "My package hasn't arrived yet",
    "How do I reset my password?",
]
vectors = model.encode(sentences, normalize_embeddings=True)   # shape (4, 384), unit length

def cosine(a: np.ndarray, b: np.ndarray) -> float:
    return float(a @ b / (np.linalg.norm(a) * np.linalg.norm(b)))

similarity = vectors @ vectors.T              # normalized → dot product == cosine
np.set_printoptions(precision=2, suppress=True)
print(similarity)
print(round(cosine(vectors[0], vectors[1]), 3), round(cosine(vectors[0], vectors[3]), 3))

query = model.encode(["package delayed"], normalize_embeddings=True)[0]
scores = vectors @ query
top_k = np.argsort(-scores)[:2]
print([(sentences[i], round(float(scores[i]), 3)) for i in top_k])
```

Observe that the three shipping sentences score high with each other and low with the password sentence. Then try an order ID ("order 88123") and notice how weakly embeddings distinguish exact identifiers. That's the motivation for hybrid search.

#### Example 2 — Realistic: Provider-neutral embedder + pgvector with SQLAlchemy 2.x

```python
# app/rag/embeddings.py
from collections.abc import Sequence
from typing import Protocol

import numpy as np


class Embedder(Protocol):
    model_name: str
    dimension: int

    async def embed_documents(self, texts: Sequence[str]) -> list[list[float]]: ...
    async def embed_query(self, text: str) -> list[float]: ...


def normalize(vec: Sequence[float]) -> list[float]:
    arr = np.asarray(vec, dtype=np.float32)
    norm = float(np.linalg.norm(arr))
    return (arr / norm).tolist() if norm > 0 else arr.tolist()


class LocalSentenceTransformerEmbedder:
    """Self-hosted embedder for development/tests. CPU-bound → run in a thread."""

    def __init__(self, model_name: str = "sentence-transformers/all-MiniLM-L6-v2") -> None:
        from sentence_transformers import SentenceTransformer
        self._model = SentenceTransformer(model_name)
        self.model_name = model_name
        self.dimension = self._model.get_sentence_embedding_dimension()

    async def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        import anyio
        arr = await anyio.to_thread.run_sync(
            lambda: self._model.encode(list(texts), batch_size=32, normalize_embeddings=True))
        return arr.tolist()

    async def embed_query(self, text: str) -> list[float]:
        return (await self.embed_documents([text]))[0]
```

```python
# app/rag/bedrock_embedder.py
import json
from collections.abc import Sequence

import anyio
import boto3

from app.rag.embeddings import normalize


class BedrockTitanEmbedder:
    """Amazon Titan Text Embeddings V2 via Bedrock InvokeModel (one text per call)."""

    def __init__(self, region: str, dimension: int = 1024) -> None:
        self._client = boto3.client("bedrock-runtime", region_name=region)
        self.model_name = "amazon.titan-embed-text-v2:0"
        self.dimension = dimension             # V2 supports 256 / 512 / 1024

    def _embed_one(self, text: str) -> list[float]:
        body = json.dumps({"inputText": text, "dimensions": self.dimension, "normalize": True})
        resp = self._client.invoke_model(modelId=self.model_name, body=body,
                                         contentType="application/json", accept="application/json")
        return json.loads(resp["body"].read())["embedding"]

    async def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        limiter = anyio.CapacityLimiter(8)          # bounded concurrency against quotas
        results: list[list[float] | None] = [None] * len(texts)

        async def run(i: int, t: str) -> None:
            async with limiter:
                results[i] = normalize(await anyio.to_thread.run_sync(self._embed_one, t))

        async with anyio.create_task_group() as tg:
            for i, t in enumerate(texts):
                tg.start_soon(run, i, t)
        return [r for r in results if r is not None]

    async def embed_query(self, text: str) -> list[float]:
        return (await self.embed_documents([text]))[0]
```

(Request/response field names for Titan V2 follow the Bedrock model parameters documentation. Verify against your region's current docs. Some providers offer batch endpoints that are cheaper for bulk ingestion.)

```python
# app/repositories/kb_models.py
import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import ARRAY, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

EMBED_DIM = 1024


class Base(DeclarativeBase):
    pass


class KbDocument(Base):
    __tablename__ = "kb_document"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[str] = mapped_column(String, index=True)
    title: Mapped[str] = mapped_column(Text)
    source_uri: Mapped[str] = mapped_column(Text)
    version: Mapped[int] = mapped_column(Integer)
    acl_groups: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now())
    chunks: Mapped[list["KbChunk"]] = relationship(back_populates="document", cascade="all, delete-orphan")


class KbChunk(Base):
    __tablename__ = "kb_chunk"
    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("kb_document.id", ondelete="CASCADE"))
    tenant_id: Mapped[str] = mapped_column(String)
    acl_groups: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    chunk_index: Mapped[int] = mapped_column(Integer)
    heading_path: Mapped[str] = mapped_column(Text, default="")
    content: Mapped[str] = mapped_column(Text)
    content_hash: Mapped[str] = mapped_column(String(64))
    token_count: Mapped[int] = mapped_column(Integer)
    embedding_model: Mapped[str] = mapped_column(String)
    embedding: Mapped[list[float]] = mapped_column(Vector(EMBED_DIM))
    document: Mapped[KbDocument] = relationship(back_populates="chunks")

    __table_args__ = (
        Index("kb_chunk_embedding_hnsw", "embedding", postgresql_using="hnsw",
              postgresql_with={"m": 16, "ef_construction": 64},
              postgresql_ops={"embedding": "vector_cosine_ops"}),
    )
```

```python
# app/repositories/vector_search.py
from dataclasses import dataclass

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.kb_models import KbChunk, KbDocument


@dataclass(frozen=True)
class ChunkHit:
    chunk_id: int
    document_id: str
    title: str
    heading_path: str
    content: str
    similarity: float


async def search_chunks(session: AsyncSession, query_vec: list[float], tenant_id: str,
                        user_groups: list[str], k: int = 8, ef_search: int = 100) -> list[ChunkHit]:
    # Settings scoped to this transaction (safe with pooled connections).
    await session.execute(text("SET LOCAL hnsw.ef_search = :ef").bindparams(ef=ef_search))
    await session.execute(text("SET LOCAL hnsw.iterative_scan = relaxed_order"))

    distance = KbChunk.embedding.cosine_distance(query_vec)
    stmt = (
        select(KbChunk.id, KbChunk.document_id, KbDocument.title, KbChunk.heading_path,
               KbChunk.content, (1 - distance).label("similarity"))
        .join(KbDocument, KbDocument.id == KbChunk.document_id)
        .where(KbChunk.tenant_id == tenant_id)
        .where(KbChunk.acl_groups.overlap(user_groups))           # authorization filter IN the query
        .order_by(distance)                                       # ascending distance → uses HNSW
        .limit(k)
    )
    rows = (await session.execute(stmt)).all()
    return [ChunkHit(r.id, str(r.document_id), r.title, r.heading_path, r.content, float(r.similarity))
            for r in rows]
```

Notes. `SET LOCAL` with bind parameters isn't supported for all settings in all drivers. If `SET LOCAL hnsw.ef_search = $1` fails, validate the integer and format it into the statement (never format user input). Callers run `search_chunks` inside `async with session.begin():` so `SET LOCAL` applies. The ACL filter in SQL means users never receive chunks they can't see. Never retrieve first and filter later in Python or in the prompt.

#### Example 3 — Production-oriented: Chunk-size and top-k experiment harness

**Goal:** choose chunk size and k with evidence. You need a labelled set of (query → relevant document/section IDs), say 50–200 queries written by support staff or mined from tickets.

```python
# experiments/chunk_topk.py
import asyncio
import json
import statistics
from dataclasses import dataclass
from pathlib import Path

from app.rag.chunking import chunk_markdown          # structure-aware chunker (Unit 31)
from app.rag.embeddings import Embedder


@dataclass(frozen=True)
class LabeledQuery:
    query: str
    relevant_sections: frozenset[str]    # e.g. {"returns.md#refund-timeline"}


def recall_at_k(retrieved: list[str], relevant: frozenset[str], k: int) -> float:
    return len(set(retrieved[:k]) & relevant) / len(relevant)


def reciprocal_rank(retrieved: list[str], relevant: frozenset[str]) -> float:
    for i, sec in enumerate(retrieved, start=1):
        if sec in relevant:
            return 1.0 / i
    return 0.0


async def run(embedder: Embedder, docs: dict[str, str], queries: list[LabeledQuery],
              chunk_sizes: list[int], ks: list[int]) -> list[dict]:
    import numpy as np
    results = []
    for size in chunk_sizes:
        chunks = [c for name, md in docs.items() for c in chunk_markdown(name, md, max_tokens=size, overlap=size // 8)]
        matrix = np.asarray(await embedder.embed_documents([c.text_for_embedding for c in chunks]), dtype=np.float32)
        q_matrix = np.asarray([await embedder.embed_query(q.query) for q in queries], dtype=np.float32)
        scores = q_matrix @ matrix.T                                # exact search: ground truth for this config
        for k in ks:
            recalls, rrs = [], []
            for qi, q in enumerate(queries):
                order = np.argsort(-scores[qi])
                sections: list[str] = []
                for idx in order:                                   # dedupe by section, keep rank order
                    sec = chunks[idx].section_id
                    if sec not in sections:
                        sections.append(sec)
                    if len(sections) >= k:
                        break
                recalls.append(recall_at_k(sections, q.relevant_sections, k))
                rrs.append(reciprocal_rank(sections, q.relevant_sections))
            results.append({"chunk_tokens": size, "k": k, "n_chunks": len(chunks),
                            "recall_at_k": round(statistics.mean(recalls), 3),
                            "mrr": round(statistics.mean(rrs), 3)})
    return results


if __name__ == "__main__":
    from app.rag.embeddings import LocalSentenceTransformerEmbedder
    docs = {p.name: p.read_text() for p in Path("data/kb").glob("*.md")}
    queries = [LabeledQuery(q["query"], frozenset(q["relevant"]))
               for q in map(json.loads, Path("data/eval/retrieval.jsonl").read_text().splitlines())]
    table = asyncio.run(run(LocalSentenceTransformerEmbedder(), docs, queries,
                            chunk_sizes=[128, 256, 512, 1024], ks=[1, 3, 5, 10, 20]))
    for row in table:
        print(row)
```

**Reading the results.** Recall@k rises with k, so look for the knee where extra k adds little. Smaller chunks often improve precision and MRR, but they can lose context (answers spanning chunks). Larger chunks raise recall at small k but dilute similarity and cost more prompt tokens. Choose the configuration that meets a recall target (for example recall@5 ≥ 0.9) at the lowest prompt-token cost, then verify answer quality end-to-end in Unit 31.

**Then verify the ANN index against exact search.** Run the same queries through pgvector with HNSW at `ef_search` ∈ {40, 100, 200} and compare to the exact top-k. Report ANN recall and p95 latency, and pick the smallest `ef_search` meeting, say, ≥ 0.98 overlap.

### 7. Comparative Analysis

| Comparison | Key difference | When | Trap |
|---|---|---|---|
| Token vs embedding | Discrete text unit vs dense vector representation | Tokens for model input/billing; embeddings for similarity | "Embeddings are tokens" |
| Embedding model vs generative model | Text → vector vs text → text | Retrieval vs generation | Using a chat model to "embed" via prompts |
| Cosine vs dot vs L2 | Angle vs angle×magnitude vs distance | Use model's metric; equivalent ranking if normalized | Operator/opclass mismatch → no index use |
| Exact vs ANN | Perfect recall O(N) vs approximate, fast | Exact for small/filtered sets; ANN at scale | Not measuring ANN recall |
| HNSW vs IVFFlat | Graph, incremental, memory-heavy vs clusters, needs training data | HNSW default | IVFFlat built on empty table |
| pgvector vs dedicated vector DB | One DB with SQL/ACL/transactions vs specialized scale/features | pgvector until scale/features demand otherwise | Adding a vector DB on day one |
| Small vs large chunks | Precision vs context | Measure recall@k and answer quality | Defaults copied from a tutorial |
| Vector vs lexical search | Meaning vs exact terms | Hybrid for IDs, codes, names | Vector-only for SKU lookups |
| Similarity threshold vs top-k | Absolute cutoff vs fixed count | Thresholds only after calibration per model | Universal "0.8 threshold" |

### 8. Failure Modes and Debugging

**Failure 1 — Query returns fewer than k rows.**

- CAUSE: ANN + restrictive filter (overfiltering).
- INVESTIGATE: run without the filter, count matches of the filter alone, `EXPLAIN ANALYZE`.
- FIX: iterative scans (pgvector ≥ 0.8), higher `ef_search`, partial indexes/partitioning, exact search on small filtered sets.

**Failure 2 — Index not used; queries take seconds.**

- CAUSE: `ORDER BY similarity DESC` instead of `ORDER BY embedding <=> q`; opclass mismatch (`vector_l2_ops` index, `<=>` query); casting the parameter wrongly; missing `LIMIT`.
- INVESTIGATE: `EXPLAIN (ANALYZE, BUFFERS)` shows `Seq Scan` + `Sort`.
- FIX: order by the operator, match the opclass, keep LIMIT.

**Failure 3 — Relevant document never retrieved.**

- CAUSE: chunk lacks context (no title), relevant info split across chunks, exact identifier query, wrong query/document mode for the model, truncated chunk beyond the model's max tokens.
- INVESTIGATE: find the target chunk, compute its similarity to the query directly, inspect chunk text and token count.
- FIX: contextual prefixes, chunking changes, hybrid search, correct `input_type`, size limits.

**Failure 4 — Results got worse after "upgrading" the embedding model.**

- CAUSE: new query vectors compared against old document vectors (mixed models).
- FIX: never mix models in one index. Re-embed fully and switch atomically (Unit 32 migrations). Store `embedding_model` per row and filter on it.

**Failure 5 — Ingestion is slow and expensive.**

- CAUSE: one API call per chunk, no batching, re-embedding unchanged chunks.
- FIX: batch requests, bounded concurrency, content-hash cache (skip unchanged), provider batch APIs.

**Failure 6 — HNSW build takes hours and memory spikes.**

- FIX: increase `maintenance_work_mem`, use parallel builds (`max_parallel_maintenance_workers`), build after bulk loading, consider `halfvec` or smaller dimensions.

### 9. Guided Practice

#### Level 1 — Concept Reinforcement

**1.1** Prove (algebraically) that for unit vectors, ranking by L2 distance equals ranking by cosine similarity.

**1.2** For each query, predict whether vector or lexical search does better: "refund timeline", "error E-4012", "order 88123", "can I send it back if I changed my mind?", "Zebra-X200 battery".

#### Level 2 — Implementation

**2.1 Cosine utilities.**
- Objective: implement `cosine`, `normalize`, and a batched `top_k(query, matrix, k)` with NumPy, using `argpartition` for O(N) selection.
- Tests: Hypothesis property tests (cosine ∈ [−1, 1]; cosine(a, a) = 1 for nonzero a; top_k matches a full sort).
- Hints: `np.argpartition(-scores, k)[:k]` then sort those k.

**2.2 pgvector repository.** Implement the schema with Alembic, `search_chunks` with tenant/ACL filters, and an integration test with Testcontainers (`pgvector/pgvector:0.8.1-pg17`) proving that (a) another tenant's chunks are never returned, and (b) the HNSW index is used (`EXPLAIN` contains `kb_chunk_embedding_hnsw`).
*Hints:* insert synthetic vectors (random normalized). For `EXPLAIN`, set `enable_seqscan = off` in a test transaction only to confirm usability, then test the realistic plan separately.

#### Level 3 — Integration

**3.1 Chunk/top-k experiment.** Build a 60-query labelled set over your KB (or a public docs set), run Example 3 for 4 chunk sizes × 5 k values with two embedding models, then report recall@k, MRR, chunk count, average tokens per prompt, and your recommendation.

#### Level 4 — Debugging / Production Scenario

**4.1** Diagnose:

```python
rows = session.execute(text(f"""
    SELECT content, 1 - (embedding <=> '{query_vec}') AS score
    FROM kb_chunk ORDER BY score DESC LIMIT 5""")).all()
results = [r for r in rows if r.tenant_id == current_tenant and r.score > 0.8]
```

*Hints:* string-formatted SQL; ordering by expression (no index); tenant filter after retrieval (leak and fewer results); `tenant_id` not selected; arbitrary threshold; LIMIT applied before filtering.

**4.2** After adding 2M chunks, p95 latency jumped from 30 ms to 900 ms. List hypotheses and the measurements that would distinguish them.
*Hints:* index fits in memory? `ef_search` changed? Seq scan due to stats? Overfiltering with iterative scans hitting `max_scan_tuples`?

### 10. Independent Implementation Project — SupportDesk Vector Search

**Goal.** A tested embedding + vector search module for SupportDesk's knowledge base, with an experiment report justifying chunk size, model and k.

**Requirements.**

1. `Embedder` Protocol with local (sentence-transformers) and hosted (Bedrock Titan or a hosted API) implementations; batching, bounded concurrency, retries, normalization.
2. PostgreSQL schema with pgvector, HNSW index, tenant and ACL metadata, embedding model per row; Alembic migrations.
3. `search_chunks` with mandatory tenant + ACL filters, `SET LOCAL` tuning, iterative scans.
4. CLI: `embed-kb` (chunk + embed + upsert with content-hash skip) and `search "query" --tenant t --groups g1,g2`.
5. Experiment harness and a report (`docs/retrieval-experiments.md`) with recall@k, MRR, ANN-vs-exact overlap, latency, and storage size.

**Technical requirements.** Python 3.13, NumPy, sentence-transformers (pinned), boto3 (optional), SQLAlchemy 2.0 async + psycopg 3, `pgvector` Python package, Alembic, pytest, Hypothesis, Testcontainers.

**Suggested structure.**

```
app/rag/ embeddings.py  bedrock_embedder.py  chunking.py  similarity.py
app/repositories/ kb_models.py  vector_search.py  kb_writer.py
migrations/versions/0003_kb_vectors.py
cli/ embed_kb.py  search.py
experiments/ chunk_topk.py  ann_vs_exact.py
data/eval/retrieval.jsonl
tests/unit/ test_similarity.py  test_chunking.py
tests/integration/ test_vector_search.py  test_tenant_isolation.py  test_index_usage.py
docs/retrieval-experiments.md
```

**Milestones.** (1) Similarity utilities + tests. (2) Embedder implementations. (3) Schema + migrations. (4) Writer with content-hash skip. (5) Search with filters. (6) Experiments. (7) Report.

**Testing requirements.** Property tests for similarity. Tenant/ACL isolation tests (critical). Index usage test. Idempotent re-embedding test (running `embed-kb` twice creates no duplicates and makes no new embedding calls for unchanged chunks).

**Definition of done.** Recall@5 meets the target you set (justified) on your labelled set. ANN overlap with exact ≥ 0.98 at the chosen `ef_search`. p95 search latency documented. Zero cross-tenant results in tests.

**Optional extensions.** `halfvec` storage comparison. Matryoshka dimension truncation experiment. Partitioning by tenant. A sparse vector (`sparsevec`) experiment.

### 11. Testing Strategy

- **Math/unit:** Hypothesis properties for cosine/normalization/top-k.
- **Chunking:** golden-file tests on representative documents (tables, lists, long sections, code blocks), asserting chunk boundaries, headings and token limits.
- **Integration (Testcontainers pgvector):** filters, isolation, index usage, iterative scan behavior, migrations.
- **Retrieval evaluation:** labelled queries → recall@k, MRR, nDCG. Tracked over time (regression testing in Unit 32).
- **Performance:** latency at realistic data sizes with `EXPLAIN ANALYZE`, and index build time.

```python
# tests/integration/test_tenant_isolation.py
import numpy as np
import pytest

from app.repositories.vector_search import search_chunks
from tests.integration.factories import insert_chunk


@pytest.mark.anyio
async def test_other_tenant_chunks_never_returned(session) -> None:
    rng = np.random.default_rng(0)
    target = rng.normal(size=1024); target /= np.linalg.norm(target)
    async with session.begin():
        await insert_chunk(session, tenant="A", groups=["support"], vec=target.tolist(), content="A policy")
        await insert_chunk(session, tenant="B", groups=["support"], vec=target.tolist(), content="B secret")
    async with session.begin():
        hits = await search_chunks(session, target.tolist(), tenant_id="A", user_groups=["support"], k=10)
    assert [h.content for h in hits] == ["A policy"]
```

### 12. Engineering Scenarios

**Scenario 1 — "Use the best embedding model" (FDE).** The customer's CTO read a leaderboard and wants the top model. *Questions:* What languages and content types? Data governance (can text leave their AWS account)? Volume and budget? *Reasoning:* Shortlist 3 models (one Bedrock-hosted for governance) and evaluate on 100 of their real queries with recall@5 and cost per million chunks. Present a table and choose by quality/cost/governance. Evidence: experiment report on their data.

**Scenario 2 — pgvector or a vector database?** 5M chunks today, 50M projected, multi-tenant, 50 QPS. *Reasoning:* pgvector with HNSW, halfvec and partitioning by tenant likely suffices. Measure memory and latency. Define triggers for migration (index > memory, p95 above SLO, operational limits). Keep a retrieval interface so the switch is contained.

**Scenario 3 — Identifiers in queries.** Agents search "INC-20391". Vector search returns unrelated incidents. *Reasoning:* Detect identifier patterns and route to exact lookup or lexical search, i.e. hybrid retrieval (Unit 32).

**Scenario 4 — Multilingual content.** *Reasoning:* Multilingual embedding model, language metadata, an evaluation per language, and query-language detection for filtering or boosting.

### 13. Interview Preparation

#### Quick Questions

**Q: Embedding vs token?**
*Strong answer:* Tokens are the discrete text units models consume and bill by. An embedding is a dense vector representing a text's meaning, produced by an embedding model and used for similarity.

**Q: What does cosine similarity measure?**
*Strong answer:* The angle between vectors, ignoring magnitude. For normalized vectors it equals the dot product and gives the same ranking as Euclidean distance.

**Q: Why chunk documents?**
*Strong answer:* Model input limits, and specificity: one vector per long document averages many topics. Chunks are retrievable, citable units.

#### Intermediate Questions

**Q: How do you choose chunk size and top-k?**
*Strong answer:* Experimentally: build a labelled query set, measure recall@k/MRR across chunk sizes and k (and end-to-end answer quality), and choose the cheapest configuration meeting the recall target. Structure-aware chunks with titles and some overlap are the usual starting point.

**Q: What metadata do you store with chunks, and why?**
*Strong answer:* Tenant, ACL groups, document ID/version, section path, source URI, language, timestamps, content hash and embedding model. Needed for authorization filters, citations, incremental updates, dedupe and migrations.

**Q: When would you choose a dedicated vector database over pgvector?**
*Strong answer:* At scales or QPS where PostgreSQL's memory/latency limits are hit, or when you need features pgvector lacks or a managed vector service. Otherwise pgvector wins on simplicity, transactions and SQL filtering.

#### Advanced Questions

**Q: Your filtered vector query returns 3 results instead of 10. Why, and how do you fix it?**
*Strong answer:* ANN overfiltering: the index produces nearest candidates, and the filter discards most of them. Fix with iterative index scans (pgvector 0.8), a higher `ef_search`, partial indexes/partitioning, or exact search on small filtered sets. Verify with `EXPLAIN ANALYZE`.

**Q: How does HNSW work, and what do its parameters do?**
*Strong answer:* A multi-layer proximity graph with greedy search from coarse to fine layers. `m` sets connectivity (recall/memory), `ef_construction` sets build quality, and `ef_search` sets query breadth (recall vs latency). Measure recall against exact search.

#### Coding Questions

1. Implement top-k cosine search over a NumPy matrix in O(N) selection.
2. Write a pgvector SQL query with tenant and ACL filters that uses the HNSW index.
3. Implement recall@k and MRR.

#### Scenario Questions

**Q: Search quality dropped after a deploy, and nothing in the code changed except the embedding model version.**
*Strong answer:* Mixed vector spaces: old document vectors and new query vectors. Roll back the query model, re-embed all documents into a new column/table, validate with retrieval evals, switch atomically, and add a guard (`embedding_model` filter and a startup check).

### 14. Explain-It-at-Three-Levels

**Concept: Vector search**

- *30 seconds:* We embed chunks into vectors, store them in pgvector, embed the query, and return the k nearest chunks by cosine distance, filtered by tenant and permissions in the same SQL query.
- *2 minutes:* Embedding models, normalization and metrics, chunking with metadata, HNSW vs exact, filtered search and evaluation with recall@k.
- *Deep:* HNSW internals and parameters, the planner and operator/opclass matching, iterative scans, memory sizing, quantization, migration between models, and when to move to a dedicated store.

**Concept: Chunking**

- *30 seconds:* Split documents into self-contained, titled pieces small enough to be specific and large enough to carry context, and measure the choice with recall@k.
- *2 minutes:* Strategies (fixed, structure-aware, semantic, hierarchical), overlap, tables, metadata.
- *Deep:* Interaction with embedding limits, reranking and prompt cost, plus experiments and regression tests.

### 15. Knowledge Check

1. Why are vectors from different embedding models not comparable?
2. When do cosine, dot product and L2 produce the same ranking?
3. What does `hnsw.ef_search` trade off?
4. Why prefix chunks with document title and heading path?
5. Why must authorization filters be in the SQL query?
6. *Code reading:* Why does `search_chunks` use `SET LOCAL` rather than `SET`?
7. *Code reading:* Why `.order_by(distance)` rather than ordering by similarity descending?
8. *Code reading:* In the experiment harness, why dedupe by section before computing recall?
9. *Debugging:* `EXPLAIN` shows a sequential scan and sort for your vector query. Two likely causes?
10. *Debugging:* Recall dropped only for one tenant with few documents. Why?
11. *Design:* Exact search or HNSW for a tenant with 20k chunks?
12. *Design:* What triggers would make you move from pgvector to a dedicated vector DB?

#### Knowledge Check Answers

1. Each model defines its own learned space. Coordinates and distances only have meaning within that space.
2. When vectors are unit-normalized.
3. Recall vs latency: a wider candidate list finds more true neighbors but costs more time.
4. To make each chunk self-describing, improving embedding relevance and giving the generator context for answering and citing.
5. Otherwise unauthorized data is retrieved (and may leak through prompts or logs), and post-filtering reduces results unpredictably.
6. So the setting applies only within the current transaction and doesn't leak to other requests sharing the pooled connection.
7. The HNSW index supports `ORDER BY <distance operator> LIMIT` ascending. Ordering by a derived expression prevents index use.
8. Multiple chunks from the same section would otherwise inflate or distort recall. Relevance is labelled at the section level.
9. Ordering by an expression instead of the operator; opclass/operator mismatch (also missing LIMIT or parameter type mismatch).
10. Overfiltering with ANN: the tenant's few chunks are rarely among global nearest candidates. Fix with iterative scans, partial indexes, or exact search for small tenants.
11. Exact search over the tenant's filtered rows is likely fast enough (tens of ms) with perfect recall. Measure, and possibly rely on the B-tree tenant filter plan.
12. Index size beyond memory with unacceptable latency, QPS beyond what replicas handle, operational burden of very large index builds, or required features (multi-vector, native hybrid at scale, managed sharding).

### 16. Common Interview Traps

- **"Similarity = relevance."** Similar isn't necessarily answering. Measure relevance.
- **"0.8 cosine means 80% relevant."** Scores aren't calibrated across models.
- **"Bigger embeddings are always better."** Cost, storage and latency matter, so measure on your data.
- **"Filter results after retrieval."** That's a security leak and gives unpredictable counts.
- **"Vector DB required for RAG."** pgvector is often enough.
- **"Upgrade the embedding model in place."** Mixed spaces break retrieval.
- **"Embeddings handle IDs and codes well."** Use lexical/hybrid search for exact terms.

### 17. Cheat Sheet

- **Similarity:** `cos = a·b/(‖a‖‖b‖)`; normalized → cos = dot; `‖a−b‖² = 2 − 2cos`.
- **pgvector:** `vector(n)`, `halfvec(n)`, `sparsevec`, `bit`; `<=>` cosine distance, `<#>` neg inner product, `<->` L2, `<+>` L1.
- **HNSW:** `CREATE INDEX … USING hnsw (embedding vector_cosine_ops) WITH (m=16, ef_construction=64)`; `SET LOCAL hnsw.ef_search = 100`; `SET LOCAL hnsw.iterative_scan = relaxed_order` (≥ 0.8).
- **IVFFlat:** `USING ivfflat (embedding vector_cosine_ops) WITH (lists = rows/1000)`; `SET ivfflat.probes = 10`; build after loading data.
- **Query shape:** `WHERE tenant_id = $t AND acl_groups && $g ORDER BY embedding <=> $q LIMIT k`.
- **SQLAlchemy:** `from pgvector.sqlalchemy import Vector`; `Mapped[list[float]] = mapped_column(Vector(1024))`; `col.cosine_distance(vec)`.
- **Chunking:** structure-aware, ~300–500 tokens, 10–15% overlap, title + heading prefix, tables intact, metadata (tenant, ACL, doc/version, section, hash, model).
- **Metrics:** recall@k, precision@k, MRR, nDCG; ANN overlap vs exact; p95 latency.

### 18. Completion Checklist

- [ ] I can explain embeddings, vector spaces and the limits of similarity.
- [ ] I can compute and choose similarity metrics and matching pgvector operators/opclasses.
- [ ] I can design chunking and metadata for secure, citable retrieval.
- [ ] I can implement embedders, pgvector storage and filtered top-k search with SQLAlchemy 2.x.
- [ ] I can tune and verify HNSW (ef_search, iterative scans) against exact search.
- [ ] I can run chunk-size/top-k experiments with recall@k and MRR.
- [ ] I can debug overfiltering, index non-use, missed documents and mixed-model indexes.
- [ ] I can identify when not to add a dedicated vector database.

### 19. Further Research

**Essential**

- pgvector README — <https://github.com/pgvector/pgvector>. Types, operators, HNSW/IVFFlat, filtering, iterative scans, tuning.
- pgvector-python — <https://github.com/pgvector/pgvector-python>. SQLAlchemy/psycopg integration.
- Sentence Transformers docs — <https://www.sbert.net/>. Local embedding models, normalization, asymmetric search.
- Anthropic embeddings guidance — <https://docs.claude.com/en/docs/build-with-claude/embeddings>. Provider options (Voyage AI) and usage.
- Amazon Titan Text Embeddings V2 — <https://docs.aws.amazon.com/bedrock/latest/userguide/titan-embedding-models.html>.

**Deeper Study**

- Malkov & Yashunin, "Efficient and robust approximate nearest neighbor search using HNSW graphs" — <https://arxiv.org/abs/1603.09320>.
- MTEB leaderboard — <https://huggingface.co/spaces/mteb/leaderboard>. Benchmarks (use as a shortlist, not a decision).
- Kusupati et al., "Matryoshka Representation Learning" — <https://arxiv.org/abs/2205.13147>. Truncatable embeddings.

**Practice**

- BEIR benchmark datasets — <https://github.com/beir-cellar/beir>. Practice retrieval evaluation on public data.
- Your own support tickets: mine 100 real questions and label relevant articles. This is the most valuable dataset you'll build.

### Unit Completion Standard

Before moving on, you must be able to:

- **Explain** embedding models and vector spaces, cosine/dot/L2 and their relationships, embeddings vs tokens, chunking and metadata, top-k ANN search, pgvector's types/operators/indexes, and hybrid search/reranking concepts.
- **Implement** provider-neutral embedders, a pgvector schema with HNSW and metadata, and tenant/ACL-filtered top-k search with SQLAlchemy 2.x.
- **Test** similarity math with properties, chunking with golden files, isolation and index usage with Testcontainers, and retrieval quality with recall@k/MRR experiments.
- **Debug** overfiltering, sequential scans, missed relevant chunks, mixed embedding models and slow ingestion.
- **Defend** in an interview your embedding model, metric, chunking, k and storage choices with experimental evidence.
