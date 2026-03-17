"""Intent synthesis for query generation."""

from typing import List, Dict, Any, Optional
from ...models.artifacts import PRRecord
from ...utils.text_utils import extract_action_verb, extract_subject, extract_key_context


class IntentSynthesizer:
    """Synthesizes high-level intent from PR metadata."""

    def __init__(self, llm_client=None):
        """
        Initialize intent synthesizer.

        Args:
            llm_client: Optional LLM client for enhanced synthesis
        """
        self.llm_client = llm_client

    def synthesize_chain_intent(
        self,
        topic: str,
        evolution_pattern: str,
        pr_records: List[PRRecord],
        reasoning: str
    ) -> str:
        """
        Synthesize high-level intent for entire PR chain.

        Args:
            topic: Chain topic
            evolution_pattern: Evolution pattern (incremental_enhancement, etc.)
            pr_records: List of PR records in chain
            reasoning: LLM judgment reasoning

        Returns:
            High-level intent statement
        """
        if not pr_records:
            return f"Implement {topic}"

        # Extract key information
        pr_titles = [pr.title for pr in pr_records]
        first_pr = pr_records[0]
        last_pr = pr_records[-1]

        # Build intent based on evolution pattern
        if evolution_pattern == "incremental_enhancement":
            intent = self._build_incremental_intent(topic, pr_titles, first_pr, last_pr)
        elif evolution_pattern == "collaborative_development":
            intent = self._build_collaborative_intent(topic, pr_titles, reasoning)
        else:
            intent = self._build_generic_intent(topic, pr_titles, pr_records)

        return intent

    def _build_incremental_intent(
        self,
        topic: str,
        pr_titles: List[str],
        first_pr: PRRecord,
        last_pr: PRRecord
    ) -> str:
        """Build intent for incremental enhancement pattern."""
        first_action = extract_action_verb(first_pr.title)
        first_subject = extract_subject(first_pr.title)
        last_subject = extract_subject(last_pr.title)

        return (
            f"Systematically {first_action.lower()} {topic} through incremental optimizations, "
            f"starting with {first_subject}, and progressively extending to {last_subject}."
        )

    def _build_collaborative_intent(
        self,
        topic: str,
        pr_titles: List[str],
        reasoning: str
    ) -> str:
        """Build intent for collaborative development pattern."""
        # Extract key phrases from reasoning
        key_phrases = self._extract_key_phrases(reasoning)

        return (
            f"Implement {topic} through collaborative development, "
            f"involving {len(pr_titles)} interconnected changes that collectively "
            f"address {', '.join(key_phrases[:2])}."
        )

    def _build_generic_intent(
        self,
        topic: str,
        pr_titles: List[str],
        pr_records: List[PRRecord]
    ) -> str:
        """Build generic intent statement."""
        actions = [extract_action_verb(title) for title in pr_titles]
        unique_actions = list(dict.fromkeys(actions))  # Preserve order

        return (
            f"Implement {topic} through {len(pr_records)} related changes that "
            f"{', '.join(unique_actions[:3]).lower()} the functionality."
        )

    def synthesize_atomic_intent(self, pr: PRRecord) -> str:
        """
        Synthesize intent for a single PR.

        Args:
            pr: PR record

        Returns:
            Focused intent statement
        """
        action = extract_action_verb(pr.title)
        subject = extract_subject(pr.title)

        # Enrich with description if available
        if pr.description:
            context = extract_key_context(pr.description, max_length=100)
            if context:
                return f"{action} {subject} to {context}"

        return f"{action} {subject}"

    def build_evolution_narrative(
        self,
        pr_records: List[PRRecord],
        evolution_pattern: str,
        reasoning: str
    ) -> str:
        """
        Build evolution narrative for chain-level queries.

        Args:
            pr_records: List of PR records
            evolution_pattern: Evolution pattern
            reasoning: LLM judgment reasoning

        Returns:
            Evolution narrative
        """
        if not pr_records:
            return ""

        narrative_parts = []

        # Opening
        narrative_parts.append(
            f"This evolution follows a {evolution_pattern.replace('_', ' ')} pattern, "
            f"progressing through {len(pr_records)} stages:"
        )

        # Describe each PR's role
        for idx, pr in enumerate(pr_records, 1):
            role = self._infer_pr_role(idx, len(pr_records), pr)
            narrative_parts.append(
                f"{idx}. {pr.title} - {role}"
            )

        # Closing with reasoning insight
        key_insight = self._extract_key_insight(reasoning)
        if key_insight:
            narrative_parts.append(f"\n{key_insight}")

        return "\n".join(narrative_parts)

    def _infer_pr_role(self, index: int, total: int, pr: PRRecord) -> str:
        """Infer the role of a PR in the chain."""
        if index == 1:
            return "establishes the foundation"
        elif index == total:
            return "completes and refines the implementation"
        else:
            action = extract_action_verb(pr.title).lower()
            return f"{action}s upon the previous work"

    def _extract_key_phrases(self, text: str, max_phrases: int = 3) -> List[str]:
        """Extract key phrases from text."""
        # Simple extraction: look for phrases after common markers
        phrases = []

        # Look for phrases after colons or dashes
        import re
        matches = re.findall(r'[:\-]\s*([^.,:;]+)', text)
        phrases.extend([m.strip() for m in matches if len(m.strip()) > 10])

        # Look for quoted phrases
        quoted = re.findall(r'"([^"]+)"', text)
        phrases.extend(quoted)

        return phrases[:max_phrases] if phrases else ["key functionality"]

    def _extract_key_insight(self, reasoning: str) -> str:
        """Extract key insight from reasoning."""
        # Look for sentences containing key words
        sentences = reasoning.split(". ")
        for sentence in sentences:
            if any(word in sentence.lower() for word in ["clear", "strong", "explicit", "coherent"]):
                return sentence.strip() + "."

        return ""
