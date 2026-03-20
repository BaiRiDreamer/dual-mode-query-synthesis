"""Tests for resumable synthesis helpers."""

import json

from src.utils.resume_utils import build_resume_plan


def test_build_resume_plan_skips_existing_outputs(tmp_path):
    """Existing valid outputs should be skipped while missing ones stay pending."""
    chain_data = {
        "chain_id": "chain_0001",
        "original_chain": ["owner/repo#10", "owner/repo#11"],
    }

    chain_dir = tmp_path / "chain"
    atomic_dir = tmp_path / "atomic"
    chain_dir.mkdir()
    atomic_dir.mkdir()

    (chain_dir / "chain--owner-repo--10-11.jsonl").write_text(json.dumps({
        "query_id": "chain--owner-repo--10-11",
        "prompt": "chain prompt",
        "ground_truth": {"patch": "diff"}
    }))
    (atomic_dir / "atomic--owner-repo--10.jsonl").write_text(json.dumps({
        "query_id": "atomic--owner-repo--10",
        "prompt": "atomic prompt",
        "ground_truth": {"patch": "diff"}
    }))

    plan = build_resume_plan(
        chain_data,
        mode="both",
        output_chain_dir=chain_dir,
        output_atomic_dir=atomic_dir
    )

    assert plan.skipped_chain is True
    assert plan.needs_chain is False
    assert plan.skipped_atomic_pr_ids == ["owner/repo#10"]
    assert plan.pending_atomic_pr_ids == ["owner/repo#11"]


def test_build_resume_plan_reruns_invalid_existing_outputs(tmp_path):
    """Corrupt or incomplete outputs should not be treated as complete."""
    chain_data = {
        "chain_id": "chain_0002",
        "original_chain": ["owner/repo#20"],
    }

    chain_dir = tmp_path / "chain"
    atomic_dir = tmp_path / "atomic"
    chain_dir.mkdir()
    atomic_dir.mkdir()

    (chain_dir / "chain--owner-repo--20.jsonl").write_text("{bad json")
    (atomic_dir / "atomic--owner-repo--20.jsonl").write_text(json.dumps({
        "query_id": "atomic--owner-repo--20",
        "prompt": "",
        "ground_truth": {"patch": ""}
    }))

    plan = build_resume_plan(
        chain_data,
        mode="both",
        output_chain_dir=chain_dir,
        output_atomic_dir=atomic_dir
    )

    assert plan.needs_chain is True
    assert plan.pending_atomic_pr_ids == ["owner/repo#20"]
