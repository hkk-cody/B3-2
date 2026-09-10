import json
import os

import pytest
import requests

from conftest import response_for
from gitgen.cli import main
from gitgen.config import DEFAULT_BASE_URL, DEFAULT_MODEL, load_api_key, load_settings, normalize_base_url
from gitgen.errors import GitgenError


@pytest.mark.parametrize("content", [
    "AI_API_KEY=fake-dotenv-key\n",
    'AI_API_KEY="fake-dotenv-key" # comment\n',
    "export AI_API_KEY='fake-dotenv-key'\n",
    "\ufeffAI_API_KEY=fake-dotenv-key\r\n",
])
def test_load_dotenv_key(tmp_path, content):
    (tmp_path / ".env").write_text(content, encoding="utf-8")
    assert load_api_key(tmp_path) == "fake-dotenv-key"
    assert os.environ["AI_API_KEY"] == "fake-dotenv-key"


def test_existing_environment_wins(tmp_path, monkeypatch):
    monkeypatch.setenv("AI_API_KEY", "fake-environment-key")
    (tmp_path / ".env").write_text("AI_API_KEY=fake-file-key\n")
    assert load_api_key(tmp_path) == "fake-environment-key"


def test_empty_environment_falls_back_to_dotenv(tmp_path, monkeypatch):
    monkeypatch.setenv("AI_API_KEY", "")
    (tmp_path / ".env").write_text("AI_API_KEY=fake-file-key\n")
    assert load_api_key(tmp_path) == "fake-file-key"


@pytest.mark.parametrize("content", [None, "AI_API_KEY=\n", "AI_API_KEY\n", "# comment only\n"])
def test_missing_or_empty_dotenv(tmp_path, content):
    if content is not None:
        (tmp_path / ".env").write_text(content)
    assert load_api_key(tmp_path) == ""


def test_does_not_expand_or_load_other_variables(tmp_path):
    (tmp_path / ".env").write_text('AI_API_KEY="${DOTENV_UNUSED_VALUE}"\nDOTENV_UNUSED_VALUE=not-imported\n')
    assert load_api_key(tmp_path) == "${DOTENV_UNUSED_VALUE}"
    assert "DOTENV_UNUSED_VALUE" not in os.environ


def test_parent_directory_not_searched(tmp_path):
    (tmp_path / ".env").write_text("AI_API_KEY=fake-parent-key\n")
    child = tmp_path / "child"
    child.mkdir()
    assert load_api_key(child) == ""


def test_invalid_encoding_has_safe_error(tmp_path):
    (tmp_path / ".env").write_bytes(b"AI_API_KEY=DO_NOT_LOG\xff")
    with pytest.raises(GitgenError, match="UTF-8") as exc:
        load_api_key(tmp_path)
    assert "DO_NOT_LOG" not in str(exc.value)


def test_dotenv_directory_rejected(tmp_path):
    (tmp_path / ".env").mkdir()
    with pytest.raises(GitgenError, match="텍스트 파일"):
        load_api_key(tmp_path)


def test_cli_uses_dotenv_and_redacts_request(repo, monkeypatch, capsys, commit_draft):
    (repo / ".env").write_text("AI_API_KEY=fake-dotenv-key\n")
    (repo / "app.py").write_text("print('fake-dotenv-key')\n")
    seen = []
    def post(*args, **kwargs):
        seen.append(kwargs)
        return response_for(commit_draft)
    monkeypatch.setattr(requests, "post", post)
    assert main(["commit"]) == 0
    out, err = capsys.readouterr()
    assert "fake-dotenv-key" not in out + err
    assert seen[0]["headers"]["Authorization"] == "Bearer fake-dotenv-key"
    assert "fake-dotenv-key" not in seen[0]["data"].decode()


def test_dry_run_redacts_dotenv_key_without_api(repo, capsys):
    (repo / ".env").write_text("AI_API_KEY=fake-dotenv-key\n")
    (repo / "app.py").write_text("print('fake-dotenv-key')\n")
    assert main(["pr", "--dry-run"]) == 0
    out, err = capsys.readouterr()
    assert "fake-dotenv-key" not in out + err
    assert "API 호출 횟수: 0회" in err
    assert json.loads(out.split("\n", 1)[1])["messages"][1]["content"]


def test_codyssey_defaults(tmp_path):
    settings = load_settings(tmp_path)
    assert settings.base_url == DEFAULT_BASE_URL == "https://copa.codyssey.kr/v1"
    assert settings.model == DEFAULT_MODEL == "gpt-5-mini"


def test_dotenv_connection_settings(tmp_path):
    (tmp_path / ".env").write_text("AI_API_KEY=fake-key\nAI_BASE_URL=https://copa.codyssey.kr\nAI_MODEL=gpt-5.4-mini\n")
    settings = load_settings(tmp_path)
    assert settings.base_url == "https://copa.codyssey.kr/v1" and settings.model == "gpt-5.4-mini"
    assert "fake-key" not in repr(settings)


def test_environment_connection_settings_win(tmp_path, monkeypatch):
    (tmp_path / ".env").write_text("AI_BASE_URL=https://copa.codyssey.kr/v1\nAI_MODEL=gpt-5-mini\n")
    monkeypatch.setenv("AI_BASE_URL", "https://example.invalid/v1")
    monkeypatch.setenv("AI_MODEL", "gpt-5.4-mini")
    settings = load_settings(tmp_path)
    assert settings.base_url == "https://example.invalid/v1" and settings.model == "gpt-5.4-mini"


@pytest.mark.parametrize("base_url", [
    "http://copa.codyssey.kr/v1", "https://user:secret@copa.codyssey.kr/v1",
    "https://copa.codyssey.kr/v1?api_key=secret", "https://copa.codyssey.kr/v1#secret",
    "https://copa.codyssey.kr/v1/chat/completions", "https://copa.codyssey.kr/v1/responses",
    "https://copa.codyssey.kr:invalid/v1", "https://copa.codyssey.kr/\n/v1", "file:///tmp/api",
])
def test_invalid_api_address_has_safe_error(base_url):
    with pytest.raises(GitgenError, match="AI_BASE_URL") as error:
        normalize_base_url(base_url)
    assert "secret" not in str(error.value)


def test_cli_model_overrides_dotenv_and_shows_endpoint(repo, capsys):
    (repo / ".env").write_text("AI_MODEL=gpt-5-mini\nAI_BASE_URL=https://copa.codyssey.kr\n")
    (repo / "app.py").write_text("changed\n")
    assert main(["commit", "--dry-run", "--model", "gpt-5.4-mini"]) == 0
    out, err = capsys.readouterr()
    assert json.loads(out.split("\n", 1)[1])["model"] == "gpt-5.4-mini"
    assert "https://copa.codyssey.kr/v1/chat/completions" in err


def test_invalid_dotenv_model_fails_before_api(repo, capsys):
    (repo / ".env").write_text('AI_MODEL="invalid model name"\n')
    (repo / "app.py").write_text("changed\n")
    assert main(["commit", "--dry-run"]) == 1
    assert "AI_MODEL 설정 오류" in capsys.readouterr().err
