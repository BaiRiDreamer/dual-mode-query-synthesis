"""Context enrichment for PR data."""

from typing import List, Dict, Any, Optional
from datetime import datetime
from ...models.artifacts import PRRecord, DiffPatch
from ...utils.github_client import GitHubClient


class ContextEnricher:
    """Enriches PR chain data with additional context from GitHub API."""

    def __init__(self, github_client: GitHubClient):
        """
        Initialize context enricher.

        Args:
            github_client: GitHub API client
        """
        self.github = github_client

    def enrich_pr_records(self, pr_ids: List[str]) -> List[PRRecord]:
        """
        Fetch and enrich PR records from GitHub API.

        Args:
            pr_ids: List of PR IDs in format "owner/repo#number"

        Returns:
            List of enriched PR records
        """
        pr_records = []
        failed_pr_ids = []

        for pr_id in pr_ids:
            try:
                pr_record = self.fetch_pr_record(pr_id)
                if pr_record:
                    pr_records.append(pr_record)
                else:
                    failed_pr_ids.append(pr_id)
            except Exception as e:
                failed_pr_ids.append(pr_id)
                print(f"Error fetching PR {pr_id}: {e}")

        if failed_pr_ids:
            failed = ", ".join(failed_pr_ids)
            raise RuntimeError(f"Failed to fetch complete PR chain. Missing PR data for: {failed}")

        return pr_records

    def fetch_pr_record(self, pr_id: str) -> Optional[PRRecord]:
        """
        Fetch a single PR record from GitHub API.

        Args:
            pr_id: PR ID in format "owner/repo#number"

        Returns:
            PRRecord or None if not found
        """
        try:
            repo, pr_number = self.github.parse_pr_id(pr_id)
        except ValueError as e:
            print(f"Invalid PR ID format: {pr_id} - {e}")
            return None

        # Fetch PR details
        pr_data = self.github.get_pr_details(repo, pr_number)
        if not pr_data:
            return None

        # Fetch PR files
        files_data = self.github.get_pr_files(repo, pr_number)

        # Extract file changes and patches
        files_changed = []
        patches = []

        for file_data in files_data:
            filename = file_data.get("filename", "")
            files_changed.append(filename)

            # Extract patch if available
            patch_content = file_data.get("patch", "")
            if patch_content:
                patches.append(DiffPatch(
                    path=filename,
                    patch=patch_content,
                    additions=file_data.get("additions", 0),
                    deletions=file_data.get("deletions", 0)
                ))

        # Parse dates
        created_at = self._parse_datetime(pr_data.get("created_at"))
        merged_at = self._parse_datetime(pr_data.get("merged_at"))

        # Extract labels
        labels = [label.get("name", "") for label in pr_data.get("labels", [])]

        # Build PR record
        pr_record = PRRecord(
            pr_id=pr_id,
            pr_number=pr_number,
            repository=repo,
            title=pr_data.get("title", ""),
            description=pr_data.get("body", ""),
            author=pr_data.get("user", {}).get("login", "unknown"),
            created_at=created_at,
            merged_at=merged_at,
            labels=labels,
            files_changed=files_changed,
            base_commit=pr_data.get("base", {}).get("sha"),
            head_commit=pr_data.get("head", {}).get("sha"),
            patches=patches,
            status=pr_data.get("state", "merged")
        )

        return pr_record

    def compute_cumulative_diff(
        self,
        repository: str,
        base_commit: str,
        head_commit: str
    ) -> str:
        """
        Compute cumulative diff between two commits.

        Args:
            repository: Repository in format "owner/repo"
            base_commit: Base commit SHA
            head_commit: Head commit SHA

        Returns:
            Unified diff string
        """
        diff = self.github.get_commit_diff(repository, base_commit, head_commit)
        return diff or ""

    def _parse_datetime(self, date_str: Optional[str]) -> Optional[datetime]:
        """Parse ISO datetime string."""
        if not date_str:
            return None

        try:
            # GitHub returns ISO 8601 format
            return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        except Exception:
            return None

    def extract_topic_from_chain(self, pr_records: List[PRRecord]) -> str:
        """
        Extract topic from PR chain.

        Args:
            pr_records: List of PR records

        Returns:
            Topic string
        """
        if not pr_records:
            return "unknown"

        # Look for common words in titles
        titles = [pr.title.lower() for pr in pr_records]

        # Extract common significant words
        from collections import Counter
        import re

        all_words = []
        for title in titles:
            # Extract words (skip common words)
            words = re.findall(r'\b\w+\b', title)
            significant_words = [
                w for w in words
                if len(w) > 3 and w not in {
                    "add", "fix", "update", "remove", "improve", "implement",
                    "enhance", "optimize", "refactor", "the", "and", "for", "with"
                }
            ]
            all_words.extend(significant_words)

        if not all_words:
            return pr_records[0].title[:50]

        # Find most common words
        word_counts = Counter(all_words)
        top_words = [word for word, count in word_counts.most_common(3)]

        return " ".join(top_words)
