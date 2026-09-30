"""민감정보 마스킹 및 diff 전송량 제한."""

from dataclasses import dataclass
import json
from pathlib import PurePosixPath
import re

from .git_context import GitContext, read_diff

MAX_FILES = 10
MAX_LINES = 200
MAX_DATA_CHARS = 12_000

# 주요 민감정보 마스킹 패턴 (API 키, 개인키, 패스워드, 이메일, 인증 헤더)
PATTERNS = [
    (re.compile(r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----.*?(?:-----END [A-Z0-9 ]*PRIVATE KEY-----|\Z)", re.DOTALL), "[REDACTED PRIVATE KEY]"),
    (re.compile(r"\b(?:sk-[A-Za-z0-9_-]{8,}|gh[pousr]_[A-Za-z0-9_]{8,}|AKIA[A-Z0-9]{16})\b"), "[REDACTED]"),
    (re.compile(r'(?i)(["\']?\b[\w.-]*(?:api[_-]?key|secret|password|passwd|token)[\w.-]*["\']?\s*[:=]\s*)(["\'].*?["\']|\S+)'), r'\1"[REDACTED]"'),
    (re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"), "[REDACTED EMAIL]"),
    (re.compile(r"(?i)\b(?:Bearer|Basic)\s+[A-Za-z0-9._~+/=-]+"), "[REDACTED AUTH]"),
    (re.compile(r"([a-z]+://)[^\s/@:]+:[^\s/@]+@"), r"\1[REDACTED]@"),
]

EXCLUDED_NAMES = {".env", "id_rsa", "id_ed25519", "credentials", "credentials.json", "secrets.json"}
EXCLUDED_EXTS = (".pem", ".key", ".p12", ".pfx", ".keystore")


def excluded(path: str) -> bool:
    """민감정보 파일(설정, 비밀키 등)을 분석 대상에서 제외합니다."""
    parts = PurePosixPath(path.lower()).parts
    name = parts[-1] if parts else ""
    return (
        any(p in {".ssh", ".aws", ".gnupg"} for p in parts)
        or name == ".env" or name.startswith(".env.") or name.endswith(".env")
        or name in EXCLUDED_NAMES
        or name.endswith(EXCLUDED_EXTS)
    )


def redact(text: str, api_key: str = "") -> str:
    """텍스트 내의 민감정보를 [REDACTED]로 치환합니다."""
    if api_key:
        text = text.replace(api_key, "[REDACTED]")
    for pattern, replacement in PATTERNS:
        text = pattern.sub(replacement, text)
    return text


def dumps(value: object) -> str:
    """JSON 직렬화 축약."""
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


@dataclass
class SafeInput:
    data: dict
    excluded_files: int
    omitted_files: int
    truncated_blocks: int
    line_count: int


def prepare(
    context: GitContext, *,
    safe_mode: bool = True,
    api_key: str = "",
) -> SafeInput:
    """staged diff를 수집하고 안전 모드(마스킹 및 전송 한도)를 적용합니다."""
    eligible = [change for change in context.changes if change.layers()]
    excluded_count = 0

    if safe_mode:
        filtered = []
        for change in eligible:
            if excluded(change.path) or (change.old_path and excluded(change.old_path)):
                excluded_count += 1
            else:
                filtered.append(change)
        eligible = filtered

    target_files = eligible[:MAX_FILES] if safe_mode else eligible
    omitted_files = max(0, len(eligible) - len(target_files))
    truncated_blocks = 0
    total_lines = 0

    data = {
        "scope": "staged",
        "partial": False,
        "changes": [],
    }

    for change in target_files:
        for layer in change.layers():
            raw_diff = read_diff(context, change, layer)
            if not raw_diff.strip():
                continue

            diff_text = redact(raw_diff, api_key) if safe_mode else raw_diff
            lines = diff_text.splitlines()

            if safe_mode:
                remaining = MAX_LINES - total_lines
                kept_lines = lines[:remaining]
                is_truncated = len(kept_lines) < len(lines)
            else:
                kept_lines = lines
                is_truncated = False

            if is_truncated:
                truncated_blocks += 1

            if kept_lines:
                total_lines += len(kept_lines)
                block = {
                    "path": redact(change.path, api_key) if safe_mode else change.path,
                    "status": change.status,
                    "layer": layer,
                    "diff": "\n".join(kept_lines),
                    "truncated": is_truncated,
                }
                if change.old_path:
                    block["old_path"] = redact(change.old_path, api_key) if safe_mode else change.old_path
                data["changes"].append(block)

    data["partial"] = bool(safe_mode and (omitted_files or truncated_blocks or excluded_count))
    return SafeInput(data, excluded_count, omitted_files, truncated_blocks, total_lines)
