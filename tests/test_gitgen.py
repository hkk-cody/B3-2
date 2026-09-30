from gitgen.validator import (
    apply_safe_mode,
    mask_sensitive_info,
    validate_and_format_commit,
    validate_and_format_pr,
)
from gitgen.git_utils import is_git_repo, get_current_branch


def test_mask_sensitive_info():
    text = "API_KEY = 'sk-123456789012345678901234' and contact user@example.com"
    masked = mask_sensitive_info(text)
    assert "[MASKED" in masked
    assert "sk-1234" not in masked
    assert "user@example.com" not in masked


def test_apply_safe_mode_limits():
    files = [f"file_{i}.py" for i in range(15)]
    diff = "\n".join([f"+line {i}" for i in range(250)])
    safe_diff, safe_files = apply_safe_mode(diff, files, max_files=10, max_lines=200)

    # 10개 파일 + 생략 안내문구
    assert len(safe_files) == 11
    # 200줄 이내로 잘림
    assert len(safe_diff.splitlines()) <= 205
    assert "safe-mode" in safe_diff


def test_validate_and_format_commit():
    raw = "```\nfeat: 새로운 기능 추가\n\n- 기능 구현 완료\n```"
    result = validate_and_format_commit(raw)
    assert result.startswith("feat: 새로운 기능 추가")
    assert "```" not in result
    assert "- 기능 구현 완료" in result


def test_validate_and_format_pr():
    raw = """
Title: feat: PR 제목 테스트
## Why
- 이유 설명
## What
- 변경 사항
## How to Test
- 테스트 방법
"""
    title, body = validate_and_format_pr(raw)
    assert title == "feat: PR 제목 테스트"
    assert "## Why" in body
    assert "## What" in body
    assert "## How to Test" in body


def test_git_utils_in_repo():
    # 현재 디렉토리는 git 저장소 내부
    assert is_git_repo() is True
    assert isinstance(get_current_branch(), str)
