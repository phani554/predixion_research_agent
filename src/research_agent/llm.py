"""Provider-agnostic LLM interface with structured output parsing and test doubles."""
from __future__ import annotations

import json
import re
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Protocol, TypeVar
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class LLMError(Exception):
    """Raised when an underlying LLM provider call fails or times out."""


class StructuredOutputError(LLMError):
    """Raised when the LLM response cannot be parsed or validated against the expected schema."""


@dataclass(frozen=True)
class LLMResponse:
    """Standardized response from an LLM call across providers."""

    text: str
    prompt_tokens: int = 0
    completion_tokens: int = 0


class LLMClient(Protocol):
    """Protocol defining the standard interface for any LLM provider."""

    def complete(
        self,
        messages: list[dict[str, str]],
        *,
        json_mode: bool = True,
        purpose: str = "",
    ) -> LLMResponse:
        """Execute a completion call with the given messages."""
        ...


def extract_json(text: str) -> str:
    """Extract a JSON object substring from model output, stripping code fences and surrounding prose.

    Finds the first '{' and matching last '}' after removing markdown fences.
    """
    s = text.strip()
    if "```" in s:
        lines = s.splitlines()
        inner_lines: list[str] = []
        in_fence = False
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("```"):
                in_fence = not in_fence
                continue
            if in_fence:
                inner_lines.append(line)
        if inner_lines:
            s = "\n".join(inner_lines).strip()

    start = s.find("{")
    end = s.rfind("}")
    if start != -1 and end != -1 and end >= start:
        return s[start : end + 1]
    return s


def schema_hint(model_cls: type[BaseModel]) -> str:
    """Generate a strict JSON schema prompt instruction for the given Pydantic model class."""
    schema_json = json.dumps(model_cls.model_json_schema(), indent=2)
    return (
        f"Respond with valid JSON matching this schema exactly. No commentary or markdown outside the JSON.\n"
        f"JSON Schema:\n{schema_json}"
    )


def parse_retry_after(err_str: str) -> float:
    """Extract retry-after seconds from rate limit error text, clamped to 1..35 seconds."""
    match = re.search(r"retry after (\d+(?:\.\d+)?)s?", err_str, re.IGNORECASE)
    if match:
        val = float(match.group(1))
        return min(max(val, 1.0), 35.0)
    return 5.0


class OpenAICompatLLM:
    """OpenAI-compatible LLM client with error normalization, throttling, and retry bounds."""

    _lock = threading.Lock()
    _last_request_time: float = 0.0

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        model: str = "",
        timeout_s: float = 60.0,
        max_retries: int = 2,
        json_mode: bool = True,
        min_interval_s: float = 0.0,
        max_tokens: int = 4096,
        extra_body: dict[str, Any] | None = None,
    ) -> None:
        if not model or not model.strip():
            raise LLMError("LLM_MODEL must be provided and non-empty")

        self.model = model.strip()
        self.timeout_s = timeout_s
        self.max_retries = max_retries
        self.json_mode = json_mode
        self.min_interval_s = min_interval_s
        self.max_tokens = max_tokens
        self.extra_body = extra_body

        import openai

        self._client = openai.OpenAI(
            base_url=base_url or None,
            api_key=api_key or "no-key",
            timeout=timeout_s,
            max_retries=max_retries,
        )

    def _apply_throttle(self) -> None:
        if self.min_interval_s <= 0:
            return
        with OpenAICompatLLM._lock:
            now = time.monotonic()
            elapsed = now - OpenAICompatLLM._last_request_time
            if elapsed < self.min_interval_s:
                sleep_time = self.min_interval_s - elapsed
                time.sleep(sleep_time)
            OpenAICompatLLM._last_request_time = time.monotonic()

    def complete(
        self,
        messages: list[dict[str, str]],
        *,
        json_mode: bool = True,
        purpose: str = "",
    ) -> LLMResponse:
        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.0,
            "max_tokens": self.max_tokens,
        }
        if self.json_mode and json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        if self.extra_body:
            kwargs["extra_body"] = self.extra_body

        retried_rate_limit = False

        while True:
            self._apply_throttle()
            try:
                resp = self._client.chat.completions.create(**kwargs)
                choice = resp.choices[0]
                text = choice.message.content or ""
                p_tokens = getattr(resp.usage, "prompt_tokens", 0) or 0
                c_tokens = getattr(resp.usage, "completion_tokens", 0) or 0
                return LLMResponse(
                    text=text,
                    prompt_tokens=p_tokens,
                    completion_tokens=c_tokens,
                )
            except Exception as err:
                err_str = str(err)
                is_rate_limit = (
                    "429" in err_str
                    or "limit reached" in err_str.lower()
                    or "rate limit" in err_str.lower()
                    or type(err).__name__ == "RateLimitError"
                )

                if is_rate_limit and not retried_rate_limit:
                    retried_rate_limit = True
                    wait_time = parse_retry_after(err_str)
                    time.sleep(wait_time)
                    continue

                raise LLMError(f"LLM call failed for purpose '{purpose}': {err}") from err


