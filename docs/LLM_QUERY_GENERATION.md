# LLM-Based Query Generation Implementation

## Overview

The query generation system has been completely redesigned to use LLM-based synthesis instead of rule-based templates. This produces natural, diverse, user-perspective queries.

## Architecture

```
PR Chain Data
     ↓
┌─────────────────────────────────────┐
│  Step 1: Intent Synthesis (LLM)    │
│  - Analyze PR metadata              │
│  - Reconstruct user's original     │
│    requirement/problem              │
└─────────────────────────────────────┘
     ↓
┌─────────────────────────────────────┐
│  Step 2: Query Generation (LLM)    │
│  - Convert intent to natural        │
│    language query                   │
│  - Vary style and detail level     │
└─────────────────────────────────────┘
     ↓
┌─────────────────────────────────────┐
│  Step 3: Ground Truth Attachment   │
│  - Add patch/diff                   │
│  - Add validation criteria          │
└─────────────────────────────────────┘
     ↓
  Final Query Artifact
```

## Key Components

### 1. IntentSynthesizer

**Location:** `src/pipelines/query_constructor/intent_synthesizer.py`

**Purpose:** Uses LLM to understand PR changes and reconstruct the original user requirement.

**Methods:**
- `synthesize_chain_intent()` - For PR chains
- `synthesize_atomic_intent()` - For single PRs

**Prompts:**
- `src/prompts/intent_synthesis/chain_level_intent.txt`
- `src/prompts/intent_synthesis/atomic_level_intent.txt`

**Example Output:**
```
"We need to add GraphQL support to our API. Current REST endpoints are
getting unwieldy with all the nested resources. Should set up Apollo Server
alongside existing REST (no breaking changes), then migrate user/auth
queries first as a pilot..."
```

### 2. QueryGenerator

**Location:** `src/pipelines/query_constructor/query_generator.py`

**Purpose:** Converts synthesized intent into natural language user queries.

**Methods:**
- `generate_chain_query()` - For PR chains
- `generate_atomic_query()` - For single PRs

**Prompts:**
- `src/prompts/query_generation/chain_level_query.txt`
- `src/prompts/query_generation/atomic_level_query.txt`

**Example Output:**
```
"Hey, I need help adding GraphQL to our API. The REST endpoints are
becoming a mess with all the nested data. Can we set up Apollo Server
alongside the existing REST API? Want to make sure we don't break anything
for current users..."
```

### 3. Updated Builders

**ChainLevelBuilder** and **AtomicLevelBuilder** now:
- No longer use Jinja2 templates
- Call IntentSynthesizer → QueryGenerator pipeline
- Attach ground truth to generated queries
- Support fallback to rule-based generation if LLM unavailable

## Prompt Design Philosophy

### Intent Synthesis Prompts

**Goal:** Reconstruct what the user originally wanted

**Key Features:**
- Analyze PR metadata (title, description, diff, files)
- Consider different user types (PM, tech lead, developer)
- Focus on problem/need, not implementation
- Capture the "why" behind changes

**Constraints Removed:**
- ❌ No "must not mention files"
- ❌ No "must not use technical terms"
- ❌ No "must not structure with steps"

**Constraints Kept:**
- ✅ Write from user perspective (what they want)
- ✅ Focus on problem/outcome
- ✅ Be natural and varied

### Query Generation Prompts

**Goal:** Convert intent to natural user request

**Key Features:**
- Use first person ("I need...", "Can you...")
- Allow technical or non-technical language
- Allow structured (markdown) or casual style
- Allow mentioning files/modules if appropriate
- Vary in detail level and clarity

**Style Variety:**
- Casual: "The login button is broken. Can you fix it?"
- Structured: "## Problem\n## Proposed Solution\n## Acceptance Criteria"
- Technical: "Need to refactor UserService using dependency injection..."

## Configuration

### LLM Parameters

In `config/config.yaml`:
```yaml
llm:
  api_key: ${AZURE_OPENAI_API_KEY}
  endpoint: https://gpt-5.4-2026-03-05.openai.azure.com/
  model: gpt-5.4-2026-03-05
  temperature: 0.8  # Higher for diversity
  max_tokens: 4096
```

