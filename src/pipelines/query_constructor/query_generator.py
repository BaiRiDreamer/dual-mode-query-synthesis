"""Query generation using LLM - converts intent to natural user queries."""

from typing import List, Optional
from pathlib import Path


class QueryGenerator:
    """Generates natural language queries from synthesized intent using LLM."""

    def __init__(self, llm_client=None):
        """
        Initialize query generator.

        Args:
            llm_client: LLM client for query generation
        """
        self.llm_client = llm_client
        self._load_prompts()

    def _load_prompts(self):
        """Load prompt templates from files."""
        prompt_dir = Path(__file__).parent.parent.parent / "prompts" / "query_generation"

        # Load chain-level query prompt
        chain_query_path = prompt_dir / "chain_level_query.txt"
        if chain_query_path.exists():
            with open(chain_query_path, 'r') as f:
                self.chain_query_prompt = f.read()
        else:
            self.chain_query_prompt = self._get_default_chain_query_prompt()

        # Load atomic-level query prompt
        atomic_query_path = prompt_dir / "atomic_level_query.txt"
        if atomic_query_path.exists():
            with open(atomic_query_path, 'r') as f:
                self.atomic_query_prompt = f.read()
        else:
            self.atomic_query_prompt = self._get_default_atomic_query_prompt()

    def generate_chain_query(
        self,
        synthesized_intent: str,
        repository: str,
        modules: List[str]
    ) -> str:
        """
        Generate chain-level query from synthesized intent.

        Args:
            synthesized_intent: The intent synthesized from PR chain
            repository: Repository name
            modules: Main modules involved

        Returns:
            Natural language query from user perspective
        """
        # Fallback if no LLM client
        if not self.llm_client:
            return self._fallback_chain_query(synthesized_intent, repository)

        # Format modules
        modules_str = ", ".join(modules[:5]) if modules else "various modules"

        # Build prompt
        prompt = self.chain_query_prompt.format(
            synthesized_intent=synthesized_intent,
            repository=repository,
            modules=modules_str
        )

        # Generate query using LLM
        try:
            query = self.llm_client.generate(prompt, temperature=0.9, max_tokens=800)
            return query.strip()
        except Exception as e:
            print(f"Warning: LLM query generation failed: {e}")
            return self._fallback_chain_query(synthesized_intent, repository)

    def generate_atomic_query(
        self,
        synthesized_intent: str,
        repository: str
    ) -> str:
        """
        Generate atomic-level query from synthesized intent.

        Args:
            synthesized_intent: The intent synthesized from single PR
            repository: Repository name

        Returns:
            Natural language query from user perspective
        """
        # Fallback if no LLM client
        if not self.llm_client:
            return self._fallback_atomic_query(synthesized_intent)

        # Build prompt
        prompt = self.atomic_query_prompt.format(
            synthesized_intent=synthesized_intent,
            repository=repository
        )

        # Generate query using LLM
        try:
            query = self.llm_client.generate(prompt, temperature=0.9, max_tokens=500)
            return query.strip()
        except Exception as e:
            print(f"Warning: LLM query generation failed: {e}")
            return self._fallback_atomic_query(synthesized_intent)

    def _fallback_chain_query(self, intent: str, repository: str) -> str:
        """Fallback query generation without LLM."""
        return f"In the {repository} repository, I need to: {intent}"

    def _fallback_atomic_query(self, intent: str) -> str:
        """Fallback query generation without LLM."""
        return intent

    def _get_default_chain_query_prompt(self) -> str:
        """Get default chain query prompt if file not found."""
        return """You are a user requesting development work.

Requirement: {synthesized_intent}
Repository: {repository}
Modules: {modules}

Write your request naturally (150-500 words):"""

    def _get_default_atomic_query_prompt(self) -> str:
        """Get default atomic query prompt if file not found."""
        return """You are a user requesting development work.

Requirement: {synthesized_intent}
Repository: {repository}

Write your request naturally (50-300 words):"""
