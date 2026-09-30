"""AI 응답 생성 및 형식 오류 시 1회 재생성 처리."""

from .api_client import ApiClient
from .errors import GitgenError, ValidationError
from .safety import dumps
from .validators import validate


def generate(command: str, payload: dict, client: ApiClient, log) -> dict:
    """AI API를 호출하고 응답을 검증합니다. 실패 시 1회 재생성을 시도합니다."""
    original_messages = [dict(msg) for msg in payload["messages"]]
    request = dict(payload)
    request["messages"] = original_messages

    for attempt in range(2):
        try:
            log("INFO", "AI API 요청 중...")
            raw = client.generate(request)
            return validate(command, raw)
        except ValidationError as exc:
            if attempt == 1:
                raise GitgenError(f"재생성 후에도 출력 검증에 실패했습니다: {exc}") from None
            log("WARN", f"출력 검증 실패: {exc} 1회 재생성합니다.")
            request["messages"] = original_messages + [{
                "role": "user",
                "content": dumps({
                    "correction": str(exc),
                    "request": "원래 Git 데이터와 규칙을 사용하여 전체 JSON 초안을 다시 작성하세요.",
                }),
            }]
    raise AssertionError("unreachable")
