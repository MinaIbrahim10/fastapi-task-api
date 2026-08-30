from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import dataclass
from threading import Lock
from typing import Any


@dataclass
class CacheEntry:
    value: dict[str, Any]
    expires_at: float


class TriageCache:
    def __init__(self) -> None:
        self._items: dict[str, CacheEntry] = {}
        self._lock = Lock()

    @staticmethod
    def build_key(
        *,
        text: str,
        prompt_version: str,
        model: str,
        provider: str,
    ) -> str:
        payload = json.dumps(
            {
                "text": text,
                "prompt_version": prompt_version,
                "model": model,
                "provider": provider,
            },
            sort_keys=True,
            ensure_ascii=False,
        )

        return hashlib.sha256(
            payload.encode("utf-8")
        ).hexdigest()

    def get(
        self,
        key: str,
    ) -> dict[str, Any] | None:
        now = time.time()

        with self._lock:
            entry = self._items.get(key)

            if entry is None:
                return None

            if entry.expires_at <= now:
                self._items.pop(key, None)
                return None

            return dict(entry.value)

    def set(
        self,
        key: str,
        value: dict[str, Any],
        *,
        ttl_seconds: int,
    ) -> None:
        with self._lock:
            self._items[key] = CacheEntry(
                value=dict(value),
                expires_at=(
                    time.time()
                    + ttl_seconds
                ),
            )

    def clear(self) -> None:
        with self._lock:
            self._items.clear()


triage_cache = TriageCache()


def cache_enabled() -> bool:
    return (
        os.getenv(
            "LLM_CACHE_ENABLED",
            "true",
        ).lower()
        == "true"
    )


def cache_ttl_seconds() -> int:
    return int(
        os.getenv(
            "LLM_CACHE_TTL_SECONDS",
            "300",
        )
    )
