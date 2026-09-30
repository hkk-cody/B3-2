import json

import pytest
import requests

from tests.conftest import Response, response_for
from gitgen.api_client import ApiClient, ENDPOINT, parse_response
from gitgen.errors import GitgenError, ValidationError
from gitgen.generation import generate
from gitgen.prompts import build_payload
from gitgen.validators import validate


@pytest.fixture
def payload():
    return build_payload("commit", {"changes": []}, "gpt-5-mini", None, 4096)


@pytest.mark.parametrize("command,length,valid", [
    ("commit", 50, True), ("commit", 51, True), ("commit", 72, True), ("commit", 73, False),
    ("pr", 80, True), ("pr", 81, False),
])
def test_title_boundaries(command, length, valid, commit_draft, pr_draft):
    draft = commit_draft if command == "commit" else pr_draft
    draft["title"] = "가" * length
    if valid:
        assert len(validate(command, json.dumps(draft))["title"]) == length
    else:
        with pytest.raises(ValidationError):
            validate(command, json.dumps(draft))


@pytest.mark.parametrize("title", ["", " ", "first\nsecond", "a\r", 4, None])
def test_invalid_title(title, commit_draft):
    commit_draft["title"] = title
    with pytest.raises(ValidationError):
        validate("commit", json.dumps(commit_draft))


@pytest.mark.parametrize("raw", ["bad json", "[]", "null", "{}", '{"summary":"s"}'])
def test_malformed_draft(raw):
    with pytest.raises(ValidationError):
        validate("commit", raw)


@pytest.mark.parametrize("items", [[], "string", [""], [1], ["a", "b", "c"]])
def test_bad_commit_bullets(items, commit_draft):
    commit_draft["changes"] = items
    with pytest.raises(ValidationError):
        validate("commit", json.dumps(commit_draft))


def test_request_and_response_contract(monkeypatch, payload, commit_draft):
    seen = []
    def post(url, **kwargs):
        seen.append((url, kwargs))
        return response_for(commit_draft)
    monkeypatch.setattr(requests, "post", post)
    client = ApiClient("fake-key")
    draft = generate("commit", payload, client, lambda *args: None)
    assert draft == commit_draft and client.calls == 1
    url, kwargs = seen[0]
    assert url == ENDPOINT == "https://copa.codyssey.kr/v1/chat/completions"
    assert kwargs["headers"]["Authorization"] == "Bearer fake-key"
    body = json.loads(kwargs["data"])
    assert body["max_completion_tokens"] == 4096 and "temperature" not in body
    assert body["model"] == "gpt-5-mini"
    assert [message["role"] for message in body["messages"]] == ["system", "user"]
    assert '"required"' in body["messages"][0]["content"]
    assert not {"input", "instructions", "text", "store", "max_output_tokens"} & set(body)
    assert kwargs["allow_redirects"] is False


def test_reads_codyssey_choices_message_content():
    body = {"choices": [{"message": {"role": "assistant", "content": "{}"}}]}
    assert parse_response(body) == "{}"


def test_explicit_generation_parameters():
    payload = build_payload("pr", {}, "gpt-5.4-mini", 1.0, 8000)
    assert payload["temperature"] == 1.0 and payload["max_completion_tokens"] == 8000


@pytest.mark.parametrize("body", [None, [], {}, {"choices": []}, {"choices": [None]},
    {"choices": [{"message": None}]}, {"choices": [{"message": {"content": []}}]},
    {"choices": [{"message": {"content": ""}}]},
])
def test_invalid_chat_response(body):
    with pytest.raises(ValidationError):
        parse_response(body)


def test_custom_base_url(monkeypatch, payload, commit_draft):
    seen = []
    def post(url, **kwargs):
        seen.append(url)
        return response_for(commit_draft)
    monkeypatch.setattr(requests, "post", post)
    ApiClient("fake-key", "https://example.invalid/v1/").generate(payload)
    assert seen == ["https://example.invalid/v1/chat/completions"]


@pytest.mark.parametrize("status", [400, 401, 403, 404, 429, 500, 302])
def test_http_errors_no_retry_or_secret_leak(monkeypatch, payload, status):
    monkeypatch.setattr(requests, "post", lambda *a, **k: Response({"error": "DO_NOT_LOG_SECRET"}, status))
    client = ApiClient("fake-key")
    with pytest.raises(GitgenError, match=f"HTTP {status}") as error:
        generate("commit", payload, client, lambda *args: None)
    assert "DO_NOT_LOG_SECRET" not in str(error.value) and client.calls == 1


@pytest.mark.parametrize("error", [requests.Timeout("DO_NOT_LOG_SECRET"), requests.ConnectionError("DO_NOT_LOG_SECRET")])
def test_network_errors_no_retry(monkeypatch, payload, error):
    def post(*args, **kwargs):
        raise error
    monkeypatch.setattr(requests, "post", post)
    client = ApiClient("fake-key")
    with pytest.raises(GitgenError) as exc:
        generate("commit", payload, client, lambda *args: None)
    assert "DO_NOT_LOG_SECRET" not in str(exc.value) and client.calls == 1


def test_correction_request_then_success(monkeypatch, payload, commit_draft):
    replies = iter([response_for({"title": "fake-key"}), response_for(commit_draft)])
    seen = []
    def post(*args, **kwargs):
        seen.append(json.loads(kwargs["data"]))
        return next(replies)
    monkeypatch.setattr(requests, "post", post)
    client = ApiClient("fake-key")
    assert generate("commit", payload, client, lambda *args: None) == commit_draft
    assert client.calls == 2
    assert "correction" in seen[1]["messages"][-1]["content"]
    assert "fake-key" not in json.dumps(seen[1]["messages"])
    assert seen[1]["messages"][:2] == payload["messages"]
    assert len(payload["messages"]) == 2


def test_failure_is_limited_to_two_calls(monkeypatch, payload):
    monkeypatch.setattr(requests, "post", lambda *args, **kwargs: Response(b"invalid JSON"))
    client = ApiClient("fake-key")
    with pytest.raises(GitgenError, match="재생성"):
        generate("commit", payload, client, lambda *args: None)
    assert client.calls == 2
    with pytest.raises(GitgenError, match="한도"):
        client.generate(payload)


@pytest.mark.parametrize("body", [
    {"choices": [{"finish_reason": "length", "message": {"content": "partial"}}]},
    {"choices": [{"finish_reason": "content_filter", "message": {"content": None}}]},
    {"choices": [{"finish_reason": "stop", "message": {"refusal": "secret"}}]},
    {"error": {"message": "secret"}},
])
def test_incomplete_or_refused_responses_do_not_retry(monkeypatch, payload, body):
    monkeypatch.setattr(requests, "post", lambda *a, **k: Response(body))
    client = ApiClient("fake-key")
    with pytest.raises(GitgenError):
        generate("commit", payload, client, lambda *args: None)
    assert client.calls == 1



def test_commit_and_pr_prompts_are_separated():
    commit_payload = build_payload("commit", {}, "gpt-5-mini", None, 4096)
    commit_system = commit_payload["messages"][0]["content"]
    assert "커밋 메시지 작성 규칙" in commit_system
    assert "50자 이내" in commit_system
    assert "how_to_test" not in commit_system.split("다음 JSON 스키마에 맞춰")[0]

    pr_payload = build_payload("pr", {}, "gpt-5-mini", None, 4096)
    pr_system = pr_payload["messages"][0]["content"]
    assert "PR 작성 규칙" in pr_system
    assert "how_to_test" in pr_system
    assert "50자 이내를 목표로" not in pr_system

