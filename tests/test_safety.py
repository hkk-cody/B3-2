"""안전 모드(민감정보 마스킹, 파일 수 및 diff 줄 수 제한) 검증."""

import pytest

from tests.conftest import git
from gitgen.git_context import collect
from gitgen.prompts import build_payload
from gitgen.api_client import encode_payload
from gitgen.safety import excluded, prepare, redact


@pytest.mark.parametrize("secret", [
    'sk-proj-FAKE_ONLY_123456789', 'ghp_FAKE_TOKEN_12345', 'AKIA1234567890123456',
    'alice@example.com', '"password": "fake-password-value"', "token = 'fake-token-value'",
    'Authorization: Bearer fake-token-value', 'https://user:fake-password-value@example.invalid/',
    '-----BEGIN RSA PRIVATE KEY-----\nFAKE_CONTENT\n-----END RSA PRIVATE KEY-----',
])
def test_known_patterns_are_redacted(secret):
    """API 키, 토큰, 이메일, 패스워드, 개인키 등 민감정보 마스킹 확인."""
    result = redact(secret)
    assert "[REDACTED" in result
    assert "FAKE_CONTENT" not in result
    assert "fake-password-value" not in result
    assert "fake-token-value" not in result
    assert "alice@example.com" not in result


def test_exact_api_key_redacted():
    """전달받은 사용자의 API Key가 본문에서 마스킹되는지 확인."""
    assert "fake-unusual-key" not in redact("text fake-unusual-key", "fake-unusual-key")


@pytest.mark.parametrize("path", [
    ".env", "config/.env.prod", "config/dev.env",
    ".ssh/id_rsa", "private.key", ".aws/credentials", "cert.pem"
])
def test_excluded_paths(path):
    """.env, 비밀키 등 민감 파일이 제외 대상인지 확인."""
    assert excluded(path)


def test_secrets_removed_from_full_request(repo):
    """실제 git diff 수집 후 마스킹 및 민감 파일 제외 동작 확인."""
    (repo / "app.py").write_text('API_KEY = "fake-unusual-key"\nemail = "alice@example.com"\n')
    (repo / ".env").write_text("PASSWORD=DO_NOT_SEND\n")
    git(repo, "add", ".env", "app.py")
    safe = prepare(collect(repo), api_key="fake-unusual-key")
    encoded = encode_payload(build_payload("pr", safe.data, "gpt-4.1-mini", 0.2, 1200)).decode()
    assert "fake-unusual-key" not in encoded
    assert "alice@example.com" not in encoded
    assert "DO_NOT_SEND" not in encoded
    assert safe.excluded_files == 1 and safe.data["partial"]


def test_renamed_secret_stays_excluded(repo):
    """.env 이름 변경 파일도 제외 대상인지 확인."""
    (repo / ".env").write_text("secret data\n")
    git(repo, "add", ".env")
    git(repo, "commit", "-m", "fixture only")
    git(repo, "config", "status.renames", "false")
    git(repo, "mv", ".env", "normal.txt")
    safe = prepare(collect(repo))
    assert safe.excluded_files == 1
    assert safe.data["changes"] == []


@pytest.mark.parametrize("count", [10, 11])
def test_file_limit(repo, count):
    """과제 요구사항: 파일 최대 10개 제한 확인."""
    for number in range(count):
        (repo / f"{number:02}.txt").write_text("new\n")
    git(repo, "add", ".")
    safe = prepare(collect(repo))
    assert len({block["path"] for block in safe.data["changes"]}) == min(10, count)
    assert safe.omitted_files == max(0, count - 10)
    assert safe.data["partial"] == (count > 10)


@pytest.mark.parametrize("line_count", [200, 201])
def test_exact_line_boundary(repo, monkeypatch, line_count):
    """과제 요구사항: diff 최대 200줄 제한 확인."""
    (repo / "app.py").write_text("changed\n")
    git(repo, "add", "app.py")
    monkeypatch.setattr("gitgen.safety.read_diff", lambda *a: "line\n" * line_count)
    safe = prepare(collect(repo))
    assert safe.line_count == 200
    assert safe.data["partial"] == (line_count > 200)


def test_staged_only_does_not_read_unstaged_content(repo):
    """staged 상태의 변경만 분석하는지 확인."""
    from gitgen.safety import dumps
    (repo / "app.py").write_text("staged\n")
    git(repo, "add", "app.py")
    (repo / "app.py").write_text("UNSTAGED_CONTENT\n")
    assert "UNSTAGED_CONTENT" not in dumps(prepare(collect(repo)).data)
