"""Azure OpenAI LLM Client for query synthesis."""

import os
from typing import Optional, Dict, Any
from openai import AzureOpenAI


class LLMClient:
    """Client for Azure OpenAI API."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        endpoint: Optional[str] = None,
        model: Optional[str] = None,
        api_version: str = "2024-08-01-preview",
        temperature: float = 0.7,
        max_tokens: int = 4096,
        top_p: float = 0.95
    ):
        self.api_key = api_key or os.getenv("AZURE_OPENAI_API_KEY")
        self.endpoint = endpoint
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.top_p = top_p

        self.client = AzureOpenAI(
            api_key=self.api_key,
            api_version=api_version,
            azure_endpoint=self.endpoint
        )

    def generate(self, prompt: str, **kwargs) -> str:
        """Generate text from prompt."""
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=kwargs.get("temperature", self.temperature),
            max_tokens=kwargs.get("max_tokens", self.max_tokens),
            top_p=kwargs.get("top_p", self.top_p)
        )
        return response.choices[0].message.content
