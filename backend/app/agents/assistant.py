"""Manual tool-use loop for the customer assistant. Talks to services only (via tools)."""

import logging
import threading
import uuid
from dataclasses import dataclass, field
from functools import lru_cache

import anthropic
from sqlalchemy.orm import Session

from app.agents import tools
from app.agents.prompt import SYSTEM_PROMPT
from app.core.config import get_settings
from app.core.errors import AppError
from app.services import conversations

log = logging.getLogger(__name__)

MODEL = "claude-opus-5-5"  # exact id, no date suffix
MAX_ROUNDS = 8  # model calls per customer message; each may run tools
FALLBACK_BETA = "server-side-fallback-2026-07-01"
UNAVAILABLE = "The assistant is unavailable right now. Your order is unchanged."

_MSG = {  # shown instead of model text when the model refused, was cut off or looped
    "refusal": {
        "en": "Sorry, I can't help with that request. Your order is unchanged.",
        "he": "מצטער, אני לא יכול לעזור בבקשה הזו. ההזמנה שלך לא השתנתה.",
        "ar": "عذرًا، لا أستطيع المساعدة في هذا الطلب. طلبك لم يتغير.",
    },
    "max_tokens": {
        "en": "My answer got too long. Please try a shorter or simpler request.",
        "he": "התשובה שלי ארוכה מדי. נסו בקשה קצרה או פשוטה יותר.",
        "ar": "أصبحت إجابتي طويلة جدًا. يرجى تجربة طلب أقصر أو أبسط.",
    },
    "cap": {
        "en": "I couldn't finish that request. Please try again with a simpler request.",
        "he": "לא הצלחתי להשלים את הבקשה. נסו שוב עם בקשה פשוטה יותר.",
        "ar": "لم أتمكن من إكمال الطلب. يرجى المحاولة مجددًا بطلب أبسط.",
    },
}


class AnthropicLLM:
    """Thin wrapper so tests can replace the network call with a fake exposing .create()."""

    def __init__(self, api_key: str):
        self._client = anthropic.Anthropic(api_key=api_key, timeout=120.0, max_retries=2)

    def create(self, **kwargs):
        return self._client.beta.messages.create(**kwargs)


@lru_cache
def _llm(api_key: str) -> AnthropicLLM:
    return AnthropicLLM(api_key)


def get_llm() -> AnthropicLLM:
    key = get_settings().anthropic_api_key
    if not key:
        raise AppError(503, UNAVAILABLE)
    return _llm(key)


@dataclass
class Turn:
    reply: str
    proposals: list = field(default_factory=list)


def _usage(resp) -> dict:
    u = resp.usage
    return {
        "input_tokens": u.input_tokens or 0, "output_tokens": u.output_tokens or 0,
        "cache_read_tokens": getattr(u, "cache_read_input_tokens", 0) or 0,
        "cache_creation_tokens": getattr(u, "cache_creation_input_tokens", 0) or 0,
    }  # fmt: skip


# shortcut: per-process lock; with several app workers use a DB-backed lock instead (Phase 6).
_busy: set[uuid.UUID] = set()
_busy_lock = threading.Lock()


def chat(
    db: Session, llm, order_id: uuid.UUID, token: str | None, message: str, lang: str = "he"
) -> Turn:
    """One turn at a time per order, so two turns' rows never interleave in the history."""
    with _busy_lock:
        if order_id in _busy:
            raise AppError(409, "The assistant is still answering your previous message.")
        _busy.add(order_id)
    try:
        return _turn(db, llm, order_id, token, message, lang)
    finally:
        with _busy_lock:
            _busy.discard(order_id)


def _turn(db: Session, llm, order_id, token, message: str, lang: str) -> Turn:
    conv = conversations.start(db, order_id, token)
    conversations.add(db, conv.id, "user", {"text": message})  # counted even if the call fails
    ctx = tools.Ctx(db, order_id, conv.id, lang)
    messages = conversations.history(db, conv.id)
    new_rows: list[tuple[str, list, dict]] = []  # persisted together once the turn is complete
    totals = dict.fromkeys(("input_tokens", "output_tokens", "cache_read_tokens",
                            "cache_creation_tokens"), 0)  # fmt: skip
    reply, stop = "", "cap"

    def text_row(kind: str):
        return [{"type": "text", "text": _MSG[kind][lang]}]

    for _ in range(MAX_ROUNDS):
        try:
            resp = llm.create(
                model=MODEL, max_tokens=16000, system=SYSTEM_PROMPT, tools=tools.TOOLS,
                messages=list(messages), output_config={"effort": "low"},
                cache_control={"type": "ephemeral"},
                fallbacks="default", betas=[FALLBACK_BETA],
            )  # fmt: skip
        except anthropic.APIError as e:
            log.warning("llm error order=%s type=%s status=%s", order_id, type(e).__name__,
                        getattr(e, "status_code", None))  # fmt: skip
            raise AppError(503, UNAVAILABLE) from None
        usage = _usage(resp)
        for k, v in usage.items():
            totals[k] += v
        stop = resp.stop_reason
        if stop in ("refusal", "max_tokens"):
            if stop == "refusal":
                details = getattr(resp, "stop_details", None)
                log.info(
                    "refusal order=%s category=%s", order_id, getattr(details, "category", None)
                )
            reply = _MSG[stop][lang]
            new_rows.append(("assistant", text_row(stop), usage | {"stop_reason": stop}))
            break
        blocks = [b.model_dump(mode="json", exclude_none=True) for b in resp.content]
        new_rows.append(("assistant", blocks, usage | {"stop_reason": stop}))
        messages.append({"role": "assistant", "content": blocks})
        if stop != "tool_use":
            reply = "".join(b.get("text", "") for b in blocks if b["type"] == "text").strip()
            if not reply:
                reply = _MSG["cap"][lang]
            break
        results = []
        for b in (b for b in blocks if b["type"] == "tool_use"):
            content, is_error = tools.run(ctx, b["name"], b["input"])
            results.append({"type": "tool_result", "tool_use_id": b["id"], "content": content,
                            **({"is_error": True} if is_error else {})})  # fmt: skip
        messages.append({"role": "user", "content": results})
        new_rows.append(("tool", results, {}))
    else:
        reply, stop = _MSG["cap"][lang], "round_cap"
        new_rows.append(("assistant", text_row("cap"), {"stop_reason": stop}))

    for role, content, extra in new_rows:
        conversations.add(db, conv.id, role, content, **extra)
    log.info(
        "assistant turn order=%s stop=%s proposals=%d %s", order_id, stop, len(ctx.created), totals
    )  # ids, counts and reasons only
    return Turn(reply, ctx.created)
