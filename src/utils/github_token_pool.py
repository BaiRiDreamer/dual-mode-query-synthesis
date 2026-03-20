"""Thread-safe GitHub token pool with per-token rate limit tracking."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass
class TokenLease:
    """A temporary assignment of a token to one request."""

    token_id: str
    token: Optional[str]


@dataclass
class GitHubTokenState:
    """Mutable runtime state for one GitHub token."""

    token_id: str
    token: Optional[str]
    display_name: str
    rate_limit_remaining: Optional[int] = None
    rate_limit_reset_at: Optional[float] = None
    cooldown_until: float = 0.0
    disabled: bool = False
    last_used_at: float = 0.0
    in_flight: int = 0


class GitHubTokenPool:
    """Coordinates token allocation across concurrent GitHub requests."""

    def __init__(
        self,
        tokens: List[Optional[str]],
        cooldown_buffer_seconds: float = 1.0
    ):
        normalized = []
        for token in tokens:
            token_str = token.strip() if isinstance(token, str) else token
            if token_str == "":
                continue
            normalized.append(token_str)

        if not normalized:
            raise ValueError("GitHubTokenPool requires at least one token")

        self.cooldown_buffer_seconds = max(0.0, cooldown_buffer_seconds)
        self._condition = threading.Condition()
        self._cursor = -1
        self._states: List[GitHubTokenState] = [
            GitHubTokenState(
                token_id=f"token-{index}",
                token=token,
                display_name=self._build_display_name(index, token)
            )
            for index, token in enumerate(normalized)
        ]
        self._state_by_id: Dict[str, GitHubTokenState] = {
            state.token_id: state for state in self._states
        }

    def acquire(self) -> TokenLease:
        """Block until a token is available and return a lease for it."""
        with self._condition:
            while True:
                now = time.time()
                available = self._find_available_index(now)
                if available is not None:
                    state = self._states[available]
                    state.in_flight += 1
                    state.last_used_at = now
                    self._cursor = available
                    return TokenLease(token_id=state.token_id, token=state.token)

                wait_until = self._next_available_time()
                if wait_until is None:
                    raise RuntimeError("No usable GitHub tokens remain")

                timeout = max(wait_until - now, 0.01)
                self._condition.wait(timeout=timeout)

    def record_response(self, lease: TokenLease, status_code: int, headers: Dict[str, str]) -> None:
        """Update token state from a completed HTTP response."""
        with self._condition:
            state = self._state_by_id[lease.token_id]
            self._finish_lease(state)
            self._update_rate_limit_state(state, headers)

            if status_code == 401:
                state.disabled = True
            elif self._is_rate_limited(status_code, headers):
                state.cooldown_until = max(
                    state.cooldown_until,
                    self._resolve_cooldown_deadline(headers)
                )

            self._condition.notify_all()

    def record_error(self, lease: TokenLease) -> None:
        """Release a token after a transport-level error."""
        with self._condition:
            state = self._state_by_id[lease.token_id]
            self._finish_lease(state)
            self._condition.notify_all()

    def describe_token(self, lease: TokenLease) -> str:
        """Return a masked token identifier suitable for logs."""
        return self._state_by_id[lease.token_id].display_name

    def _finish_lease(self, state: GitHubTokenState) -> None:
        if state.in_flight > 0:
            state.in_flight -= 1

    def _find_available_index(self, now: float) -> Optional[int]:
        total = len(self._states)
        if total == 0:
            return None

        for offset in range(1, total + 1):
            index = (self._cursor + offset) % total
            state = self._states[index]
            if state.disabled:
                continue
            if state.cooldown_until > now:
                continue
            return index

        return None

    def _next_available_time(self) -> Optional[float]:
        candidates = [
            state.cooldown_until
            for state in self._states
            if not state.disabled
        ]
        if not candidates:
            return None
        return min(candidates)

    def _update_rate_limit_state(self, state: GitHubTokenState, headers: Dict[str, str]) -> None:
        remaining_header = headers.get("X-RateLimit-Remaining")
        reset_header = headers.get("X-RateLimit-Reset")

        if remaining_header is not None:
            try:
                state.rate_limit_remaining = int(remaining_header)
            except (TypeError, ValueError):
                state.rate_limit_remaining = None

        if reset_header is not None:
            try:
                state.rate_limit_reset_at = float(reset_header)
            except (TypeError, ValueError):
                state.rate_limit_reset_at = None

        if state.rate_limit_remaining == 0:
            deadline = self._resolve_cooldown_deadline(headers)
            state.cooldown_until = max(state.cooldown_until, deadline)

    def _resolve_cooldown_deadline(self, headers: Dict[str, str]) -> float:
        retry_after = headers.get("Retry-After")
        if retry_after is not None:
            try:
                return time.time() + float(retry_after) + self.cooldown_buffer_seconds
            except (TypeError, ValueError):
                pass

        reset_header = headers.get("X-RateLimit-Reset")
        if reset_header is not None:
            try:
                return float(reset_header) + self.cooldown_buffer_seconds
            except (TypeError, ValueError):
                pass

        return time.time() + self.cooldown_buffer_seconds

    def _is_rate_limited(self, status_code: int, headers: Dict[str, str]) -> bool:
        return status_code in {403, 429} and headers.get("X-RateLimit-Remaining") == "0"

    def _build_display_name(self, index: int, token: Optional[str]) -> str:
        if not token:
            return "anonymous"
        suffix = token[-4:] if len(token) >= 4 else token
        return f"token[{index}]:{suffix}"
