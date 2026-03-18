# Implementation Complete: LLM-Based Query Generation

## Summary

Successfully implemented LLM-based query generation system that produces natural, diverse, user-perspective queries instead of template-based outputs.

## What Changed

### 1. Intent Synthesis (NEW)
- **File:** `src/pipelines/query_constructor/intent_synthesizer.py`
- **Purpose:** Uses LLM to reconstruct original user requirement from PR metadata
- **Prompts:**
  - `src/prompts/intent_synthesis/chain_level_intent.txt`
  - `src/prompts/intent_synthesis/atomic_level_intent.txt`

### 2. Query Generation (NEW)
- **File:** `src/pipelines/query_constructor/query_generator.py`
- **Purpose:** Converts intent to natural language user query
- **Prompts:**
  - `src/prompts/query_generation/chain_level_query.txt`
  - `src/prompts/query_generation/atomic_level_query.txt`

### 3. Builder Updates
- **ChainLevelBuilder:** No longer uses Jinja2 templates, calls LLM pipeline
- **AtomicLevelBuilder:** No longer uses Jinja2 templates, calls LLM pipeline
- **DualModeBuilder:** Removed template path parameters

## Key Improvements

### Before (Template-Based)
```
## Role
You are an AI Software Evolution Architect...

### Phase 1: Foundation Analysis
1. Examine the repository structure...

#### Step 1: Add OAuth2 Provider
- **Files to modify**: src/auth/oauth.ts
- **Objective**: Implement OAuth2
```

**Problems:**
- God's-eye view (knows the answer)
- Lists exact files to modify
- Structured like a solution

### After (LLM-Generated)
```
We need to add OAuth2 support to our auth system. Currently only have
username/password login, but users want Google and GitHub options.

Can we do this incrementally? Start with OAuth2 framework, then add
Google first, then token refresh? Important not to break existing login.

The auth code is in src/auth/ but not sure exactly which files need changes.
```

**Benefits:**
- User perspective (describes need)
- Natural, conversational
- Admits uncertainty
- Suggests approach, doesn't prescribe

## Prompt Design Philosophy

### Removed Constraints
- ❌ "Must not mention files" → Users often do
- ❌ "Must not use technical terms" → Technical users do
- ❌ "Must not use Step 1/2/3" → Structured users do
- ❌ "Must be casual" → Some users write formal issues

### Kept Principles
- ✅ Write from user perspective (what they want)
- ✅ Focus on problem/need and outcome
- ✅ Allow varied styles (casual, structured, technical)
- ✅ Be natural and diverse

## Configuration

```yaml
llm:
  api_key: ${AZURE_OPENAI_API_KEY}
  endpoint: https://gpt-5.4-2026-03-05.openai.azure.com/
  model: gpt-5.4-2026-03-05
  temperature: 0.8  # Intent synthesis
  max_tokens: 4096
```

Query generation uses temperature=0.9 for maximum diversity.

## Usage

```bash
# Set environment variable
export AZURE_OPENAI_API_KEY="your_key"

# Run with LLM-based generation
python -m src.cli.dual_mode_query_constructor_cli \
  --input data/input/PR-list-output.jsonl \
  --output-chain data/output/chain/ \
  --output-atomic data/output/atomic/ \
  --mode both \
  --concurrent
```

## Fallback Behavior

If LLM client unavailable or fails:
- Falls back to rule-based generation
- Uses PR titles/descriptions directly
- Still produces valid queries

## Testing

```bash
# Test imports
python3 -c "from src.pipelines.query_constructor import IntentSynthesizer, QueryGenerator; print('✓ OK')"

# Test LLM client
python3 test_llm.py
```

## Files Created/Modified

**New Files:**
- `src/pipelines/query_constructor/query_generator.py`
- `src/prompts/intent_synthesis/chain_level_intent.txt`
- `src/prompts/intent_synthesis/atomic_level_intent.txt`
- `src/prompts/query_generation/chain_level_query.txt`
- `src/prompts/query_generation/atomic_level_query.txt`
- `docs/LLM_QUERY_GENERATION.md`

**Modified Files:**
- `src/pipelines/query_constructor/intent_synthesizer.py` - Complete rewrite
- `src/pipelines/query_constructor/chain_level_builder.py` - Use LLM pipeline
- `src/pipelines/query_constructor/atomic_level_builder.py` - Use LLM pipeline
- `src/pipelines/query_constructor/dual_mode_builder.py` - Remove template params
- `src/pipelines/query_constructor/__init__.py` - Export new classes

**Deprecated:**
- `src/prompts/query/chain_level.j2` - No longer used
- `src/prompts/query/atomic_level.j2` - No longer used

## Documentation

See `docs/LLM_QUERY_GENERATION.md` for detailed documentation.

## Next Steps

1. Test with real PR chain data
2. Evaluate query quality and diversity
3. Tune temperature parameters if needed
4. Collect user feedback on query naturalness
