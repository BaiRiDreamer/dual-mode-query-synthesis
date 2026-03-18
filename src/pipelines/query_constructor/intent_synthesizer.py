"""Intent synthesis for query generation using LLM."""

from typing import List, Dict, Any, Optional
from pathlib import Path
from ...models.artifacts import PRRecord


class IntentSynthesizer:
    """Synthesizes high-level intent from PR metadata using LLM."""

    def __init__(self, llm_client=None):
        """
        Initialize intent synthesizer.

        Args:
            llm_client: LLM client for intent generation
        """
        self.llm_client = llm_client
        self._load_prompts()

    def _load_prompts(self):
        """Load prompt templates from files."""
        prompt_dir = Path(__file__).parent.parent.parent / "prompts" / "intent_synthesis"

        # Load chain-level intent prompt
        chain_intent_path = prompt_dir / "chain_level_intent.txt"
        if chain_intent_path.exists():
            with open(chain_intent_path, 'r') as f:
                self.chain_intent_prompt = f.read()
        else:
            self.chain_intent_prompt = self._get_default_chain_intent_prompt()

        # Load atomic-level intent prompt
        atomic_intent_path = prompt_dir / "atomic_level_intent.txt"
        if atomic_intent_path.exists():
            with open(atomic_intent_path, 'r') as f:
                self.atomic_intent_prompt = f.read()
        else:
            self.atomic_intent_prompt = self._get_default_atomic_intent_prompt()

    def synthesize_chain_intent(
        self,
        repository: str,
        topic: str,
        evolution_pattern: str,
        pr_records: List[PRRecord],
        reasoning: str
    ) -> str:
        """
        Synthesize high-level intent for entire PR chain using LLM.

        Args:
            repository: Repository name
            topic: Chain topic
            evolution_pattern: Evolution pattern (incremental_enhancement, etc.)
            pr_records: List of PR records in chain
            reasoning: LLM judgment reasoning

        Returns:
            High-level intent statement from user perspective
        """
        if not pr_records:
            return f"Implement {topic}"

        # Fallback to rule-based if no LLM client
        if not self.llm_client:
            return self._fallback_chain_intent(topic, pr_records)

        # Format PR sequence information
        pr_sequence_info = self._format_pr_sequence(pr_records)

        # Build prompt
        prompt = self.chain_intent_prompt.format(
            repository=repository,
            topic=topic,
            evolution_pattern=evolution_pattern,
            pr_sequence_info=pr_sequence_info
        )

        # Generate intent using LLM
        try:
            intent = self.llm_client.generate(prompt, temperature=0.8, max_tokens=600)
            return intent.strip()
        except Exception as e:
            print(f"Warning: LLM intent synthesis failed: {e}")
            return self._fallback_chain_intent(topic, pr_records)

    def synthesize_atomic_intent(self, pr: PRRecord) -> str:
        """
        Synthesize intent for a single PR using LLM.

        Args:
            pr: PR record

        Returns:
            Focused intent statement from user perspective
        """
        # Fallback to rule-based if no LLM client
        if not self.llm_client:
            return self._fallback_atomic_intent(pr)

        # Format PR information
        files_changed = ", ".join(pr.files_changed[:10])
        if len(pr.files_changed) > 10:
            files_changed += f" (and {len(pr.files_changed) - 10} more)"

        # Summarize diff
        diff_summary = self._summarize_diff(pr.patches)

        # Build prompt
        prompt = self.atomic_intent_prompt.format(
            pr_title=pr.title,
            pr_description=pr.description or "No description provided",
            files_changed=files_changed,
            diff_summary=diff_summary
        )

        # Generate intent using LLM
        try:
            intent = self.llm_client.generate(prompt, temperature=0.8, max_tokens=300)
            return intent.strip()
        except Exception as e:
            print(f"Warning: LLM intent synthesis failed: {e}")
            return self._fallback_atomic_intent(pr)

    def _format_pr_sequence(self, pr_records: List[PRRecord]) -> str:
        """Format PR sequence for prompt."""
        lines = []
        for idx, pr in enumerate(pr_records, 1):
            lines.append(f"PR {idx}: {pr.title}")
            if pr.description:
                # Truncate long descriptions
                desc = pr.description[:200] + "..." if len(pr.description) > 200 else pr.description
                lines.append(f"  Description: {desc}")
            lines.append(f"  Files changed: {len(pr.files_changed)} files")
            if pr.files_changed:
                sample_files = pr.files_changed[:3]
                lines.append(f"  Sample files: {', '.join(sample_files)}")
            lines.append("")

        return "\n".join(lines)

    def _summarize_diff(self, patches: List[Any]) -> str:
        """Summarize diff patches."""
        if not patches:
            return "No diff information available"

        total_additions = 0
        total_deletions = 0

        for patch in patches[:5]:  # Sample first 5 patches
            if hasattr(patch, 'additions'):
                total_additions += patch.additions
            if hasattr(patch, 'deletions'):
                total_deletions += patch.deletions

        return f"+{total_additions} -{total_deletions} lines across {len(patches)} files"

    def _fallback_chain_intent(self, topic: str, pr_records: List[PRRecord]) -> str:
        """Fallback rule-based chain intent generation."""
        pr_titles = [pr.title for pr in pr_records]
        return (
            f"Implement {topic} through {len(pr_records)} related changes: "
            f"{', '.join(pr_titles[:3])}"
            + (f", and {len(pr_titles) - 3} more" if len(pr_titles) > 3 else "")
        )

    def _fallback_atomic_intent(self, pr: PRRecord) -> str:
        """Fallback rule-based atomic intent generation."""
        if pr.description:
            return f"{pr.title}. {pr.description[:100]}"
        return pr.title

    def _get_default_chain_intent_prompt(self) -> str:
        """Get default chain intent prompt if file not found."""
        return """Analyze these PRs and reconstruct the original user request:

Repository: {repository}
Topic: {topic}
Pattern: {evolution_pattern}

PRs:
{pr_sequence_info}

Write the original user request (100-400 words):"""

    def _get_default_atomic_intent_prompt(self) -> str:
        """Get default atomic intent prompt if file not found."""
        return """Analyze this PR and reconstruct the original user request:

Title: {pr_title}
Description: {pr_description}
Files: {files_changed}
Changes: {diff_summary}

Write the original user request (50-200 words):"""
