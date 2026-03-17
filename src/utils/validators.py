"""Validation utilities for query synthesis."""

from typing import Dict, Any, List
from ..models.artifacts import PRChain, ChainLevelQuery, AtomicLevelQuery


def validate_pr_chain(chain_data: Dict[str, Any]) -> bool:
    """
    Validate PR chain data structure.

    Args:
        chain_data: Raw chain data from input file

    Returns:
        True if valid, False otherwise
    """
    required_fields = ["chain_id", "original_chain", "status", "quality_score", "llm_judgment"]

    for field in required_fields:
        if field not in chain_data:
            print(f"Missing required field: {field}")
            return False

    if not isinstance(chain_data["original_chain"], list):
        print("original_chain must be a list")
        return False

    if len(chain_data["original_chain"]) == 0:
        print("original_chain cannot be empty")
        return False

    if not isinstance(chain_data["llm_judgment"], dict):
        print("llm_judgment must be a dict")
        return False

    return True


def validate_query(query: Any) -> List[str]:
    """
    Validate generated query artifact.

    Args:
        query: ChainLevelQuery or AtomicLevelQuery instance

    Returns:
        List of validation error messages (empty if valid)
    """
    errors = []

    if isinstance(query, ChainLevelQuery):
        if not query.prompt or len(query.prompt.strip()) == 0:
            errors.append("Prompt cannot be empty")

        if not query.pr_sequence or len(query.pr_sequence) == 0:
            errors.append("PR sequence cannot be empty")

        if not query.ground_truth.patch:
            errors.append("Ground truth patch is required")

        if query.chain_metadata.pr_count != len(query.pr_sequence):
            errors.append("PR count mismatch in metadata")

    elif isinstance(query, AtomicLevelQuery):
        if not query.prompt or len(query.prompt.strip()) == 0:
            errors.append("Prompt cannot be empty")

        if not query.ground_truth.patch:
            errors.append("Ground truth patch is required")

        if not query.pr_metadata.pr_id:
            errors.append("PR ID is required")

    else:
        errors.append(f"Unknown query type: {type(query)}")

    return errors


def validate_commit_sha(sha: str) -> bool:
    """Validate commit SHA format."""
    if not sha:
        return False
    if len(sha) < 7 or len(sha) > 40:
        return False
    try:
        int(sha, 16)
        return True
    except ValueError:
        return False
