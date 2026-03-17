#!/usr/bin/env python3
"""Test script for Azure OpenAI integration."""

import os
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.utils.llm_client import LLMClient


def test_llm_client():
    """Test LLM client initialization and generation."""
    print("Testing LLM Client...")

    # Check environment variables
    api_key = os.getenv("AZURE_OPENAI_API_KEY")
    if not api_key:
        print("⚠️  AZURE_OPENAI_API_KEY not set")
        print("Set it with: export AZURE_OPENAI_API_KEY='your_key'")
        return False

    # Initialize client
    try:
        client = LLMClient(
            api_key=api_key,
            endpoint="https://gpt-5.4-2026-03-05.openai.azure.com/",
            model="gpt-5.4-2026-03-05",
            temperature=0.7,
            max_tokens=100
        )
        print("✓ LLM client initialized")
    except Exception as e:
        print(f"✗ Failed to initialize client: {e}")
        return False

    # Test generation
    try:
        response = client.generate("Say 'Hello, World!' in one sentence.")
        print(f"✓ Generation successful")
        print(f"Response: {response[:100]}...")
        return True
    except Exception as e:
        print(f"✗ Generation failed: {e}")
        return False


if __name__ == "__main__":
    success = test_llm_client()
    sys.exit(0 if success else 1)
