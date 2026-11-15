"""Round-robin key pools: spread AI requests across several API keys of one provider.

Each request takes the next key in turn (1, 2, 3, 1, ...). A key that hits a rate limit
rests for a while and is skipped until then. Keys are only ever referred to by their
slot number ("gemini key #2"), never by value, so they can't leak into logs.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field

from pydantic import SecretStr


@dataclass(frozen=True)
class PooledKey:
    provider: str
    slot: int  # 1-based, for logs
    secret: SecretStr

    def __repr__(self) -> str:
        return f"<{self.provider} key #{self.slot}>"


@dataclass
class KeyPool:
    provider: str
    keys: Sequence[SecretStr]
    rest_seconds: float = 60.0
    clock: Callable[[], float] = time.monotonic
    _next: int = field(default=0, init=False)
    _resting_until: dict[int, float] = field(default_factory=dict, init=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False, repr=False)

    def __len__(self) -> int:
        return len(self.keys)

    def take(self, count: int = 1) -> list[PooledKey]:
        """The next `count` distinct keys in rotation, skipping resting ones.

        If every key is resting, the ones that recover soonest are returned anyway:
        a request that might work beats one that certainly fails.
        """
        if not self.keys:
            return []
        count = min(count, len(self.keys))
        with self._lock:
            now = self.clock()
            order = [(self._next + i) % len(self.keys) for i in range(len(self.keys))]
            ready = [i for i in order if self._resting_until.get(i, 0) <= now]
            resting = sorted(
                (i for i in order if i not in ready), key=lambda i: self._resting_until[i]
            )
            chosen = (ready + resting)[:count]
            self._next = (chosen[0] + 1) % len(self.keys)
        return [PooledKey(self.provider, i + 1, self.keys[i]) for i in chosen]

    def rest(self, key: PooledKey) -> None:
        """Bench a key after a rate limit."""
        with self._lock:
            self._resting_until[key.slot - 1] = self.clock() + self.rest_seconds
