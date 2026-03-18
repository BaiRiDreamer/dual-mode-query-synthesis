"""Chain-level query builder using LLM-based generation."""

from typing import List, Dict, Any, Optional
from pathlib import Path
from ...models.artifacts import (
    PRRecord, ChainLevelQuery, ChainMetadata, TaskSpecification,
    TaskScope, GroundTruth, PRSequenceItem
)
from ...utils.text_utils import extract_modules, extract_key_areas, infer_function_type
from .intent_synthesizer import IntentSynthesizer
from .query_generator import QueryGenerator
from .ground_truth_generator import GroundTruthGenerator


class ChainLevelBuilder:
    """Builds chain-level queries from PR chains using LLM."""

    def __init__(self, llm_client=None):
        """
        Initialize chain-level builder.

        Args:
            llm_client: Optional LLM client for query generation
        """
        self.llm_client = llm_client
        self.intent_synthesizer = IntentSynthesizer(llm_client)
        self.query_generator = QueryGenerator(llm_client)
        self.ground_truth_gen = GroundTruthGenerator()

    def build_query(
        self,
        chain_id: str,
        pr_records: List[PRRecord],
        llm_judgment: Dict[str, Any],
        quality_score: float
    ) -> ChainLevelQuery:
        """
        Build chain-level query from PR chain.

        Args:
            chain_id: Chain identifier
            pr_records: List of PR records
            llm_judgment: LLM judgment data
            quality_score: Quality score

        Returns:
            ChainLevelQuery artifact
        """
        # Extract metadata
        repository = pr_records[0].repository if pr_records else "unknown"
        topic = self._extract_topic(pr_records, llm_judgment)
        evolution_pattern = llm_judgment.get("evolution_pattern", "unknown")

        # Build metadata
        chain_metadata = ChainMetadata(
            chain_id=chain_id,
            repository=repository,
            topic=topic,
            evolution_pattern=evolution_pattern,
            quality_score=quality_score,
            pr_count=len(pr_records),
            total_commits=sum(1 for pr in pr_records if pr.head_commit),
            file_overlap_rate=0.0
        )

        # Step 1: Synthesize intent using LLM
        intent = self.intent_synthesizer.synthesize_chain_intent(
            repository=repository,
            topic=topic,
            evolution_pattern=evolution_pattern,
            pr_records=pr_records,
            reasoning=llm_judgment.get("reasoning", "")
        )

        # Extract scope
        all_files = []
        for pr in pr_records:
            all_files.extend(pr.files_changed)

        modules = list(extract_modules(all_files))
        key_areas = extract_key_areas(all_files)

        # Step 2: Generate natural language query using LLM
        query_text = self.query_generator.generate_chain_query(
            synthesized_intent=intent,
            repository=repository,
            modules=modules
        )

        # Build scope
        scope = TaskScope(
            modules=modules,
            files=list(set(all_files)),
            functions=[]
        )

        # Generate constraints
        constraints = self._generate_constraints(pr_records, llm_judgment)

        # Build task specification
        task_spec = TaskSpecification(
            intent=intent,
            description=query_text,  # Use generated query as description
            scope=scope,
            evolution_narrative="",  # Not needed with LLM-generated query
            constraints=constraints
        )

        # Build PR sequence
        pr_sequence = self._build_pr_sequence(pr_records, llm_judgment)

        # Generate ground truth
        cumulative_patch = self.ground_truth_gen.generate_cumulative_patch(pr_records)
        validation_criteria = ["All changes integrate cohesively", "Tests pass", "Code quality maintained"]

        ground_truth = GroundTruth(
            patch=cumulative_patch,
            base_commit=pr_records[0].base_commit if pr_records else None,
            head_commit=pr_records[-1].head_commit if pr_records else None,
            validation_criteria=validation_criteria
        )

        # Build query artifact
        query = ChainLevelQuery(
            query_id=f"chain-level-{chain_id}",
            chain_metadata=chain_metadata,
            task_specification=task_spec,
            pr_sequence=pr_sequence,
            ground_truth=ground_truth,
            prompt=query_text  # Use LLM-generated query directly
        )

        return query

    def _extract_topic(self, pr_records: List[PRRecord], llm_judgment: Dict[str, Any]) -> str:
        """Extract topic from PR records and judgment."""
        # Try to get from judgment
        if "topic" in llm_judgment:
            return llm_judgment["topic"]

        # Try to extract from reasoning
        reasoning = llm_judgment.get("reasoning", "")
        if reasoning:
            import re
            match = re.search(r'(all|both|three|four).*(PR|change)s?\s+(?:are|center|focus|concern)\s+(?:on|around)\s+([^.]+)', reasoning, re.IGNORECASE)
            if match:
                return match.group(3).strip()

        # Fallback to first PR title
        if pr_records:
            return pr_records[0].title

        return "unknown"

    def _build_pr_sequence(self, pr_records: List[PRRecord], llm_judgment: Dict[str, Any]) -> List[PRSequenceItem]:
        """Build PR sequence items."""
        sequence = []
        function_types = llm_judgment.get("function_types", [])

        for idx, pr in enumerate(pr_records):
            # Infer function type
            func_type = function_types[idx] if idx < len(function_types) else infer_function_type(pr.title, pr.labels)

            # Assign role
            role = self._assign_role(idx, len(pr_records), func_type)

            # Generate validation criteria
            criteria = self.ground_truth_gen.generate_validation_criteria(pr)

            sequence.append(PRSequenceItem(
                pr_id=pr.pr_id,
                title=pr.title,
                description=pr.description,
                function_type=func_type,
                files_changed=pr.files_changed,
                base_commit=pr.base_commit,
                head_commit=pr.head_commit,
                patches=pr.patches,
                role_in_chain=role,
                validation_criteria=criteria
            ))

        return sequence

    def _assign_role(self, index: int, total: int, func_type: str) -> str:
        """Assign role to PR in chain."""
        if index == 0:
            return "foundation"
        elif index == total - 1:
            return "refinement"
        elif func_type == "BUG":
            return "bugfix"
        else:
            return "enhancement"

    def _generate_constraints(self, pr_records: List[PRRecord], llm_judgment: Dict[str, Any]) -> List[str]:
        """Generate implementation constraints."""
        constraints = [
            "Maintain backward compatibility unless explicitly breaking changes are noted",
            "Follow existing code style and conventions",
            "Ensure all existing tests continue to pass"
        ]

        evolution_pattern = llm_judgment.get("evolution_pattern", "")
        if evolution_pattern == "incremental_enhancement":
            constraints.append("Each change should build incrementally on the previous state")

        function_types = llm_judgment.get("function_types", [])
        if "BUG" in function_types:
            constraints.append("Include regression tests for fixed bugs")
        if "DOC" in function_types:
            constraints.append("Ensure documentation follows project standards")

        return constraints
