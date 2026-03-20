"""Tests for ContextEnricher resumable PR record caching."""

from pathlib import Path

from src.pipelines.query_constructor.context_enricher import ContextEnricher


class FakeGitHubClient:
    """Minimal GitHub client stub for PR record cache tests."""

    def __init__(self, cache_dir: Path):
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.details_calls = 0
        self.files_calls = 0

    def parse_pr_id(self, pr_id: str):
        repo, number = pr_id.rsplit("#", 1)
        return repo, int(number)

    def get_pr_details(self, repo: str, pr_number: int):
        self.details_calls += 1
        return {
            "title": f"PR {pr_number}",
            "body": "description",
            "user": {"login": "tester"},
            "labels": [{"name": "enhancement"}],
            "base": {"sha": "abc1234"},
            "head": {"sha": "def5678"},
            "state": "merged",
            "created_at": "2026-01-01T00:00:00Z",
            "merged_at": "2026-01-02T00:00:00Z"
        }

    def get_pr_files(self, repo: str, pr_number: int):
        self.files_calls += 1
        return [{
            "filename": "src/module.py",
            "patch": "@@ -1 +1 @@\n-old\n+new",
            "additions": 1,
            "deletions": 1
        }]


def test_context_enricher_uses_cached_pr_record(tmp_path):
    """Once cached, a PR record should be loaded locally without new API calls."""
    github = FakeGitHubClient(tmp_path / ".cache" / "github")
    enricher = ContextEnricher(github)

    first_record = enricher.fetch_pr_record("owner/repo#42")
    assert first_record is not None
    assert github.details_calls == 1
    assert github.files_calls == 1

    github.get_pr_details = lambda repo, pr_number: (_ for _ in ()).throw(AssertionError("should not refetch details"))
    github.get_pr_files = lambda repo, pr_number: (_ for _ in ()).throw(AssertionError("should not refetch files"))

    second_record = enricher.fetch_pr_record("owner/repo#42")
    assert second_record is not None
    assert second_record.pr_id == "owner/repo#42"
