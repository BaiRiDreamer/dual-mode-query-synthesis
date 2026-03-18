"""Atomic-level query builder using LLM-based generation."""

from typing import Optional, List
from pathlib import Path
from ...models.artifacts import (
    PRRecord, AtomicLevelQuery, PRMetadata, ChainContext,
    TaskSpecification, TaskScope, GroundTruth
)
from ...utils.text_utils import extract_modules, extract_key_areas, infer_function_type
from .intent_synthesizer import IntentSynthesizer
from .query_generator import QueryGenerator
from .ground_truth_generator import GroundTruthGenerator


class AtomicLevelBuilder:
    """Builds atomic-level queries from individual PRs using LLM."""

    def __init__(self, llm_client=None):
        """
        Initialize atomic-level builder.

        Args:
            llm_client: Optional LLM client for query generation
        """
        self.llm_client = llm_client
        self.intent_synthesizer = IntentSynthesizer(llm_client)
        self.query_generator = QueryGenerator(llm_client)
        self.ground_truth_gen = GroundTruthGenerator()


    def build_query(
        self,
        pr: PRRecord,
        chain_id: str,
        position: int,
        total_prs: int,
        preceding_pr_ids: List[str],
        following_pr_ids: List[str]
    ) -> AtomicLevelQuery:
        """
        Build atomic-level query from single PR.

        Args:
            pr: PR record
            chain_id: Chain identifier
            position: Position in chain (1-indexed)
            total_prs: Total PRs in chain
            preceding_pr_ids: IDs of preceding PRs
            following_pr_ids: IDs of following PRs

        Returns:
            AtomicLevelQuery artifact
        """
        # Build PR metadata
        pr_metadata = PRMetadata(
            pr_id=pr.pr_id,
            pr_number=pr.pr_number,
            repository=pr.repository,
            title=pr.title,
            author=pr.author,
            created_at=pr.created_at,
            merged_at=pr.merged_at,
            labels=pr.labels,
            function_type=infer_function_type(pr.title, pr.labels)
        )

        # Build chain context
        chain_context = ChainContext(
            chain_id=chain_id,
            position_in_chain=position,
            total_prs_in_chain=total_prs,
            is_first=(position == 1),
            is_last=(position == total_prs),
            preceding_pr_ids=preceding_pr_ids,
            following_pr_ids=following_pr_ids
        )

        # Step 1: Synthesize intent using LLM
        intent = self.intent_synthesizer.synthesize_atomic_intent(pr)

        # Step 2: Generate natural language query using LLM
        query_text = self.query_generator.generate_atomic_query(
            synthesized_intent=intent,
            repository=pr.repository
        )

        # Extract scope
        modules = list(extract_modules(pr.files_changed))
        key_areas = extract_key_areas(pr.files_changed)

        scope = TaskScope(
            modules=modules,
            files=pr.files_changed,
            functions=[]
        )

        # Generate constraints
        constraints = self._generate_constraints(pr)

        # Build task specification
        task_spec = TaskSpecification(
            intent=intent,
            description=query_text,  # Use generated query as description
            scope=scope,
            evolution_narrative="",  # Not needed for atomic queries
            constraints=constraints
        )

        # Generate ground truth
        patch = self.ground_truth_gen.generate_pr_patch(pr)
        validation_criteria = self.ground_truth_gen.generate_validation_criteria(pr)

        ground_truth = GroundTruth(
            patch=patch,
            base_commit=pr.base_commit,
            head_commit=pr.head_commit,
            validation_criteria=validation_criteria
        )

        # Build query artifact
        query = AtomicLevelQuery(
            query_id=f"atomic-{chain_id}-pr{position}",
            pr_metadata=pr_metadata,
            chain_context=chain_context,
            task_specification=task_spec,
            ground_truth=ground_truth,
            prompt=query_text  # Use LLM-generated query directly
        )

        return query

    def _generate_constraints(self, pr: PRRecord) -> List[str]:
        """Generate implementation constraints for atomic query."""
        constraints = [
            "Follow existing code style and conventions",
            "Ensure all tests pass"
        ]

        # Add function-type specific constraints
        func_type = infer_function_type(pr.title, pr.labels)

        if func_type == "BUG":
            constraints.append("Include test case that reproduces the bug")
        elif func_type == "ENH":
            constraints.append("Add tests for new functionality")
        elif func_type == "DOC":
            constraints.append("Follow documentation standards")
        elif func_type == "TST":
            constraints.append("Ensure test coverage is improved")

        # Add file-specific constraints
        if any(f.endswith('.test.js') or f.endswith('.spec.ts') for f in pr.files_changed):
            constraints.append("Maintain test isolation and independence")

        if any('api' in f.lower() or 'endpoint' in f.lower() for f in pr.files_changed):
            constraints.append("Maintain API backward compatibility")

        return constraints

