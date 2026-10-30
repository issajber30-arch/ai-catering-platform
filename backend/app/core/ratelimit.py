import threading
import time
from collections import defaultdict, deque

from fastapi import Request

from app.core.errors import AppError

# shortcut: per-process memory; use Redis/DB when running more than one instance.
_hits: dict[tuple[str, str], deque] = defaultdict(deque)
_lock = threading.Lock()


def client_ip(request: Request) -> str:
    # Rightmost entry is the one our own proxy appended; the leftmost ones are client-forgeable.
    parts = [p.strip() for p in request.headers.get("x-forwarded-for", "").split(",")]
    if ip := next((p for p in reversed(parts) if p), None):
        return ip
    return request.client.host if request.client else "unknown"


def limit(key: str, max_calls: int, window_s: int):
    def check(request: Request) -> None:
        now = time.monotonic()
        with _lock:
            q = _hits[(key, client_ip(request))]
            while q and now - q[0] >= window_s:
                q.popleft()
            if len(q) >= max_calls:
                retry = max(1, int(window_s - (now - q[0])) + 1)
                raise AppError(
                    429, "Too many requests. Please try again later.", code="rate_limited",
                    headers={"Retry-After": str(retry)},
                )  # fmt: skip
            q.append(now)

    return check


def reset() -> None:
    with _lock:
        _hits.clear()
