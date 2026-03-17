"""Atomic-level query builder."""

from typing import Optional, List
from jinja2 import Template
from pathlib import Path
from ...models.artifacts import (
    PRRecord, AtomicLevelQuery, PRMetadata, ChainContext,
    TaskSpecification, TaskScope, GroundTruth
)
from ...utils.text_utils import extract_modules, extract_key_areas, infer_function_type
from .intent_synthesizer import IntentSynthesizer
from .ground_truth_generator import GroundTruthGenerator


class AtomicLevelBuilder:
    """Builds atomic-level queries from individual PRs."""

    def __init__(self, template_path: str, llm_client=None):
        """
        Initialize atomic-level builder.

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
            self.template = Template(self._get_default_template())

    def build_query(
        self,
        pr: PRRecord,
        chain_id: str,
        position: int,
        total_prs: int,
        preceding_pr_ids: list = None,
        following_pr_ids: list = None
    ) -> AtomicLevelQuery:
        """
        Build atomic-level query from single PR.

        Args:
            pr: PR record
            chain_id: Chain identifier
            position: Position in chain (1-indexed)
            total_prs: Total PRs in chain
            preceding_pr_ids: List of preceding PR IDs
            following_pr_ids: List of following PR IDs

        Returns:
            AtomicLevelQuery artifact
        """
        # Build PR metadata
        func_type = infer_function_type(pr.title, pr.labels)

        pr_metadata = PRMetadata(
            pr_id=pr.pr_id,
            pr_number=pr.pr_number,
            repository=pr.repository,
            title=pr.title,
            author=pr.author,
            created_at=pr.created_at,
            merged_at=pr.merged_at,
            function_type=func_type,
            labels=pr.labels
        )

        # Build chain context
        chain_context = ChainContext(
            chain_id=chain_id,
            position_in_chain=position,
            total_prs_in_chain=total_prs,
            is_first=(position == 1),
            is_last=(position == total_prs),
            preceding_pr_ids=preceding_pr_ids or [],
            following_pr_ids=following_pr_ids or []
        )

        # Synthesize intent
        intent = self.intent_synthesizer.synthesize_atomic_intent(pr)

        # Extract scope
        modules = list(extract_modules(pr.files_changed))
        key_areas = extract_key_areas(pr.files_changed)

        scope = TaskScope(
            modules=modules,
            files=pr.files_changed,
            functions=[]
        )

        # Generate constraints
        constraints = self._generate_constraints(pr, func_type)

        # Build task specification
        task_spec = TaskSpecification(
            intent=intent,
            description=pr.description,
            scope=scope,
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

        # Render prompt
        prompt = self._render_prompt(
            repository=pr.repository,
            pr_id=pr.pr_id,
            pr_title=pr.title,
            pr_description=pr.description or "",
            function_type=func_type,
            task_intent=intent,
            files=pr.files_changed,
            modules=modules,
            key_functions=[],
            constraints=constraints,
            chain_context=chain_context
        )

        # Build query artifact
        query = AtomicLevelQuery(
            query_id=f"atomic-{chain_id}-pr{position}",
            pr_metadata=pr_metadata,
            chain_context=chain_context,
            task_specification=task_spec,
            ground_truth=ground_truth,
            prompt=prompt
        )

        return query

    def _generate_constraints(self, pr: PRRecord, func_type: str) -> list:
        """Generate implementation constraints."""
        constraints = [
            "Maintain code quality and consistency",
            "Follow existing patterns in the codebase",
            "Ensure backward compatibility where applicable"
        ]

        if func_type == "BUG":
            constraints.append("Include regression test for the bug fix")
        elif func_type == "ENH":
            constraints.append("Add tests for new functionality")
        elif func_type == "DOC":
            constraints.append("Ensure documentation is clear and follows project standards")

        return constraints

    def _render_prompt(self, **context) -> str:
        """Render prompt from template."""
        return self.template.render(**context)

    def _get_default_template(self) -> str:
        """Get default template content."""
        return """## Role
You are an AI Software Engineer tasked with implementing a specific code change in the {{ repository }} repository.

## Task Context
This is a {{ function_type }} task: {{ pr_title }}

{% if pr_description %}
### Detailed Description
{{ pr_description }}
{% endif %}

## Task Specification

### Objective
{{ task_intent }}

### Scope
- **Files to modify**: {{ files | join(', ') }}
{% if modules %}
- **Modules affected**: {{ modules | join(', ') }}
{% endif %}

### Implementation Constraints
{% for constraint in constraints %}
- {{ constraint }}
{% endfor %}

## Execution Guidelines

### Step 1: Analysis
1. Read the relevant files to understand the current implementation
2. Identify the specific locations that need modification
3. Understand the existing code patterns and conventions

### Step 2: Implementation
Implement the required changes according to the objective. Focus on:
- Maintaining code quality and consistency
- Following existing patterns in the codebase
- Ensuring backward compatibility where applicable

### Step 3: Validation
1. Verify that your changes compile/run without errors
2. Test the modified functionality
3. Ensure no regressions in existing behavior

## Critical Success Factors
- The implementation should be minimal and focused
- Changes should integrate seamlessly with existing code
- All tests should pass after implementation

{% if chain_context %}
## Additional Context
This change is part of a larger evolution chain ({{ chain_context.position_in_chain }}/{{ chain_context.total_prs_in_chain }}), but should be implemented independently.
{% endif %}

## Output Requirements
Your implementation should result in changes that match the specified objective while maintaining code quality.
"""
