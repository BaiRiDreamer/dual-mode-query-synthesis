"""CLI for dual-mode query synthesis."""

import argparse
import json
import sys
import yaml
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from tqdm import tqdm

from ..pipelines.query_constructor import DualModeBuilder
from ..utils.persistence import atomic_write_text
from ..utils.resume_utils import ResumePlan, build_resume_plan
from ..utils.validators import validate_pr_chain, validate_query


def load_config(config_path: str = "config/config.yaml") -> Dict[str, Any]:
    """Load configuration from YAML file."""
    config_file = Path(config_path)
    if not config_file.exists():
        return {}

    with open(config_file, 'r') as f:
        config = yaml.safe_load(f)

    # Expand environment variables
    llm = config.get("llm", {})
    if "api_key" in llm:
        llm["api_key"] = _expand_env_placeholder(llm.get("api_key"))

    github = config.get("github", {})
    if "token" in github:
        github["token"] = _expand_env_placeholder(github.get("token"))
    if "tokens" in github and isinstance(github["tokens"], list):
        expanded_tokens = []
        for value in github["tokens"]:
            expanded_value = _expand_env_placeholder(value)
            if expanded_value:
                expanded_tokens.append(expanded_value)
        github["tokens"] = expanded_tokens

    return config


def _expand_env_placeholder(value: Any) -> Any:
    """Expand ${ENV_VAR} placeholders for scalar config values."""
    import os

    if isinstance(value, str) and value.startswith("${") and value.endswith("}"):
        env_var = value[2:-1]
        return os.getenv(env_var)
    return value


def load_chains(input_path: Path) -> List[Dict[str, Any]]:
    """Load PR chains from JSONL file."""
    chains = []
    with open(input_path, 'r') as f:
        for line in f:
            if line.strip():
                chains.append(json.loads(line))
    return chains


def filter_chains(
    chains: List[Dict[str, Any]],
    approved_only: bool = True,
    min_quality_score: float = 0.0
) -> List[Dict[str, Any]]:
    """Filter chains based on criteria."""
    filtered = []

    for chain in chains:
        # Validate structure
        if not validate_pr_chain(chain):
            continue

        # Filter by status
        if approved_only and chain.get("status") != "approved":
            continue

        # Filter by quality score
        if chain.get("quality_score", 0.0) < min_quality_score:
            continue

        filtered.append(chain)

    return filtered


def save_chain_query(query, output_dir: Path):
    """Save chain-level query to file."""
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / f"{query.query_id}.jsonl"

    atomic_write_text(output_file, query.model_dump_json(indent=2))


def save_atomic_queries(queries, output_dir: Path, chain_id: str):
    """Save atomic-level queries to files."""
    output_dir.mkdir(parents=True, exist_ok=True)

    for query in queries:
        output_file = output_dir / f"{query.query_id}.jsonl"
        atomic_write_text(output_file, query.model_dump_json(indent=2))


