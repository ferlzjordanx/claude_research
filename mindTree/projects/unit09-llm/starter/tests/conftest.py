import pytest

from app.config import Settings
from app.llm.fake import FakeLLM
from app.triage import CallPolicy, TriageService


def valid(**overrides: object) -> dict[str, object]:
    """A valid TriageResult payload, as a model would return it."""
    data: dict[str, object] = {
        "category": "billing",
        "priority": "medium",
        "summary": "Customer reports a duplicate charge.",
        "needs_human": False,
        "confidence": 0.9,
    }
    data.update(overrides)
    return data


class SleepRecorder:
    """Injected instead of asyncio.sleep: records, never waits."""

    def __init__(self) -> None:
        self.delays: list[float] = []

    async def __call__(self, seconds: float) -> None:
        self.delays.append(seconds)


@pytest.fixture
def settings() -> Settings:
    return Settings(env="test", llm_provider="fake", _env_file=None)


@pytest.fixture
def sleeper() -> SleepRecorder:
    return SleepRecorder()


def make_service(
    llm: FakeLLM, sleeper: SleepRecorder, **policy: object
) -> TriageService:
    return TriageService(
        llm,
        CallPolicy(**policy),  # type: ignore[arg-type]
        prices={"fake-model": (1.0, 2.0)},
        sleep=sleeper,
        rand=lambda: 1.0,  # no jitter: delays are exact
    )
