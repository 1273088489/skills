from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .acquire import acquire, load_manifest
from .config import RuntimePaths
from .runner import write_json


BACKOFF_MINUTES = (10, 30, 120, 720, 1440)


def load_queue(paths: RuntimePaths) -> list[dict[str, Any]]:
    path = paths.state / "retry-queue.json"
    if not path.is_file():
        return []
    try:
        import json

        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, list) else []
    except (OSError, ValueError):
        return []


def save_queue(paths: RuntimePaths, items: list[dict[str, Any]]) -> Path:
    path = paths.state / "retry-queue.json"
    write_json(path, items)
    return path


def next_retry_at(attempts: int, now: datetime | None = None) -> str:
    now = now or datetime.now(timezone.utc)
    minutes = BACKOFF_MINUTES[min(max(attempts, 0), len(BACKOFF_MINUTES) - 1)]
    return (now + timedelta(minutes=minutes)).isoformat()


def run_retries(paths: RuntimePaths, *, once: bool = True, asr_model: str = "small") -> list[tuple[str, str]]:
    items = load_queue(paths)
    if not items:
        return []
    now = datetime.now(timezone.utc)
    due = [item for item in items if item.get("next_retry_at", "") <= now.isoformat()]
    if not due:
        return []

    results: list[tuple[str, str]] = []
    for item in (due[:1] if once else due):
        url = str(item.get("url", ""))
        manifest_file = Path(item.get("manifest_path", ""))
        manifest = load_manifest(manifest_file) if manifest_file.is_file() else None
        if manifest is None:
            items.remove(item)
            results.append((url, "dropped-manifest-missing"))
            continue

        new_manifest, _ = acquire(
            paths,
            manifest.original_input or url,
            url,
            force=True,
            asr_model=asr_model,
        )
        attempts = int(item.get("attempts", 0)) + 1
        item["attempts"] = attempts
        if new_manifest.analysis_status in {"complete", "partial"}:
            items.remove(item)
            results.append((url, "success"))
        elif attempts >= len(BACKOFF_MINUTES):
            items.remove(item)
            results.append((url, "exhausted"))
        else:
            item["next_retry_at"] = next_retry_at(attempts, now)
            item["manifest_path"] = str(manifest_file)
            results.append((url, "queued"))

    save_queue(paths, items)
    return results
