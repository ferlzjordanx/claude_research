"""Application factory: wiring only.

Run with: uvicorn app.main:create_app --factory --reload
"""

import logging
from typing import Annotated, Literal

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from app.agent.anthropic_llm import AnthropicToolLLM
from app.agent.fake import FakeToolLLM
from app.agent.loop import Agent, AgentLimits, new_context_id
from app.agent.openai_llm import OpenAIToolLLM
from app.agent.types import ToolLLM
from app.config import Settings, get_settings
from app.rag.documents import chunk_all, load_kb
from app.rag.embeddings import HashingEmbedder
from app.rag.retriever import HybridRetriever
from app.rag.service import AskService
from app.roles import Principal, Role
from app.tools.registry import ToolContext, ToolError
from app.tools.support import SupportDesk, build_registry

log = logging.getLogger("assistant")
DEV_TOKENS = (
    "t-alice:alice:customer,t-bob:bob:customer,"
    "t-sam:sam:agent,t-pat:pat:agent"
)
ERROR_STATUS = {"not_found": 404, "forbidden": 403}


class AskIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question: str = Field(min_length=3, max_length=500)
    k: int = Field(default=4, ge=1, le=8)


class Source(BaseModel):
    id: str
    title: str
    relevance: float
    bm25_rank: int | None
    vector_rank: int | None


class AskOut(BaseModel):
    answer: str
    abstained: bool
    citations: list[str]
    sources: list[Source]
    generator: str
    fallback_reason: str


class AgentIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    message: str = Field(min_length=3, max_length=2000)


class StepOut(BaseModel):
    turn: int
    kind: str
    name: str
    detail: dict[str, object]
    elapsed_ms: float


class AgentOut(BaseModel):
    run_id: str
    stop_reason: str
    answer: str | None
    pending_approvals: list[str]
    citation_problems: list[str]
    tool_calls: int
    tokens: int
    steps: list[StepOut]


class DecisionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    decision: Literal["approve", "reject"]


class ApprovalOut(BaseModel):
    approval_id: str
    status: str
    order_id: str
    amount_cents: int
    requested_by: str
    decided_by: str | None
    refund_id: str | None


def parse_tokens(spec: str) -> dict[str, Principal]:
    tokens = {}
    for entry in filter(None, (e.strip() for e in spec.split(","))):
        token, user, role = entry.split(":")
        tokens[token] = Principal(user, Role(role))
    return tokens


def build_llm(settings: Settings) -> ToolLLM:
    if settings.provider == "anthropic":
        return AnthropicToolLLM.from_env(
            settings.anthropic_model,
            settings.max_output_tokens,
            settings.llm_timeout_s,
        )
    if settings.provider == "openai":
        return OpenAIToolLLM.from_env(
            settings.openai_model,
            settings.max_output_tokens,
            settings.llm_timeout_s,
        )
    return FakeToolLLM()


def create_app(
    settings: Settings | None = None, llm: ToolLLM | None = None
) -> FastAPI:
    logging.basicConfig(level=logging.INFO)
    settings = settings or get_settings()
    docs = load_kb(settings.kb_dir)
    chunks = chunk_all(
        docs, settings.chunk_max_chars, settings.chunk_overlap
    )
    retriever = HybridRetriever(chunks, HashingEmbedder())
    desk = SupportDesk(
        approval_threshold_cents=settings.approval_threshold_cents,
        max_refund_cents=settings.max_refund_cents,
    )
    registry = build_registry(retriever, desk, settings.min_relevance)
    llm = llm or build_llm(settings)
    ask_llm = None if isinstance(llm, FakeToolLLM) else llm
    asker = AskService(retriever, settings.min_relevance, ask_llm)
    limits = AgentLimits(
        max_turns=settings.agent_max_turns,
        max_tool_calls=settings.agent_max_tool_calls,
        timeout_s=settings.agent_timeout_s,
        max_total_tokens=settings.agent_max_tokens,
    )
    spec = settings.demo_tokens or (
        DEV_TOKENS if settings.env != "prod" else ""
    )
    tokens = parse_tokens(spec)

    def principal(
        authorization: Annotated[str, Header()] = "",
    ) -> Principal:
        """Auth STUB: a static token table. Production verifies a
        JWT/OIDC token exactly as in Units 2 and 5."""
        scheme, _, token = authorization.partition(" ")
        who = tokens.get(token) if scheme.lower() == "bearer" else None
        if who is None:
            raise HTTPException(401, "Missing or unknown token.")
        return who

    Caller = Annotated[Principal, Depends(principal)]

    app = FastAPI(
        title="Support Assistant",
        version="1.0.0",
        description="Unit 10: RAG, tool calling and a bounded agent.",
    )
    app.dependency_overrides[get_settings] = lambda: settings
    app.state.desk = desk
    app.state.retriever = retriever

    @app.exception_handler(ToolError)
    async def tool_error(_: Request, exc: ToolError) -> JSONResponse:
        return JSONResponse(
            {"title": exc.code, "detail": exc.message},
            status_code=ERROR_STATUS.get(exc.code, 409),
        )

    @app.get("/health", tags=["ops"])
    def health() -> dict[str, object]:
        return {"status": "ok", "chunks": len(chunks), "llm": llm.name}

    @app.post("/ask", tags=["rag"])
    def ask(body: AskIn, who: Caller) -> AskOut:
        result = asker.ask(body.question, who.role, body.k)
        return AskOut(
            answer=result.answer.text,
            abstained=result.answer.abstained,
            citations=result.answer.citations,
            sources=[
                Source(
                    id=h.chunk.chunk_id,
                    title=h.chunk.title,
                    relevance=round(h.relevance, 4),
                    bm25_rank=h.bm25_rank,
                    vector_rank=h.vector_rank,
                )
                for h in result.hits
            ],
            generator=result.generator,
            fallback_reason=result.fallback_reason,
        )

    @app.post("/agent/run", tags=["agent"])
    def run_agent(body: AgentIn, who: Caller) -> AgentOut:
        ctx = ToolContext(principal=who, run_id=new_context_id())
        result = Agent(llm, registry, limits).run(body.message, ctx)
        log.info(
            "agent run=%s user=%s stop=%s tools=%d",
            result.run_id,
            who.user_id,
            result.stop_reason,
            result.tool_calls,
        )
        return AgentOut(
            run_id=result.run_id,
            stop_reason=result.stop_reason.value,
            answer=result.answer,
            pending_approvals=result.pending_approvals,
            citation_problems=result.citation_problems,
            tool_calls=result.tool_calls,
            tokens=result.input_tokens + result.output_tokens,
            steps=[StepOut(**vars(s)) for s in result.steps],
        )

    @app.get("/approvals", tags=["agent"])
    def list_approvals(who: Caller) -> list[ApprovalOut]:
        if who.role is not Role.AGENT:
            raise HTTPException(403, "Only agents can see approvals.")
        return [_approval_out(a) for a in desk.approvals.values()]

    @app.post("/approvals/{approval_id}", tags=["agent"])
    def decide(
        approval_id: str, body: DecisionIn, who: Caller
    ) -> ApprovalOut:
        approval = desk.decide(
            approval_id, who, approve=body.decision == "approve"
        )
        return _approval_out(approval)

    return app


def _approval_out(a: object) -> ApprovalOut:
    return ApprovalOut.model_validate(a, from_attributes=True)
