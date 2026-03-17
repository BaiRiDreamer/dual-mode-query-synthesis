"""CLI for dual-mode query synthesis."""

import argparse
import json
import sys
import yaml
from pathlib import Path
from typing import List, Dict, Any
from tqdm import tqdm

from ..pipelines.query_constructor import DualModeBuilder
from ..utils.validators import validate_pr_chain, validate_query


def load_config(config_path: str = "config/config.yaml") -> Dict[str, Any]:
    """Load configuration from YAML file."""
    config_file = Path(config_path)
    if not config_file.exists():
        return {}

    with open(config_file, 'r') as f:
        config = yaml.safe_load(f)

    # Expand environment variables
    import os
    if config.get("llm", {}).get("api_key", "").startswith("${"):
        env_var = config["llm"]["api_key"][2:-1]
        config["llm"]["api_key"] = os.getenv(env_var)

    if config.get("github", {}).get("token", "").startswith("${"):
        env_var = config["github"]["token"][2:-1]
        config["github"]["token"] = os.getenv(env_var)

    return config


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

    with open(output_file, 'w') as f:
        f.write(query.model_dump_json(indent=2))


def save_atomic_queries(queries, output_dir: Path, chain_id: str):
    """Save atomic-level queries to files."""
    output_dir.mkdir(parents=True, exist_ok=True)

    for query in queries:
        output_file = output_dir / f"{query.query_id}.jsonl"
        with open(output_file, 'w') as f:
            f.write(query.model_dump_json(indent=2))


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
        type=str,
        help="GitHub API token (defaults to GITHUB_TOKEN env var)"
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

    # Initialize builder
    print("Initializing dual-mode builder...")

    # Prepare LLM config
    llm_config = None
    if config.get("llm"):
        llm_config = {
            "api_key": config["llm"].get("api_key"),
            "endpoint": config["llm"].get("endpoint"),
            "model": config["llm"].get("model"),
            "api_version": config["llm"].get("api_version", "2024-08-01-preview"),
            "temperature": config["llm"].get("temperature", 0.7),
            "max_tokens": config["llm"].get("max_tokens", 4096),
            "top_p": config["llm"].get("top_p", 0.95)
        }

    max_workers = args.max_workers or config.get("synthesis", {}).get("max_workers", 5)

    builder = DualModeBuilder(
        github_token=args.github_token or config.get("github", {}).get("token"),
        cache_dir=args.cache_dir,
        llm_config=llm_config,
        max_workers=max_workers
    )

    # Process chains
    stats = {
        "total": len(filtered_chains),
        "chain_success": 0,
        "chain_failed": 0,
        "atomic_success": 0,
        "atomic_failed": 0
    }

    # Concurrent processing
    if args.concurrent:
        print(f"Processing {len(filtered_chains)} chains concurrently (max_workers={max_workers})...")

        progress_bar = tqdm(total=len(filtered_chains), desc="Processing chains")

        def progress_callback(msg: str):
            progress_bar.write(msg)

        results = builder.build_multiple_chains(
            filtered_chains,
            mode=args.mode,
            progress_callback=progress_callback
        )

        for chain_id, result in results:
            if result is None:
                stats["chain_failed"] += 1
                progress_bar.update(1)
                continue

            try:
                if args.mode == "chain":
                    chain_query = result
                    errors = validate_query(chain_query)
                    if errors:
                        progress_bar.write(f"Warning: Chain query validation errors for {chain_id}: {errors}")
                    save_chain_query(chain_query, Path(args.output_chain))
                    stats["chain_success"] += 1

                elif args.mode == "atomic":
                    atomic_queries = result
                    for query in atomic_queries:
                        errors = validate_query(query)
                        if errors:
                            progress_bar.write(f"Warning: Atomic query validation errors for {query.query_id}: {errors}")
                    save_atomic_queries(atomic_queries, Path(args.output_atomic), chain_id)
                    stats["atomic_success"] += len(atomic_queries)

                else:  # both
                    chain_query, atomic_queries = result

                    errors = validate_query(chain_query)
                    if errors:
                        progress_bar.write(f"Warning: Chain query validation errors for {chain_id}: {errors}")
                    save_chain_query(chain_query, Path(args.output_chain))
                    stats["chain_success"] += 1

                    for query in atomic_queries:
                        errors = validate_query(query)
                        if errors:
                            progress_bar.write(f"Warning: Atomic query validation errors for {query.query_id}: {errors}")
                    save_atomic_queries(atomic_queries, Path(args.output_atomic), chain_id)
                    stats["atomic_success"] += len(atomic_queries)

            except Exception as e:
                progress_bar.write(f"Error saving results for {chain_id}: {e}")

            progress_bar.update(1)

        progress_bar.close()

    else:
        # Sequential processing with streaming output
        for chain_data in tqdm(filtered_chains, desc="Processing chains"):
            chain_id = chain_data["chain_id"]

            def progress_callback(msg: str):
                tqdm.write(msg)

            try:
                if args.mode in ["chain", "both"]:
                    try:
                        chain_query = builder.build_chain_query(chain_data, progress_callback)

                        errors = validate_query(chain_query)
                        if errors:
                            tqdm.write(f"Warning: Chain query validation errors for {chain_id}: {errors}")

                        save_chain_query(chain_query, Path(args.output_chain))
                        stats["chain_success"] += 1

                    except Exception as e:
                        tqdm.write(f"Error building chain query for {chain_id}: {e}")
                        stats["chain_failed"] += 1

                if args.mode in ["atomic", "both"]:
                    try:
                        atomic_queries = builder.build_atomic_queries(chain_data, progress_callback)

                        for query in atomic_queries:
                            errors = validate_query(query)
                            if errors:
                                tqdm.write(f"Warning: Atomic query validation errors for {query.query_id}: {errors}")

                        save_atomic_queries(atomic_queries, Path(args.output_atomic), chain_id)
                        stats["atomic_success"] += len(atomic_queries)

                    except Exception as e:
                        tqdm.write(f"Error building atomic queries for {chain_id}: {e}")
                        stats["atomic_failed"] += 1

            except Exception as e:
                tqdm.write(f"Error processing chain {chain_id}: {e}")
                continue

    # Print summary
    print("\n" + "=" * 60)
    print("SYNTHESIS SUMMARY")
    print("=" * 60)
    print(f"Total chains processed: {stats['total']}")

    if args.mode in ["chain", "both"]:
        print(f"\nChain-level queries:")
        print(f"  Success: {stats['chain_success']}")
        print(f"  Failed: {stats['chain_failed']}")
        if args.output_chain:
            print(f"  Output: {args.output_chain}")

    if args.mode in ["atomic", "both"]:
        print(f"\nAtomic-level queries:")
        print(f"  Success: {stats['atomic_success']}")
        print(f"  Failed: {stats['atomic_failed']}")
        if args.output_atomic:
            print(f"  Output: {args.output_atomic}")

    print("=" * 60)


if __name__ == "__main__":
    main()
