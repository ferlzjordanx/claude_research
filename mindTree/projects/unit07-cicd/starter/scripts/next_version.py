"""Compute the next semantic version from Conventional Commits.

Usage:
    git log --format=%B%x00 v1.4.0..HEAD \
        | python -m scripts.next_version v1.4.0

Rules (https://www.conventionalcommits.org):
    feat!: ... or a "BREAKING CHANGE:" footer  -> major
    feat: ...                                  -> minor
    fix: ... / perf: ...                       -> patch
    anything else (docs, chore, ci, test, ...) -> no release
"""

import re
import sys
from collections.abc import Iterable, Sequence
from enum import IntEnum

HEADER = re.compile(
    r"^(?P<type>[a-z]+)(\([\w./-]+\))?(?P<bang>!)?: \S", re.IGNORECASE
)
BREAKING_FOOTER = re.compile(r"^BREAKING[ -]CHANGE: ", re.MULTILINE)
SEMVER = re.compile(r"^(?P<v>v?)(\d+)\.(\d+)\.(\d+)$")


class Bump(IntEnum):
    # IntEnum so max() picks the biggest bump across many commits.
    NONE = 0
    PATCH = 1
    MINOR = 2
    MAJOR = 3


def classify(message: str) -> Bump:
    """Bump implied by one commit message (header + body)."""
    # TODO(3): match the first line against HEADER.
    #  - no match                              -> Bump.NONE
    #  - "!" before the colon, or a
    #    BREAKING CHANGE footer anywhere       -> Bump.MAJOR
    #  - type feat                             -> Bump.MINOR
    #  - type fix or perf                      -> Bump.PATCH
    #  - any other type                        -> Bump.NONE
    raise NotImplementedError("TODO(3)")


def bump_version(version: str, bump: Bump) -> str:
    """Apply a bump to 'X.Y.Z' or 'vX.Y.Z', keeping the prefix."""
    match = SEMVER.match(version.strip())
    if match is None:
        raise ValueError(f"not a semantic version: {version!r}")
    # TODO(4): read major/minor/patch from groups 2-4, apply the
    # bump (a bigger bump resets the smaller parts to 0) and keep
    # the optional "v" prefix from match["v"].
    raise NotImplementedError("TODO(4)")


def next_version(current: str, messages: Iterable[str]) -> str:
    bump = max((classify(m) for m in messages), default=Bump.NONE)
    return bump_version(current, bump)


def main(argv: Sequence[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) != 1:
        print("usage: next_version CURRENT < messages", file=sys.stderr)
        return 2
    messages = [m for m in sys.stdin.read().split("\0") if m.strip()]
    try:
        print(next_version(args[0], messages))
    except ValueError as exc:
        print(exc, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
