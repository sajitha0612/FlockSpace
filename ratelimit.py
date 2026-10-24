"""
Sliding-window rate limits, enforced on the server for every protected action.

Limits are per (action, key) where key is usually a user id (or a hashed IP for signup/login).
State is in memory: the app runs as one process, and a restart only ever loosens limits for
a moment. Limits that must survive restarts (AI quotas, daily Golden Nest cap) are counted from
the database instead.
"""
import threading
import time
from collections import defaultdict, deque

from .errors import ApiError

# action -> (max events, window seconds)
LIMITS: dict[str, tuple[int, int]] = {
    "signup": (5, 3600),
    "login": (10, 900),
    "verify_send": (3, 900),
    "reset_send": (3, 900),
    "verify_try": (10, 900),
    "room_create": (10, 3600),
    "room_join": (12, 3600),
    "chat": (8, 10),
    "chat_minute": (40, 60),
    "follow": (30, 3600),
    "buddy_request": (15, 3600),
    "nudge": (10, 86400),
    "invite": (20, 3600),
    "upload": (15, 3600),
    "ai": (4, 60),
    "quiz_submit": (60, 60),
    "meeting_create": (10, 3600),
    "report": (10, 3600),
    "feedback": (30, 3600),
    "topic_toggle": (60, 60),
    "pomodoro": (30, 60),
}


class RateLimiter:
    def __init__(self):
        self._events: dict[tuple[str, str], deque] = defaultdict(deque)
        self._lock = threading.Lock()

    def hit(self, action: str, key: str, limit: tuple[int, int] | None = None) -> None:
        count, window = limit or LIMITS[action]
        now = time.monotonic()
        with self._lock:
            q = self._events[(action, key)]
            while q and q[0] <= now - window:
                q.popleft()
            if len(q) >= count:
                wait = int(window - (now - q[0])) + 1
                raise ApiError("RATE_LIMITED", f"You're doing that too often. Try again in {wait} seconds.", 429, {"retry_after": wait})
            q.append(now)

    def reset(self) -> None:
        with self._lock:
            self._events.clear()


limiter = RateLimiter()
