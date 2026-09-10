"""Codyssey's OpenAI-compatible Chat Completions API; no HTTP retries."""

import json

from .errors import GitgenError, ValidationError
from .config import DEFAULT_BASE_URL, normalize_base_url
from .safety import MAX_REQUEST_CHARS, dumps

ENDPOINT = DEFAULT_BASE_URL + "/chat/completions"
MAX_RESPONSE_BYTES = 256_000


def encode_payload(payload: dict) -> bytes:
    body = dumps(payload)
    if len(body) > MAX_REQUEST_CHARS:
        raise GitgenError("API 요청이 20,000자를 초과했습니다. 변경 맥락이나 diff를 줄이세요.")
    return body.encode("utf-8")


def parse_response(body: object) -> str:
    if not isinstance(body, dict):
        raise ValidationError("API 응답이 JSON 객체가 아닙니다.")
    if body.get("error"):
        raise GitgenError("API가 오류를 반환했습니다. Codyssey 콘솔의 키·모델 권한과 사용 한도를 확인하세요.")
    choices = body.get("choices")
    if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
        raise ValidationError("API 응답에 choices 배열이 없습니다.")
    choice = choices[0]
    if choice.get("finish_reason") == "length":
        raise GitgenError("AI 응답이 완료되지 않았습니다. --max-tokens를 늘리거나 변경 범위를 줄이세요.")
    if choice.get("finish_reason") == "content_filter":
        raise GitgenError("AI가 초안 생성을 거절했습니다. 입력 내용을 검토하세요.")
    if choice.get("finish_reason") not in (None, "stop"):
        raise GitgenError("AI 응답이 정상적으로 완료되지 않았습니다. 입력을 검토하세요.")
    message = choice.get("message")
    if not isinstance(message, dict):
        raise ValidationError("API 응답에 message 객체가 없습니다.")
    if message.get("refusal"):
        raise GitgenError("AI가 초안 생성을 거절했습니다. 입력 내용을 검토하세요.")
    content = message.get("content")
    if not isinstance(content, str) or not content.strip():
        raise ValidationError("API 응답에 생성된 텍스트가 없습니다.")
    return content


class ApiClient:
    def __init__(self, api_key: str, base_url: str = DEFAULT_BASE_URL):
        self.api_key = api_key
        self.endpoint = normalize_base_url(base_url) + "/chat/completions"
        self.calls = 0

    def generate(self, payload: dict) -> str:
        try:
            import requests
        except ImportError:
            raise GitgenError("의존성이 없습니다. python -m pip install -r requirements.txt를 실행하세요.") from None
        if self.calls >= 2:
            raise GitgenError("1회 실행의 API 호출 한도(2회)에 도달했습니다.")
        encoded = encode_payload(payload)
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        self.calls += 1
        try:
            # No SDK retries, redirects, tools, or remote side effects.
            with requests.post(
                self.endpoint, headers=headers, data=encoded, timeout=30,
                allow_redirects=False, stream=True,
            ) as response:
                code = response.status_code
                if not 200 <= code < 300:
                    messages = {
                        400: "요청 설정 오류. --temperature를 생략하거나 모델의 토큰 한도·지원 파라미터를 확인하세요.",
                        401: "인증 실패. Codyssey에서 발급한 OpenAI 호환 키를 AI_API_KEY에 입력했는지 확인하세요.",
                        403: "접근 거부. Codyssey 키의 프로토콜·모델 사용 권한을 확인하세요.",
                        404: "API 주소 또는 모델을 찾을 수 없습니다. AI_BASE_URL과 --model을 확인하세요.",
                        429: "요청 제한 또는 사용량 한도 초과. Codyssey 콘솔의 잔여 토큰·키 한도를 확인하거나 잠시 후 재실행하세요.",
                    }
                    message = messages.get(code, "API 서버 오류입니다." if code >= 500 else "예상하지 못한 API HTTP 응답입니다.")
                    raise GitgenError(f"HTTP {code}: {message}")
                chunks = bytearray()
                for chunk in response.iter_content(chunk_size=8192):
                    chunks.extend(chunk)
                    if len(chunks) > MAX_RESPONSE_BYTES:
                        raise GitgenError("API 응답이 크기 제한을 초과했습니다. --max-tokens를 줄이세요.")
        except requests.exceptions.Timeout:
            raise GitgenError("API 요청 시간 초과(30초). 네트워크 상태를 확인한 뒤 다시 실행하세요.") from None
        except requests.exceptions.RequestException:
            raise GitgenError("API 네트워크 연결 실패. 인터넷·프록시·인증서 설정을 확인하세요.") from None
        try:
            body = json.loads(chunks)
        except (ValueError, UnicodeDecodeError, RecursionError):
            raise ValidationError("API 응답이 유효한 JSON이 아닙니다.") from None
        return parse_response(body)
