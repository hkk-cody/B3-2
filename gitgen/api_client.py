"""Codyssey OpenAI 호환 Chat Completions API 클라이언트."""

import json

from .config import DEFAULT_BASE_URL, normalize_base_url
from .errors import GitgenError, ValidationError
from .safety import dumps

ENDPOINT = DEFAULT_BASE_URL + "/chat/completions"


def encode_payload(payload: dict) -> bytes:
    """페이로드를 UTF-8 바이트로 직렬화합니다."""
    return dumps(payload).encode("utf-8")


def parse_response(body: object) -> str:
    """API 응답 JSON에서 생성된 텍스트 내용을 추출합니다."""
    if not isinstance(body, dict):
        raise ValidationError("API 응답이 JSON 객체가 아닙니다.")
    if body.get("error"):
        raise GitgenError("API가 오류를 반환했습니다. Codyssey 콘솔의 키·모델 권한을 확인하세요.")

    choices = body.get("choices")
    if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
        raise ValidationError("API 응답에 choices 배열이 없습니다.")

    choice = choices[0]
    if choice.get("finish_reason") == "length":
        raise GitgenError("AI 응답이 완료되지 않았습니다. --max-tokens를 늘리거나 변경 범위를 줄이세요.")
    if choice.get("finish_reason") == "content_filter" or (choice.get("message") and choice["message"].get("refusal")):
        raise GitgenError("AI가 초안 생성을 거절했습니다. 입력 내용을 검토하세요.")

    message = choice.get("message")
    if not isinstance(message, dict) or not message.get("content"):
        raise ValidationError("API 응답에 생성된 텍스트가 없습니다.")
    return message["content"]


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

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        self.calls += 1

        try:
            response = requests.post(
                self.endpoint,
                headers=headers,
                data=encode_payload(payload),
                timeout=30,
                allow_redirects=False,
            )
            code = response.status_code
            if not 200 <= code < 300:
                status_messages = {
                    400: "요청 설정 오류. --temperature를 생략하거나 지원 파라미터를 확인하세요.",
                    401: "인증 실패. Codyssey에서 발급한 API Key를 확인하세요.",
                    403: "접근 거부. 모델 사용 권한을 확인하세요.",
                    404: "API 주소 또는 모델을 찾을 수 없습니다.",
                    429: "요청 한도 초과. 잠시 후 다시 시도하세요.",
                }
                msg = status_messages.get(code, f"API 오류 (HTTP {code})")
                raise GitgenError(f"HTTP {code}: {msg}")

            raw_body = getattr(response, "body", None)
            if raw_body is None:
                raw_body = response.content
            body = json.loads(raw_body)
        except requests.exceptions.Timeout:
            raise GitgenError("API 요청 시간 초과(30초). 네트워크 상태를 확인하세요.") from None
        except requests.exceptions.RequestException:
            raise GitgenError("API 네트워크 연결에 실패했습니다.") from None
        except ValueError:
            raise ValidationError("API 응답이 유효한 JSON이 아닙니다.") from None

        return parse_response(body)
