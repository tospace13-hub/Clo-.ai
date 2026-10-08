"""The only place Cloé talks to Claude.

Three shapes, matching the trust rules in sprint.md → Security:
- `extract(schema, system, blocks)` — a reader. Sees untrusted blocks, has no tools,
  must return `schema`.
- `draft(system, prompt)` — a writer. Sees only trusted text (facts, summaries, tone.md),
  has no tools, returns text that the caller validates.
- `research(system, prompt)` — a reader with Anthropic's server-side web tools only.
  Its text is untrusted: wrap it before any other call sees it.

Every call checks for a refusal and for the canary before returning. `FakeClaude` has the
same interface and runs the same guards, so tests exercise them without the network.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any, TypeVar

from pydantic import BaseModel

from cloe import db
from cloe.config import Settings
from cloe.untrusted import contains_canary

T = TypeVar("T", bound=BaseModel)

FALLBACK_BETA = "server-side-fallback-2026-07-01"
MAX_TOKENS = 16_000
MAX_PAUSE_CONTINUES = 5
RETURN_SCHEMA_NOTE = "Return the structured output your task describes."

System = str | list[dict[str, Any]]


class LLMError(Exception):
    """Base class: the output of this call must not be used."""


class Refused(LLMError):
    def __init__(self, category: str | None = None, explanation: str | None = None):
        self.category = category
        self.explanation = explanation
        super().__init__(f"model refused (category={category})")


class InjectionSuspected(LLMError):
    """The output contained the canary: the system prompt leaked. Output discarded."""


class Truncated(LLMError):
    """The output hit max_tokens or the pause_turn limit and is incomplete."""


class UnwrappedInput(LLMError):
    """A reader was handed text that did not go through `untrusted.wrap()`."""


@dataclass
class ResearchResult:
    """Output of `research()`. Untrusted: wrap `text` before another call reads it."""

    text: str
    sources: list[dict[str, str]] = field(default_factory=list)
    continues: int = 0


@dataclass
class Call:
    method: str
    model: str
    effort: str
    system: list[dict[str, Any]]
    content: Any
    schema: str | None = None
    tools: list[dict[str, Any]] | None = None


def as_system(system: System) -> list[dict[str, Any]]:
    """A plain string becomes one cached block; lists (from `persona`) pass through."""
    if isinstance(system, str):
        return [{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}]
    return system


def _check_wrapped(blocks: Sequence[str]) -> None:
    for block in blocks:
        b = block.strip()
        if not (b.startswith("<untrusted source=") and b.endswith("</untrusted>")):
            raise UnwrappedInput("extract() blocks must come from untrusted.wrap()")


def _extract_content(blocks: Sequence[str]) -> list[dict[str, str]]:
    return [{"type": "text", "text": b} for b in blocks] + [
        {"type": "text", "text": RETURN_SCHEMA_NOTE}
    ]


def web_tools(
    allowed_domains: Sequence[str] | None = None,
    blocked_domains: Sequence[str] | None = None,
    max_uses: int = 8,
) -> list[dict[str, Any]]:
    """Anthropic's server-side web tools. Never pass both domain lists (the API refuses)."""
    if allowed_domains and blocked_domains:
        raise ValueError("pass allowed_domains or blocked_domains, not both")
    extra: dict[str, Any] = {}
    if allowed_domains:
        extra["allowed_domains"] = list(allowed_domains)
    elif blocked_domains:
        extra["blocked_domains"] = list(blocked_domains)
    return [
        {"type": "web_search_20260209", "name": "web_search", "max_uses": max_uses, **extra},
        {"type": "web_fetch_20260209", "name": "web_fetch", "max_uses": max_uses, **extra},
    ]


class _Guarded:
    """Shared guards. Subclasses implement `_extract`, `_draft`, `_research`."""

    def __init__(self, settings: Settings, conn: sqlite3.Connection | None = None):
        self.settings = settings
        self.conn = conn

    # -- public interface -------------------------------------------------------------

    def extract(
        self,
        schema: type[T],
        system: System,
        blocks: Sequence[str],
        effort: str | None = None,
        *,
        bulk: bool = False,
    ) -> T:
        _check_wrapped(blocks)
        model, effort = self._model(bulk), effort or self.settings.effort
        result, raw_text = self._extract(schema, as_system(system), blocks, model, effort)
        self._guard(raw_text, f"extract:{schema.__name__}")
        return result

    def draft(
        self, system: System, prompt: str, effort: str | None = None, *, bulk: bool = False
    ) -> str:
        model, effort = self._model(bulk), effort or self.settings.effort
        text = self._draft(as_system(system), prompt, model, effort)
        self._guard(text, "draft")
        return text

    def research(
        self,
        system: System,
        prompt: str,
        *,
        allowed_domains: Sequence[str] | None = None,
        blocked_domains: Sequence[str] | None = None,
        max_uses: int = 8,
        effort: str | None = None,
    ) -> ResearchResult:
        tools = web_tools(allowed_domains, blocked_domains, max_uses)
        model, effort = self._model(False), effort or self.settings.effort
        result = self._research(as_system(system), prompt, tools, model, effort)
        self._guard(result.text, "research")
        return result

    # -- shared helpers ---------------------------------------------------------------

    def _model(self, bulk: bool) -> str:
        return self.settings.model_bulk if bulk else self.settings.model

    def _guard(self, text: str, ref: str) -> None:
        if contains_canary(text, self.settings.canary):
            if self.conn is not None:
                db.event(self.conn, "llm", "injection_suspected", ref=ref)
            raise InjectionSuspected(ref)

    def _refused(self, category: str | None, ref: str) -> Refused:
        if self.conn is not None:
            db.event(self.conn, "llm", "refused", ref=ref, detail={"category": category})
        return Refused(category)

    # -- implemented by subclasses ----------------------------------------------------

    def _extract(self, schema, system, blocks, model, effort) -> tuple[Any, str]:
        raise NotImplementedError

    def _draft(self, system, prompt, model, effort) -> str:
        raise NotImplementedError

    def _research(self, system, prompt, tools, model, effort) -> ResearchResult:
        raise NotImplementedError


