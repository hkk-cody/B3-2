import os
import sys
import time

import requests

from gitgen.config import DEFAULT_BASE_URL, DEFAULT_MODEL, DEFAULT_TEMPERATURE


class AIClient:
    """OpenAI 호환 Chat Completions API 클라이언트"""

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
    ):
        self.api_key = (
            api_key
            or os.environ.get("AI_API_KEY")
            or os.environ.get("GEMINI_API_KEY")
        )
        self.base_url = (base_url or os.environ.get("AI_BASE_URL") or DEFAULT_BASE_URL).rstrip("/")
        self.model = model or os.environ.get("AI_MODEL") or DEFAULT_MODEL
        self.call_count = 0

    def check_api_key(self) -> bool:
        """API 키가 설정되어 있는지 확인합니다."""
        if not self.api_key or not self.api_key.strip():
            print("[ERROR] AI_API_KEY 환경변수가 설정되지 않았습니다.", file=sys.stderr)
            print("예) export AI_API_KEY=\"YOUR_KEY\"", file=sys.stderr)
            return False
        return True

    def request_completion(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
        temperature: float = DEFAULT_TEMPERATURE,
        max_tokens: int = 2000,
    ) -> str:
        """
        OpenAI 호환 Chat Completions API를 호출합니다.
        일시적 서버 오류(502/503/504) 발생 시 최대 1회 자동 재시도합니다.
        """
        if not self.check_api_key():
            sys.exit(1)

        target_model = model or self.model
        url = f"{self.base_url}/chat/completions"

        # gpt-5 reasoning 모델은 내부 reasoning 토큰을 소모하므로 최소 토큰을 보장
        effective_max_tokens = int(max_tokens)
        if "gpt-5" in target_model.lower() and effective_max_tokens < 1500:
            effective_max_tokens = 2000

        payload = {
            "model": target_model,
            "messages": messages,
            "max_tokens": effective_max_tokens,
        }

        # gpt-5 계열 모델은 temperature 커스텀 값 전달 시 502 에러가 발생하므로
        # 기본값(1.0)일 때만 전달하고, 나머지 모델은 자유롭게 설정
        if "gpt-5" in target_model.lower():
            if temperature == 1.0:
                payload["temperature"] = 1.0
        else:
            payload["temperature"] = float(temperature)

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "User-Agent": "AIGitGenerator/1.0",
        }

        max_retries = 2

        for attempt in range(max_retries):
            self.call_count += 1

            try:
                response = requests.post(url, headers=headers, json=payload, timeout=30)

                if response.status_code == 200:
                    data = response.json()
                    return data["choices"][0]["message"]["content"]

                err_msg = response.text
                try:
                    err_json = response.json()
                    if "error" in err_json:
                        err_msg = err_json["error"].get("message", err_msg)
                except Exception:
                    pass

                # 일시적 서버 오류인 경우 재시도
                if response.status_code in (500, 502, 503, 504) and attempt < max_retries - 1:
                    time.sleep(1.5)
                    continue

                raise RuntimeError(f"HTTP {response.status_code} - {err_msg}")

            except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
                if attempt < max_retries - 1:
                    time.sleep(1.5)
                    continue
                raise RuntimeError(f"네트워크 연결 오류: {str(e)}")

            except RuntimeError:
                raise

            except Exception as e:
                if attempt < max_retries - 1:
                    time.sleep(1.5)
                    continue
                raise RuntimeError(f"API 요청 중 오류 발생: {str(e)}")

        raise RuntimeError("API 요청 재시도 횟수를 초과했습니다.")