### Temperature Settings

- **Intent Synthesis:** 0.8 (moderate diversity)
- **Query Generation:** 0.9 (high diversity)

Higher temperature ensures each query is unique and natural.

## Fallback Behavior

If LLM client is not configured or fails:
- Falls back to simple rule-based generation
- Uses PR titles and descriptions directly
- Still produces valid queries, just less natural

## Usage Example

```python
from src.utils.llm_client import LLMClient
from src.pipelines.query_constructor import ChainLevelBuilder

# Initialize LLM client
llm_client = LLMClient(
    api_key="your_key",
    endpoint="https://your-endpoint.openai.azure.com/",
    model="gpt-5.4-2026-03-05"
)

# Initialize builder
builder = ChainLevelBuilder(llm_client=llm_client)

# Build query
query = builder.build_query(
    chain_id="chain_001",
    pr_records=pr_records,
    llm_judgment=judgment,
    quality_score=9.5
)

# query.prompt now contains natural language user query
print(query.prompt)
```

## Benefits

### 1. Natural Language
- Queries read like real user requests
- No template artifacts
- Varied expression styles

### 2. Diversity
- Each query is unique
- Different levels of technical detail
- Different communication styles

### 3. User Perspective
- Describes problems, not solutions
- Focuses on "what" and "why"
- May suggest "how" but doesn't prescribe it

### 4. Flexibility
- Handles technical and non-technical users
- Supports structured and casual formats
- Adapts to PR complexity

## Comparison: Old vs New

### Old (Template-Based)

```
## Role
You are an AI Software Evolution Architect...

### Phase 1: Foundation Analysis
1. Examine the repository structure...

### Phase 2: Incremental Implementation
#### Step 1: Add OAuth2 Provider
- **Files to modify**: src/auth/oauth.ts, src/auth/provider.ts
- **Objective**: Implement OAuth2 authentication
```

**Problems:**
- ❌ God's-eye view (already knows the answer)
- ❌ Tells agent exactly what to do
- ❌ Lists files to modify (cheating)
- ❌ Structured like a solution, not a problem

### New (LLM-Generated)

```
We need to add OAuth2 support to our authentication system. Currently we
only have basic username/password login, but users are asking for Google
and GitHub login options.

Can we implement this incrementally? Maybe start with the OAuth2 framework,
then add Google as the first provider, and finally add token refresh?
Important that we don't break existing login during the migration.

The auth code is in src/auth/ but I'm not sure exactly which files need
changes. Let me know if you need more context.
```

**Benefits:**
- ✅ User perspective (describes need)
- ✅ Explains "why" (user requests)
- ✅ Suggests approach but doesn't prescribe
- ✅ Natural, conversational tone
- ✅ Admits uncertainty ("not sure exactly")

## Testing

Test intent synthesis:
```bash
python3 -c "
from src.utils.llm_client import LLMClient
from src.pipelines.query_constructor import IntentSynthesizer

client = LLMClient(api_key='...', endpoint='...', model='...')
synthesizer = IntentSynthesizer(client)

# Test with sample PR
intent = synthesizer.synthesize_atomic_intent(pr_record)
print(intent)
"
```

## Files Modified

- `src/pipelines/query_constructor/intent_synthesizer.py` - Complete rewrite
- `src/pipelines/query_constructor/query_generator.py` - New file
- `src/pipelines/query_constructor/chain_level_builder.py` - Updated to use LLM
- `src/pipelines/query_constructor/atomic_level_builder.py` - Updated to use LLM
- `src/pipelines/query_constructor/dual_mode_builder.py` - Removed template paths
- `src/prompts/intent_synthesis/` - New prompt directory
- `src/prompts/query_generation/` - New prompt directory

## Deprecated

- `src/prompts/query/chain_level.j2` - No longer used
- `src/prompts/query/atomic_level.j2` - No longer used
- Jinja2 template rendering in builders
