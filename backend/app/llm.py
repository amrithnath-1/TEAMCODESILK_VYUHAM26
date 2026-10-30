"""Server-side Anthropic Claude client. The API key is read from the environment and never leaves the backend."""
import json
import os
from typing import Any, Dict, List, Optional

import anthropic

from . import db
from .audit import utcnow

DEFAULT_MODEL = "claude-opus-5-5"
_client: Optional[Any] = None


class LLMUnavailable(Exception):
    """Claude could not be used; the message is safe to show to the user."""


def model() -> str:
    return os.environ.get("AF07_MODEL") or DEFAULT_MODEL


def is_configured() -> bool:
    return _client is not None or bool(os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN"))


def status() -> Dict:
    return {"configured": is_configured(), "model": model(),
            "setup": None if is_configured() else "Set ANTHROPIC_API_KEY in the backend .env file and restart the API."}


def set_client_for_tests(client: Optional[Any]) -> None:
    global _client
    _client = client


def _get_client() -> Any:
    global _client
    if _client is None:
        if not is_configured():
            raise LLMUnavailable("Claude is not configured. Set ANTHROPIC_API_KEY in the backend .env file.")
        _client = anthropic.Anthropic(timeout=90.0, max_retries=2)
    return _client


def _record(feature: str, usage: Any, ok: bool, error: Optional[str] = None) -> None:
    # Only usage metadata is kept here, never prompt or response content.
    with db.tx() as c:
        c.execute("INSERT INTO ai_usage (feature, model, input_tokens, output_tokens, ok, error, created_at) VALUES (?,?,?,?,?,?,?)",
                  (feature, model(), getattr(usage, "input_tokens", None), getattr(usage, "output_tokens", None), int(ok), error, utcnow()))


def _check_daily_limit() -> None:
    limit = os.environ.get("AF07_DAILY_AI_CALLS", "").strip()
    if not limit:
        return
    today = utcnow()[:10]
    used = db.one("SELECT COUNT(*) AS n FROM ai_usage WHERE org_id = ? AND created_at >= ?", (db.org(), today))["n"]
    if used >= int(limit):
        raise LLMUnavailable("This company has reached its daily limit for AI requests. It resets at midnight UTC.")


def create_message(feature: str, *, system: str, messages: List[Dict], tools: Optional[List[Dict]] = None,
                   output_schema: Optional[Dict] = None, max_tokens: int = 8000, effort: str = "medium") -> Any:
    """One Messages API call with typed error handling. Refusals fall back server-side to another model."""
    client = _get_client()
    _check_daily_limit()
    params: Dict[str, Any] = {
        "model": model(), "max_tokens": max_tokens, "messages": messages,
        "system": [{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
        "output_config": {"effort": effort},
        "betas": ["server-side-fallback-2026-07-01"], "fallbacks": "default",
    }
    if tools:
        params["tools"] = tools
    if output_schema:
        params["output_config"]["format"] = {"type": "json_schema", "schema": output_schema}
    try:
        response = client.beta.messages.create(**params)
    except anthropic.AuthenticationError:
        _record(feature, None, False, "authentication")
        raise LLMUnavailable("Claude rejected the API key. Check ANTHROPIC_API_KEY in the backend .env file.")
    except anthropic.RateLimitError:
        _record(feature, None, False, "rate_limit")
        raise LLMUnavailable("Claude's rate limit was reached. Wait a minute and try again.")
    except anthropic.APITimeoutError:
        _record(feature, None, False, "timeout")
        raise LLMUnavailable("Claude took too long to respond. Please try again.")
    except anthropic.APIConnectionError:
        _record(feature, None, False, "connection")
        raise LLMUnavailable("Could not reach the Claude API. Check the server's network connection.")
    except anthropic.APIStatusError as exc:
        _record(feature, None, False, f"status_{exc.status_code}")
        raise LLMUnavailable(f"The Claude API returned an error ({exc.status_code}). Please try again.")
    _record(feature, response.usage, True)
    if response.stop_reason == "refusal":
        raise LLMUnavailable("Claude declined this request.")
    return response


def text_of(response: Any) -> str:
    return "".join(b.text for b in response.content if b.type == "text").strip()


def structured(feature: str, *, system: str, prompt: str, schema: Dict, max_tokens: int = 16000) -> Dict:
    """Schema-constrained JSON output, validated by the caller."""
    response = create_message(feature, system=system, messages=[{"role": "user", "content": prompt}],
                              output_schema=schema, max_tokens=max_tokens)
    if response.stop_reason == "max_tokens":
        raise LLMUnavailable("Claude's answer was cut off because the documents are too long. Try fewer documents.")
    try:
        return json.loads(text_of(response))
    except json.JSONDecodeError:
        raise LLMUnavailable("Claude returned a malformed result. Please try again.")
