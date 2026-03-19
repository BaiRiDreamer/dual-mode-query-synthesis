"""Helpers for resumable query synthesis runs."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple


@dataclass
class ResumePlan:
    """Describes which outputs still need to be generated for one chain."""

    chain_id: str
    chain_output_path: Optional[Path] = None
    needs_chain: bool = False
    pending_atomic_pr_ids: List[str] = field(default_factory=list)
    atomic_output_paths: Dict[str, Path] = field(default_factory=dict)
    skipped_chain: bool = False
    skipped_atomic_pr_ids: List[str] = field(default_factory=list)

    @property
    def skipped_atomic_count(self) -> int:
        return len(self.skipped_atomic_pr_ids)

    @property
    def pending_atomic_count(self) -> int:
        return len(self.pending_atomic_pr_ids)

    def has_work(self) -> bool:
        """Whether this chain still has outputs to generate."""
        return self.needs_chain or bool(self.pending_atomic_pr_ids)


def parse_pr_id(pr_id: str) -> Tuple[str, int]:
    """Parse a PR identifier in ``owner/repo#number`` format."""
    if "#" not in pr_id:
        raise ValueError(f"Invalid PR ID format: {pr_id}")

    repo, number_str = pr_id.rsplit("#", 1)
    return repo, int(number_str)


def build_chain_query_id(chain_data: Dict) -> str:
    """Build the on-disk chain query id without hitting external APIs."""
    original_chain = chain_data["original_chain"]
    first_repo, first_pr_number = parse_pr_id(original_chain[0])
    pr_numbers = [str(parse_pr_id(pr_id)[1]) for pr_id in original_chain]
    pr_range = f"{pr_numbers[0]}-{pr_numbers[-1]}" if len(pr_numbers) > 1 else str(first_pr_number)
    return f"chain--{first_repo.replace('/', '-')}--{pr_range}"


def build_atomic_query_map(chain_data: Dict) -> Dict[str, str]:
    """Map PR ids to the atomic query ids the builders will emit."""
    query_ids = {}
    for pr_id in chain_data["original_chain"]:
        repo, pr_number = parse_pr_id(pr_id)
        query_ids[pr_id] = f"atomic--{repo.replace('/', '-')}--{pr_number}"
    return query_ids


def is_valid_existing_output(output_path: Path, expected_query_id: Optional[str] = None) -> bool:
    """Check whether an existing output file looks complete enough to skip."""
    if not output_path.exists() or output_path.stat().st_size == 0:
        return False

    try:
        payload = json.loads(output_path.read_text())
    except Exception:
        return False

    if not isinstance(payload, dict):
        return False

    if expected_query_id and payload.get("query_id") != expected_query_id:
        return False

    prompt = payload.get("prompt")
    ground_truth = payload.get("ground_truth")
    patch = ground_truth.get("patch") if isinstance(ground_truth, dict) else None

    return bool(prompt and str(prompt).strip()) and isinstance(ground_truth, dict) and bool(patch)


def build_resume_plan(
    chain_data: Dict,
    mode: str,
    output_chain_dir: Optional[Path] = None,
    output_atomic_dir: Optional[Path] = None,
    overwrite_existing: bool = False
) -> ResumePlan:
    """Inspect outputs on disk and decide what still needs to run."""
    plan = ResumePlan(chain_id=chain_data["chain_id"])

    if mode in {"chain", "both"} and output_chain_dir:
        chain_query_id = build_chain_query_id(chain_data)
        chain_output_path = output_chain_dir / f"{chain_query_id}.jsonl"
        plan.chain_output_path = chain_output_path

        if not overwrite_existing and is_valid_existing_output(chain_output_path, chain_query_id):
            plan.skipped_chain = True
        else:
            plan.needs_chain = True

    if mode in {"atomic", "both"} and output_atomic_dir:
        atomic_query_map = build_atomic_query_map(chain_data)

        for pr_id, query_id in atomic_query_map.items():
            output_path = output_atomic_dir / f"{query_id}.jsonl"
            plan.atomic_output_paths[pr_id] = output_path

            if not overwrite_existing and is_valid_existing_output(output_path, query_id):
                plan.skipped_atomic_pr_ids.append(pr_id)
            else:
                plan.pending_atomic_pr_ids.append(pr_id)

    return plan
