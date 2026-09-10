import json

import pytest

from conftest import git
from gitgen.git_context import collect
from gitgen.prompts import build_payload
from gitgen.api_client import ApiClient, encode_payload
from gitgen.generation import generate
from gitgen.safety import MAX_DATA_CHARS, dumps, excluded, prepare, redact


@pytest.mark.parametrize("secret", [
    'sk-proj-FAKE_ONLY_123456789', 'ghp_FAKE_TOKEN_12345', 'AKIA1234567890123456',
    'alice@example.com', '"password": "fake-password-value"', "token = 'fake-token-value'",
    'Authorization: Bearer fake-token-value', 'https://user:fake-password-value@example.invalid/',
    '-----BEGIN RSA PRIVATE KEY-----\nFAKE_CONTENT\n-----END RSA PRIVATE KEY-----',
])
def test_known_patterns_are_redacted(secret):
    result = redact(secret)
    assert "[REDACTED" in result
    assert "FAKE_CONTENT" not in result
    assert "fake-password-value" not in result
    assert "fake-token-value" not in result
    assert "alice@example.com" not in result


def test_exact_api_key_and_terminal_controls():
    assert "fake-unusual-key" not in redact("text fake-unusual-key", "fake-unusual-key")
    assert "\x1b" not in redact("\x1b[31msecret")
    assert "\u202e" not in redact("\u202ehidden")


@pytest.mark.parametrize("value", [
    'password = "ab\\"LEAKED_SUFFIX"',
    "password = 'ab\\'LEAKED_SUFFIX'",
    'password = """LEAKED_VALUE"""',
    "password = '''LEAKED_VALUE'''",
    '+password = """first\n+LEAKED_VALUE\n+"""',
    '+password = """LEAKED_VALUE',
    'password = "unfinished LEAKED_VALUE',
    'password = """prefix\\"""LEAKED_SUFFIX"""',
    '-password = """OLD_SECRET\n+password = """LEAKED_NEW_SECRET\n common\n """',
    'DATABASE_URL=postgresql://demo_user:LEAKED_VALUE@localhost/db',
])
def test_escaped_multiline_and_database_secrets(value):
    assert "LEAKED" not in redact(value)


@pytest.mark.parametrize("path", [".env", "config/.env.prod", "config/dev.env", ".ssh/id_rsa", "private.key", ".aws/credentials", "cert.pem"])
def test_excluded_paths(path):
    assert excluded(path)


def test_secrets_removed_from_full_request(repo):
    (repo / "app.py").write_text('API_KEY = "fake-unusual-key"\nemail = "alice@example.com"\n')
    (repo / ".env").write_text("PASSWORD=DO_NOT_SEND\n")
    git(repo, "add", ".env")
    safe = prepare(collect(repo), reason="alice@example.com fake-unusual-key", api_key="fake-unusual-key")
    encoded = encode_payload(build_payload("pr", safe.data, "gpt-4.1-mini", 0.2, 1200)).decode()
    assert "fake-unusual-key" not in encoded and "alice@example.com" not in encoded
    assert "DO_NOT_SEND" not in encoded
    assert safe.excluded_files == 1 and safe.data["partial"]


def test_renamed_secret_stays_excluded(repo):
    (repo / ".env").write_text("secret data\n")
    git(repo, "add", ".env")
    git(repo, "commit", "-m", "fixture only")
    git(repo, "config", "status.renames", "false")
    git(repo, "mv", ".env", "normal.txt")
    safe = prepare(collect(repo))
    assert safe.excluded_files == 1
    assert safe.data["changes"] == []


def test_editing_multiline_password_excludes_both_diff_sides(repo):
    (repo / "app.py").write_text('password = """OLD_SECRET\ncommon\n"""\n')
    git(repo, "add", "app.py")
    git(repo, "commit", "-m", "multiline fixture")
    (repo / "app.py").write_text('password = """NEW_SECRET\ncommon\n"""\n')
    (repo / "safe.txt").write_text("ordinary change\n")
    git(repo, "add", "safe.txt")
    safe = prepare(collect(repo))
    sent = dumps(safe.data)
    assert "OLD_SECRET" not in sent and "NEW_SECRET" not in sent
    assert safe.excluded_files == 1 and safe.data["partial"]
    assert len(safe.data["changes"]) == 1
    assert safe.data["changes"][0]["path"] == "safe.txt"


@pytest.mark.parametrize("count", [10, 11])
def test_file_limit(repo, count):
    for number in range(count):
        (repo / f"{number:02}.txt").write_text("new\n")
    git(repo, "add", ".")
    safe = prepare(collect(repo))
    assert len({block["path"] for block in safe.data["changes"]}) == min(10, count)
    assert safe.omitted_files == max(0, count - 10)
    assert safe.data["partial"] == (count > 10)


def test_combined_layer_line_and_character_limits(repo):
    (repo / "app.py").write_text("\n".join(f"line{i}" for i in range(300)))
    git(repo, "add", "app.py")
    (repo / "app.py").write_text("x" * 30_000)
    safe = prepare(collect(repo), reason="r" * 2000, test_context="t" * 2000)
    assert safe.line_count <= 200
    assert len(dumps(dumps(safe.data))) <= MAX_DATA_CHARS
    assert len(safe.data["context"]) == 1000
    assert safe.data["partial"] and safe.truncated_blocks >= 1


def test_long_line_is_omitted_not_split(repo):
    (repo / "app.py").write_text("s" * 30_000)
    safe = prepare(collect(repo))
    assert "s" * 1000 not in dumps(safe.data)
    assert safe.truncated_blocks == 1


def test_staged_only_does_not_read_unstaged_content(repo):
    (repo / "app.py").write_text("staged\n")
    git(repo, "add", "app.py")
    (repo / "app.py").write_text("UNSTAGED_CONTENT\n")
    assert "UNSTAGED_CONTENT" not in dumps(prepare(collect(repo), staged_only=True).data)


def test_encoded_request_budget():
    with pytest.raises(Exception, match="20,000"):
        encode_payload({"input": "a" * 20_000})


@pytest.mark.parametrize("line_count", [200, 201])
def test_exact_line_boundary(repo, monkeypatch, line_count):
    (repo / "app.py").write_text("changed\n")
    monkeypatch.setattr("gitgen.safety.read_diff", lambda *a: "line\n" * line_count)
    safe = prepare(collect(repo))
    assert safe.line_count == 200
    assert safe.data["partial"] == (line_count > 200)


def test_heavily_escaped_input_leaves_room_for_correction(repo, monkeypatch, commit_draft):
    import requests
    from conftest import response_for

    (repo / "app.py").write_text(json.dumps([""] * 2200) + "\n")
    safe = prepare(collect(repo), reason="\\" * 1000, test_context='"' * 1000)
    payload = build_payload("commit", safe.data, "gpt-4.1-mini", 0.2, 1200)
    seen = []
    replies = iter([response_for({"unexpected": "\\" * 1000}), response_for(commit_draft)])
    def post(*args, **kwargs):
        seen.append(len(kwargs["data"].decode("utf-8")))
        return next(replies)
    monkeypatch.setattr(requests, "post", post)
    client = ApiClient("fake-key")
    assert generate("commit", payload, client, lambda *args: None) == commit_draft
    assert client.calls == 2 and max(seen) <= 20_000