def structured(
    llm: LLMClient,
    messages: list[dict[str, str]],
    model_cls: type[T],
    *,
    tracer: Any = None,
    purpose: str = "",
) -> T:
    """Request structured output from the LLM, validating against model_cls with at most one repair retry."""
    resp = llm.complete(messages, json_mode=True, purpose=purpose)
    if tracer and hasattr(tracer, "record_llm"):
        tracer.record_llm(resp.prompt_tokens, resp.completion_tokens, purpose=purpose)

    try:
        raw_json = extract_json(resp.text)
        data = json.loads(raw_json)
        return model_cls.model_validate(data)
    except Exception as first_err:
        if tracer and hasattr(tracer, "event"):
            tracer.event(
                "invalid_llm_reply",
                error=str(first_err),
                preview=resp.text[:100],
                purpose=purpose,
            )

        # Exactly one repair attempt
        repair_messages = list(messages) + [
            {"role": "assistant", "content": resp.text},
            {
                "role": "user",
                "content": (
                    f"The previous output failed validation for schema {model_cls.__name__}:\n"
                    f"{first_err}\n"
                    f"Please fix the error and reply with valid JSON only."
                ),
            },
        ]

        repair_resp = llm.complete(repair_messages, json_mode=True, purpose=purpose)
        if tracer and hasattr(tracer, "record_llm"):
            tracer.record_llm(repair_resp.prompt_tokens, repair_resp.completion_tokens, purpose=purpose)

        try:
            repair_json = extract_json(repair_resp.text)
            repair_data = json.loads(repair_json)
            return model_cls.model_validate(repair_data)
        except Exception as second_err:
            if tracer and hasattr(tracer, "event"):
                tracer.event(
                    "invalid_llm_reply",
                    error=str(second_err),
                    preview=repair_resp.text[:100],
                    purpose=purpose,
                )
            raise StructuredOutputError(
                f"Failed to produce valid {model_cls.__name__} after one repair attempt: {second_err}"
            ) from second_err


class FaultyLLM:
    """Wrapper around an LLM client to inject faults (e.g. malformed responses or outages)."""

    def __init__(self, inner: LLMClient, faults: set[str] | list[str] | None = None) -> None:
        self.inner = inner
        self.faults: set[str] = set(faults or [])
        self._seen_purposes: set[str] = set()

    def complete(
        self,
        messages: list[dict[str, str]],
        *,
        json_mode: bool = True,
        purpose: str = "",
    ) -> LLMResponse:
        if "llm:down" in self.faults:
            raise LLMError("Injected fault: llm:down")

        if "llm:malformed" in self.faults and purpose not in self._seen_purposes:
            self._seen_purposes.add(purpose)
            return LLMResponse(
                text="This is an injected malformed non-JSON reply.",
                prompt_tokens=5,
                completion_tokens=5,
            )

        return self.inner.complete(messages, json_mode=json_mode, purpose=purpose)


class FakeLLM:
    """Scriptable in-memory test double for LLM calls."""

    def __init__(
        self,
        script: dict[str, list[str | Exception] | Callable[[list[dict[str, str]]], str]] | None = None,
    ) -> None:
        self._script: dict[str, list[str | Exception] | Callable[[list[dict[str, str]]], str]] = script or {}
        self.calls: list[tuple[str, list[dict[str, str]]]] = []

    def complete(
        self,
        messages: list[dict[str, str]],
        *,
        json_mode: bool = True,
        purpose: str = "",
    ) -> LLMResponse:
        self.calls.append((purpose, messages))

        entry = self._script.get(purpose)
        if entry is None:
            # Fallback if no specific script for purpose
            return LLMResponse(text="{}", prompt_tokens=10, completion_tokens=10)

        if callable(entry):
            text = entry(messages)
            return LLMResponse(text=text, prompt_tokens=10, completion_tokens=10)

        if isinstance(entry, list):
            if not entry:
                raise LLMError(f"FakeLLM script exhausted for purpose '{purpose}'")
            item = entry.pop(0)
            if isinstance(item, Exception):
                raise item
            return LLMResponse(text=str(item), prompt_tokens=10, completion_tokens=10)

        return LLMResponse(text=str(entry), prompt_tokens=10, completion_tokens=10)
