"""Main dual-mode query builder."""

from typing import List, Dict, Any, Tuple, Optional
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from ...models.artifacts import PRChain, ChainLevelQuery, AtomicLevelQuery
from ...utils.github_client import GitHubClient
from ...utils.llm_client import LLMClient
from .context_enricher import ContextEnricher
from .chain_level_builder import ChainLevelBuilder
from .atomic_level_builder import AtomicLevelBuilder


class DualModeBuilder:
    """Main builder for dual-mode query synthesis."""

    def __init__(
        self,
        github_token: str = None,
        cache_dir: str = ".cache/github",
        llm_config: Optional[Dict[str, Any]] = None,
        max_workers: int = 5
    ):
        """
        Initialize dual-mode builder.

        Args:
            github_token: GitHub API token
            cache_dir: Cache directory for GitHub API responses
            llm_config: LLM configuration dict
            max_workers: Max concurrent workers
        """
        self.github_client = GitHubClient(token=github_token, cache_dir=cache_dir)
        self.context_enricher = ContextEnricher(self.github_client)
        self.max_workers = max_workers

        # Initialize LLM client if config provided
        self.llm_client = None
        if llm_config:
            self.llm_client = LLMClient(**llm_config)

        self.chain_builder = ChainLevelBuilder(self.llm_client)
        self.atomic_builder = AtomicLevelBuilder(self.llm_client)

    def build_chain_query(self, chain_data: Dict[str, Any], progress_callback=None) -> ChainLevelQuery:
        """
        Build chain-level query from PR chain data.

        Args:
            chain_data: Raw chain data from input file
            progress_callback: Optional callback for progress updates

        Returns:
            ChainLevelQuery artifact
        """
        chain_id = chain_data["chain_id"]
        original_chain = chain_data["original_chain"]
        llm_judgment = chain_data["llm_judgment"]
        quality_score = chain_data["quality_score"]

        if progress_callback:
            progress_callback(f"Enriching PR records for chain {chain_id}...")

        pr_records = self.context_enricher.enrich_pr_records(original_chain)

        if not pr_records:
            raise ValueError(f"No PR records found for chain {chain_id}")

        if progress_callback:
            progress_callback(f"Building chain-level query for {chain_id}...")

        query = self.chain_builder.build_query(
            chain_id=chain_id,
            pr_records=pr_records,
            llm_judgment=llm_judgment,
            quality_score=quality_score
        )

        return query

    def build_atomic_queries(self, chain_data: Dict[str, Any], progress_callback=None) -> List[AtomicLevelQuery]:
        """
        Build atomic-level queries from PR chain data.

        Args:
            chain_data: Raw chain data from input file
            progress_callback: Optional callback for progress updates

        Returns:
            List of AtomicLevelQuery artifacts
        """
        chain_id = chain_data["chain_id"]
        original_chain = chain_data["original_chain"]

        if progress_callback:
            progress_callback(f"Enriching PR records for chain {chain_id}...")

        pr_records = self.context_enricher.enrich_pr_records(original_chain)

        if not pr_records:
            raise ValueError(f"No PR records found for chain {chain_id}")

        queries = []
        total_prs = len(pr_records)

        for idx, pr in enumerate(pr_records, 1):
            if progress_callback:
                progress_callback(f"Building atomic query {idx}/{total_prs} for {chain_id}...")

            preceding = [pr_records[i].pr_id for i in range(idx - 1)]
            following = [pr_records[i].pr_id for i in range(idx, total_prs)]

            query = self.atomic_builder.build_query(
                pr=pr,
                chain_id=chain_id,
                position=idx,
                total_prs=total_prs,
                preceding_pr_ids=preceding,
                following_pr_ids=following
            )

            queries.append(query)

        return queries

    def build_both(self, chain_data: Dict[str, Any], progress_callback=None) -> Tuple[ChainLevelQuery, List[AtomicLevelQuery]]:
        """
        Build both chain-level and atomic-level queries.

        Args:
            chain_data: Raw chain data from input file
            progress_callback: Optional callback for progress updates

        Returns:
            Tuple of (ChainLevelQuery, List[AtomicLevelQuery])
        """
        chain_query = self.build_chain_query(chain_data, progress_callback)
        atomic_queries = self.build_atomic_queries(chain_data, progress_callback)

        return chain_query, atomic_queries

    def build_multiple_chains(
        self,
        chain_data_list: List[Dict[str, Any]],
        mode: str = "both",
        progress_callback=None
    ) -> List[Tuple[str, Any]]:
        """
        Build queries for multiple chains concurrently.

        Args:
            chain_data_list: List of chain data dicts
            mode: "chain", "atomic", or "both"
            progress_callback: Optional callback for progress updates

        Returns:
            List of (chain_id, result) tuples
        """
        results = []

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {}

            for chain_data in chain_data_list:
                chain_id = chain_data["chain_id"]

                if mode == "chain":
                    future = executor.submit(self.build_chain_query, chain_data, progress_callback)
                elif mode == "atomic":
                    future = executor.submit(self.build_atomic_queries, chain_data, progress_callback)
                else:  # both
                    future = executor.submit(self.build_both, chain_data, progress_callback)

                futures[future] = chain_id

            for future in as_completed(futures):
                chain_id = futures[future]
                try:
                    result = future.result()
                    results.append((chain_id, result))
                    if progress_callback:
                        progress_callback(f"✓ Completed {chain_id}")
                except Exception as e:
                    if progress_callback:
                        progress_callback(f"✗ Failed {chain_id}: {str(e)}")
                    results.append((chain_id, None))

        return results
