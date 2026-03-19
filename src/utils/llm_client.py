"""Azure OpenAI LLM Client for query synthesis."""

import os
import time
from typing import Optional
from openai import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    AzureOpenAI,
    InternalServerError,
    RateLimitError,
)


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
        top_p: float = 0.95,
        request_timeout: float = 60.0,
        max_retries: int = 3,
        initial_retry_delay: float = 1.0,
        backoff_factor: float = 2.0,
        max_retry_delay: float = 60.0
    ):
        self.api_key = api_key or os.getenv("AZURE_OPENAI_API_KEY")
        self.endpoint = endpoint
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.top_p = top_p
        self.request_timeout = request_timeout
        self.max_retries = max(0, max_retries)
        self.initial_retry_delay = max(0.0, initial_retry_delay)
        self.backoff_factor = max(1.0, backoff_factor)
        self.max_retry_delay = max_retry_delay

        self.client = AzureOpenAI(
            api_key=self.api_key,
            api_version=api_version,
            azure_endpoint=self.endpoint
        )

    def _compute_retry_delay(self, attempt: int, retry_after: Optional[str] = None) -> float:
        """Compute retry delay with optional Retry-After override."""
        if retry_after is not None:
            try:
                return min(float(retry_after), self.max_retry_delay)
            except (TypeError, ValueError):
                pass

        return min(
            self.initial_retry_delay * (self.backoff_factor ** attempt),
            self.max_retry_delay
        )

    def generate(self, prompt: str, **kwargs) -> str:
        """Generate text from prompt with retry handling for transient failures."""
        timeout = kwargs.get("timeout", self.request_timeout)
        last_error = None

        for attempt in range(self.max_retries + 1):
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=kwargs.get("temperature", self.temperature),
                    max_tokens=kwargs.get("max_tokens", self.max_tokens),
                    top_p=kwargs.get("top_p", self.top_p),
                    timeout=timeout
                )
                content = response.choices[0].message.content
                if not content:
                    raise ValueError("LLM returned empty content")
                return content
            except RateLimitError as e:
                last_error = e
                retry_after = None
                if getattr(e, "response", None) is not None:
                    retry_after = e.response.headers.get("Retry-After")
                delay = self._compute_retry_delay(attempt, retry_after)
            except (APITimeoutError, APIConnectionError, InternalServerError) as e:
                last_error = e
                delay = self._compute_retry_delay(attempt)
            except APIStatusError as e:
                last_error = e
                if e.status_code not in {408, 409, 425, 429, 500, 502, 503, 504}:
                    raise
                retry_after = None
                if getattr(e, "response", None) is not None:
                    retry_after = e.response.headers.get("Retry-After")
                delay = self._compute_retry_delay(attempt, retry_after)
            except Exception:
                raise

            if attempt >= self.max_retries:
                break

            print(
                f"LLM request failed; retrying in {delay:.1f}s "
                f"({attempt + 1}/{self.max_retries})..."
            )
            time.sleep(delay)

        if last_error is not None:
            raise last_error
        raise RuntimeError("LLM generation failed without a captured exception")
