# Dual-Mode Query Synthesis

## Quick Start Guide

### 1. Installation

```bash
cd /home/bairidreamer/Repos/dual-mode-query-synthesis
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Prepare Input Data

Copy your PR chain data to the input directory:

```bash
cp /home/bairidreamer/Repos/daVinci-Agency/PR-list-output.jsonl data/input/
```

### 3. Set Environment Variables

```bash
export GITHUB_TOKEN="your_github_token_here"
export AZURE_OPENAI_API_KEY="your_azure_openai_key_here"
```

### 4. Run Query Synthesis

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

**With concurrent processing (faster):**
```bash
python -m src.cli.dual_mode_query_constructor_cli \
  --input data/input/PR-list-output.jsonl \
  --output-chain data/output/chain/ \
  --output-atomic data/output/atomic/ \
  --mode both \
  --concurrent \
  --max-workers 10 \
  --filter-approved-only \
  --min-quality-score 8.0
```

**Or use the example script:**
```bash
./run_example.sh
```

### 5. Check Output

Chain-level queries will be in: `data/output/chain/`
Atomic-level queries will be in: `data/output/atomic/`

## Project Structure

```
dual-mode-query-synthesis/
├── src/
│   ├── models/              # Data models
│   ├── utils/               # Utilities (GitHub client, validators, text utils)
│   ├── pipelines/
│   │   └── query_constructor/
│   │       ├── dual_mode_builder.py
│   │       ├── chain_level_builder.py
│   │       ├── atomic_level_builder.py
│   │       ├── intent_synthesizer.py
│   │       ├── context_enricher.py
│   │       └── ground_truth_generator.py
│   ├── prompts/query/       # Jinja2 templates
│   └── cli/                 # CLI interface
├── data/
│   ├── input/               # Input PR chains
│   └── output/              # Generated queries
├── config/                  # Configuration files
└── tests/                   # Unit tests
```

## Features Implemented

✅ Chain-Level Query Synthesis
✅ Atomic-Level Query Synthesis
✅ GitHub API Integration with Caching
✅ Intent Synthesis from PR Metadata
✅ Ground Truth Generation
✅ Jinja2 Template System
✅ Comprehensive Validation
✅ CLI Interface
✅ Progress Tracking
✅ Error Handling
✅ Azure OpenAI Integration
✅ Concurrent Processing
✅ Streaming Output

## Next Steps

1. Test with your PR chain data
2. Adjust templates if needed (src/prompts/query/)
3. Configure settings in config/config.yaml
4. Use generated queries with rollout executor

For detailed documentation, see the main README.md
