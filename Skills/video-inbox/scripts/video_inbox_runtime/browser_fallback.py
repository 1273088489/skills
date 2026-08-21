from __future__ import annotations

import json
import re
import urllib.request
from pathlib import Path
from typing import Any

from .config import RuntimePaths
from .models import Manifest
from .runner import write_json


DAEMON_URL = "http://127.0.0.1:10086/command"
ALLOWED_EVIDENCE = {"visible-transcript", "video-playback", "screenshots", "page-only", "ai-only"}
REQUIRED_FIELDS = {"task_id", "url", "evidence_type", "coverage", "source"}
TRANSCRIPT_RE = re.compile(r"(?:\d{1,2}:\d{2}(?::\d{2})?\s+[^\n]{4,}){3,}")
CAPTION_HINT_RE = re.compile(r"字幕|字幕文件|自动字幕|captions?|transcript|subtitle", re.IGNORECASE)
_TEXT_KEYS = ("name", "text", "value", "label", "title", "placeholder", "content", "description")


class BrowserBridgeError(RuntimeError):
    pass


def kimi_request(action: str, args: dict[str, Any] | None = None, session: str = "video-inbox") -> dict[str, Any]:
    body = json.dumps({"action": action, "args": args or {}, "session": session}, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        DAEMON_URL,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=45) as response:
            return json.loads(response.read().decode("utf-8"))
    except (OSError, ValueError) as exc:
        raise BrowserBridgeError(f"Kimi WebBridge 调用失败：{exc}") from exc


def collect_text(node: Any) -> list[str]:
    texts: list[str] = []
    seen: set[str] = set()

    def walk(value: Any) -> None:
        if isinstance(value, dict):
            for key in _TEXT_KEYS:
                item = value.get(key)
                if isinstance(item, str) and item.strip():
                    cleaned = " ".join(item.split())
                    if cleaned not in seen:
                        seen.add(cleaned)
                        texts.append(cleaned)
            for key, item in value.items():
                if key not in _TEXT_KEYS:
                    walk(item)
        elif isinstance(value, list):
            for item in value:
                walk(item)

    walk(node)
    return texts


def find_transcript_hint(texts: list[str]) -> str:
    joined = "\n".join(texts)
    matches = TRANSCRIPT_RE.findall(joined)
    if matches:
        return "\n".join(matches)[:20000]
    caption_lines = [line for line in texts if CAPTION_HINT_RE.search(line)]
    return "\n".join(caption_lines)[:20000] if caption_lines else ""


def browser_acquire(paths: RuntimePaths, manifest: Manifest, *, max_text_chars: int = 80000, session: str | None = None) -> dict[str, Any]:
    session = session or f"video-inbox-{manifest.task_id[:8]}"
    url = manifest.resolved_url or manifest.original_url
    result: dict[str, Any] = {
        "task_id": manifest.task_id,
        "url": url,
        "source": "kimi-webbridge",
        "evidence_type": "page-only",
        "actual_content_access": False,
        "coverage": 0.0,
        "timestamps": [],
        "explicit_content": [],
        "inferences": [],
        "unavailable": [],
        "acquisition_chain": [],
        "status": "error",
    }
    try:
        navigation = kimi_request(
            "navigate",
            {
                "url": url,
                "newTab": True,
                "group_title": f"视频分析：{manifest.title or url[:60]}",
            },
            session,
        )
        if not navigation.get("success"):
            raise BrowserBridgeError(f"导航失败：{navigation}")
        result["acquisition_chain"].append("kimi-webbridge:navigate:success")

        snapshot = kimi_request("snapshot", {}, session)
        result["snapshot_url"] = snapshot.get("url")
        result["snapshot_title"] = snapshot.get("title")
        texts = collect_text(snapshot.get("tree"))
        visible = "\n".join(texts)[:max_text_chars]
        result["page_text"] = visible
        result["explicit_content"] = texts[:80]
        result["acquisition_chain"].append("kimi-webbridge:snapshot:success")

        hint = find_transcript_hint(texts)
        if hint:
            result["evidence_type"] = "visible-transcript"
            result["actual_content_access"] = True
            result["transcript_excerpt"] = hint
            result["timestamps"] = _extract_timestamps(hint)
            result["coverage"] = 0.0
        result["status"] = "ok"
    except BrowserBridgeError as exc:
        result["error"] = str(exc)
        result["acquisition_chain"].append("kimi-webbridge:error")

    result_path = paths.browser_results / f"{manifest.task_id}.json"
    write_json(result_path, result)
    result["result_path"] = str(result_path)
    return result


def _extract_timestamps(text: str) -> list[dict[str, str]]:
    timestamps: list[dict[str, str]] = []
    for line in text.splitlines()[:40]:
        match = re.match(r"^\s*(\d{1,2}:\d{2}(?::\d{2})?)\s+(.+)$", line)
        if match:
            timestamps.append({"time": match.group(1), "claim": match.group(2)[:200]})
    return timestamps


def validate_browser_result(data: dict[str, Any]) -> tuple[bool, list[str]]:
    issues: list[str] = []
    if not isinstance(data, dict):
        return False, ["结果不是 JSON 对象"]

    for field_name in REQUIRED_FIELDS:
        value = data.get(field_name)
        if value is None or value == "":
            issues.append(f"缺少必需字段：{field_name}")

    evidence = data.get("evidence_type")
    if evidence not in ALLOWED_EVIDENCE:
        issues.append(f"非法 evidence_type：{evidence!r}")

    coverage = data.get("coverage")
    if not isinstance(coverage, (int, float)):
        issues.append("coverage 必须是数字")

    accessed = data.get("actual_content_access") is True
    if evidence in {"visible-transcript", "video-playback", "screenshots"} and not accessed:
        issues.append("evidence_type 声称访问了内容，但 actual_content_access 不是 true")
    if evidence in {"page-only", "ai-only"} and accessed:
        issues.append("page-only/ai-only 不应声明实际内容访问")

    explicit = data.get("explicit_content")
    if evidence not in {"page-only"} and not explicit:
        issues.append("缺少 explicit_content 锚点")
    if evidence == "ai-only" and not data.get("timestamps") and not data.get("transcript_excerpt"):
        issues.append("ai-only 输出应提供可核对的时间戳或文本锚点")

    return not issues, issues


def load_browser_result(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))
