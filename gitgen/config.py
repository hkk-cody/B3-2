"""설정 로드 및 정규화."""

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
    """AI API 베이스 URL 정규화."""
    value = value.strip().rstrip("/")
    try:
        p = urlsplit(value)
        _ = p.port  # 포트 형식 검증 (유효하지 않은 포트 시 ValueError 발생)
        if (
            p.scheme != "https" or not p.hostname or " " in value or "\n" in value
            or p.username or p.password or p.query or p.fragment
            or value.endswith(("/chat/completions", "/responses"))
        ):
            raise GitgenError("AI_BASE_URL에는 인증정보·쿼리 없는 HTTPS 기본 주소를 입력하세요. 예: https://copa.codyssey.kr/v1")
    except ValueError:
        raise GitgenError("AI_BASE_URL 형식이 올바르지 않습니다.") from None

    return value if p.path else value + "/v1"


def _read_env_file(env_file: Path) -> dict[str, str]:
    """표준 라이브러리만으로 .env 파일을 안전하게 파싱합니다."""
    if not env_file.exists():
        return {}
    if not env_file.is_file():
        raise GitgenError("프로젝트 루트의 .env는 일반 텍스트 파일이어야 합니다.")
    try:
        content = env_file.read_text(encoding="utf-8-sig")
    except (UnicodeError, OSError):
        raise GitgenError(".env를 읽을 수 없습니다. 파일 권한과 UTF-8 인코딩을 확인하세요.") from None

    values = {}
    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].strip()
        if "=" not in line:
            continue
        key, val = line.split("=", 1)
        key = key.strip()
        val = val.strip()

        if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
            val = val[1:-1]
        elif val.startswith('"') and '"' in val[1:]:
            val = val[1:val.find('"', 1)]
        elif val.startswith("'") and "'" in val[1:]:
            val = val[1:val.find("'", 1)]
        elif " #" in val:
            val = val.split(" #", 1)[0].strip()

        values[key] = val
    return values


def load_settings(root: Path) -> Settings:
    """환경변수 및 .env 파일에서 설정 로드."""
    env_values = _read_env_file(root / ".env")

    def get_val(key: str, default: str = "") -> str:
        return os.environ.get(key, "").strip() or (env_values.get(key) or "").strip() or default

    api_key = get_val("AI_API_KEY")
    if api_key:
        os.environ["AI_API_KEY"] = api_key

    base_url = normalize_base_url(get_val("AI_BASE_URL", DEFAULT_BASE_URL))
    model = get_val("AI_MODEL", DEFAULT_MODEL)
    return Settings(api_key=api_key, base_url=base_url, model=model)


def load_api_key(root: Path) -> str:
    return load_settings(root).api_key
