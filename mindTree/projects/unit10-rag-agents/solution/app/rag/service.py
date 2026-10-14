"""/ask orchestration: retrieve -> generate -> verify citations."""

from __future__ import annotations

from dataclasses import dataclass

from app.agent.types import ToolLLM, UserMessage
from app.rag.answer import (
    ABSTAIN_TEXT,
    Answer,
    build_grounded_prompt,
    check_citations,
    compose_answer,
    extract_citations,
    should_abstain,
)
from app.rag.retriever import Hit, HybridRetriever
from app.roles import Role

GENERATOR_SYSTEM = "You answer support questions from sources only."


@dataclass(frozen=True)
class AskResult:
    answer: Answer
    hits: list[Hit]
    generator: str  # "extractive" or the LLM adapter name
    fallback_reason: str = ""


class AskService:
    def __init__(
        self,
        retriever: HybridRetriever,
        min_relevance: float,
        llm: ToolLLM | None = None,
    ) -> None:
        self.retriever = retriever
        self.min_relevance = min_relevance
        self.llm = llm  # None: deterministic extractive answers

    def ask(self, question: str, role: Role, k: int = 4) -> AskResult:
        hits = self.retriever.search(question, role, k)
        extractive = compose_answer(question, hits, self.min_relevance)
        if self.llm is None or should_abstain(hits, self.min_relevance):
            # Abstain BEFORE calling a model: no sources, no answer.
            return AskResult(extractive, hits, "extractive")
        response = self.llm.complete(
            GENERATOR_SYSTEM,
            [UserMessage(build_grounded_prompt(question, hits))],
            [],
        )
        text = response.text.strip()
        if text == ABSTAIN_TEXT:
            return AskResult(
                Answer(text, abstained=True), hits, self.llm.name
            )
        problems = check_citations(text, {h.chunk.chunk_id for h in hits})
        if problems:
            # Probabilistic output failed a deterministic check.
            return AskResult(
                extractive, hits, "extractive", "; ".join(problems)
            )
        answer = Answer(text, False, extract_citations(text))
        return AskResult(answer, hits, self.llm.name)
