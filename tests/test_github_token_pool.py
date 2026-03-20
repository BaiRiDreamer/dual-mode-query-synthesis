"""Tests for GitHub token pool behavior."""

from src.utils.github_token_pool import GitHubTokenPool


def test_github_token_pool_rotates_tokens():
    """The pool should distribute consecutive requests across tokens."""
    pool = GitHubTokenPool(["token-a", "token-b"], cooldown_buffer_seconds=0)

    lease1 = pool.acquire()
    pool.record_response(lease1, 200, {
        "X-RateLimit-Remaining": "100",
        "X-RateLimit-Reset": "0"
    })

    lease2 = pool.acquire()
    pool.record_response(lease2, 200, {
        "X-RateLimit-Remaining": "100",
        "X-RateLimit-Reset": "0"
    })

    assert lease1.token == "token-a"
    assert lease2.token == "token-b"


def test_github_token_pool_skips_rate_limited_token():
    """A rate-limited token should be cooled down while other tokens stay usable."""
    pool = GitHubTokenPool(["token-a", "token-b"], cooldown_buffer_seconds=0)

    lease1 = pool.acquire()
    pool.record_response(lease1, 429, {
        "X-RateLimit-Remaining": "0",
        "Retry-After": "120"
    })

    lease2 = pool.acquire()
    pool.record_response(lease2, 200, {
        "X-RateLimit-Remaining": "100",
        "X-RateLimit-Reset": "0"
    })

    assert lease2.token == "token-b"
