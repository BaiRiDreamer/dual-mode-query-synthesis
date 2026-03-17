# Configuration Guide

## Overview

The dual-mode query synthesis system is configured via `config/config.yaml`. This file controls GitHub API access, LLM integration, synthesis parameters, and output settings.

## Configuration File Structure

```yaml
github:
  token: ${GITHUB_TOKEN}
  cache_dir: .cache/github

llm:
  api_key: ${AZURE_OPENAI_API_KEY}
  endpoint: https://gpt-5.4-2026-03-05.openai.azure.com/
  model: gpt-5.4-2026-03-05
  api_version: "2024-08-01-preview"
  temperature: 0.7
  max_tokens: 4096
  top_p: 0.95

synthesis:
  max_context_bytes: 204800
  min_quality_score: 8.0
  filter_approved_only: true
  max_workers: 5

templates:
  chain_level: src/prompts/query/chain_level.j2
  atomic_level: src/prompts/query/atomic_level.j2

output:
  chain_dir: data/output/chain
  atomic_dir: data/output/atomic
```

## Configuration Sections

### GitHub Configuration

- `token`: GitHub API token (supports environment variable expansion)
- `cache_dir`: Directory for caching GitHub API responses

### LLM Configuration

- `api_key`: Azure OpenAI API key
- `endpoint`: Azure OpenAI endpoint URL
- `model`: Model deployment name
- `api_version`: API version string
- `temperature`: Sampling temperature (0.0-1.0)
- `max_tokens`: Maximum tokens in response
- `top_p`: Nucleus sampling parameter

### Synthesis Configuration

- `max_context_bytes`: Maximum context size in bytes
- `min_quality_score`: Minimum quality score threshold
- `filter_approved_only`: Only process approved chains
- `max_workers`: Maximum concurrent workers for parallel processing

### Templates Configuration

- `chain_level`: Path to chain-level Jinja2 template
- `atomic_level`: Path to atomic-level Jinja2 template

### Output Configuration

- `chain_dir`: Output directory for chain-level queries
- `atomic_dir`: Output directory for atomic-level queries

## Environment Variables

The configuration supports environment variable expansion using `${VAR_NAME}` syntax:

```bash
export GITHUB_TOKEN="ghp_xxxxxxxxxxxx"
export AZURE_OPENAI_API_KEY="your_api_key_here"
```

## CLI Overrides

CLI arguments override configuration file settings:

```bash
python -m src.cli.dual_mode_query_constructor_cli \
  --config custom_config.yaml \
  --max-workers 10 \
  --concurrent
```

## Concurrent Processing

Enable concurrent processing for faster query generation:

```bash
--concurrent --max-workers 10
```

This processes multiple chains in parallel using ThreadPoolExecutor.

## Streaming Output

The CLI provides real-time progress updates:
- Progress bars show overall completion
- Streaming messages show current operations
- Validation warnings appear immediately
