"""Health semantics.

/health/live   "is this process able to make progress?" No dependency
               checks: a DB outage must not make Kubernetes restart
               every pod (that turns an outage into a crash loop).
/health/ready  "should this pod receive traffic right now?" Checks the
               DB and returns 503 while draining for shutdown, so the
               load balancer stops sending new requests.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from sqlalchemy import text  # noqa: F401  (for TODO 1)
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError  # noqa: F401

log = logging.getLogger("health")


@dataclass
class HealthState:
    draining: bool = False

    def begin_drain(self) -> None:
        if not self.draining:
            log.info("draining: readiness now reports 503")
        self.draining = True


def check_ready(
    state: HealthState, engine: Engine
) -> tuple[bool, dict[str, str]]:
    """Return (ready, details). Never raises."""
    # TODO(1): readiness logic.
    #   - draining -> (False, {"status": "draining"})
    #   - run SELECT 1 on a connection from `engine`; on
    #     SQLAlchemyError log a warning and return
    #     (False, {"status": "unavailable", "database": "down"})
    #   - otherwise -> (True, {"status": "ready", "database": "ok"})
    raise NotImplementedError("TODO(1)")
