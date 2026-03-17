# Azure OpenAI Integration Guide

## Overview

The dual-mode query synthesis system integrates with Azure OpenAI for enhanced intent synthesis. This guide explains how to configure and use the LLM integration.

## Setup

### 1. Get Azure OpenAI Credentials

You need:
- API key
- Endpoint URL
- Model deployment name

### 2. Set Environment Variable

```bash
export AZURE_OPENAI_API_KEY="your_api_key_here"
```

### 3. Configure config.yaml

Edit `config/config.yaml`:

```yaml
llm:
  api_key: ${AZURE_OPENAI_API_KEY}
  endpoint: https://gpt-5.4-2026-03-05.openai.azure.com/
  model: gpt-5.4-2026-03-05
  api_version: "2024-08-01-preview"
  temperature: 0.7
  max_tokens: 4096
  top_p: 0.95
```

## Usage

The LLM client is automatically initialized when running the CLI:

```bash
python -m src.cli.dual_mode_query_constructor_cli \
  --input data/input/PR-list-output.jsonl \
  --output-chain data/output/chain/ \
  --output-atomic data/output/atomic/ \
  --mode both
```

## LLM Client API

The `LLMClient` class provides a simple interface:

```python
from src.utils.llm_client import LLMClient

# Initialize
client = LLMClient(
    api_key="your_key",
    endpoint="https://your-endpoint.openai.azure.com/",
    model="gpt-5.4-2026-03-05",
    temperature=0.7
)

# Generate text
response = client.generate("Your prompt here")
```

## Parameters

- `api_key`: Azure OpenAI API key
- `endpoint`: Azure OpenAI endpoint URL
- `model`: Model deployment name
- `api_version`: API version (default: "2024-08-01-preview")
- `temperature`: Sampling temperature (0.0-1.0, default: 0.7)
- `max_tokens`: Maximum tokens in response (default: 4096)
- `top_p`: Nucleus sampling parameter (default: 0.95)

## Intent Synthesis

The LLM client is used by `IntentSynthesizer` to generate high-level intent statements from PR metadata. This enhances the quality of synthesized queries by providing more nuanced understanding of PR chains.

## Error Handling

If the LLM client is not configured or credentials are invalid, the system falls back to rule-based intent synthesis using PR titles and descriptions.
