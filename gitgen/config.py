"""Codyssey connection settings from the environment or repository .env."""

from dataclasses import dataclass, field
import os
from pathlib import Path
from urllib.parse import urlsplit

from .errors import GitgenError


DEFAULT_BASE_URL = "https://copa.codyssey.kr/v1"
DEFAULT_MODEL = "gpt-5-mini"


@dataclass(frozen=True)
class Settings:
    api_key: str = field(repr=False)
    base_url: str = DEFAULT_BASE_URL
    model: str = DEFAULT_MODEL


def normalize_base_url(value: str) -> str:
    value = value.strip().rstrip("/")
    try:
        parsed = urlsplit(value)
        invalid = (
            not value.isascii() or any(ch.isspace() or ord(ch) < 32 for ch in value)
            or parsed.scheme != "https" or not parsed.hostname
            or parsed.username is not None or parsed.password is not None
            or parsed.query or parsed.fragment or parsed.port == 0
            or parsed.path.endswith(("/chat/completions", "/responses"))
        )
    except ValueError:
        invalid = True
    if invalid:
        raise GitgenError("AI_BASE_URL에는 인증정보·쿼리 없는 HTTPS 기본 주소를 입력하세요. 예: https://copa.codyssey.kr/v1")
    return value + "/v1" if not parsed.path else value


def _env_values(root: Path) -> dict:

    env_file = root / ".env"
    if not env_file.exists():
        return {}
    if not env_file.is_file():
        raise GitgenError("프로젝트 루트의 .env는 일반 텍스트 파일이어야 합니다.")
    try:
        from dotenv import dotenv_values
    except ImportError:
        raise GitgenError(".env 로딩에 필요한 의존성이 없습니다. python -m pip install -r requirements.txt를 실행하세요.") from None
    try:
        # Explicit path: do not search parent directories or the tool's own repo.
        # Parse as data; do not expand other variables or load unrelated settings.
        return dotenv_values(env_file, encoding="utf-8-sig", interpolate=False)
    except (OSError, UnicodeError):
        raise GitgenError(".env를 읽을 수 없습니다. 파일 권한과 UTF-8 인코딩을 확인하세요.") from None


def load_settings(root: Path) -> Settings:
    values = _env_values(root)

    def setting(name: str, default: str = "") -> str:
        return os.environ.get(name, "").strip() or (values.get(name) or "").strip() or default

    key = setting("AI_API_KEY")
    if key:
        try:
            os.environ["AI_API_KEY"] = key
        except (ValueError, UnicodeError):
            raise GitgenError(".env의 AI_API_KEY 형식이 올바르지 않습니다. API Key만 한 줄로 입력하세요.") from None
    return Settings(key, normalize_base_url(setting("AI_BASE_URL", DEFAULT_BASE_URL)), setting("AI_MODEL", DEFAULT_MODEL))


def load_api_key(root: Path) -> str:
    return load_settings(root).api_key
