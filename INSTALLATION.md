# Installation Guide

## Prerequisites

- Python 3.8 or higher
- pip package manager
- Git (optional, for cloning)
- GitHub account with API token (optional but recommended)

## Step-by-Step Installation

### 1. Navigate to Project Directory

```bash
cd /home/bairidreamer/Repos/dual-mode-query-synthesis
```

### 2. Create Virtual Environment

```bash
python3 -m venv venv
```

### 3. Activate Virtual Environment

**On Linux/Mac:**
```bash
source venv/bin/activate
```

**On Windows:**
```bash
venv\Scripts\activate
```

### 4. Install Dependencies

```bash
pip install -r requirements.txt
```

### 5. Verify Installation

```bash
python -c "from src.pipelines.query_constructor import DualModeBuilder; print('Installation successful!')"
```

## Optional: GitHub API Token

For better rate limits and access to private repositories:

### 1. Create GitHub Token

1. Go to https://github.com/settings/tokens
2. Click "Generate new token (classic)"
3. Select scopes: `repo`, `read:org`
4. Generate and copy token

### 2. Set Environment Variable

**Temporary (current session):**
```bash
export GITHUB_TOKEN="ghp_your_token_here"
```

**Permanent (add to ~/.bashrc or ~/.zshrc):**
```bash
echo 'export GITHUB_TOKEN="ghp_your_token_here"' >> ~/.bashrc
source ~/.bashrc
```

## Verify Setup

Run the test suite:

```bash
pytest tests/ -v
```

Expected output:
```
tests/test_synthesis.py::test_extract_modules PASSED
tests/test_synthesis.py::test_extract_action_verb PASSED
tests/test_synthesis.py::test_extract_subject PASSED
tests/test_synthesis.py::test_infer_function_type PASSED
tests/test_synthesis.py::test_pr_record_creation PASSED
```

## Troubleshooting

### Issue: ModuleNotFoundError

**Solution:**
```bash
# Make sure you're in the project root
cd /home/bairidreamer/Repos/dual-mode-query-synthesis

# Reinstall dependencies
pip install -r requirements.txt
```

### Issue: Permission Denied

**Solution:**
```bash
# Make scripts executable
chmod +x run_example.sh
```

### Issue: GitHub API Rate Limit

**Solution:**
- Set GITHUB_TOKEN environment variable
- Use `--cache-dir` to cache API responses

## Next Steps

After installation, see:
- `QUICKSTART.md` for quick start guide
- `USAGE_EXAMPLES.md` for usage examples
- `README.md` for full documentation
