"""GitHub API client for fetching PR details."""

import json
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests
from requests.exceptions import RequestException, Timeout

from .github_token_pool import GitHubTokenPool, TokenLease
from .persistence import atomic_write_json


class GitHubClient:
    """Client for interacting with GitHub API."""

    RETRYABLE_STATUS_CODES = {408, 409, 425, 429, 500, 502, 503, 504}

    def __init__(
        self,
        token: Optional[str] = None,
        tokens: Optional[List[str]] = None,
        cache_dir: Optional[str] = None,
        request_timeout: float = 30.0,
        max_retries: int = 3,
        initial_retry_delay: float = 1.0,
        backoff_factor: float = 2.0,
        max_retry_delay: float = 60.0,
        token_cooldown_buffer_seconds: float = 1.0
    ):
        """
        Initialize GitHub client.

        Args:
            token: GitHub API token (defaults to GITHUB_TOKEN env var)
            tokens: GitHub API tokens for pooled access
            cache_dir: Directory for caching API responses
            request_timeout: Per-request timeout in seconds
            max_retries: Number of retries for transient failures
            initial_retry_delay: Initial retry sleep in seconds
            backoff_factor: Multiplier applied to each retry wait
            max_retry_delay: Maximum sleep between retries
        """
        self.tokens = self._resolve_tokens(token=token, tokens=tokens)
        self.token = self.tokens[0] if self.tokens else None
        self.base_url = "https://api.github.com"
        self.session = requests.Session()
        self.request_timeout = request_timeout
        self.max_retries = max(0, max_retries)
        self.initial_retry_delay = max(0.0, initial_retry_delay)
        self.backoff_factor = max(1.0, backoff_factor)
        self.max_retry_delay = max_retry_delay
        self.token_pool = (
            GitHubTokenPool(
                self.tokens,
                cooldown_buffer_seconds=token_cooldown_buffer_seconds
            )
            if self.tokens else None
        )

        self.session.headers.update({
            "Accept": "application/vnd.github.v3+json"
        })

        self.cache_dir = Path(cache_dir) if cache_dir else Path(".cache/github")
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        self.rate_limit_remaining = None
        self.rate_limit_reset = None

    def _get_cache_path(self, cache_key: str) -> Path:
        """Get cache file path for a given key."""
        return self.cache_dir / f"{cache_key}.json"

    def _load_from_cache(self, cache_key: str) -> Optional[Any]:
        """Load data from cache if available."""
        cache_path = self._get_cache_path(cache_key)
        if cache_path.exists():
            try:
                with open(cache_path, 'r') as f:
                    return json.load(f)
            except Exception:
                return None
        return None

    def _save_to_cache(self, cache_key: str, data: Any):
        """Save data to cache."""
        cache_path = self._get_cache_path(cache_key)
        try:
            atomic_write_json(cache_path, data, indent=2)
        except Exception as e:
            print(f"Warning: Failed to cache data: {e}")

    def _check_rate_limit(self):
        """Check and handle rate limiting."""
        if self.rate_limit_remaining is not None and self.rate_limit_remaining < 10:
            if self.rate_limit_reset:
                wait_time = self.rate_limit_reset - time.time()
                if wait_time > 0:
                    print(f"Rate limit low, waiting {wait_time:.0f}s...")
                    time.sleep(wait_time + 1)

    def _compute_retry_delay(self, attempt: int, retry_after: Optional[str] = None) -> float:
        """Compute retry delay with optional Retry-After override."""
        if retry_after is not None:
            try:
                return min(float(retry_after), self.max_retry_delay)
            except (TypeError, ValueError):
                pass

        return min(
            self.initial_retry_delay * (self.backoff_factor ** attempt),
            self.max_retry_delay
        )

    def _wait_for_rate_limit(self, headers: Dict[str, Any]) -> float:
        """Wait until GitHub rate limit resets, if known."""
        reset_time = headers.get("X-RateLimit-Reset")
        retry_after = headers.get("Retry-After")

        if retry_after is not None:
            delay = self._compute_retry_delay(0, retry_after)
            if delay > 0:
                print(f"GitHub rate limited, waiting {delay:.1f}s before retrying...")
                time.sleep(delay)
            return delay

        if reset_time is None:
            return 0.0

        try:
            wait_time = max(float(reset_time) - time.time(), 0.0) + 1.0
        except (TypeError, ValueError):
            return 0.0

        if wait_time > 0:
            print(f"GitHub rate limited, waiting {wait_time:.1f}s before retrying...")
            time.sleep(wait_time)
            return wait_time

        return 0.0

    def _request(self, url: str, headers: Optional[Dict[str, str]] = None) -> Optional[requests.Response]:
        """Make a raw HTTP request with retry, timeout, and rate limit handling."""
        if not self.token_pool:
            self._check_rate_limit()

        attempt = 0

        while True:
            lease: Optional[TokenLease] = None
            try:
                if self.token_pool:
                    lease = self.token_pool.acquire()

                response = self.session.get(
                    url,
                    headers=self._build_request_headers(headers, lease),
                    timeout=self.request_timeout
                )

                if self.token_pool and lease:
                    self.token_pool.record_response(lease, response.status_code, response.headers)
                else:
                    self.rate_limit_remaining = int(response.headers.get("X-RateLimit-Remaining", 0))
                    self.rate_limit_reset = int(response.headers.get("X-RateLimit-Reset", 0))

                if response.status_code == 200:
                    return response

                if response.status_code == 404:
                    print(f"Warning: Resource not found: {url}")
                    return None

                if response.status_code == 401 and self.token_pool and lease:
                    print(
                        f"GitHub token {self.token_pool.describe_token(lease)} is unauthorized; "
                        "removing it from the pool and retrying..."
                    )
                    continue

                is_rate_limited = (
                    response.status_code in {403, 429}
                    and response.headers.get("X-RateLimit-Remaining") == "0"
                )
                if is_rate_limited:
                    if self.token_pool and lease:
                        print(
                            f"GitHub token {self.token_pool.describe_token(lease)} is rate limited; "
                            "waiting for another available token..."
                        )
                        continue

                    self._wait_for_rate_limit(response.headers)
                    attempt += 1
                    if attempt > self.max_retries:
                        print(f"Warning: API request exhausted retries due to rate limiting: {url}")
                        return None
                    continue
                elif response.status_code in self.RETRYABLE_STATUS_CODES:
                    delay = self._compute_retry_delay(attempt, response.headers.get("Retry-After"))
                    if attempt < self.max_retries and delay > 0:
                        print(
                            f"GitHub request failed with status {response.status_code}; "
                            f"retrying in {delay:.1f}s ({attempt + 1}/{self.max_retries})..."
                        )
                        time.sleep(delay)
                        attempt += 1
                        continue
                    else:
                        print(f"Warning: API request failed with status {response.status_code}")
                        return None
                elif response.status_code == 403:
                    print(f"Warning: Forbidden GitHub request: {url}")
                    return None
                else:
                    print(f"Warning: API request failed with status {response.status_code}")
                    return None

            except Timeout:
                if self.token_pool and lease:
                    self.token_pool.record_error(lease)

                delay = self._compute_retry_delay(attempt)
                if attempt < self.max_retries:
                    print(
                        f"GitHub request timed out; retrying in {delay:.1f}s "
                        f"({attempt + 1}/{self.max_retries})..."
                    )
                    time.sleep(delay)
                    attempt += 1
                    continue
                print(f"Warning: GitHub request timed out after {self.max_retries + 1} attempts: {url}")
                return None
            except RequestException as e:
                if self.token_pool and lease:
                    self.token_pool.record_error(lease)

                delay = self._compute_retry_delay(attempt)
                if attempt < self.max_retries:
                    print(
                        f"GitHub request error: {e}; retrying in {delay:.1f}s "
                        f"({attempt + 1}/{self.max_retries})..."
                    )
                    time.sleep(delay)
                    attempt += 1
                    continue
                print(f"Warning: API request error after retries: {e}")
                return None
            except RuntimeError as e:
                print(f"Warning: {e}")
                return None

        return None

    def _build_request_headers(
        self,
        headers: Optional[Dict[str, str]],
        lease: Optional[TokenLease]
    ) -> Dict[str, str]:
        """Build request headers with token-specific authorization."""
        request_headers = dict(headers or {})
        request_headers.setdefault("Accept", "application/vnd.github.v3+json")

        token = lease.token if lease else self.token
        if token:
            request_headers["Authorization"] = f"token {token}"

        return request_headers

    def _resolve_tokens(
        self,
        token: Optional[str] = None,
        tokens: Optional[List[str]] = None
    ) -> List[str]:
        """Resolve tokens from args and environment variables."""
        resolved: List[str] = []

        if tokens:
            for item in tokens:
                resolved.extend(self._split_token_values(item))

        if token:
            resolved.extend(self._split_token_values(token))

        env_tokens = os.getenv("GITHUB_TOKENS")
        if env_tokens:
            resolved.extend(self._split_token_values(env_tokens))

        for env_name in ("GITHUB_TOKEN", "GH_TOKEN"):
            env_value = os.getenv(env_name)
            if env_value:
                resolved.extend(self._split_token_values(env_value))

        deduped = []
        seen = set()
        for value in resolved:
            if value in seen:
                continue
            seen.add(value)
            deduped.append(value)

        return deduped

    def _split_token_values(self, value: str) -> List[str]:
        """Split token values from comma-separated or newline-separated strings."""
        return [
            token.strip()
            for token in value.replace("\n", ",").split(",")
            if token.strip()
        ]

    def _make_request(self, url: str, use_cache: bool = True) -> Optional[Any]:
        """Make JSON API request with caching and retry handling."""
        cache_key = url.replace(self.base_url + "/", "").replace("/", "_")

        # Try cache first
        if use_cache:
            cached = self._load_from_cache(cache_key)
            if cached is not None:
                return cached

        response = self._request(url)
        if response is None:
            return None

        try:
            data = response.json()
        except ValueError as e:
            print(f"Warning: Failed to decode GitHub response JSON: {e}")
            return None

        if use_cache:
            self._save_to_cache(cache_key, data)

        return data

    def get_pr_details(self, repo: str, pr_number: int) -> Optional[Dict[str, Any]]:
        """
        Fetch PR details from GitHub API.

        Args:
            repo: Repository in format "owner/repo"
            pr_number: PR number

        Returns:
            PR details dict or None if not found
        """
        url = f"{self.base_url}/repos/{repo}/pulls/{pr_number}"
        return self._make_request(url)

    def get_pr_commits(self, repo: str, pr_number: int) -> List[Dict[str, Any]]:
        """Fetch commits for a PR."""
        url = f"{self.base_url}/repos/{repo}/pulls/{pr_number}/commits"
        data = self._make_request(url)
        return data if isinstance(data, list) else []

    def get_pr_files(self, repo: str, pr_number: int) -> List[Dict[str, Any]]:
        """Fetch changed files for a PR."""
        url = f"{self.base_url}/repos/{repo}/pulls/{pr_number}/files"
        data = self._make_request(url)
        return data if isinstance(data, list) else []

    def get_commit_diff(self, repo: str, base: str, head: str) -> Optional[str]:
        """
        Get diff between two commits.

        Args:
            repo: Repository in format "owner/repo"
            base: Base commit SHA
            head: Head commit SHA

        Returns:
            Unified diff string or None
        """
        url = f"{self.base_url}/repos/{repo}/compare/{base}...{head}"
        response = self._request(url, headers={"Accept": "application/vnd.github.v3.diff"})
        if response is None:
            return None
        return response.text

    def parse_pr_id(self, pr_id: str) -> tuple[str, int]:
        """
        Parse PR ID in format 'owner/repo#number'.

        Args:
            pr_id: PR identifier like "scipy/scipy#333"

        Returns:
            Tuple of (repo, pr_number)
        """
        if "#" not in pr_id:
            raise ValueError(f"Invalid PR ID format: {pr_id}")

        repo, number_str = pr_id.rsplit("#", 1)
        return repo, int(number_str)
