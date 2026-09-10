"""Best-effort redaction and deterministic request budgets."""

from dataclasses import dataclass
import json
from pathlib import PurePosixPath
import re
import unicodedata

from .git_context import GitContext, read_diff

MAX_FILES = 10
MAX_LINES = 200
MAX_DATA_CHARS = 12_000
MAX_REQUEST_CHARS = 20_000
MAX_CONTEXT_CHARS = 1_000

PRIVATE_KEY = re.compile(
    r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----.*?(?:-----END [A-Z0-9 ]*PRIVATE KEY-----|\Z)",
    re.DOTALL,
)
SECRET_TOKEN = re.compile(
    r"\b(?:sk-[A-Za-z0-9_-]{8,}|gh[pousr]_[A-Za-z0-9_]{8,}|"
    r"github_pat_[A-Za-z0-9_]{8,}|AKIA[A-Z0-9]{16})\b"
)
MULTILINE_SECRET_START = re.compile(
    r"(?im)([\"']?\b[\w.-]*(?:api[_-]?key|secret|password|passwd|token)[\w.-]*[\"']?\s*[:=]\s*)"
    r"(?:\"{3}|'{3})"
)
ASSIGNMENT = re.compile(
    r'''(?im)(["']?\b[\w.-]*(?:api[_-]?key|secret|password|passwd|token)[\w.-]*["']?\s*[:=]\s*)(?:"(?:\\.|[^"\\\r\n])*(?:"|(?=\r?\n|\Z))|'(?:\\.|[^'\\\r\n])*(?:'|(?=\r?\n|\Z))|[^\s,;}]+)'''
)
EMAIL = re.compile(r"\b[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
AUTH = re.compile(r"(?i)\b(?:Bearer|Basic)\s+[A-Za-z0-9._~+/=-]+")
URL_AUTH = re.compile(r"([a-z][a-z0-9+.-]*://)[^\s/@:]+:[^\s/@]+@", re.IGNORECASE)


def terminal_safe(text: str) -> str:
    return "".join(
        ch if ch in "\n\t" or unicodedata.category(ch) not in {"Cc", "Cf", "Cs"}
        else "?" for ch in text
    )


def redact(text: str, api_key: str = "") -> str:
    if api_key:
        text = text.replace(api_key, "[REDACTED]")
    text = PRIVATE_KEY.sub("[REDACTED PRIVATE KEY]", text)
    text = SECRET_TOKEN.sub("[REDACTED]", text)
    # Do not try to pair triple quotes in interleaved old/new diff streams.
    # A partial hunk may also lack the closing quote. Drop the remainder.
    multiline = MULTILINE_SECRET_START.search(text)
    if multiline:
        text = text[:multiline.start()] + multiline[1] + '"[REDACTED MULTILINE]"'
    text = ASSIGNMENT.sub(lambda match: match[1] + '"[REDACTED]"', text)
    text = AUTH.sub("[REDACTED AUTH]", text)
    text = URL_AUTH.sub(r"\1[REDACTED]@", text)
    return terminal_safe(EMAIL.sub("[REDACTED EMAIL]", text))


def excluded(path: str) -> bool:
    parts = PurePosixPath(path.lower()).parts
    name = parts[-1] if parts else ""
    return (
        any(part in {".ssh", ".aws", ".gnupg"} for part in parts)
        or name == ".env" or name.startswith(".env.") or name.endswith(".env")
        or name in {"id_rsa", "id_ed25519", "id_ecdsa", "id_dsa", "credentials", "credentials.json", "secrets.json"}
        or name.endswith((".pem", ".key", ".p12", ".pfx", ".keystore"))
    )


def dumps(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


@dataclass
class SafeInput:
    data: dict
    excluded_files: int
    omitted_files: int
    truncated_blocks: int
    line_count: int


def prepare(
    context: GitContext, *, staged_only: bool = False,
    reason: str = "", test_context: str = "", api_key: str = "",
) -> SafeInput:
    reason = redact(reason, api_key)
    test_context = redact(test_context, api_key)
    data = {
        "scope": "staged" if staged_only else "staged + unstaged",
        "context": reason[:MAX_CONTEXT_CHARS],
        "test_context": test_context[:MAX_CONTEXT_CHARS],
        "partial": len(reason) > MAX_CONTEXT_CHARS or len(test_context) > MAX_CONTEXT_CHARS,
        "changes": [],
    }
    eligible = []
    excluded_count = 0
    for change in context.changes:
        if not change.layers(staged_only):
            continue
        if excluded(change.path) or (change.old_path and excluded(change.old_path)):
            excluded_count += 1
        else:
            eligible.append(change)
    omitted = max(0, len(eligible) - MAX_FILES)
    truncated = 0
    lines_used = 0
    for change in eligible[:MAX_FILES]:
        diffs = [(layer, read_diff(context, change, layer)) for layer in change.layers(staged_only)]
        # Omitting the whole file prevents either side of a multiline secret
        # edit from being mistaken for the other side's closing delimiter.
        if any(MULTILINE_SECRET_START.search(diff) for _, diff in diffs):
            excluded_count += 1
            continue
        included_file = False
        for layer, raw_diff in diffs:
            if not raw_diff.strip():
                continue
            lines = redact(raw_diff, api_key).splitlines()
            remaining = MAX_LINES - lines_used
            block = {
                "path": redact(change.path, api_key),
                "status": change.status,
                "layer": layer,
                "diff": "",
                "truncated": False,
            }
            if change.old_path:
                block["old_path"] = redact(change.old_path, api_key)
            data["changes"].append(block)
            kept = []
            for line in lines[:remaining]:
                block["diff"] = "\n".join([*kept, line])
                # input is a JSON string inside the outer REST JSON request.
                # Count both escaping layers, reserving room for instructions,
                # schema, and a correction containing up to 1,000 characters.
                if len(dumps(dumps(data))) > MAX_DATA_CHARS:
                    break
                kept.append(line)
            block["diff"] = "\n".join(kept)
            if len(kept) < len(lines):
                truncated += 1
                block["truncated"] = True
            if not kept:
                data["changes"].pop()
            else:
                lines_used += len(kept)
                included_file = True
        if not included_file:
            omitted += 1
    data["partial"] = bool(data["partial"] or omitted or truncated or excluded_count)
    return SafeInput(data, excluded_count, omitted, truncated, lines_used)
