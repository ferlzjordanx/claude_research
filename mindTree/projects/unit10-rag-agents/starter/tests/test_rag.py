import pytest

from app.rag.answer import (
    ABSTAIN_TEXT,
    check_citations,
    compose_answer,
)
from app.rag.bm25 import BM25Index
from app.rag.documents import (
    Audience,
    Chunk,
    Document,
    chunk_document,
    parse_document,
)
from app.rag.embeddings import HashingEmbedder, cosine
from app.rag.retriever import HybridRetriever, rrf
from app.roles import Role

INTERNAL_QUESTIONS = [
    "goodwill store credit for a late delivery",
    "fraud flag risk team",
    "refunds outside the 30 day window supervisor",
    "escalation response targets",
]


def test_front_matter_is_parsed() -> None:
    raw = "---\nid: x\ntitle: X\naudience: public\n---\n# X\nBody."
    doc = parse_document(raw, "fallback")
    assert (doc.doc_id, doc.title, doc.audience) == (
        "x",
        "X",
        Audience.PUBLIC,
    )
    assert doc.body.startswith("# X")


def test_missing_audience_fails_closed() -> None:
    doc = parse_document("# Untagged\nSecret text.", "untagged")
    assert doc.audience is Audience.INTERNAL


def test_chunks_follow_headings(chunks: list[Chunk]) -> None:
    refund = [c for c in chunks if c.doc_id == "refund-policy"]
    assert [c.heading for c in refund] == [
        "Eligibility",
        "How refunds are paid",
        "Partial refunds",
        "Shipping costs",
    ]
    assert refund[0].chunk_id == "refund-policy#0"


def test_long_section_is_windowed_with_overlap() -> None:
    words = " ".join(f"word{i}" for i in range(200))
    doc = Document("long", "Long", Audience.PUBLIC, f"# H\n{words}")
    pieces = chunk_document(doc, max_chars=200, overlap=40)
    assert len(pieces) > 1
    assert all(len(p.text) <= 200 for p in pieces)
    first, second = pieces[0].text.split(), pieces[1].text.split()
    assert first[-1] in second  # the boundary is repeated
    assert {p.heading for p in pieces} == {"H"}


def test_bm25_ranks_the_matching_chunk_first(
    chunks: list[Chunk],
) -> None:
    index = BM25Index(chunks)
    top, score = index.search("two-factor authentication", 3)[0]
    assert top.doc_id == "account-security" and score > 0


def test_bm25_prefilter_excludes_chunks(chunks: list[Chunk]) -> None:
    index = BM25Index(chunks)
    allowed = {c.chunk_id for c in chunks if c.doc_id != "warranty"}
    results = index.search("warranty claim", 5, allowed)
    assert all(c.doc_id != "warranty" for c, _ in results)


def test_hashing_embedding_is_deterministic_and_normalized() -> None:
    a = HashingEmbedder().embed(["Refund within 30 days"])[0]
    b = HashingEmbedder().embed(["Refund within 30 days"])[0]
    assert a == b
    assert cosine(a, a) == pytest.approx(1.0)


def test_embedding_similarity_prefers_shared_words() -> None:
    e = HashingEmbedder()
    q, near, far = e.embed(
        ["refund to card", "refunds go back to the card", "ship to EU"]
    )
    assert cosine(q, near) > cosine(q, far)


def test_rrf_rewards_agreement_between_rankers() -> None:
    fused = rrf([["a", "b", "c"], ["b", "c", "a"]])
    assert [item for item, _ in fused][0] == "b"
    score_b = 1 / 61 + 1 / 62
    assert dict(fused)["b"] == pytest.approx(score_b)


def test_rrf_includes_items_from_one_list_and_breaks_ties() -> None:
    fused = rrf([["x"], ["y"]])
    assert fused == [("x", 1 / 61), ("y", 1 / 61)]


@pytest.mark.parametrize("question", INTERNAL_QUESTIONS)
def test_customer_never_retrieves_internal_docs(
    retriever: HybridRetriever, question: str
) -> None:
    hits = retriever.search(question, Role.CUSTOMER, k=8)
    assert all(h.chunk.audience is Audience.PUBLIC for h in hits)


def test_agent_can_retrieve_internal_docs(
    retriever: HybridRetriever,
) -> None:
    hits = retriever.search(INTERNAL_QUESTIONS[0], Role.AGENT, k=3)
    assert hits[0].chunk.doc_id == "refund-exceptions-internal"


def test_abstains_when_nothing_relevant(
    retriever: HybridRetriever,
) -> None:
    question = "What is the capital of France?"
    hits = retriever.search(question, Role.CUSTOMER)
    answer = compose_answer(question, hits, min_relevance=0.5)
    assert answer.abstained and answer.text == ABSTAIN_TEXT
    assert answer.citations == []


def test_answer_cites_retrieved_chunks(
    retriever: HybridRetriever,
) -> None:
    question = "Where do refunds go?"
    hits = retriever.search(question, Role.CUSTOMER)
    answer = compose_answer(question, hits, min_relevance=0.5)
    assert not answer.abstained
    assert answer.citations == ["refund-policy#1"]
    assert "original payment method" in answer.text
    ids = {h.chunk.chunk_id for h in hits}
    assert check_citations(answer.text, ids) == []


def test_check_citations_flags_missing_and_invented() -> None:
    assert check_citations("No sources here.", {"a#0"}) == [
        "answer has no citations"
    ]
    problems = check_citations("Claim [made-up#9].", {"a#0"})
    assert problems and "made-up#9" in problems[0]
