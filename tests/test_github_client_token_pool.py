"""Tests for GitHubClient token pool failover behavior."""

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


def test_github_client_switches_tokens_when_one_hits_rate_limit(tmp_path, monkeypatch):
    """When a token is rate limited, the client should retry with another token."""
    client = GitHubClient(
        tokens=["token-a", "token-b"],
        cache_dir=str(tmp_path / ".cache"),
        request_timeout=1,
        max_retries=1,
        initial_retry_delay=0.1,
        backoff_factor=2.0,
        max_retry_delay=1.0,
        token_cooldown_buffer_seconds=0.0
    )

    auth_headers = []

    def fake_get(url, headers=None, timeout=None):
        auth_headers.append(headers.get("Authorization"))
        if headers.get("Authorization") == "token token-a":
            return FakeResponse(status_code=429, headers={
                "X-RateLimit-Remaining": "0",
                "Retry-After": "120"
            })
        return FakeResponse(payload={"id": 123})

    monkeypatch.setattr(client.session, "get", fake_get)

    payload = client.get_pr_details("owner/repo", 123)

    assert payload == {"id": 123}
    assert auth_headers[:2] == ["token token-a", "token token-b"]
