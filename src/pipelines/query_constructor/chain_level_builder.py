"""Chain-level query builder."""

from typing import List, Dict, Any, Optional
from jinja2 import Template
from pathlib import Path
from ...models.artifacts import (
    PRRecord, ChainLevelQuery, ChainMetadata, TaskSpecification,
    TaskScope, GroundTruth, PRSequenceItem
)
from ...utils.text_utils import extract_modules, extract_key_areas, infer_function_type
from .intent_synthesizer import IntentSynthesizer
from .ground_truth_generator import GroundTruthGenerator


class ChainLevelBuilder:
    """Builds chain-level queries from PR chains."""

    def __init__(self, template_path: str, llm_client=None):
        """
        Initialize chain-level builder.

        Args:
            template_path: Path to Jinja2 template file
            llm_client: Optional LLM client for intent synthesis
        """
        self.template_path = Path(template_path)
        self.llm_client = llm_client
        self.intent_synthesizer = IntentSynthesizer(llm_client)
        self.ground_truth_gen = GroundTruthGenerator()
        self._load_template()

    def _load_template(self):
        """Load Jinja2 template."""
        if self.template_path.exists():
            with open(self.template_path, 'r') as f:
                self.template = Template(f.read())
        else:
            # Use default template if file doesn't exist
            self.template = Template(self._get_default_template())

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
            file_overlap_rate=0.0  # Could be computed if needed
        )

        # Synthesize intent
        intent = self.intent_synthesizer.synthesize_chain_intent(
            topic=topic,
            evolution_pattern=evolution_pattern,
            pr_records=pr_records,
            reasoning=llm_judgment.get("reasoning", "")
        )

        # Build evolution narrative
        evolution_narrative = self.intent_synthesizer.build_evolution_narrative(
            pr_records=pr_records,
            evolution_pattern=evolution_pattern,
            reasoning=llm_judgment.get("reasoning", "")
        )

        # Extract scope
        all_files = []
        for pr in pr_records:
            all_files.extend(pr.files_changed)

        modules = list(extract_modules(all_files))
        key_areas = extract_key_areas(all_files)

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
            description=evolution_narrative,
            scope=scope,
            evolution_narrative=evolution_narrative,
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

        # Render prompt
        prompt = self._render_prompt(
            repository=repository,
            pr_count=len(pr_records),
            evolution_intent=intent,
            evolution_pattern=evolution_pattern,
            task_intent=intent,
            evolution_narrative=evolution_narrative,
            pr_sequence=pr_sequence,
            modules=modules,
            files=list(set(all_files)),
            key_areas=key_areas,
            constraints=constraints
        )

        # Build query artifact
        query = ChainLevelQuery(
            query_id=f"chain-level-{chain_id}",
            chain_metadata=chain_metadata,
            task_specification=task_spec,
            pr_sequence=pr_sequence,
            ground_truth=ground_truth,
            prompt=prompt
        )

        return query

    def _extract_topic(self, pr_records: List[PRRecord], llm_judgment: Dict[str, Any]) -> str:
        """Extract topic from PR records and judgment."""
        # Try to extract from reasoning
        reasoning = llm_judgment.get("reasoning", "")
        if reasoning:
            # Look for topic indicators
            import re
            match = re.search(r'(all|both|three|four).*(PR|change)s?\s+(?:are|center|focus|concern)\s+(?:on|around)\s+([^.]+)', reasoning, re.IGNORECASE)
            if match:
                return match.group(3).strip()

        # Fallback to common words in titles
        from ...pipelines.query_constructor.context_enricher import ContextEnricher
        from ...utils.github_client import GitHubClient
        enricher = ContextEnricher(GitHubClient())
        return enricher.extract_topic_from_chain(pr_records)

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

    def _render_prompt(self, **context) -> str:
        """Render prompt from template."""
        return self.template.render(**context)

    def _get_default_template(self) -> str:
        """Get default template content."""
        return """## Role
You are an AI Software Evolution Architect tasked with implementing a complete feature evolution chain in the {{ repository }} repository.

## Evolution Context
This task involves implementing a sequence of {{ pr_count }} interconnected changes that collectively achieve: {{ evolution_intent }}

The evolution follows a {{ evolution_pattern }} pattern.

## Task Specification

### High-Level Intent
{{ task_intent }}

### Scope
- **Modules**: {{ modules | join(', ') }}
- **Files**: {{ files[:10] | join(', ') }}{% if files|length > 10 %} (and {{ files|length - 10 }} more){% endif %}
- **Key Areas**: {{ key_areas | join(', ') }}

### Evolution Narrative
{{ evolution_narrative }}

### Implementation Constraints
{% for constraint in constraints %}
- {{ constraint }}
{% endfor %}

## Execution Guidelines

### Phase 1: Foundation Analysis
1. Examine the repository structure and identify the baseline state
2. Understand the architectural context for the changes
3. Review existing tests and documentation

### Phase 2: Incremental Implementation
Implement the changes in sequence, ensuring each step builds on the previous:

{% for pr in pr_sequence %}
#### Step {{ loop.index }}: {{ pr.title }}
- **Objective**: {{ pr.description[:200] if pr.description else pr.title }}
- **Files to modify**: {{ pr.files_changed[:5] | join(', ') }}{% if pr.files_changed|length > 5 %} (and {{ pr.files_changed|length - 5 }} more){% endif %}
- **Role**: {{ pr.role_in_chain }}

{% endfor %}

### Phase 3: Integration & Validation
1. Verify that all changes work together cohesively
2. Run comprehensive tests across the entire change set
3. Validate that the cumulative effect matches the intended evolution

## Critical Success Factors
- Maintain consistency across all {{ pr_count }} changes
- Preserve backward compatibility where specified
- Ensure each incremental change is functional before proceeding

## Output Requirements
Your implementation should result in changes that collectively achieve the evolution goal while maintaining code quality and test coverage.
"""
