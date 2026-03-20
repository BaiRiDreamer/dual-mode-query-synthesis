"""Tests for GitHub client retry behavior."""

import src.utils.github_client as github_client_module
from requests.exceptions import Timeout

from src.utils.github_client import GitHubClient


class FakeResponse:
    """Minimal response stub for GitHub client tests."""

    def __init__(self, status_code=200, payload=None, headers=None, text=""):
        self.status_code = status_code
        self._payload = payload or {}
        self.headers = headers or {
            "X-RateLimit-Remaining": "100",
            "X-RateLimit-Reset": "0"
        }
        self.text = text

    def json(self):
        return self._payload


def test_github_client_retries_timeout_then_succeeds(tmp_path, monkeypatch):
    """Transient timeouts should be retried with backoff."""
    client = GitHubClient(
        token="token",
        cache_dir=str(tmp_path / ".cache"),
        request_timeout=1,
        max_retries=2,
        initial_retry_delay=0.5,
        backoff_factor=2.0,
        max_retry_delay=5.0
    )

    calls = {"count": 0}
    sleep_calls = []

    def fake_get(url, headers=None, timeout=None):
        calls["count"] += 1
        if calls["count"] == 1:
            raise Timeout("timed out")
        return FakeResponse(payload={"id": 123})

    monkeypatch.setattr(client.session, "get", fake_get)
    monkeypatch.setattr(github_client_module.time, "sleep", lambda delay: sleep_calls.append(delay))

    payload = client.get_pr_details("owner/repo", 123)

    assert payload == {"id": 123}
    assert calls["count"] == 2
    assert sleep_calls == [0.5]
