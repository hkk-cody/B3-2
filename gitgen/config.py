import os
from pathlib import Path


def load_env(env_path: str = ".env") -> None:
    """
    외부 패키지(python-dotenv 등) 없이도 동작하도록
    .env 파일을 읽어 os.environ에 등록하는 함수입니다.
    이미 환경변수가 설정되어 있다면 덮어쓰지 않습니다.
    """
    p = Path(env_path)
    if not p.is_file():
        return

    try:
        with open(p, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                if line.startswith("export "):
                    line = line[7:].strip()
                key, val = line.split("=", 1)
                key = key.strip()
                val = val.strip().strip("'\"")
                if key not in os.environ:
                    os.environ[key] = val
    except Exception:
        pass


# .env 파일이 존재하는 경우 기본 로드
load_env()

DEFAULT_BASE_URL = os.environ.get("AI_BASE_URL", "https://copa.codyssey.kr/v1").rstrip("/")
DEFAULT_MODEL = os.environ.get("AI_MODEL", "gpt-5-mini")
DEFAULT_TEMPERATURE = 1.0
DEFAULT_COMMIT_MAX_TOKENS = 2000
DEFAULT_PR_MAX_TOKENS = 2500
