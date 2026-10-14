"""Smoke-test script tests with httpx.MockTransport (no network)."""

from collections.abc import Callable

import httpx
import pytest

from scripts.smoke_test import (
    EXIT_OK,
    EXIT_UNHEALTHY,
    EXIT_WRONG_VERSION,
    SmokeConfig,
    main,
    run_smoke,
)

SHA = "abc1234def5678"
Handler = Callable[[httpx.Request], httpx.Response]


def service(sha: str = SHA, health_status: int = 200) -> Handler:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/health":
            return httpx.Response(health_status, json={"status": "ok"})
        if request.url.path == "/version":
            return httpx.Response(200, json={"git_sha": sha})
        return httpx.Response(404)

    return handler


def run(handler: Handler, attempts: int = 3) -> tuple[int, list[float]]:
    sleeps: list[float] = []
    client = httpx.Client(
        base_url="http://svc", transport=httpx.MockTransport(handler)
    )
    with client:
        code = run_smoke(
            client,
            SmokeConfig(SHA, attempts=attempts, delay_seconds=0.5),
            sleep=sleeps.append,
            log=lambda _msg: None,
        )
    return code, sleeps


def test_passes_when_healthy_and_sha_matches() -> None:
    assert run(service()) == (EXIT_OK, [])


def test_accepts_short_sha_from_service() -> None:
    code, _ = run(service(sha=SHA[:7]))
    assert code == EXIT_OK


def test_wrong_sha_after_all_attempts_is_exit_3() -> None:
    code, sleeps = run(service(sha="0000000"), attempts=3)
    assert code == EXIT_WRONG_VERSION
    assert sleeps == [0.5, 0.5]  # no sleep after the final attempt


def test_unhealthy_is_exit_1() -> None:
    code, sleeps = run(service(health_status=503), attempts=2)
    assert code == EXIT_UNHEALTHY
    assert len(sleeps) == 1


def test_recovers_while_rollout_is_in_progress() -> None:
    # Old pods answer first, then the new version takes over.
    served = iter(["oldsha1", "oldsha1", SHA])

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/health":
            return httpx.Response(200, json={"status": "ok"})
        return httpx.Response(200, json={"git_sha": next(served)})

    code, sleeps = run(handler, attempts=5)
    assert code == EXIT_OK
    assert len(sleeps) == 2


def test_connection_errors_are_retried_then_exit_1() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        raise httpx.ConnectError("connection refused", request=request)

    code, _ = run(handler, attempts=4)
    assert code == EXIT_UNHEALTHY
    assert calls == 4


def test_non_json_version_is_unhealthy() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/health":
            return httpx.Response(200)
        return httpx.Response(200, text="<html>proxy page</html>")

    code, _ = run(handler, attempts=1)
    assert code == EXIT_UNHEALTHY


def test_main_end_to_end_with_cli_args() -> None:
    code = main(
        ["--base-url", "http://svc", "--expected-sha", SHA],
        transport=httpx.MockTransport(service()),
        sleep=lambda _s: None,
    )
    assert code == EXIT_OK


def test_main_rejects_zero_attempts() -> None:
    with pytest.raises(SystemExit) as excinfo:
        main(["--base-url", "x", "--expected-sha", SHA, "--attempts", "0"])
    assert excinfo.value.code == 2
