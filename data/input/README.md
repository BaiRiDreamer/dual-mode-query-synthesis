# Example: Sample PR chain data for testing

This directory should contain your PR chain data from daVinci-Agency.

## Expected Format

The input file should be a JSONL file where each line is a JSON object representing a PR chain:

```json
{
  "chain_id": "chain_0001",
  "original_chain": ["scipy/scipy#333", "scipy/scipy#334", "scipy/scipy#339"],
  "status": "approved",
  "quality_score": 9.0,
  "file_overlap_rate": 0.176,
  "llm_judgment": {
    "is_valid_chain": true,
    "confidence": 0.94,
    "overall_score": 9.0,
    "scores": {
      "topic_consistency": 9,
      "logical_relevance": 9,
      "temporal_reasonableness": 10,
      "author_consistency": 8
    },
    "reasoning": "All three PRs center on scipy.special internals...",
    "evolution_pattern": "collaborative_development",
    "function_types": ["MAINT", "ENH"],
    "issues": []
  },
  "issues": []
}
```

## How to Get Input Data

Copy your PR chain data from daVinci-Agency:

```bash
cp /path/to/daVinci-Agency/PR-list-output.jsonl data/input/
```
