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


def test_apply_safe_mode():
    files = ["file_a.py", "file_b.py"]
    diff = "API_KEY = 'sk-123456789012345678901234'\n+password = 'mypassword123'"
    safe_diff, safe_files = apply_safe_mode(diff, files)

    # 파일 목록 유지 확인
    assert safe_files == files
    # 민감 정보 마스킹 확인
    assert "[MASKED" in safe_diff
    assert "sk-1234" not in safe_diff
    assert "mypassword123" not in safe_diff


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


def test_check_range():
    import argparse
    import pytest
    from main import check_range

    temp_checker = check_range(float, 0.0, 2.0)
    assert temp_checker("0.0") == 0.0
    assert temp_checker("1.5") == 1.5
    assert temp_checker("2.0") == 2.0
    with pytest.raises(argparse.ArgumentTypeError):
        temp_checker("2.5")
    with pytest.raises(argparse.ArgumentTypeError):
        temp_checker("-0.5")
    with pytest.raises(argparse.ArgumentTypeError):
        temp_checker("not-a-number")

    token_checker = check_range(int, 16, 32768)
    assert token_checker("2000") == 2000
    with pytest.raises(argparse.ArgumentTypeError):
        token_checker("10")
    with pytest.raises(argparse.ArgumentTypeError):
        token_checker("40000")


def test_ai_client_check_api_key():
    from gitgen.ai_client import AIClient
    # API 키가 없을 때 False 반환
    client_empty = AIClient(api_key="")
    assert client_empty.check_api_key() is False

    # API 키가 있을 때 True 반환
    client_valid = AIClient(api_key="test-key-12345")
    assert client_valid.check_api_key() is True


def test_prompts_structure():
    from gitgen.prompts import get_commit_prompt, get_pr_prompt

    files = ["main.py", "gitgen/config.py"]
    diff = "+ def new_func(): pass"

    commit_msgs = get_commit_prompt(files, diff)
    assert len(commit_msgs) == 2
    assert commit_msgs[0]["role"] == "system"
    assert commit_msgs[1]["role"] == "user"
    assert "main.py" in commit_msgs[1]["content"]

    pr_msgs = get_pr_prompt("feature/branch", files, diff)
    assert len(pr_msgs) == 2
    assert pr_msgs[0]["role"] == "system"
    assert "feature/branch" in pr_msgs[1]["content"]


def test_repo_fixture_git_status_and_diff(repo):
    from gitgen.git_utils import get_git_status, get_git_diff

    # 초기 상태: 변경 사항 없음
    status = get_git_status()
    assert status["count"] == 0

    diff = get_git_diff()
    assert diff["diff"] == ""

    # 파일 수정
    app_file = repo / "app.py"
    app_file.write_text("print('after')\n", encoding="utf-8")

    status = get_git_status()
    assert status["count"] == 1
    assert "app.py" in status["files"]

    diff = get_git_diff()
    assert "print('after')" in diff["diff"]
    assert diff["line_count"] > 0


