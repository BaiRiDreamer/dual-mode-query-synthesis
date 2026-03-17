"""Unit tests for dual-mode query synthesis."""

import pytest
from src.models.artifacts import PRRecord, DiffPatch
from src.utils.text_utils import (
    extract_modules,
    extract_action_verb,
    extract_subject,
    infer_function_type
)


def test_extract_modules():
    """Test module extraction from file paths."""
    files = [
        "scipy/sparse/base.py",
        "scipy/sparse/tests/test_base.py",
        "scipy/special/orthogonal.py"
    ]
    modules = extract_modules(files)
    assert "scipy" in modules


def test_extract_action_verb():
    """Test action verb extraction from PR titles."""
    assert extract_action_verb("Add new feature") == "Add"
    assert extract_action_verb("Fix bug in parser") == "Fix"
    assert extract_action_verb("Update documentation") == "Update"


def test_extract_subject():
    """Test subject extraction from PR titles."""
    assert "new feature" in extract_subject("Add new feature")
    assert "bug in parser" in extract_subject("Fix bug in parser")


def test_infer_function_type():
    """Test function type inference."""
    assert infer_function_type("Fix bug in parser", ["bug"]) == "BUG"
    assert infer_function_type("Add new feature", ["enhancement"]) == "ENH"
    assert infer_function_type("Update docs", ["documentation"]) == "DOC"


def test_pr_record_creation():
    """Test PR record creation."""
    pr = PRRecord(
        pr_id="scipy/scipy#333",
        pr_number=333,
        repository="scipy/scipy",
        title="Test PR",
        author="testuser",
        files_changed=["test.py"]
    )
    assert pr.pr_id == "scipy/scipy#333"
    assert pr.pr_number == 333


if __name__ == "__main__":
    pytest.main([__file__])
