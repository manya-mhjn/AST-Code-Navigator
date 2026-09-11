"""
gemini_router.py — Quota-Aware Multi-Model Router for Google Gemini API.

Manages dynamic routing, sliding-window rate limiting (RPM/TPM/RPD),
and zero-error automated failover across:
  - LLM Text Models:
      * gemini-3.6-flash  (5 RPM, 250K TPM, 20 RPD)
      * gemini-3.7-flash  (5 RPM, 250K TPM, 20 RPD)
      * gemini-3.8-flash  (5 RPM, 250K TPM, 20 RPD)
  - Embedding Models:
      * gemini-embedding-001  (100 RPM, 30K TPM, 1,000 RPD)
      * gemini-embedding-2    (100 RPM, 30K TPM, 1,000 RPD)
"""

import os
import time
import threading
from collections import deque
from typing import Any, Dict, List, Optional

from google import genai
from google.genai import types
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import BaseMessage, AIMessage, HumanMessage, SystemMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from pydantic import Field


# =============================================================================
# 1. Model Quota Tracker (Sliding Window RPM / TPM / RPD)
# =============================================================================

class ModelQuotaTracker:
    def __init__(self, model_id: str, rpm_limit: int, tpm_limit: int, rpd_limit: int):
        self.model_id = model_id
        self.rpm_limit = rpm_limit
        self.tpm_limit = tpm_limit
        self.rpd_limit = rpd_limit

        self.request_window: deque[float] = deque()
        self.token_window: deque[tuple[float, int]] = deque()
        self.daily_requests: deque[float] = deque()
        self.cooldown_until: float = 0.0
        self.lock = threading.Lock()

    def _purge_old(self, now: float):
        while self.request_window and (now - self.request_window[0] >= 60.0):
            self.request_window.popleft()

        while self.token_window and (now - self.token_window[0][0] >= 60.0):
            self.token_window.popleft()

        while self.daily_requests and (now - self.daily_requests[0] >= 86400.0):
            self.daily_requests.popleft()

    def get_current_tpm(self, now: float) -> int:
        return sum(tokens for _, tokens in self.token_window)

    def can_accept(self, estimated_tokens: int = 1000) -> bool:
        now = time.time()
        with self.lock:
            self._purge_old(now)
            if now < self.cooldown_until:
                return False
            if len(self.request_window) >= self.rpm_limit:
                return False
            if self.get_current_tpm(now) + estimated_tokens > self.tpm_limit:
                return False
            if len(self.daily_requests) >= self.rpd_limit:
                return False
            return True

    def available_capacity(self, estimated_tokens: int = 1000) -> float:
        now = time.time()
        with self.lock:
            self._purge_old(now)
            if now < self.cooldown_until or len(self.daily_requests) >= self.rpd_limit:
                return 0.0

            rpm_rem = max(0, self.rpm_limit - len(self.request_window)) / float(self.rpm_limit)
            tpm_rem = max(0, self.tpm_limit - (self.get_current_tpm(now) + estimated_tokens)) / float(self.tpm_limit)
            return (rpm_rem * 0.6) + (tpm_rem * 0.4)

    def wait_time_needed(self) -> float:
        now = time.time()
        with self.lock:
            self._purge_old(now)
            if now < self.cooldown_until:
                return max(0.0, self.cooldown_until - now)
            if len(self.request_window) < self.rpm_limit:
                return 0.0
            earliest = self.request_window[0]
            return max(0.0, (earliest + 60.0) - now + 0.1)

    def record_usage(self, tokens_used: int):
        now = time.time()
        with self.lock:
            self.request_window.append(now)
            self.token_window.append((now, max(1, tokens_used)))
            self.daily_requests.append(now)

    def mark_error_cooldown(self, seconds: float = 6.0):
        with self.lock:
            self.cooldown_until = time.time() + seconds


# =============================================================================
# 2. Gemini LLM Multi-Model Router
# =============================================================================

