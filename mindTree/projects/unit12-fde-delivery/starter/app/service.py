"""The intake pipeline and review workflow (no HTTP here)."""

import logging
from collections.abc import Callable, Mapping
from datetime import UTC, date, datetime

from app.config import Settings
from app.errors import CorrectionError, NotFoundError, StateError
from app.extraction.deterministic import extract_deterministic
from app.extraction.llm import LLMExtractor
from app.fields import ALL_FIELDS
from app.merge import merge
from app.models import (
    AuditEntry,
    FieldResult,  # noqa: F401
    MetricsSummary,
    Route,
    Source,  # noqa: F401
    Status,
    Submission,
)
from app.repository import InMemoryRepository
from app.routing import decide_route
from app.validation import validate_values

log = logging.getLogger("intake")
SYSTEM_ACTOR = "system"


class IntakeService:
    def __init__(
        self,
        repo: InMemoryRepository,
        extractor: LLMExtractor,
        settings: Settings,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._repo = repo
        self._extractor = extractor
        self._settings = settings
        self._clock = clock or (lambda: datetime.now(UTC))

    def _today(self) -> date:
        return self._clock().date()

    # ---- pipeline -------------------------------------------------

    def submit(self, text: str, channel: str) -> Submission:
        det = extract_deterministic(text)
        ask = (
            list(ALL_FIELDS)
            if self._settings.llm_cross_check
            else [f for f in ALL_FIELDS if f not in det]
        )
        guesses = self._extractor.extract(text, ask) if ask else {}
        merged = merge(det, guesses, ALL_FIELDS)
        values = {str(f): r.value for f, r in merged.items()}
        issues = validate_values(values, self._today())
        decision = decide_route(
            merged, issues, self._settings.auto_accept_threshold
        )
        auto = decision.route is Route.AUTO_ACCEPT
        sub = Submission(
            id=self._repo.next_id(),
            received_at=self._clock(),
            channel=channel,
            raw_text=text,
            fields={str(f): r for f, r in merged.items()},
            issues=issues,
            route=decision.route,
            reasons=decision.reasons,
            status=Status.AUTO_ACCEPTED if auto else Status.PENDING_REVIEW,
        )
        self._repo.save(sub)
        self._audit(
            sub.id,
            SYSTEM_ACTOR,
            "auto_accept" if auto else "route_review",
            note="; ".join(decision.reasons) or None,
        )
        # IDs and counts only. Never log the text or field values:
        # they are patient data (requirements.md NFR-2).
        log.info(
            "intake id=%s route=%s reasons=%d",
            sub.id,
            sub.route,
            len(sub.reasons),
        )
        return sub

    # ---- review workflow ------------------------------------------

    def get(self, submission_id: int) -> Submission:
        sub = self._repo.get(submission_id)
        if sub is None:
            raise NotFoundError(f"submission {submission_id} not found")
        return sub

    def review_queue(self) -> list[Submission]:
        return self._repo.by_status(Status.PENDING_REVIEW)

    def approve(
        self,
        submission_id: int,
        reviewer: str,
        corrections: Mapping[str, str | None],
        note: str | None = None,
    ) -> Submission:
        sub = self._pending(submission_id)
        unknown = set(corrections) - {str(f) for f in ALL_FIELDS}
        if unknown:
            raise CorrectionError(
                {name: "unknown field" for name in sorted(unknown)}
            )
        new_values = {**sub.values(), **corrections}
        issues = validate_values(new_values, self._today())
        if issues:
            raise CorrectionError(issues)

        self._apply_corrections(sub, reviewer, corrections)
        sub.issues = {}
        sub.status = Status.APPROVED
        sub.reviewed_by = reviewer
        self._repo.save(sub)
        self._audit(sub.id, reviewer, "approve", note=note)
        log.info(
            "review id=%s approved corrections=%d",
            sub.id,
            len(sub.corrected_fields),
        )
        return sub

    def _apply_corrections(
        self,
        sub: Submission,
        reviewer: str,
        corrections: Mapping[str, str | None],
    ) -> None:
        """Apply each changed field and write one audit entry per
        change: who, which field, old value, new value, when.

        Unchanged values are not corrections: re-typing the same
        value must not inflate the correction rate.
        """
        # TODO(3): for each (name, new) in sorted(corrections.items()):
        #   - skip it if sub.fields[name].value == new;
        #   - otherwise write an audit entry with self._audit(...):
        #     actor=reviewer, action "correct", field, old and new;
        #   - replace sub.fields[name] with a FieldResult whose
        #     source is Source.HUMAN and confidence 1.0;
        #   - append name to sub.corrected_fields.
        raise NotImplementedError("TODO(3)")

    def reject(
        self, submission_id: int, reviewer: str, reason: str
    ) -> Submission:
        sub = self._pending(submission_id)
        sub.status = Status.REJECTED
        sub.reviewed_by = reviewer
        self._repo.save(sub)
        self._audit(sub.id, reviewer, "reject", note=reason)
        log.info("review id=%s rejected", sub.id)
        return sub

    def audit_for(self, submission_id: int) -> list[AuditEntry]:
        self.get(submission_id)
        return self._repo.audit_for(submission_id)

    # ---- metrics --------------------------------------------------

    def metrics(self) -> MetricsSummary:
        subs = self._repo.all()
        by = {s: [x for x in subs if x.status is s] for s in Status}
        approved = by[Status.APPROVED]
        corrected: dict[str, int] = {str(f): 0 for f in ALL_FIELDS}
        for sub in approved:
            for name in set(sub.corrected_fields):
                corrected[name] += 1
        rates = {
            name: round(count / len(approved), 3) if approved else 0.0
            for name, count in corrected.items()
        }
        total = len(subs)
        auto = len(by[Status.AUTO_ACCEPTED])
        return MetricsSummary(
            total=total,
            auto_accepted=auto,
            sent_to_review=total - auto,
            pending_review=len(by[Status.PENDING_REVIEW]),
            approved=len(approved),
            rejected=len(by[Status.REJECTED]),
            auto_accept_rate=round(auto / total, 3) if total else 0.0,
            corrections_total=sum(
                len(s.corrected_fields) for s in approved
            ),
            field_correction_rates=rates,
        )

    # ---- helpers --------------------------------------------------

    def _pending(self, submission_id: int) -> Submission:
        sub = self.get(submission_id)
        if sub.status is not Status.PENDING_REVIEW:
            raise StateError(
                f"submission {submission_id} is {sub.status}, "
                "not pending_review"
            )
        return sub

    def _audit(
        self,
        submission_id: int,
        actor: str,
        action: str,
        *,
        field: str | None = None,
        old: str | None = None,
        new: str | None = None,
        note: str | None = None,
    ) -> None:
        self._repo.add_audit(
            AuditEntry(
                submission_id=submission_id,
                at=self._clock(),
                actor=actor,
                action=action,
                field=field,
                old_value=old,
                new_value=new,
                note=note,
            )
        )
