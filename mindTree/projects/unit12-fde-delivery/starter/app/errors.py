"""Domain errors the service raises on purpose."""


class DomainError(Exception):
    status_code = 400

    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


class NotFoundError(DomainError):
    status_code = 404


class StateError(DomainError):
    """Action not allowed in the submission's current status."""

    status_code = 409


class CorrectionError(DomainError):
    """A reviewer's corrections do not pass validation."""

    status_code = 422

    def __init__(self, issues: dict[str, str]) -> None:
        super().__init__("corrections are not valid")
        self.issues = issues
