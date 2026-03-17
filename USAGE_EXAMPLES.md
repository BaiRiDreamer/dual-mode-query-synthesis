# Usage Examples

## Basic Usage

### 1. Generate Both Modes

```bash
python -m src.cli.dual_mode_query_constructor_cli \
  --input data/input/PR-list-output.jsonl \
  --output-chain data/output/chain/ \
  --output-atomic data/output/atomic/ \
  --mode both \
  --filter-approved-only \
  --min-quality-score 8.0
```

### 2. Generate Only Chain-Level Queries

```bash
python -m src.cli.dual_mode_query_constructor_cli \
  --input data/input/PR-list-output.jsonl \
  --output data/output/chain/ \
  --mode chain \
  --filter-approved-only
```

### 3. Generate Only Atomic-Level Queries

```bash
python -m src.cli.dual_mode_query_constructor_cli \
  --input data/input/PR-list-output.jsonl \
  --output data/output/atomic/ \
  --mode atomic \
  --filter-approved-only
```

## Advanced Usage

### Process Limited Number of Chains

```bash
python -m src.cli.dual_mode_query_constructor_cli \
  --input data/input/PR-list-output.jsonl \
  --output-chain data/output/chain/ \
  --output-atomic data/output/atomic/ \
  --mode both \
  --limit 10
```

### Custom Quality Threshold

```bash
python -m src.cli.dual_mode_query_constructor_cli \
  --input data/input/PR-list-output.jsonl \
  --output-chain data/output/chain/ \
  --output-atomic data/output/atomic/ \
  --mode both \
  --min-quality-score 9.0
```

### Include All Chains (Not Just Approved)

```bash
python -m src.cli.dual_mode_query_constructor_cli \
  --input data/input/PR-list-output.jsonl \
  --output-chain data/output/chain/ \
  --output-atomic data/output/atomic/ \
  --mode both \
  --min-quality-score 0.0
```

### Custom GitHub Token and Cache

```bash
python -m src.cli.dual_mode_query_constructor_cli \
  --input data/input/PR-list-output.jsonl \
  --output-chain data/output/chain/ \
  --output-atomic data/output/atomic/ \
  --mode both \
  --github-token "ghp_your_token_here" \
  --cache-dir ".cache/custom"
```

## Programmatic Usage

### Python API Example

```python
from src.pipelines.query_constructor import DualModeBuilder

# Initialize builder
builder = DualModeBuilder(
    github_token="your_token",
    cache_dir=".cache/github"
)

# Load chain data
import json
with open("data/input/PR-list-output.jsonl") as f:
    chain_data = json.loads(f.readline())

# Build chain-level query
chain_query = builder.build_chain_query(chain_data)
print(f"Generated: {chain_query.query_id}")
print(f"Prompt length: {len(chain_query.prompt)} chars")

# Build atomic-level queries
atomic_queries = builder.build_atomic_queries(chain_data)
print(f"Generated {len(atomic_queries)} atomic queries")

# Save queries
with open(f"data/output/chain/{chain_query.query_id}.jsonl", "w") as f:
    f.write(chain_query.model_dump_json(indent=2))

for query in atomic_queries:
    with open(f"data/output/atomic/{query.query_id}.jsonl", "w") as f:
        f.write(query.model_dump_json(indent=2))
```

## Integration with Rollout Executor

After generating queries, use them with the daVinci-Agency rollout executor:

### Chain-Level Execution

```bash
# Using sii-agent-sdk
uv run python -m src.cli.rollout_executor_cli \
  --queries data/output/chain/chain-level-chain_0001.jsonl \
  --scaffold sii \
  --staged-session

# Using mini-swe-agent
uv run python -m src.cli.rollout_executor_cli \
  --queries data/output/chain/chain-level-chain_0001.jsonl \
  --scaffold mini \
  --concurrency 1
```

### Atomic-Level Execution (Parallel)

```bash
uv run python -m src.cli.rollout_executor_cli \
  --queries data/output/atomic/atomic-chain_0001-*.jsonl \
  --scaffold mini \
  --concurrency 4
```

## Troubleshooting

### GitHub Rate Limiting

If you hit rate limits:
1. Set `GITHUB_TOKEN` environment variable
2. Use `--cache-dir` to cache API responses
3. Process chains in smaller batches with `--limit`

### Missing PR Data

If PRs cannot be fetched:
1. Check GitHub token permissions
2. Verify PR IDs are in correct format: "owner/repo#number"
3. Check if PRs are public and accessible

### Template Customization

To customize prompts, edit:
- `src/prompts/query/chain_level.j2` for chain-level queries
- `src/prompts/query/atomic_level.j2` for atomic-level queries
