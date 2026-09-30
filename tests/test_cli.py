import json
from pathlib import Path
import subprocess
import sys

import pytest
import requests

from tests.conftest import git, response_for
from gitgen.cli import main


def modify(repo):
    (repo / "app.py").write_text("print('after')\n")
    git(repo, "add", "app.py")


def test_no_changes_needs_no_key(repo, capsys):
    assert main(["commit"]) == 0
    out, err = capsys.readouterr()
    assert not out and "변경 사항이 없습니다" in err and "0회" in err


def test_untracked_only_needs_no_key(repo, capsys):
    (repo / "untracked.txt").write_text("not sent")
    assert main(["commit"]) == 0
    assert "분석할 diff가 없습니다" in capsys.readouterr().err


def test_unstaged_only_needs_staging(repo, capsys):
    (repo / "app.py").write_text("print('unstaged only')\n")
    assert main(["commit"]) == 0
    assert "staged 변경 사항이 없습니다" in capsys.readouterr().err


def test_missing_key(repo, capsys):
    modify(repo)
    assert main(["commit"]) == 1
    out, err = capsys.readouterr()
    assert not out and "AI_API_KEY" in err and "0회" in err


def test_all_excluded_needs_no_key(repo, capsys):
    (repo / ".env").write_text("secret\n")
    git(repo, "add", ".env")
    assert main(["pr", "--safe-mode"]) == 0
    assert "전송 가능한 diff가 없습니다" in capsys.readouterr().err


def test_dry_run_and_legacy_flags(repo, capsys):
    modify(repo)
    assert main(["pr", "--dry-run", "-model", "gpt-4.1-mini", "-temperature", "0.1", "-max-tokens", "1500", "-safe-mode"]) == 0
    out, err = capsys.readouterr()
    body = json.loads(out.split("\n", 1)[1])
    assert body["temperature"] == 0.1 and body["max_completion_tokens"] == 1500
    assert "Authorization" not in body and "0회" in err


@pytest.mark.parametrize("command", ["commit", "pr"])
def test_end_to_end_mocked_api(repo, monkeypatch, capsys, command, commit_draft, pr_draft):
    modify(repo)
    monkeypatch.setenv("AI_API_KEY", "fake-key")
    draft = commit_draft if command == "commit" else pr_draft
    monkeypatch.setattr(requests, "post", lambda *args, **kwargs: response_for(draft))
    assert main([command]) == 0
    out, err = capsys.readouterr()
    assert "--- Change Summary ---" in out and draft["title"] in out
    assert "API 호출 횟수: 1회" in err and "[INFO]" not in out
    if command == "pr":
        for section in ["Why", "What", "How to Test"]:
            assert f"## {section}\n- " in out
        assert "변경 배경 확인 필요" in out and "미실행" in out


def test_partial_analysis_in_pr(repo, monkeypatch, capsys, pr_draft):
    (repo / "app.py").write_text("\n".join(f"line{i}" for i in range(500)))
    git(repo, "add", "app.py")
    monkeypatch.setenv("AI_API_KEY", "fake-key")
    monkeypatch.setattr(requests, "post", lambda *a, **k: response_for(pr_draft))
    assert main(["pr", "--safe-mode"]) == 0
    assert "부분 분석" in capsys.readouterr().out


@pytest.mark.parametrize("args", [
    ["--temperature", "nan"], ["--temperature", "-1"], ["--temperature", "3"],
    ["--max-tokens", "0"], ["--max-tokens", "abc"], ["--model", "a\nb"],
])
def test_invalid_options_fail_before_api(args):
    with pytest.raises(SystemExit) as exc:
        main(["commit", *args])
    assert exc.value.code == 2


def test_actual_entrypoint_dry_run(repo):
    modify(repo)
    entrypoint = Path(__file__).resolve().parents[1] / "main.py"
    completed = subprocess.run([sys.executable, str(entrypoint), "commit", "--dry-run"], cwd=repo, capture_output=True, text=True)
    assert completed.returncode == 0
    assert "API Request Preview" in completed.stdout
    assert "API 호출 횟수: 0회" in completed.stderr


def test_safe_mode_on_off_difference(repo, capsys):
    (repo / "secret.py").write_text("password = 'super_secret_password'\n")
    git(repo, "add", "secret.py")

    # 1. 안전 모드 OFF (기본값): 비밀번호가 그대로 요청 본문에 포함됨
    assert main(["commit", "--dry-run"]) == 0
    out_off, err_off = capsys.readouterr()
    assert "super_secret_password" in out_off
    assert "안전 모드 미적용" in err_off

    # 2. 안전 모드 ON (--safe-mode 지정): 비밀번호가 [REDACTED]로 마스킹됨
    assert main(["commit", "--dry-run", "--safe-mode"]) == 0
    out_on, err_on = capsys.readouterr()
    assert "super_secret_password" not in out_on
    assert "[REDACTED]" in out_on
    assert "안전 모드 적용" in err_on
