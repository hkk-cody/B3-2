from .api_client import ApiClient
from .errors import GitgenError, ValidationError
from .safety import dumps, redact
from .validators import validate


def generate(command: str, payload: dict, client: ApiClient, log) -> dict:
    original_messages = [dict(message) for message in payload["messages"]]
    request = dict(payload)
    request["messages"] = original_messages
    for attempt in range(2):
        raw = ""
        try:
            log("INFO", "AI API 요청 중...")
            raw = client.generate(request)
            draft = validate(command, raw)
            # Redact each value, not serialized JSON, to preserve JSON escaping.
            safe = {
                key: [redact(item, client.api_key) for item in value]
                if isinstance(value, list) else redact(value, client.api_key)
                for key, value in draft.items()
            }
            return validate(command, dumps(safe))
        except ValidationError as exc:
            if attempt == 1:
                raise GitgenError(f"재생성 후에도 출력 검증에 실패했습니다: {exc}") from None
            log("WARN", f"출력 검증 실패: {exc} 1회 재생성합니다.")
            request["messages"] = original_messages + [{"role": "user", "content": dumps({
                "correction": str(exc),
                "previous_excerpt": redact(raw, client.api_key)[:1000],
                "request": "원래 Git 데이터와 규칙을 사용하여 전체 JSON 초안을 다시 작성하세요.",
            })}]
    raise AssertionError("unreachable")