def _text_of(content: Sequence[Any]) -> str:
    return "".join(getattr(b, "text", "") for b in content if getattr(b, "type", "") == "text")


def _sources_of(content: Sequence[Any]) -> list[dict[str, str]]:
    seen: dict[str, dict[str, str]] = {}
    for block in content:
        kind = getattr(block, "type", "")
        inner = getattr(block, "content", None)
        if kind == "web_search_tool_result" and isinstance(inner, list):  # error = object
            for r in inner:
                url = getattr(r, "url", "")
                if url:
                    seen.setdefault(url, {"url": url, "title": getattr(r, "title", "") or ""})
        elif kind == "web_fetch_tool_result" and getattr(inner, "type", "") == "web_fetch_result":
            url = getattr(inner, "url", "")
            if url:
                seen.setdefault(url, {"url": url, "title": ""})
    return list(seen.values())


class Claude(_Guarded):
    """Real client. Thinking is always on for this model family, so `thinking` is omitted;
    effort is set explicitly; no sampling parameters; no prefill; no forced tool_choice."""

    def __init__(self, settings: Settings, conn: sqlite3.Connection | None = None, client=None):
        super().__init__(settings, conn)
        self._client = client

    @property
    def client(self):
        if self._client is None:
            import anthropic

            self._client = anthropic.Anthropic(api_key=self.settings.anthropic_api_key or None)
        return self._client

    def _common(self, system, model, effort) -> dict[str, Any]:
        return {
            "model": model,
            "max_tokens": MAX_TOKENS,
            "system": system,
            "output_config": {"effort": effort},
            "fallbacks": "default",
            "betas": [FALLBACK_BETA],
        }

    def _check_stop(self, response, ref: str) -> None:
        if response.stop_reason == "refusal":
            details = getattr(response, "stop_details", None)
            raise self._refused(getattr(details, "category", None), ref)
        if response.stop_reason == "max_tokens":
            raise Truncated(ref)

    def _extract(self, schema, system, blocks, model, effort):
        response = self.client.beta.messages.parse(
            **self._common(system, model, effort),
            messages=[{"role": "user", "content": _extract_content(blocks)}],
            output_format=schema,
        )
        self._check_stop(response, f"extract:{schema.__name__}")
        raw = _text_of(response.content)
        parsed = response.parsed_output
        if parsed is None:
            raise LLMError(f"no parsed output for {schema.__name__}")
        return parsed, raw

    def _draft(self, system, prompt, model, effort):
        response = self.client.beta.messages.create(
            **self._common(system, model, effort),
            messages=[{"role": "user", "content": prompt}],
        )
        self._check_stop(response, "draft")
        return _text_of(response.content)

    def _research(self, system, prompt, tools, model, effort):
        # Append-only history: on pause_turn, re-send with the assistant turn added.
        messages: list[dict[str, Any]] = [{"role": "user", "content": prompt}]
        collected: list[Any] = []
        for continues in range(MAX_PAUSE_CONTINUES + 1):
            response = self.client.beta.messages.create(
                **self._common(system, model, effort), tools=tools, messages=messages
            )
            self._check_stop(response, "research")
            collected.extend(response.content)
            if response.stop_reason != "pause_turn":
                return ResearchResult(
                    text=_text_of(response.content),
                    sources=_sources_of(collected),
                    continues=continues,
                )
            messages.append({"role": "assistant", "content": response.content})
        raise Truncated(f"research paused more than {MAX_PAUSE_CONTINUES} times")


Canned = Any  # a dict / model / str / ResearchResult, an Exception to raise, or a callable


class FakeClaude(_Guarded):
    """Test double. `outputs` maps a schema name (for extract), "draft" or "research" to a
    canned value, a list of values (used in order), an exception, or a callable taking the
    request content. Every call is recorded in `self.calls`."""

    def __init__(
        self,
        settings: Settings,
        outputs: dict[str, Canned] | None = None,
        conn: sqlite3.Connection | None = None,
    ):
        super().__init__(settings, conn)
        self.outputs = dict(outputs or {})
        self.calls: list[Call] = []

    def _next(self, key: str, content: Any) -> Any:
        if key not in self.outputs:
            raise KeyError(f"FakeClaude has no canned output for {key!r}")
        value = self.outputs[key]
        if isinstance(value, list):
            if not value:
                raise KeyError(f"FakeClaude ran out of canned outputs for {key!r}")
            value = value.pop(0)
        if callable(value) and not isinstance(value, type):
            value = value(content)
        if isinstance(value, Refused):
            raise self._refused(value.category, key)
        if isinstance(value, Exception):
            raise value
        return value

    def _extract(self, schema, system, blocks, model, effort):
        content = _extract_content(blocks)
        self.calls.append(Call("extract", model, effort, system, content, schema.__name__))
        value = self._next(schema.__name__, content)
        if isinstance(value, BaseModel):
            value = value.model_dump(mode="json")
        return schema.model_validate(value), json.dumps(value, ensure_ascii=False)

    def _draft(self, system, prompt, model, effort):
        self.calls.append(Call("draft", model, effort, system, prompt))
        return str(self._next("draft", prompt))

    def _research(self, system, prompt, tools, model, effort):
        self.calls.append(Call("research", model, effort, system, prompt, tools=tools))
        value = self._next("research", prompt)
        return value if isinstance(value, ResearchResult) else ResearchResult(text=str(value))
