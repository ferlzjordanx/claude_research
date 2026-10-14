import io

import pytest

from scripts.next_version import (
    Bump,
    bump_version,
    classify,
    main,
    next_version,
)


@pytest.mark.parametrize(
    ("message", "expected"),
    [
        ("feat: add bulk quotes", Bump.MINOR),
        ("feat(api): add /quote", Bump.MINOR),
        ("fix: round half up", Bump.PATCH),
        ("perf: cache tiers", Bump.PATCH),
        ("docs: update README", Bump.NONE),
        ("chore(deps): bump httpx", Bump.NONE),
        ("feat!: drop /v1", Bump.MAJOR),
        ("refactor(core)!: rename settings", Bump.MAJOR),
        ("fix: x\n\nBREAKING CHANGE: field renamed", Bump.MAJOR),
        ("Merge branch 'main'", Bump.NONE),
        ("", Bump.NONE),
    ],
)
def test_classify(message: str, expected: Bump) -> None:
    assert classify(message) is expected


@pytest.mark.parametrize(
    ("version", "bump", "expected"),
    [
        ("1.4.2", Bump.PATCH, "1.4.3"),
        ("1.4.2", Bump.MINOR, "1.5.0"),
        ("1.4.2", Bump.MAJOR, "2.0.0"),
        ("v1.4.2", Bump.MINOR, "v1.5.0"),
        ("1.4.2", Bump.NONE, "1.4.2"),
    ],
)
def test_bump_version(version: str, bump: Bump, expected: str) -> None:
    assert bump_version(version, bump) == expected


def test_bump_version_rejects_garbage() -> None:
    with pytest.raises(ValueError):
        bump_version("1.4", Bump.PATCH)


def test_next_version_takes_the_largest_bump() -> None:
    messages = ["fix: a", "feat: b", "docs: c"]
    assert next_version("v1.4.2", messages) == "v1.5.0"
    assert next_version("v1.4.2", []) == "v1.4.2"


def test_cli_reads_nul_separated_messages(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    stdin = "fix: a\n\0feat!: b\n\nbody\n\0"
    monkeypatch.setattr("sys.stdin", io.StringIO(stdin))
    assert main(["v0.9.1"]) == 0
    assert capsys.readouterr().out.strip() == "v1.0.0"
