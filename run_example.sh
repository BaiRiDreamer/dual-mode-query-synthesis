#!/bin/bash

# Example: Generate both chain-level and atomic-level queries with concurrent processing

python -m src.cli.dual_mode_query_constructor_cli \
  --input data/input/PR-list-output.jsonl \
  --output-chain data/output/chain/ \
  --output-atomic data/output/atomic/ \
  --mode both \
  --filter-approved-only \
  --min-quality-score 8.0 \
  --concurrent \
  --max-workers 5 \
  --limit 10

echo "Query synthesis complete!"
echo "Chain-level queries: data/output/chain/"
echo "Atomic-level queries: data/output/atomic/"
