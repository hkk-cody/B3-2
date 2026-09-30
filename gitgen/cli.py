import argparse
import math
import os
from pathlib import Path
import re
import sys

from .api_client import ApiClient, encode_payload
from .config import DEFAULT_MODEL, load_settings
from .errors import GitgenError
from .generation import generate
from .git_context import collect
from .prompts import build_payload
from .render import render
from .safety import prepare, redact


def temperature(value: str) -> float:
    try:
        number = float(value)
    except ValueError:
        raise argparse.ArgumentTypeError("temperature는 숫자여야 합니다.") from None
    if not math.isfinite(number) or not 0 <= number <= 2:
        raise argparse.ArgumentTypeError("temperature는 0~2 범위여야 합니다.")
    return number


def token_limit(value: str) -> int:
    try:
        number = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError("max-tokens는 정수여야 합니다.") from None
    if not 16 <= number <= 32768:
        raise argparse.ArgumentTypeError("max-tokens는 16~32768 범위여야 합니다.")
    return number


def model_name(value: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}", value):
        raise argparse.ArgumentTypeError("model은 128자 이내의 영문·숫자·점·밑줄·콜론·하이픈으로 입력하세요.")
    return value


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description="Git 변경 사항으로 커밋 메시지·PR 초안을 만듭니다.")
    commands = result.add_subparsers(dest="command", required=True)
    for command, description in [("commit", "커밋 메시지 생성"), ("pr", "PR 제목·본문 생성")]:
        sub = commands.add_parser(command, help=description, description=description)
        sub.add_argument("--model", "-model", type=model_name, default=None, help=f"Codyssey 모델 (AI_MODEL 또는 기본 {DEFAULT_MODEL})")
        sub.add_argument("--temperature", "-temperature", type=temperature, default=None, help="생성 무작위성 0~2 (기본: 서버 기본값, 지원 모델에서만 지정)")
        sub.add_argument("--max-tokens", "-max-tokens", type=token_limit, default=4096, help="추론 포함 생성 토큰 상한 (기본: 4096)")
        sub.add_argument("--safe-mode", "-safe-mode", action="store_true", default=False, help="민감정보 마스킹·전송량 제한 활성화 (기본: 비활성)")
        sub.add_argument("--dry-run", action="store_true", help="API 호출 없이 전송할 요청 본문 미리보기 (Key 불필요)")
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    key = os.environ.get("AI_API_KEY", "").strip()
    client = None

    def log(level: str, message: str) -> None:
        print(f"[{level}] {redact(message, key)}", file=sys.stderr)

    try:
        # 1. Git 저장소 상태 수집 및 설정 로드
        context = collect(Path.cwd())
        settings = load_settings(context.root)
        key = settings.api_key

        try:
            model = model_name(args.model or settings.model)
        except argparse.ArgumentTypeError as exc:
            raise GitgenError(f"AI_MODEL 설정 오류: {exc}") from None

        log("INFO", f"Git status 수집 완료: {len(context.changes)}개 파일 변경 감지")
        for change in context.changes[:10]:
            # repr prevents file names from injecting extra log lines.
            log("INFO", f"{change.status} {change.path!r}")

        # 2. 변경 사항 존재 여부 및 staged diff 확인
        if not context.changes:
            log("INFO", "변경 사항이 없습니다.")
            return 0

        untracked = sum(change.untracked for change in context.changes)
        if untracked:
            log("INFO", f"추적되지 않은 파일 {untracked}개는 내용 분석에서 제외합니다. 필요하면 git add 후 실행하세요.")

        if not any(change.layers() for change in context.changes):
            if all(change.untracked for change in context.changes):
                log("INFO", "추적되지 않은 파일만 있어 분석할 diff가 없습니다. git add 후 다시 실행하세요.")
            else:
                log("INFO", "분석할 staged 변경 사항이 없습니다. git add로 변경을 stage한 뒤 다시 실행하세요.")
            return 0

        # 3. 안전 모드 처리 (민감정보 마스킹 및 전송 한도 적용)
        safe = prepare(context, safe_mode=args.safe_mode, api_key=key)
        if args.safe_mode:
            log("INFO", (
                f"안전 모드 적용: diff {safe.line_count}줄, "
                f"민감 파일 제외 {safe.excluded_files}개, "
                f"한도 제외 {safe.omitted_files}개, "
                f"잘린 diff {safe.truncated_blocks}개"
            ))
        else:
            log("INFO", f"안전 모드 미적용: diff {safe.line_count}줄 전송 준비 (필요 시 --safe-mode 사용)")

        if not safe.data["changes"]:
            log("INFO", "전송 가능한 diff가 없습니다. 변경 범위와 안전 모드 제외 대상을 확인하세요.")
            return 0

        if safe.data["partial"]:
            log("WARN", "부분 분석: 일부 파일 또는 diff가 제외되거나 잘렸습니다.")

        # 4. AI 요청 페이로드 구성 및 Dry-run 처리
        payload = build_payload(args.command, safe.data, model, args.temperature, args.max_tokens)
        if args.dry_run:
            log("INFO", f"요청 주소: {settings.base_url}/chat/completions")
            print("--- API Request Preview (외부 전송 없음) ---")
            print(encode_payload(payload).decode("utf-8"))
            return 0

        # 5. API Key 검증 및 AI API 호출
        if not key:
            raise GitgenError("AI_API_KEY가 설정되지 않았습니다. 프로젝트 루트 .env의 AI_API_KEY 항목을 채우거나 환경변수로 설정하세요.")
        if not key.isascii() or any(ch.isspace() or ord(ch) < 32 or ord(ch) == 127 for ch in key):
            raise GitgenError("AI_API_KEY 형식이 올바르지 않습니다. 공백 없이 API Key만 설정하세요.")

        client = ApiClient(key, settings.base_url)
        draft = generate(args.command, payload, client, log)

        # 6. 결과 출력 및 검토 권장 안내
        if args.command == "commit" and len(draft["title"]) > 50:
            log("WARN", "커밋 제목은 50자 이내를 권장합니다. 현재 제목은 최대 72자 규칙을 충족합니다.")

        print(render(args.command, draft, partial=safe.data["partial"]))
        log("DONE", "초안 생성 완료. 내용과 테스트 사실을 검토한 뒤 복사하여 적용하세요.")
        return 0

    except GitgenError as exc:
        log("ERROR", str(exc))
        return 1
    except KeyboardInterrupt:
        log("ERROR", "사용자가 실행을 중단했습니다.")
        return 130
    finally:
        log("INFO", f"API 호출 횟수: {client.calls if client else 0}회")
