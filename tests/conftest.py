import json
import os
from pathlib import Path
import subprocess

import pytest
import requests


def git(root: Path, *arguments: str) -> str:
    env = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
    return subprocess.run(
        ["git", "-c", "user.name=Gitgen Test", "-c", "user.email=test@example.invalid",
         "-c", "commit.gpgsign=false", "-c", "core.hooksPath=/dev/null", *arguments],
        cwd=root, env=env, capture_output=True, text=True, check=True,
    ).stdout


@pytest.fixture
def repo(tmp_path, monkeypatch):
    git(tmp_path, "init", "-b", "main")
    (tmp_path / "app.py").write_text("print('before')\n", encoding="utf-8")
    git(tmp_path, "add", "app.py")
    git(tmp_path, "commit", "-m", "initial")
    monkeypatch.chdir(tmp_path)
    return tmp_path


@pytest.fixture(autouse=True)
def no_real_api(monkeypatch):
    # .env loading sets a process variable; isolate it between test cases.
    monkeypatch.setattr(os, "environ", os.environ.copy())
    monkeypatch.delenv("AI_API_KEY", raising=False)
    monkeypatch.delenv("AI_BASE_URL", raising=False)
    monkeypatch.delenv("AI_MODEL", raising=False)

    def reject(*args, **kwargs):
        pytest.fail("Tests must not make real API requests")

    monkeypatch.setattr(requests, "post", reject)


@pytest.fixture
def commit_draft():
    return {"summary": "출력 메시지를 변경했습니다.", "title": "fix: 출력 메시지 수정", "changes": ["app.py의 출력 메시지 변경"]}


@pytest.fixture
def pr_draft():
    return {
        "summary": "출력 메시지를 변경했습니다.", "title": "fix: 출력 메시지 수정",
        "why": ["변경 배경 확인 필요"], "what": ["app.py의 출력 메시지 변경"],
        "how_to_test": ["미실행: python app.py로 변경된 출력 확인"],
    }


class Response:
    def __init__(self, body, status=200):
        self.status_code = status
        self.body = body if isinstance(body, bytes) else json.dumps(body).encode()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def iter_content(self, chunk_size):
        for offset in range(0, len(self.body), chunk_size):
            yield self.body[offset:offset + chunk_size]


def response_for(draft):
    return Response({"choices": [{
        "index": 0, "finish_reason": "stop",
        "message": {"role": "assistant", "content": json.dumps(draft)},
    }]})
