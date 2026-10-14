from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.agent.fake import FakeToolLLM
from app.config import Settings
from app.main import create_app
from app.rag.documents import Chunk, chunk_all, load_kb
from app.rag.embeddings import HashingEmbedder
from app.rag.retriever import HybridRetriever
from app.roles import Principal, Role
from app.tools.registry import ToolContext, ToolRegistry
from app.tools.support import SupportDesk, build_registry

ALICE = Principal("alice", Role.CUSTOMER)
BOB = Principal("bob", Role.CUSTOMER)
SAM = Principal("sam", Role.AGENT)
PAT = Principal("pat", Role.AGENT)


def ctx(who: Principal, run_id: str = "run-test") -> ToolContext:
    return ToolContext(principal=who, run_id=run_id)


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def settings() -> Settings:
    return Settings(
        env="test",
        demo_tokens="t-alice:alice:customer,t-bob:bob:customer,"
        "t-sam:sam:agent,t-pat:pat:agent",
    )


@pytest.fixture(scope="session")
def chunks() -> list[Chunk]:
    return chunk_all(load_kb(Settings(env="test").kb_dir))


@pytest.fixture(scope="session")
def retriever(chunks: list[Chunk]) -> HybridRetriever:
    return HybridRetriever(chunks, HashingEmbedder())


@pytest.fixture
def desk() -> SupportDesk:
    return SupportDesk(approval_threshold_cents=5000)


@pytest.fixture
def registry(retriever: HybridRetriever, desk: SupportDesk) -> ToolRegistry:
    return build_registry(retriever, desk, min_relevance=0.5)


@pytest.fixture
def client(settings: Settings) -> Iterator[TestClient]:
    with TestClient(create_app(settings, llm=FakeToolLLM())) as c:
        yield c
