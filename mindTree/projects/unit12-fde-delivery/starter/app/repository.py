"""In-memory storage for submissions and the audit log.

Pilot scope: one process, data lost on restart (requirements.md,
out of scope). Production would use Postgres with the same methods
(Unit 3) and an append-only audit table.
"""

import threading

from app.models import AuditEntry, Status, Submission


class InMemoryRepository:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._submissions: dict[int, Submission] = {}
        self._audit: list[AuditEntry] = []
        self._next_id = 1

    def next_id(self) -> int:
        with self._lock:
            value = self._next_id
            self._next_id += 1
            return value

    def save(self, submission: Submission) -> None:
        with self._lock:
            self._submissions[submission.id] = submission

    def get(self, submission_id: int) -> Submission | None:
        return self._submissions.get(submission_id)

    def all(self) -> list[Submission]:
        return sorted(self._submissions.values(), key=lambda s: s.id)

    def by_status(self, status: Status) -> list[Submission]:
        return [s for s in self.all() if s.status is status]

    def add_audit(self, entry: AuditEntry) -> None:
        # Append-only: there is no update or delete method on purpose.
        with self._lock:
            self._audit.append(entry)

    def audit_for(self, submission_id: int) -> list[AuditEntry]:
        return [a for a in self._audit if a.submission_id == submission_id]

    def audit_log(self) -> list[AuditEntry]:
        return list(self._audit)
