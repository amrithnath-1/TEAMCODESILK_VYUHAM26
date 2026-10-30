"""In-memory sliding-window limits, per process."""
import time
from collections import defaultdict, deque
from typing import Dict

from fastapi import HTTPException

_rate_windows: Dict[str, deque] = defaultdict(deque)


def rate_check(key: str, limit: int, seconds: int) -> None:
    now = time.time()
    window = _rate_windows[key]
    while window and window[0] < now - seconds:
        window.popleft()
    if len(window) >= limit:
        raise HTTPException(429, f"Too many requests. Please wait up to {seconds} seconds and try again.")


def rate_limit(key: str, limit: int, seconds: int) -> None:
    rate_check(key, limit, seconds)
    _rate_windows[key].append(time.time())
