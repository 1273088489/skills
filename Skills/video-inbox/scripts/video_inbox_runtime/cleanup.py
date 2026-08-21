from __future__ import annotations

import json
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .acquire import is_partial_download, load_manifest
from .config import RuntimePaths
from .retry import load_queue
from .runner import write_json


def _dir_is_empty(directory: Path) -> bool:
    try:
        return not any(directory.iterdir())
    except OSError:
        return False


def _older_than(path: Path, cutoff: datetime) -> bool:
    try:
        mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
    except OSError:
        return False
    return mtime < cutoff


def _pending_task_ids(paths: RuntimePaths) -> set[str]:
    return {str(item.get("task_id", "")) for item in load_queue(paths) if item.get("task_id")}


def run_cleanup(paths: RuntimePaths, *, ttl_days: float = 7.0, apply: bool = False) -> dict[str, Any]:
    """统一清理失效/过期文件。apply=False 时只预览（dry-run）。"""
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=ttl_days)
    pending = _pending_task_ids(paths)
    candidates: list[tuple[Path, str]] = []
    kept: list[str] = []
    errors: list[dict[str, str]] = []

    def mark(path: Path, reason: str) -> None:
        candidates.append((path, reason))

    # 1) temp：空目录、仅半成品、过期且不在重试队列中的任务目录
    if paths.temp.is_dir():
        for task_dir in sorted(paths.temp.iterdir()):
            if not task_dir.is_dir():
                if _older_than(task_dir, cutoff):
                    mark(task_dir, f"stray-temp-file-older-than-{ttl_days:g}d")
                else:
                    kept.append(str(task_dir))
                continue
            if _dir_is_empty(task_dir):
                mark(task_dir, "empty-temp-dir")
            elif all(item.is_file() and is_partial_download(item.name) for item in task_dir.rglob("*")):
                mark(task_dir, "partial-download-only")
            elif task_dir.name in pending:
                kept.append(str(task_dir))
            elif _older_than(task_dir, cutoff):
                mark(task_dir, f"stale-temp-older-than-{ttl_days:g}d")
            else:
                kept.append(str(task_dir))

    # 2) browser-bridge：无对应结果的孤儿请求（保留结果文件作为证据）
    if paths.browser_requests.is_dir():
        for req in sorted(paths.browser_requests.glob("*.json")):
            if (paths.browser_results / req.name).is_file():
                kept.append(str(req))
            elif _older_than(req, cutoff):
                mark(req, f"orphaned-request-older-than-{ttl_days:g}d")
            else:
                kept.append(str(req))

    # 3) cache：空目录、无 manifest、或过期且 needs-review 的条目；最后清空平台空目录
    if paths.cache.is_dir():
        for platform_dir in sorted(paths.cache.iterdir()):
            if not platform_dir.is_dir():
                continue
            for item_dir in sorted(platform_dir.iterdir()):
                if not item_dir.is_dir():
                    continue
                if _dir_is_empty(item_dir):
                    mark(item_dir, "empty-cache-dir")
                    continue
                manifest_file = item_dir / "manifest.json"
                manifest = load_manifest(manifest_file) if manifest_file.is_file() else None
                if manifest is None:
                    mark(item_dir, "cache-entry-without-manifest")
                elif manifest.analysis_status == "needs-review" and _older_than(item_dir, cutoff):
                    mark(item_dir, f"stale-needs-review-older-than-{ttl_days:g}d")
                else:
                    kept.append(str(item_dir))
            if _dir_is_empty(platform_dir):
                mark(platform_dir, "empty-platform-dir")

    # 4) retry 队列：清理 manifest 已不存在的条目
    queue_path = paths.state / "retry-queue.json"
    queue_dropped = 0
    if queue_path.is_file():
        try:
            queue = json.loads(queue_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            queue = []
        remaining = []
        for item in queue:
            manifest_file = Path(str(item.get("manifest_path", "")))
            if manifest_file.is_file():
                remaining.append(item)
            else:
                queue_dropped += 1
        if queue_dropped:
            mark(queue_path, f"retry-entries-manifest-missing x{queue_dropped}")

    deleted: list[dict[str, str]] = []
    if apply:
        for path, reason in candidates:
            try:
                if path.is_dir():
                    shutil.rmtree(path)
                else:
                    path.unlink()
                deleted.append({"path": str(path), "reason": reason})
            except OSError as exc:
                errors.append({"path": str(path), "error": str(exc)})
        if queue_dropped:
            write_json(queue_path, remaining)

    return {
        "dry_run": not apply,
        "ttl_days": ttl_days,
        "planned": [{"path": str(path), "reason": reason} for path, reason in candidates] if not apply else [],
        "deleted": deleted,
        "kept": kept,
        "errors": errors,
    }


def format_cleanup_report(report: dict[str, Any]) -> str:
    lines = []
    mode = "dry-run" if report["dry_run"] else "applied"
    lines.append(f"=== video-inbox cleanup ({mode}, TTL={report['ttl_days']:g}d) ===")
    items = report["planned"] if report["dry_run"] else report["deleted"]
    if items:
        lines.append(f"清理 {len(items)} 项:")
        for item in items:
            lines.append(f"  [{item['reason']}] {item['path']}")
    else:
        lines.append("没有需要清理的项目")
    if report["kept"]:
        lines.append(f"保留 {len(report['kept'])} 项（缓存/证据/重试中/未过期）")
    if report["errors"]:
        lines.append(f"错误 {len(report['errors'])} 项:")
        for item in report["errors"]:
            lines.append(f"  [{item['path']}] {item['error']}")
    if report["dry_run"]:
        lines.append("提示：加 --apply 执行删除")
    return "\n".join(lines)
