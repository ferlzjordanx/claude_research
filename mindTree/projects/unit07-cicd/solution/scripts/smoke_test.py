"""Post-deploy smoke test.

Usage:
    python -m scripts.smoke_test --base-url https://staging.example \
        --expected-sha "$GITHUB_SHA"

Exit codes (the pipeline branches on them):
    0  healthy and serving the expected commit
    1  unhealthy or unreachable after all attempts
    2  bad command-line arguments (argparse)
    3  healthy but serving a different commit (rollout did not land)
"""

import argparse
import sys
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass

import httpx

EXIT_OK = 0
EXIT_UNHEALTHY = 1
EXIT_WRONG_VERSION = 3


class SmokeFailure(Exception):
    """One failed probe. `exit_code` says which kind."""

    def __init__(self, message: str, exit_code: int) -> None:
        super().__init__(message)
        self.exit_code = exit_code


@dataclass(frozen=True)
class SmokeConfig:
    expected_sha: str
    attempts: int = 10
    delay_seconds: float = 3.0


def probe_once(client: httpx.Client, expected_sha: str) -> str:
    """Check /health then /version once. Returns the served sha."""
    try:
        health = client.get("/health")
        if health.status_code != 200:
            raise SmokeFailure(
                f"/health returned {health.status_code}", EXIT_UNHEALTHY
            )
        version = client.get("/version")
        version.raise_for_status()
        served = str(version.json().get("git_sha", ""))
    except httpx.HTTPError as exc:  # connect, timeout, 5xx on /version
        raise SmokeFailure(
            f"request failed: {exc!r}", EXIT_UNHEALTHY
        ) from exc
    except ValueError as exc:  # body was not JSON
        raise SmokeFailure("/version is not JSON", EXIT_UNHEALTHY) from exc
    # Allow short shas on either side ("abc1234" vs the full 40 chars).
    if not served or not (
        served.startswith(expected_sha) or expected_sha.startswith(served)
    ):
        raise SmokeFailure(
            f"serving {served or '<none>'}, expected {expected_sha}",
            EXIT_WRONG_VERSION,
        )
    return served


def run_smoke(
    client: httpx.Client,
    config: SmokeConfig,
    sleep: Callable[[float], None] = time.sleep,
    log: Callable[[str], None] = print,
) -> int:
    """Retry probe_once; return an exit code.

    Retries cover both failure kinds: during a rolling update some
    pods still serve the old sha for a few seconds, so a mismatch is
    only final when it survives every attempt.
    """
    last: SmokeFailure | None = None
    for attempt in range(1, config.attempts + 1):
        try:
            served = probe_once(client, config.expected_sha)
        except SmokeFailure as failure:
            last = failure
            log(f"attempt {attempt}/{config.attempts}: {failure}")
            if attempt < config.attempts:
                sleep(config.delay_seconds)
            continue
        log(f"smoke test passed: serving {served}")
        return EXIT_OK
    assert last is not None  # attempts >= 1 guarantees one probe
    log(f"smoke test FAILED: {last}")
    return last.exit_code


def positive_int(text: str) -> int:
    value = int(text)
    if value < 1:
        raise argparse.ArgumentTypeError("must be >= 1")
    return value


def parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--expected-sha", required=True)
    parser.add_argument("--attempts", type=positive_int, default=10)
    parser.add_argument("--delay", type=float, default=3.0)
    parser.add_argument(
        "--timeout", type=float, default=5.0, help="per request, s"
    )
    return parser.parse_args(argv)


def main(
    argv: Sequence[str] | None = None,
    transport: httpx.BaseTransport | None = None,
    sleep: Callable[[float], None] = time.sleep,
) -> int:
    args = parse_args(argv)
    config = SmokeConfig(args.expected_sha, args.attempts, args.delay)
    with httpx.Client(
        base_url=args.base_url,
        timeout=args.timeout,
        transport=transport,
        follow_redirects=True,
    ) as client:
        return run_smoke(client, config, sleep=sleep)


if __name__ == "__main__":
    sys.exit(main())
