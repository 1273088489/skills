from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

import requests

from .config import USER_AGENT, TEMP_DIR


class ProbeError(Exception):
    def __init__(self, code: str, detail: str = "", attempts=None):
        super().__init__(code)
        self.code = code
        self.detail = detail
        self.attempts = attempts or []


def classify_error(msg: str) -> str:
    low = (msg or "").lower()
    if "cookies" in low or "login" in low or "sign in" in low or "account" in low:
        return "login_required"
    if "unsupported url" in low:
        return "unsupported"
    if "timed out" in low or "timeout" in low:
        return "network_timeout"
    if "http error 404" in low or "video unavailable" in low:
        return "media_unavailable"
    if "rate limit" in low or "429" in low:
        return "rate_limited"
    return "unknown"


def base_opts() -> dict:
    opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "noplaylist": True,
        "socket_timeout": 25,
        "retries": 2,
        "http_headers": {"User-Agent": USER_AGENT},
    }
    return opts


def probe_metadata(url: str, platform: str) -> tuple[dict, str, list]:
    """Public-source metadata probe (yt-dlp, no cookies, no browser needed).

    Douyin intentionally NEVER goes through here (red line: browser-only).
    """
    import yt_dlp

    attempts: list[dict] = [{"stage": "metadata", "route": "yt-dlp-no-cookie", "status": "started"}]
    try:
        with yt_dlp.YoutubeDL(base_opts()) as ydl:
            info = ydl.extract_info(url, download=False)
        attempts[0]["status"] = "success"
        return normalize_meta(info), "yt-dlp-no-cookie", attempts
    except Exception as exc:
        msg = str(exc)
        attempts[0].update({"status": "failed", "error_code": classify_error(msg), "detail": msg[-400:]})
        raise ProbeError(classify_error(msg), msg, attempts=attempts) from exc


def _norm_chapters(info: dict) -> list:
    out = []
    for ch in info.get("chapters") or []:
        if not isinstance(ch, dict):
            continue
        out.append({
            "start": ch.get("start_time"),
            "end": ch.get("end_time"),
            "title": ch.get("title") or "",
        })
    return out


def normalize_meta(info: dict) -> dict:
    published = ""
    if info.get("upload_date"):
        d = info["upload_date"]
        published = f"{d[0:4]}-{d[4:6]}-{d[6:8]}" if len(d) == 8 else d
    elif info.get("timestamp"):
        published = datetime.fromtimestamp(int(info["timestamp"])).strftime("%Y-%m-%d %H:%M")
    stat_keys = ("view_count", "like_count", "comment_count", "repost_count", "collect_count", "save_count", "share_count")
    stats = {k: info.get(k) for k in stat_keys if info.get(k) is not None}
    return {
        "id": str(info.get("id") or ""),
        "title": (info.get("title") or "").strip(),
        "uploader": info.get("channel") or info.get("uploader") or "",
        "published": published,
        "duration": float(info["duration"]) if info.get("duration") else None,
        "description": re.sub(r"\u2026{0,2}\u7248\u672c\u8fc7\u4f4e[^\n]*$", "", (info.get("description") or "")).strip(),
        "stats": stats,
        "chapters": _norm_chapters(info),
        "webpage_url": info.get("webpage_url") or "",
    }