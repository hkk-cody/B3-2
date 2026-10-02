"""
AI 기반 Git 커밋 메시지 및 PR 초안 자동 생성 CLI 도우미

사용법:
    python main.py commit                    # 커밋 메시지 자동 생성
    python main.py pr                        # PR 제목/본문 초안 생성
    python main.py commit --safe-mode        # 안전 모드 (민감정보 마스킹)
    python main.py commit --model gpt-5-mini # 모델 변경
"""

import argparse
from collections.abc import Callable
import sys

from gitgen import __version__
from gitgen.ai_client import AIClient
from gitgen.config import (
    DEFAULT_COMMIT_MAX_TOKENS,
    DEFAULT_MODEL,
    DEFAULT_PR_MAX_TOKENS,
    DEFAULT_TEMPERATURE,
)
from gitgen.git_utils import (
    get_current_branch,
    get_git_diff,
    get_git_status,
    is_git_repo,
)
from gitgen.prompts import get_commit_prompt, get_pr_prompt
from gitgen.validator import (
    apply_safe_mode,
    validate_and_format_commit,
    validate_and_format_pr,
)


def collect_git_changes(args: argparse.Namespace) -> tuple[list[str], str]:
    """Git status 및 diff를 수집하고, safe-mode가 활성화되어 있으면 적용합니다."""
    status_info = get_git_status()
    file_count = status_info["count"]
    changed_files = status_info["files"]

    diff_info = get_git_diff()
    diff_text = diff_info["diff"]
    line_count = diff_info["line_count"]

    # 변경 사항이 없을 경우 종료
    if file_count == 0 and line_count == 0:
        print("[INFO] 변경 사항이 없습니다. 작업을 생성하지 않고 종료합니다.")
        sys.exit(0)

    print(f"[INFO] Git status 수집 완료: {file_count}개 파일 변경 감지")
    print(f"[INFO] Git diff 수집 완료: {line_count}줄")

    # safe-mode 처리
    if args.safe_mode:
        print("[INFO] 안전 모드(Safe Mode) 활성화: 민감 정보 마스킹 적용")
        diff_text, changed_files = apply_safe_mode(diff_text, changed_files)

    return changed_files, diff_text


def request_ai_generation(messages: list[dict], args: argparse.Namespace) -> str:
    """AI API 클라이언트를 호출하여 생성 결과를 반환합니다."""
    safe_mode_str = "ON" if args.safe_mode else "OFF"
    print(
        f"[INFO] 실행 파라미터: model={args.model}, temp={args.temperature}, max_tokens={args.max_tokens}, safe_mode={safe_mode_str}"
    )

    client = AIClient(model=args.model)
    if not client.check_api_key():
        sys.exit(1)

    print("[INFO] AI API 요청 중...")
    try:
        raw_output = client.request_completion(
            messages=messages,
            model=args.model,
            temperature=args.temperature,
            max_tokens=args.max_tokens,
        )
    except Exception as e:
        print(f"[ERROR] AI API 호출 실패: {str(e)}", file=sys.stderr)
        sys.exit(1)

    print(f"[INFO] AI API 호출 횟수: {client.call_count}회")
    return raw_output


def handle_commit(args: argparse.Namespace) -> None:
    """commit 서브커맨드 핸들러: 커밋 메시지 자동 생성"""
    changed_files, diff_text = collect_git_changes(args)
    messages = get_commit_prompt(changed_files, diff_text)
    raw_output = request_ai_generation(messages, args)

    print("[DONE] 커밋 메시지 생성 완료\n")
    formatted_commit = validate_and_format_commit(raw_output)

    print("--- Commit Message ---")
    print(formatted_commit)
    print("----------------------")


def handle_pr(args: argparse.Namespace) -> None:
    """pr 서브커맨드 핸들러: PR 제목/본문 초안 자동 생성"""
    branch_name = get_current_branch()
    print(f"[INFO] 현재 브랜치: {branch_name}")

    changed_files, diff_text = collect_git_changes(args)
    messages = get_pr_prompt(branch_name, changed_files, diff_text)
    raw_output = request_ai_generation(messages, args)

    print("[DONE] PR 초안 생성 완료\n")
    title, body = validate_and_format_pr(raw_output)

    print("--- PR Title ---")
    print(title)
    print("\n--- PR Body ---")
    print(body)
    print("----------------")


def check_range(
    val_type: type, min_val: float | int, max_val: float | int
) -> Callable[[str], float | int]:
    """지정된 범위(min_val ~ max_val) 내의 값인지 검증하는 argparse 타입 검사기"""
    def validator(value: str) -> float | int:
        try:
            val = val_type(value)
        except ValueError:
            raise argparse.ArgumentTypeError(f"올바른 숫자가 아닙니다: {value}")
        if not (min_val <= val <= max_val):
            raise argparse.ArgumentTypeError(
                f"{min_val} ~ {max_val} 사이의 값이어야 합니다 (입력값: {value})"
            )
        return val
    return validator


def add_common_arguments(parser: argparse.ArgumentParser, default_max_tokens: int) -> None:
    """공통 CLI 옵션들을 추가합니다."""
    parser.add_argument(
        "--model",
        "-model",
        type=str,
        default=DEFAULT_MODEL,
        help=f"사용할 AI 모델 이름 (기본값: {DEFAULT_MODEL})",
    )
    parser.add_argument(
        "--temperature",
        "-temperature",
        type=check_range(float, 0.0, 2.0),
        default=DEFAULT_TEMPERATURE,
        help=f"샘플링 온도 (범위: 0.0 ~ 2.0, 기본값: {DEFAULT_TEMPERATURE})",
    )
    parser.add_argument(
        "--max-tokens",
        "-max-tokens",
        type=check_range(int, 16, 32768),
        default=default_max_tokens,
        help=f"생성할 최대 토큰 수 (범위: 16 ~ 32768, 기본값: {default_max_tokens})",
    )
    parser.add_argument(
        "--safe-mode",
        "-safe-mode",
        action="store_true",
        help="민감 정보(API 키, 패스워드, 이메일 등) 마스킹 안전 모드",
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Git 변경 사항을 기반으로 커밋 메시지와 PR 초안을 자동 생성하는 AI 도우미"
    )
    parser.add_argument(
        "-v", "--version", action="version", version=f"%(prog)s {__version__}"
    )
    subparsers = parser.add_subparsers(
        dest="command", required=True, help="실행할 명령어 (commit 또는 pr)"
    )

    # 1. commit 서브커맨드
    commit_parser = subparsers.add_parser("commit", help="Git 변경 사항을 기반으로 커밋 메시지를 생성합니다.")
    add_common_arguments(commit_parser, default_max_tokens=DEFAULT_COMMIT_MAX_TOKENS)

    # 2. pr 서브커맨드
    pr_parser = subparsers.add_parser("pr", help="Git 변경 사항을 기반으로 PR 제목과 본문 초안을 생성합니다.")
    add_common_arguments(pr_parser, default_max_tokens=DEFAULT_PR_MAX_TOKENS)

    args = parser.parse_args()

    # Git 저장소 여부 확인 (공통 가드)
    if not is_git_repo():
        print("[ERROR] Git 저장소가 아닙니다. Git 저장소 루트에서 실행해주세요.", file=sys.stderr)
        sys.exit(1)

    if args.command == "commit":
        handle_commit(args)
    elif args.command == "pr":
        handle_pr(args)


if __name__ == "__main__":
    main()
