"""JSON 응답 스키마 및 글자 수 검증."""

import json
from .errors import ValidationError


def _text(value: object, field: str, limit: int) -> str:
    """단일 줄 텍스트 및 길이 검증."""
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(f"{field}: 비어 있지 않은 문자열이 필요합니다.")
    if "\n" in value or "\r" in value:
        raise ValidationError(f"{field}: 줄바꿈을 포함할 수 없습니다.")
    value = value.strip()
    if len(value) > limit:
        raise ValidationError(f"{field}: 최대 {limit}자를 초과했습니다.")
    return value


def validate(command: str, raw: str) -> dict:
    """AI 응답 JSON을 파싱하고 필드 및 길이 규칙을 검증합니다."""
    try:
        draft = json.loads(raw)
    except (ValueError, TypeError):
        raise ValidationError("JSON 형식의 응답이 필요합니다.") from None

    if not isinstance(draft, dict):
        raise ValidationError("응답은 JSON 객체여야 합니다.")

    array_fields = ["changes"] if command == "commit" else ["why", "what", "how_to_test"]
    if set(draft) != {"summary", "title", *array_fields}:
        raise ValidationError("필수 응답 필드가 누락되었거나 불필요한 필드가 있습니다.")

    result = {
        "summary": _text(draft["summary"], "summary", 1000),
        "title": _text(draft["title"], "title", 72 if command == "commit" else 80),
    }

    for field in array_fields:
        items = draft[field]
        maximum = 2 if field == "changes" else 10
        if not isinstance(items, list) or not 1 <= len(items) <= maximum:
            raise ValidationError(f"{field}: 불릿 {maximum}개 이내의 비어 있지 않은 배열이 필요합니다.")
        result[field] = [_text(item, field, 1000) for item in items]

    return result
