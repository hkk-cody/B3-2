class GitgenError(Exception):
    """A user-facing error whose message must never contain raw secrets."""


class ValidationError(GitgenError):
    """An invalid model draft; eligible for one correction request."""