def build_llm_config(config: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Build LLM config if the required fields are present."""
    llm = config.get("llm", {})
    if not llm:
        return None

    llm_config = {
        "api_key": llm.get("api_key"),
        "endpoint": llm.get("endpoint"),
        "model": llm.get("model"),
        "api_version": llm.get("api_version", "2024-08-01-preview"),
        "temperature": llm.get("temperature", 0.7),
        "max_tokens": llm.get("max_tokens", 4096),
        "top_p": llm.get("top_p", 0.95),
        "request_timeout": llm.get("request_timeout", 60.0),
        "max_retries": llm.get("max_retries", 3),
        "initial_retry_delay": llm.get("initial_retry_delay", 1.0),
        "backoff_factor": llm.get("backoff_factor", 2.0),
        "max_retry_delay": llm.get("max_retry_delay", 60.0)
    }

    required_values = ("api_key", "endpoint", "model")
    if not all(llm_config.get(key) for key in required_values):
        print("LLM configuration is incomplete; falling back to rule-based query generation.")
        return None

    return llm_config


def build_github_client_config(config: Dict[str, Any]) -> Dict[str, Any]:
    """Build GitHub client retry/timeout config from YAML."""
    github = config.get("github", {})
    return {
        "request_timeout": github.get("request_timeout", 30.0),
        "max_retries": github.get("max_retries", 3),
        "initial_retry_delay": github.get("initial_retry_delay", 1.0),
        "backoff_factor": github.get("backoff_factor", 2.0),
        "max_retry_delay": github.get("max_retry_delay", 60.0),
        "token_cooldown_buffer_seconds": github.get("token_cooldown_buffer_seconds", 1.0)
    }


def build_github_tokens(args, config: Dict[str, Any]) -> List[str]:
    """Resolve GitHub tokens from CLI args, config, and environment-backed config."""
    values: List[str] = []

    if args.github_token:
        for item in args.github_token:
            values.extend(_split_token_values(item))

    github = config.get("github", {})
    config_tokens = github.get("tokens", [])
    if isinstance(config_tokens, list):
        for item in config_tokens:
            values.extend(_split_token_values(item))

    config_token = github.get("token")
    if config_token:
        values.extend(_split_token_values(config_token))

    deduped = []
    seen = set()
    for token in values:
        if token in seen:
            continue
        seen.add(token)
        deduped.append(token)

    return deduped


def _split_token_values(value: str) -> List[str]:
    """Split comma/newline-separated token inputs."""
    return [
        token.strip()
        for token in str(value).replace("\n", ",").split(",")
        if token.strip()
    ]


def summarize_resume_plans(
    chains: List[Dict[str, Any]],
    mode: str,
    output_chain_dir: Optional[Path],
    output_atomic_dir: Optional[Path],
    overwrite_existing: bool
) -> Tuple[List[Tuple[Dict[str, Any], ResumePlan]], Dict[str, int]]:
    """Build resume plans and aggregate skip statistics."""
    work_items: List[Tuple[Dict[str, Any], ResumePlan]] = []
    summary = {
        "chain_skipped": 0,
        "atomic_skipped": 0,
        "chains_fully_complete": 0
    }

    for chain_data in chains:
        plan = build_resume_plan(
            chain_data,
            mode=mode,
            output_chain_dir=output_chain_dir,
            output_atomic_dir=output_atomic_dir,
            overwrite_existing=overwrite_existing
        )

        if plan.skipped_chain:
            summary["chain_skipped"] += 1
        summary["atomic_skipped"] += plan.skipped_atomic_count

        if plan.has_work():
            work_items.append((chain_data, plan))
        else:
            summary["chains_fully_complete"] += 1

    return work_items, summary


def save_and_validate_results(
    chain_id: str,
    chain_query,
    atomic_queries,
    mode: str,
    output_chain_dir: Optional[Path],
    output_atomic_dir: Optional[Path],
    progress_write
) -> Dict[str, int]:
    """Validate and persist any generated outputs."""
    stats = {
        "chain_success": 0,
        "chain_failed": 0,
        "atomic_success": 0,
        "atomic_failed": 0
    }

    if chain_query is not None and mode in {"chain", "both"} and output_chain_dir:
        errors = validate_query(chain_query)
        if errors:
            progress_write(f"Warning: Chain query validation errors for {chain_id}: {errors}")
        save_chain_query(chain_query, output_chain_dir)
        stats["chain_success"] += 1

    if atomic_queries and mode in {"atomic", "both"} and output_atomic_dir:
        for query in atomic_queries:
            errors = validate_query(query)
            if errors:
                progress_write(f"Warning: Atomic query validation errors for {query.query_id}: {errors}")
        save_atomic_queries(atomic_queries, output_atomic_dir, chain_id)
        stats["atomic_success"] += len(atomic_queries)

    return stats


def process_chain_plan(
    builder: DualModeBuilder,
    chain_data: Dict[str, Any],
    plan: ResumePlan,
    progress_callback=None
):
    """Process one chain according to its resume plan."""
    if not plan.has_work():
        return None, [], []

    pr_records = builder.prepare_pr_records(chain_data, progress_callback)
    chain_query = None
    atomic_queries = []
    errors = []

    if plan.needs_chain:
        try:
            chain_query = builder.build_chain_query(
                chain_data,
                progress_callback=progress_callback,
                pr_records=pr_records
            )
        except Exception as e:
            errors.append(("chain", e))

    if plan.pending_atomic_pr_ids:
        try:
            atomic_queries = builder.build_atomic_queries(
                chain_data,
                progress_callback=progress_callback,
                pr_records=pr_records,
                target_pr_ids=plan.pending_atomic_pr_ids
            )
        except Exception as e:
            errors.append(("atomic", e))

    return chain_query, atomic_queries, errors


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Dual-Mode Query Synthesis for PR Chain Trajectory Generation"
    )

    parser.add_argument(
        "--input",
        type=str,
        required=True,
        help="Input JSONL file with PR chains"
    )

    parser.add_argument(
        "--output-chain",
        type=str,
        help="Output directory for chain-level queries"
    )

    parser.add_argument(
        "--output-atomic",
        type=str,
        help="Output directory for atomic-level queries"
    )

    parser.add_argument(
        "--output",
        type=str,
        help="Output directory (used when mode is 'chain' or 'atomic')"
    )

    parser.add_argument(
        "--mode",
        type=str,
        choices=["chain", "atomic", "both"],
        default="both",
        help="Query synthesis mode"
    )

    parser.add_argument(
        "--filter-approved-only",
        action="store_true",
        help="Only process approved chains"
    )

    parser.add_argument(
        "--min-quality-score",
        type=float,
        default=0.0,
        help="Minimum quality score threshold"
    )

    parser.add_argument(
        "--github-token",
        action="append",
        help="GitHub API token; repeat or pass comma-separated values for token pooling"
    )

    parser.add_argument(
        "--cache-dir",
        type=str,
        default=".cache/github",
        help="Cache directory for GitHub API responses"
    )

    parser.add_argument(
        "--limit",
        type=int,
        help="Limit number of chains to process"
    )

    parser.add_argument(
        "--config",
        type=str,
        default="config/config.yaml",
        help="Path to configuration file"
    )

    parser.add_argument(
        "--concurrent",
        action="store_true",
        help="Enable concurrent processing"
    )

    parser.add_argument(
        "--max-workers",
        type=int,
        help="Max concurrent workers (overrides config)"
    )

    parser.add_argument(
        "--overwrite-existing",
        action="store_true",
        help="Ignore existing output files and regenerate them"
    )

    args = parser.parse_args()

    # Load config
    config = load_config(args.config)

    # Validate arguments
    if args.mode == "both":
        if not args.output_chain or not args.output_atomic:
            print("Error: --output-chain and --output-atomic required for mode 'both'")
            sys.exit(1)
    elif args.mode == "chain":
        if not args.output and not args.output_chain:
            print("Error: --output or --output-chain required for mode 'chain'")
            sys.exit(1)
        args.output_chain = args.output_chain or args.output
    elif args.mode == "atomic":
        if not args.output and not args.output_atomic:
            print("Error: --output or --output-atomic required for mode 'atomic'")
            sys.exit(1)
        args.output_atomic = args.output_atomic or args.output

    # Load chains
    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Error: Input file not found: {input_path}")
        sys.exit(1)

    print(f"Loading chains from {input_path}...")
    chains = load_chains(input_path)
    print(f"Loaded {len(chains)} chains")

    # Filter chains
    print(f"Filtering chains (approved_only={args.filter_approved_only}, min_quality={args.min_quality_score})...")
    filtered_chains = filter_chains(
        chains,
        approved_only=args.filter_approved_only,
        min_quality_score=args.min_quality_score
    )
    print(f"Filtered to {len(filtered_chains)} chains")

    if not filtered_chains:
        print("No chains to process after filtering")
        sys.exit(0)

    # Apply limit
    if args.limit:
        filtered_chains = filtered_chains[:args.limit]
        print(f"Limited to {len(filtered_chains)} chains")

    output_chain_dir = Path(args.output_chain) if args.output_chain else None
    output_atomic_dir = Path(args.output_atomic) if args.output_atomic else None

    work_items, resume_summary = summarize_resume_plans(
        filtered_chains,
        mode=args.mode,
        output_chain_dir=output_chain_dir,
        output_atomic_dir=output_atomic_dir,
        overwrite_existing=args.overwrite_existing
    )

    if not args.overwrite_existing:
        if args.mode in ["chain", "both"] and resume_summary["chain_skipped"]:
            print(f"Skipping {resume_summary['chain_skipped']} existing chain-level outputs")
        if args.mode in ["atomic", "both"] and resume_summary["atomic_skipped"]:
            print(f"Skipping {resume_summary['atomic_skipped']} existing atomic-level outputs")

    if resume_summary["chains_fully_complete"]:
        print(f"{resume_summary['chains_fully_complete']} chains are already complete")

    if not work_items:
        print("No new work to process after resume check")
        sys.exit(0)

    # Initialize builder
    print("Initializing dual-mode builder...")

    llm_config = build_llm_config(config)
    github_client_config = build_github_client_config(config)

    max_workers = args.max_workers or config.get("synthesis", {}).get("max_workers", 5)

    github_tokens = build_github_tokens(args, config)

    builder = DualModeBuilder(
        github_token=github_tokens[0] if github_tokens else None,
        github_tokens=github_tokens,
        cache_dir=args.cache_dir,
        github_client_config=github_client_config,
        llm_config=llm_config,
        max_workers=max_workers
    )

    # Process chains
    stats = {
        "total": len(filtered_chains),
        "chains_with_work": len(work_items),
        "chain_skipped": resume_summary["chain_skipped"],
        "atomic_skipped": resume_summary["atomic_skipped"],
        "chain_success": 0,
        "chain_failed": 0,
        "atomic_success": 0,
        "atomic_failed": 0
    }

    # Concurrent processing
    if args.concurrent:
        print(f"Processing {len(work_items)} chains concurrently (max_workers={max_workers})...")

        progress_bar = tqdm(total=len(work_items), desc="Processing chains")

        def progress_callback(msg: str):
            progress_bar.write(msg)

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(process_chain_plan, builder, chain_data, plan, progress_callback): (chain_data, plan)
                for chain_data, plan in work_items
            }

            for future in as_completed(futures):
                chain_data, plan = futures[future]
                chain_id = chain_data["chain_id"]

                try:
                    chain_query, atomic_queries, errors = future.result()
                    result_stats = save_and_validate_results(
                        chain_id=chain_id,
                        chain_query=chain_query,
                        atomic_queries=atomic_queries,
                        mode=args.mode,
                        output_chain_dir=output_chain_dir,
                        output_atomic_dir=output_atomic_dir,
                        progress_write=progress_bar.write
                    )
                    for key, value in result_stats.items():
                        stats[key] += value
                    for scope, error in errors:
                        progress_bar.write(f"✗ {chain_id} {scope} build failed: {error}")
                        if scope == "chain":
                            stats["chain_failed"] += 1
                        elif scope == "atomic":
                            stats["atomic_failed"] += len(plan.pending_atomic_pr_ids)
                    if errors:
                        progress_bar.write(f"△ Completed {chain_id} with partial failures")
                    else:
                        progress_bar.write(f"✓ Completed {chain_id}")
                except Exception as e:
                    progress_bar.write(f"✗ Failed {chain_id}: {e}")
                    if plan.needs_chain:
                        stats["chain_failed"] += 1
                    if plan.pending_atomic_pr_ids:
                        stats["atomic_failed"] += len(plan.pending_atomic_pr_ids)
                finally:
                    progress_bar.update(1)

        progress_bar.close()

    else:
        # Sequential processing with streaming output
        for chain_data, plan in tqdm(work_items, desc="Processing chains"):
            chain_id = chain_data["chain_id"]

            def progress_callback(msg: str):
                tqdm.write(msg)

            try:
                chain_query, atomic_queries, errors = process_chain_plan(
                    builder,
                    chain_data,
                    plan,
                    progress_callback
                )
                result_stats = save_and_validate_results(
                    chain_id=chain_id,
                    chain_query=chain_query,
                    atomic_queries=atomic_queries,
                    mode=args.mode,
                    output_chain_dir=output_chain_dir,
                    output_atomic_dir=output_atomic_dir,
                    progress_write=tqdm.write
                )
                for key, value in result_stats.items():
                    stats[key] += value
                for scope, error in errors:
                    tqdm.write(f"Error building {scope} queries for {chain_id}: {error}")
                    if scope == "chain":
                        stats["chain_failed"] += 1
                    elif scope == "atomic":
                        stats["atomic_failed"] += len(plan.pending_atomic_pr_ids)
            except Exception as e:
                tqdm.write(f"Error processing chain {chain_id}: {e}")
                if plan.needs_chain:
                    stats["chain_failed"] += 1
                if plan.pending_atomic_pr_ids:
                    stats["atomic_failed"] += len(plan.pending_atomic_pr_ids)

    # Print summary
    print("\n" + "=" * 60)
    print("SYNTHESIS SUMMARY")
    print("=" * 60)
    print(f"Total chains processed: {stats['total']}")
    print(f"Chains with pending work: {stats['chains_with_work']}")

    if args.mode in ["chain", "both"]:
        print(f"\nChain-level queries:")
        print(f"  Success: {stats['chain_success']}")
        print(f"  Failed: {stats['chain_failed']}")
        print(f"  Skipped existing: {stats['chain_skipped']}")
        if args.output_chain:
            print(f"  Output: {args.output_chain}")

    if args.mode in ["atomic", "both"]:
        print(f"\nAtomic-level queries:")
        print(f"  Success: {stats['atomic_success']}")
        print(f"  Failed: {stats['atomic_failed']}")
        print(f"  Skipped existing: {stats['atomic_skipped']}")
        if args.output_atomic:
            print(f"  Output: {args.output_atomic}")

    print("=" * 60)


if __name__ == "__main__":
    main()
