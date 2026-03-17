"""Text processing utilities."""

import re
from typing import List, Set
from pathlib import Path


def truncate_text(text: str, max_length: int = 200, suffix: str = "...") -> str:
    """
    Truncate text to maximum length.

    Args:
        text: Text to truncate
        max_length: Maximum length in characters
        suffix: Suffix to append when truncated

    Returns:
        Truncated text
    """
    if not text:
        return ""

    if len(text) <= max_length:
        return text

    return text[:max_length - len(suffix)] + suffix


def extract_modules(file_paths: List[str]) -> Set[str]:
    """
    Extract module names from file paths.

    Args:
        file_paths: List of file paths

    Returns:
        Set of module names
    """
    modules = set()

    for path in file_paths:
        parts = Path(path).parts

        # Skip common non-module directories
        skip_dirs = {"tests", "test", "docs", "examples", "scripts", ".github"}

        for part in parts:
            if part in skip_dirs or part.startswith("."):
                continue

            # Add first meaningful directory as module
            if not part.endswith((".py", ".js", ".ts", ".java", ".cpp", ".h")):
                modules.add(part)
                break

    return modules


def extract_key_areas(file_paths: List[str]) -> List[str]:
    """
    Extract key functional areas from file paths.

    Args:
        file_paths: List of file paths

    Returns:
        List of key areas
    """
    areas = set()

    for path in file_paths:
        parts = Path(path).parts

        # Look for meaningful directory names
        for i, part in enumerate(parts):
            if part in {"src", "lib", "core", "api", "utils", "models"}:
                if i + 1 < len(parts):
                    areas.add(parts[i + 1])
            elif not part.startswith(".") and part not in {"tests", "test", "docs"}:
                areas.add(part)

    return sorted(areas)


def extract_action_verb(title: str) -> str:
    """
    Extract action verb from PR title.

    Args:
        title: PR title

    Returns:
        Action verb (Add, Fix, Update, etc.)
    """
    # Common action verbs in PR titles
    verbs = ["Add", "Fix", "Update", "Remove", "Refactor", "Improve", "Implement",
             "Enhance", "Optimize", "Deprecate", "Replace", "Merge", "Revert"]

    for verb in verbs:
        if title.startswith(verb):
            return verb

    # Default to first word if no known verb found
    first_word = title.split()[0] if title else "Modify"
    return first_word.capitalize()


def extract_subject(title: str) -> str:
    """
    Extract subject from PR title (everything after action verb).

    Args:
        title: PR title

    Returns:
        Subject of the PR
    """
    # Remove common prefixes
    title = re.sub(r"^(Add|Fix|Update|Remove|Refactor|Improve|Implement|Enhance|Optimize)\s+", "", title, flags=re.IGNORECASE)
    return title.strip()


def extract_key_context(description: str, max_length: int = 300) -> str:
    """
    Extract key context from PR description.

    Args:
        description: PR description
        max_length: Maximum length

    Returns:
        Key context summary
    """
    if not description:
        return ""

    # Take first paragraph or sentence
    lines = description.split("\n")
    first_para = lines[0].strip()

    return truncate_text(first_para, max_length)


def infer_function_type(pr_title: str, labels: List[str]) -> str:
    """
    Infer function type from PR title and labels.

    Args:
        pr_title: PR title
        labels: PR labels

    Returns:
        Function type (ENH, BUG, DOC, MAINT, etc.)
    """
    title_lower = pr_title.lower()
    labels_lower = [l.lower() for l in labels]

    # Check labels first
    if any(l in labels_lower for l in ["bug", "fix", "bugfix"]):
        return "BUG"
    if any(l in labels_lower for l in ["enhancement", "feature", "enh"]):
        return "ENH"
    if any(l in labels_lower for l in ["documentation", "docs", "doc"]):
        return "DOC"
    if any(l in labels_lower for l in ["maintenance", "maint", "refactor"]):
        return "MAINT"
    if any(l in labels_lower for l in ["test", "tests", "testing"]):
        return "TST"
    if any(l in labels_lower for l in ["performance", "perf", "optimization"]):
        return "PERF"

    # Check title
    if any(word in title_lower for word in ["fix", "bug", "error", "issue"]):
        return "BUG"
    if any(word in title_lower for word in ["add", "implement", "new", "feature"]):
        return "ENH"
    if any(word in title_lower for word in ["doc", "documentation", "readme"]):
        return "DOC"
    if any(word in title_lower for word in ["refactor", "cleanup", "maintain"]):
        return "MAINT"
    if any(word in title_lower for word in ["test", "testing"]):
        return "TST"
    if any(word in title_lower for word in ["optimize", "performance", "speed"]):
        return "PERF"

    return "ENH"  # Default to enhancement
