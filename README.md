# Dual-Mode Query Synthesis for PR Chain Trajectory Generation

A comprehensive framework for synthesizing two types of queries from PR chains: **Chain-Level Queries** (holistic implementation of entire PR chains) and **Atomic-Level Queries** (individual PR implementations).

## Overview

This project extends the daVinci-Agency paradigm to support dual-mode trajectory synthesis for long-horizon agent training:

- **Chain-Level Mode**: Synthesizes queries that capture entire PR chains as unified development narratives
- **Atomic-Level Mode**: Generates independent queries for each PR to enable fine-grained skill learning

## Features

- 🔗 **Chain-Level Query Synthesis**: Holistic evolution modeling with cross-PR dependencies
- ⚛️ **Atomic-Level Query Synthesis**: Self-contained queries for individual PRs
- 🎯 **Intent Synthesis**: Automatic extraction of high-level goals from PR metadata
- 📊 **Quality Validation**: Comprehensive validation and metrics tracking
- 🔄 **Ground Truth Generation**: Cumulative and per-PR diff computation
- 🎨 **Template System**: Jinja2-based prompt templates for both modes
- 🤖 **Azure OpenAI Integration**: Configurable LLM client for intent synthesis
- ⚡ **Concurrent Processing**: Multi-threaded query generation for faster processing
- 📡 **Streaming Output**: Real-time progress updates during synthesis
- 💾 **GitHub API Caching**: Automatic caching to reduce API calls
- 🔐 **GitHub Token Pooling**: Multi-token rate limit aware request scheduling
- ⏯️ **Resumable Fetching**: Skip already-normalized PR items on reruns

## Installation

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

## Quick Start

### 1. Prepare Input Data

Place your PR chain data (from daVinci-Agency PR combiner) in `data/input/`:

```bash
cp /path/to/PR-list-output.jsonl data/input/
```

### 2. Generate Queries

**Set up environment variables:**
```bash
export GITHUB_TOKEN="your_github_token"
export AZURE_OPENAI_API_KEY="your_azure_openai_key"
```

**Or use multiple GitHub tokens:**
```bash
export GITHUB_TOKENS="token_a,token_b,token_c"
```

**Generate both modes:**
```bash
python -m src.cli.dual_mode_query_constructor_cli \
  --input data/input/PR-list-output.jsonl \
  --output-chain data/output/chain/ \
  --output-atomic data/output/atomic/ \
  --mode both \
  --filter-approved-only \
  --min-quality-score 8.0
```

**Enable concurrent processing:**
```bash
python -m src.cli.dual_mode_query_constructor_cli \
  --input data/input/PR-list-output.jsonl \
  --output-chain data/output/chain/ \
  --output-atomic data/output/atomic/ \
  --mode both \
  --concurrent \
  --max-workers 10 \
  --filter-approved-only
```

**Generate only chain-level queries:**
```bash
python -m src.cli.dual_mode_query_constructor_cli \
  --input data/input/PR-list-output.jsonl \
  --output data/output/chain/ \
  --mode chain \
  --filter-approved-only
```

**Generate only atomic-level queries:**
```bash
python -m src.cli.dual_mode_query_constructor_cli \
  --input data/input/PR-list-output.jsonl \
  --output data/output/atomic/ \
  --mode atomic \
  --filter-approved-only
```

## Project Structure

```
dual-mode-query-synthesis/
├── src/
│   ├── pipelines/
│   │   └── query_constructor/
│   │       ├── dual_mode_builder.py      # Main entry point
│   │       ├── chain_level_builder.py    # Chain-level synthesis
│   │       ├── atomic_level_builder.py   # Atomic-level synthesis
│   │       ├── intent_synthesizer.py     # Intent extraction
│   │       ├── context_enricher.py       # PR data enrichment
│   │       └── ground_truth_generator.py # Diff computation
│   ├── prompts/
│   │   └── query/
│   │       ├── chain_level.j2            # Chain-level template
│   │       └── atomic_level.j2           # Atomic-level template
│   ├── cli/
│   │   └── dual_mode_query_constructor_cli.py
│   ├── models/
│   │   └── artifacts.py                  # Data models
│   └── utils/
│       ├── github_client.py              # GitHub API client
│       └── validators.py                 # Validation utilities
├── data/
│   ├── input/                            # Input PR chains
│   └── output/
│       ├── chain/                        # Chain-level queries
│       └── atomic/                       # Atomic-level queries
├── config/
│   └── config.yaml                       # Configuration
├── tests/                                # Unit tests
└── requirements.txt
```

## Output Format

### Chain-Level Query

```json
{
  "query_id": "chain-level-chain_0001",
  "mode": "chain_level",
  "chain_metadata": {
    "chain_id": "chain_0001",
    "repository": "scipy/scipy",
    "topic": "scipy.special API refactoring",
    "evolution_pattern": "collaborative_development",
    "quality_score": 9.0,
    "pr_count": 3
  },
  "task_specification": {
    "intent": "Refactor scipy.special internals...",
    "scope": {...},
    "evolution_narrative": "...",
    "constraints": [...]
  },
  "pr_sequence": [...],
  "ground_truth": {
    "cumulative_patch": "...",
    "validation_criteria": [...]
  },
  "prompt": "..."
}
```

### Atomic-Level Query

```json
{
  "query_id": "atomic-chain_0001-pr1",
  "mode": "atomic_level",
  "pr_metadata": {
    "pr_id": "scipy/scipy#333",
    "repository": "scipy/scipy",
    "title": "Refactor special function generation",
    "function_type": "MAINT"
  },
  "chain_context": {
    "chain_id": "chain_0001",
    "position_in_chain": 1,
    "total_prs_in_chain": 3
  },
  "task_specification": {...},
  "ground_truth": {
    "patch": "...",
    "base_commit": "...",
    "head_commit": "..."
  },
  "prompt": "..."
}
```

## Configuration

Edit `config/config.yaml` to customize:

```yaml
github:
  token: ${GITHUB_TOKEN}  # GitHub API token
  cache_dir: .cache/github

synthesis:
  max_context_bytes: 204800  # 200KB
  min_quality_score: 8.0
  filter_approved_only: true

templates:
  chain_level: prompts/query/chain_level.j2
  atomic_level: prompts/query/atomic_level.j2
```

You can also configure a token pool:

```yaml
github:
  tokens:
    - ${GITHUB_TOKEN_1}
    - ${GITHUB_TOKEN_2}
  token_cooldown_buffer_seconds: 1
```

## Development

### Run Tests

```bash
pytest tests/
```

### Code Style

```bash
black src/ tests/
flake8 src/ tests/
mypy src/
```

## Research Applications

- **Training Data Generation**: Generate trajectories for long-horizon agent training
- **Evaluation Benchmarks**: Create benchmarks for chain-level and atomic-level tasks
- **Ablation Studies**: Compare agent performance across different training modes

## Citation

If you use this framework in your research, please cite:

```bibtex
@article{jiang2026davinci,
  title={daVinci-Agency: Unlocking Long-Horizon Agency Data-Efficiently},
  author={Mohan Jiang and Dayuan Fu and Junhao Shi and Ji Zeng and Weiye Si and Keyu Li and Xuefeng Li and Yang Xiao and Wenjie Li and Dequan Wang and Pengfei Liu},
  journal={arXiv preprint arXiv:2602.02619},
  year={2026}
}
```

## License

MIT License

## Acknowledgments

Based on the daVinci-Agency framework by GAIR Lab.
