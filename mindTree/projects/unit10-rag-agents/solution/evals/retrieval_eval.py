"""Offline retrieval eval: recall@k, MRR, abstention, leakage.

Run:  python -m evals.retrieval_eval --k 3 --min-recall 0.85
Exit code 1 when a metric is below its threshold, so CI can gate
changes to chunking, ranking or the embedding model.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path

from app.config import ROOT
from app.rag.answer import should_abstain
from app.rag.documents import Audience, chunk_all, load_kb
from app.rag.embeddings import HashingEmbedder
from app.rag.retriever import HybridRetriever
from app.roles import Role

CASES = ROOT / "data" / "eval" / "retrieval_cases.json"


@dataclass(frozen=True)
class Report:
    recall_at_k: float  # share of answerable cases with a hit in top-k
    mrr: float  # mean of 1 / rank of the first relevant document
    abstain_accuracy: float  # unanswerable cases correctly refused
    leaks: int  # internal chunks returned to customers (must be 0)
    misses: list[str]


def evaluate(
    cases: list[dict[str, object]],
    retriever: HybridRetriever,
    k: int,
    min_relevance: float,
) -> Report:
    hits_at_k, rr_sum, answerable = 0, 0.0, 0
    abstain_ok, unanswerable, leaks = 0, 0, 0
    misses: list[str] = []
    for case in cases:
        question = str(case["q"])
        role = Role(str(case["role"]))
        raw_expected = case["expected"]
        assert isinstance(raw_expected, list)
        expected = {str(e) for e in raw_expected}
        hits = retriever.search(question, role, k)
        if role is Role.CUSTOMER:
            leaks += sum(
                h.chunk.audience is Audience.INTERNAL for h in hits
            )
        if not expected:
            unanswerable += 1
            abstain_ok += should_abstain(hits, min_relevance)
            continue
        answerable += 1
        ranks = [
            i
            for i, h in enumerate(hits, start=1)
            if h.chunk.doc_id in expected
        ]
        if ranks:
            hits_at_k += 1
            rr_sum += 1 / ranks[0]
        else:
            misses.append(question)
    return Report(
        recall_at_k=hits_at_k / answerable if answerable else 0.0,
        mrr=rr_sum / answerable if answerable else 0.0,
        abstain_accuracy=(
            abstain_ok / unanswerable if unanswerable else 1.0
        ),
        leaks=leaks,
        misses=misses,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", type=Path, default=CASES)
    parser.add_argument("--kb", type=Path, default=ROOT / "data" / "kb")
    parser.add_argument("--k", type=int, default=3)
    parser.add_argument("--min-recall", type=float, default=0.85)
    parser.add_argument("--min-mrr", type=float, default=0.7)
    parser.add_argument("--min-relevance", type=float, default=0.5)
    args = parser.parse_args(argv)

    cases = json.loads(args.cases.read_text(encoding="utf-8"))
    retriever = HybridRetriever(
        chunk_all(load_kb(args.kb)), HashingEmbedder()
    )
    report = evaluate(cases, retriever, args.k, args.min_relevance)
    print(f"cases={len(cases)} k={args.k}")
    print(
        f"recall@{args.k}={report.recall_at_k:.2f} "
        f"mrr={report.mrr:.2f} "
        f"abstain_acc={report.abstain_accuracy:.2f} "
        f"leaks={report.leaks}"
    )
    for question in report.misses:
        print(f"  MISS: {question}")
    failed = (
        report.recall_at_k < args.min_recall
        or report.mrr < args.min_mrr
        or report.abstain_accuracy < 1.0
        or report.leaks > 0
    )
    print("FAIL" if failed else "PASS")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