class GeminiLLMRouter:
    _instance = None
    _instance_lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        with cls._instance_lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
            return cls._instance

    def __init__(self, api_key: str):
        if hasattr(self, '_initialized') and self._initialized:
            return
        self.api_key = api_key
        self.client = genai.Client(api_key=api_key)
        self.trackers = {
            'gemini-3.6-flash': ModelQuotaTracker('gemini-3.6-flash', rpm_limit=5, tpm_limit=250_000, rpd_limit=20),
            'gemini-3.7-flash': ModelQuotaTracker('gemini-3.7-flash', rpm_limit=5, tpm_limit=250_000, rpd_limit=20),
            'gemini-3.8-flash': ModelQuotaTracker('gemini-3.8-flash', rpm_limit=5, tpm_limit=250_000, rpd_limit=20),
        }
        self._initialized = True

    def generate(self, prompt: str, temperature: float = 0.0, max_tokens: int = 2048) -> str:
        est_tokens = len(prompt) // 3 + 200

        for attempt in range(len(self.trackers) * 3):
            candidates = sorted(
                self.trackers.values(),
                key=lambda t: t.available_capacity(est_tokens),
                reverse=True
            )
            best_tracker = candidates[0]

            if not best_tracker.can_accept(est_tokens):
                min_wait = min(t.wait_time_needed() for t in self.trackers.values())
                if min_wait > 0.1:
                    print(f"  [~] [Gemini Router] All Flash models at Quota. Waiting {min_wait:.1f}s for RPM sliding window reset...")
                    time.sleep(min_wait)
                    continue

            model_id = best_tracker.model_id
            try:
                print(f"  [+] [Gemini Router] Routing request to '{model_id}' (Available Capacity: {best_tracker.available_capacity():.0%})")
                config = types.GenerateContentConfig(
                    temperature=temperature,
                    max_output_tokens=max_tokens,
                )
                response = self.client.models.generate_content(
                    model=model_id,
                    contents=prompt,
                    config=config,
                )

                tokens = 500
                if hasattr(response, 'usage_metadata') and response.usage_metadata:
                    tokens = getattr(response.usage_metadata, 'total_token_count', tokens) or tokens
                best_tracker.record_usage(tokens)

                return response.text or ''

            except Exception as e:
                print(f"  [!] [Gemini Router] Temporary issue on '{model_id}': {str(e)[:90]}... Failover to sibling model.")
                best_tracker.mark_error_cooldown(seconds=6.0)

        raise RuntimeError('All Gemini Flash models failed or are currently unavailable.')


# =============================================================================
# 3. Gemini Embedding Multi-Model Router
# =============================================================================

class GeminiEmbeddingRouter:
    _instance = None
    _instance_lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        with cls._instance_lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
            return cls._instance

    def __init__(self, api_key: str):
        if hasattr(self, '_initialized') and self._initialized:
            return
        self.api_key = api_key
        self.client = genai.Client(api_key=api_key)
        self.trackers = {
            'gemini-embedding-001': ModelQuotaTracker('gemini-embedding-001', rpm_limit=100, tpm_limit=30_000, rpd_limit=1_000),
            'gemini-embedding-2': ModelQuotaTracker('gemini-embedding-2', rpm_limit=100, tpm_limit=30_000, rpd_limit=1_000),
        }
        self._initialized = True

    def embed_query(self, text: str) -> List[float]:
        return self._embed_single(text)

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        returns = []
        for text in texts:
            returns.append(self._embed_single(text))
        return returns

    def _embed_single(self, text: str) -> List[float]:
        est_tokens = len(text) // 3 + 10

        for attempt in range(len(self.trackers) * 2):
            candidates = sorted(
                self.trackers.values(),
                key=lambda t: t.available_capacity(est_tokens),
                reverse=True
            )
            best_tracker = candidates[0]

            if not best_tracker.can_accept(est_tokens):
                min_wait = min(t.wait_time_needed() for t in self.trackers.values())
                if min_wait > 0.1:
                    time.sleep(min_wait)
                    continue

            model_id = best_tracker.model_id
            try:
                response = self.client.models.embed_content(
                    model=model_id,
                    contents=text,
                )
                best_tracker.record_usage(est_tokens)
                return response.embeddings[0].values
            except Exception as e:
                print(f"  [!] [Embedding Router] Error on '{model_id}': {e}. Switching model...")
                best_tracker.mark_error_cooldown(seconds=5.0)

        raise RuntimeError('All Gemini Embedding models failed or are currently unavailable.')


# =============================================================================
# 4. LangChain BaseChatModel Integration
# =============================================================================

class GeminiRoutedChatModel(BaseChatModel):
    api_key: str = Field(...)
    temperature: float = Field(default=0.0)
    max_tokens: int = Field(default=2048)

    @property
    def _llm_type(self) -> str:
        return 'gemini-routed-flash-pool'

    def _generate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[Any] = None,
        **kwargs: Any,
    ) -> ChatResult:
        router = GeminiLLMRouter(api_key=self.api_key)
        prompt_parts = []
        for m in messages:
            if isinstance(m, SystemMessage):
                prompt_parts.append(f"System: {m.content}")
            elif isinstance(m, HumanMessage):
                prompt_parts.append(f"User: {m.content}")
            elif isinstance(m, AIMessage):
                prompt_parts.append(f"Assistant: {m.content}")
            else:
                prompt_parts.append(f"{m.type}: {m.content}")

        full_prompt = "\n\n".join(prompt_parts)
        text_out = router.generate(
            prompt=full_prompt,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
        )

        message = AIMessage(content=text_out)
        generation = ChatGeneration(message=message)
        return ChatResult(generations=[generation])
