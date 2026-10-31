"""On-disk file cache for successful tool results."""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
import time
from pathlib import Path
from typing import Any
from pydantic import BaseModel


def _serialize(obj: Any) -> Any:
    """Recursively convert BaseModel instances into serializable dicts."""
    if isinstance(obj, BaseModel):
        return obj.model_dump()
    if isinstance(obj, list):
        return [_serialize(x) for x in obj]
    if isinstance(obj, dict):
        return {k: _serialize(v) for k, v in obj.items()}
    return obj


class Cache:
    """Atomic on-disk cache for tool execution results with TTL expiration."""

    def __init__(self, directory: str | Path = ".cache", ttl_s: int = 86400) -> None:
        self.directory = Path(directory)
        self.ttl_s = ttl_s
        self.directory.mkdir(parents=True, exist_ok=True)

    def _hash_key(self, name: str, args: dict[str, Any]) -> str:
        clean_args = _serialize(args)
        serialized = json.dumps([name, clean_args], sort_keys=True, default=str)
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    def get(self, name: str, args: dict[str, Any]) -> Any | None:
        """Retrieve cached tool result if it exists and has not expired."""
        key = self._hash_key(name, args)
        cache_file = self.directory / f"{key}.json"

        if not cache_file.is_file():
            return None

        try:
            raw = cache_file.read_text(encoding="utf-8")
            payload = json.loads(raw)
            created_at = payload.get("created_at", 0.0)

            # Check expiration
            if time.time() - created_at > self.ttl_s:
                try:
                    cache_file.unlink(missing_ok=True)
                except OSError:
                    pass
                return None

            return payload.get("data")
        except Exception:
            return None

    def set(self, name: str, args: dict[str, Any], value: Any) -> None:
        """Atomically persist successful tool results to disk."""
        key = self._hash_key(name, args)
        target_path = self.directory / f"{key}.json"

        payload = {
            "created_at": time.time(),
            "tool": name,
            "data": _serialize(value),
        }

        # Atomic file write using a temporary file in the same directory
        temp_file = tempfile.NamedTemporaryFile(
            mode="w",
            dir=self.directory,
            delete=False,
            encoding="utf-8",
        )
        try:
            with temp_file as f:
                json.dump(payload, f)
            os.replace(temp_file.name, target_path)
        except Exception:
            try:
                if os.path.exists(temp_file.name):
                    os.unlink(temp_file.name)
            except OSError:
                pass

