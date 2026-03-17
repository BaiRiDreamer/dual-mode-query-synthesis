"""GitHub API client for fetching PR details."""

import os
import json
import time
from typing import Optional, Dict, Any, List
from pathlib import Path
import requests
from datetime import datetime


class GitHubClient:
    """Client for interacting with GitHub API."""

    def __init__(self, token: Optional[str] = None, cache_dir: Optional[str] = None):
        """
        Initialize GitHub client.

        Args:
            token: GitHub API token (defaults to GITHUB_TOKEN env var)
            cache_dir: Directory for caching API responses
        """
        self.token = token or os.getenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN")
        self.base_url = "https://api.github.com"
        self.session = requests.Session()

        if self.token:
            self.session.headers.update({
                "Authorization": f"token {self.token}",
                "Accept": "application/vnd.github.v3+json"
            })

        self.cache_dir = Path(cache_dir) if cache_dir else Path(".cache/github")
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        self.rate_limit_remaining = None
        self.rate_limit_reset = None

    def _get_cache_path(self, cache_key: str) -> Path:
        """Get cache file path for a given key."""
        return self.cache_dir / f"{cache_key}.json"

    def _load_from_cache(self, cache_key: str) -> Optional[Dict[str, Any]]:
        """Load data from cache if available."""
        cache_path = self._get_cache_path(cache_key)
        if cache_path.exists():
            try:
                with open(cache_path, 'r') as f:
                    return json.load(f)
            except Exception:
                return None
        return None

    def _save_to_cache(self, cache_key: str, data: Dict[str, Any]):
        """Save data to cache."""
        cache_path = self._get_cache_path(cache_key)
        try:
            with open(cache_path, 'w') as f:
                json.dump(data, f, indent=2, default=str)
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

    def _make_request(self, url: str, use_cache: bool = True) -> Optional[Dict[str, Any]]:
        """Make API request with caching and rate limit handling."""
        cache_key = url.replace(self.base_url + "/", "").replace("/", "_")

        # Try cache first
        if use_cache:
            cached = self._load_from_cache(cache_key)
            if cached:
                return cached

        # Check rate limit
        self._check_rate_limit()

        try:
            response = self.session.get(url)

            # Update rate limit info
            self.rate_limit_remaining = int(response.headers.get("X-RateLimit-Remaining", 0))
            self.rate_limit_reset = int(response.headers.get("X-RateLimit-Reset", 0))

            if response.status_code == 200:
                data = response.json()
                self._save_to_cache(cache_key, data)
                return data
            elif response.status_code == 404:
                print(f"Warning: Resource not found: {url}")
                return None
            elif response.status_code == 403:
                print(f"Warning: Rate limited or forbidden: {url}")
                return None
            else:
                print(f"Warning: API request failed with status {response.status_code}")
                return None
        except Exception as e:
            print(f"Warning: API request error: {e}")
            return None

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

        try:
            response = self.session.get(url, headers={"Accept": "application/vnd.github.v3.diff"})
            if response.status_code == 200:
                return response.text
            return None
        except Exception as e:
            print(f"Warning: Failed to fetch diff: {e}")
            return None

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
