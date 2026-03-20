"""Main dual-mode query builder."""

from typing import List, Dict, Any, Tuple, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
from ...models.artifacts import PRRecord, ChainLevelQuery, AtomicLevelQuery
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
        github_tokens: Optional[List[str]] = None,
        cache_dir: str = ".cache/github",
        github_client_config: Optional[Dict[str, Any]] = None,
        llm_config: Optional[Dict[str, Any]] = None,
        max_workers: int = 5
    ):
        """
        Initialize dual-mode builder.

        Args:
            github_token: GitHub API token
            github_tokens: GitHub API tokens for pooled access
            cache_dir: Cache directory for GitHub API responses
            github_client_config: Extra GitHub client options
            llm_config: LLM configuration dict
            max_workers: Max concurrent workers
        """
        github_options = dict(github_client_config or {})
        self.github_client = GitHubClient(
            token=github_token,
            tokens=github_tokens,
            cache_dir=cache_dir,
            **github_options
        )
        self.context_enricher = ContextEnricher(self.github_client)
        self.max_workers = max_workers

        # Initialize LLM client if config provided
        self.llm_client = None
        if llm_config:
            self.llm_client = LLMClient(**llm_config)

        self.chain_builder = ChainLevelBuilder(self.llm_client)
        self.atomic_builder = AtomicLevelBuilder(self.llm_client)

    def _enrich_chain_records(
        self,
        chain_data: Dict[str, Any],
        progress_callback=None
    ) -> List[PRRecord]:
        """Fetch all PR records for a chain once."""
        chain_id = chain_data["chain_id"]
        original_chain = chain_data["original_chain"]

        if progress_callback:
            progress_callback(f"Enriching PR records for chain {chain_id}...")

        pr_records = self.context_enricher.enrich_pr_records(original_chain)
        if not pr_records:
            raise ValueError(f"No PR records found for chain {chain_id}")

        return pr_records

    def prepare_pr_records(
        self,
        chain_data: Dict[str, Any],
        progress_callback=None
    ) -> List[PRRecord]:
        """Public wrapper for one-time PR enrichment."""
        return self._enrich_chain_records(chain_data, progress_callback)

    def _build_atomic_queries_from_records(
        self,
        chain_id: str,
        pr_records: List[PRRecord],
        progress_callback=None,
        target_pr_ids: Optional[List[str]] = None
    ) -> List[AtomicLevelQuery]:
        """Build atomic-level queries from already-enriched PR records."""
        target_pr_ids = set(target_pr_ids) if target_pr_ids is not None else None
        queries = []
        total_prs = len(pr_records)

        for idx, pr in enumerate(pr_records, 1):
            if target_pr_ids is not None and pr.pr_id not in target_pr_ids:
                continue

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

    def build_requested(
        self,
        chain_data: Dict[str, Any],
        build_chain: bool = True,
        build_atomic: bool = False,
        target_atomic_pr_ids: Optional[List[str]] = None,
        progress_callback=None
    ) -> Tuple[Optional[ChainLevelQuery], List[AtomicLevelQuery]]:
        """Build only the query outputs that are still needed."""
        if not build_chain and not build_atomic:
            return None, []

        chain_id = chain_data["chain_id"]
        llm_judgment = chain_data["llm_judgment"]
        quality_score = chain_data["quality_score"]
        pr_records = self._enrich_chain_records(chain_data, progress_callback)

        chain_query = None
        atomic_queries: List[AtomicLevelQuery] = []

        if build_chain:
            if progress_callback:
                progress_callback(f"Building chain-level query for {chain_id}...")

            chain_query = self.chain_builder.build_query(
                chain_id=chain_id,
                pr_records=pr_records,
                llm_judgment=llm_judgment,
                quality_score=quality_score
            )

        if build_atomic:
            atomic_queries = self._build_atomic_queries_from_records(
                chain_id=chain_id,
                pr_records=pr_records,
                progress_callback=progress_callback,
                target_pr_ids=target_atomic_pr_ids
            )

        return chain_query, atomic_queries

    def build_chain_query(
        self,
        chain_data: Dict[str, Any],
        progress_callback=None,
        pr_records: Optional[List[PRRecord]] = None
    ) -> ChainLevelQuery:
        """
        Build chain-level query from PR chain data.

        Args:
            chain_data: Raw chain data from input file
            progress_callback: Optional callback for progress updates

        Returns:
            ChainLevelQuery artifact
        """
        if pr_records is not None:
            chain_id = chain_data["chain_id"]
            llm_judgment = chain_data["llm_judgment"]
            quality_score = chain_data["quality_score"]

            if progress_callback:
                progress_callback(f"Building chain-level query for {chain_id}...")

            return self.chain_builder.build_query(
                chain_id=chain_id,
                pr_records=pr_records,
                llm_judgment=llm_judgment,
                quality_score=quality_score
            )

        chain_query, _ = self.build_requested(
            chain_data,
            build_chain=True,
            build_atomic=False,
            progress_callback=progress_callback
        )
        if chain_query is None:
            raise ValueError(f"Failed to build chain query for {chain_data['chain_id']}")
        return chain_query

    def build_atomic_queries(
        self,
        chain_data: Dict[str, Any],
        progress_callback=None,
        pr_records: Optional[List[PRRecord]] = None,
        target_pr_ids: Optional[List[str]] = None
    ) -> List[AtomicLevelQuery]:
        """
        Build atomic-level queries from PR chain data.

        Args:
            chain_data: Raw chain data from input file
            progress_callback: Optional callback for progress updates

        Returns:
            List of AtomicLevelQuery artifacts
        """
        if pr_records is not None:
            return self._build_atomic_queries_from_records(
                chain_id=chain_data["chain_id"],
                pr_records=pr_records,
                progress_callback=progress_callback,
                target_pr_ids=target_pr_ids
            )

        _, atomic_queries = self.build_requested(
            chain_data,
            build_chain=False,
            build_atomic=True,
            target_atomic_pr_ids=target_pr_ids,
            progress_callback=progress_callback
        )
        return atomic_queries

    def build_both(
        self,
        chain_data: Dict[str, Any],
        progress_callback=None
    ) -> Tuple[ChainLevelQuery, List[AtomicLevelQuery]]:
        """
        Build both chain-level and atomic-level queries.

        Args:
            chain_data: Raw chain data from input file
            progress_callback: Optional callback for progress updates

        Returns:
            Tuple of (ChainLevelQuery, List[AtomicLevelQuery])
        """
        chain_query, atomic_queries = self.build_requested(
            chain_data,
            build_chain=True,
            build_atomic=True,
            progress_callback=progress_callback
        )
        if chain_query is None:
            raise ValueError(f"Failed to build both outputs for {chain_data['chain_id']}")
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
