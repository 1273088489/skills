from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from urllib.parse import urlparse, parse_qs

import requests

from .config import USER_AGENT

URL_RE = re.compile(r"https?://[^\s\u4e00-\u9fff\uff09)\u3011\u300d]+", re.IGNORECASE)

PLATFORM_PATTERNS = [
    ("douyin", ("douyin.com", "iesdouyin.com")),
    ("bilibili", ("bilibili.com", "b23.tv")),
    ("youtube", ("youtube.com", "youtu.be")),
]


@dataclass
class Identity:
    original_input: str = ""
    share_text: str = ""
    original_url: str = ""
    resolved_url: str = ""
    platform: str = "other"
    canonical_id: str = ""
    platform_id: str = ""
    extra_ids: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return dict(self.__dict__)


def extract_first_url(text: str) -> str:
    m = URL_RE.search(text or "")
    return m.group(0).rstrip(".,;\uff0c\u3002\uff1b") if m else ""


def detect_platform(url: str) -> str:
    host = urlparse(url).netloc.lower()
    for name, keys in PLATFORM_PATTERNS:
        if any(k in host for k in keys):
            return name
    return "other"


def resolve_url(url: str, timeout: int = 15) -> tuple[str, str]:
    """Follow redirects; returns (final_url, err)."""
    try:
        resp = requests.get(
            url,
            headers={"User-Agent": USER_AGENT},
            timeout=timeout,
            allow_redirects=True,
        )
        return resp.url, ""
    except Exception as exc:  # network hiccup should not kill acquisition
        return url, "resolve_failed: " + str(exc)


def canonical_from_url(url: str, platform: str) -> tuple[str, dict]:
    """Extract canonical work id from a resolved URL."""
    path = urlparse(url).path
    extra: dict = {}
    if platform == "douyin":
        m = re.search(r"/(?:video|note|article)/(\d+)", path)
        if m:
            return m.group(1), extra
    elif platform == "bilibili":
        m = re.search(r"/video/(BV[0-9A-Za-z]+)", path)
        if m:
            return m.group(1), extra
    elif platform == "youtube":
        q = parse_qs(urlparse(url).query)
        if "v" in q:
            return q["v"][0], extra
        m = re.search(r"/(?:shorts|embed)/([\w-]{11})", path)
        if m:
            return m.group(1), extra
        m = re.search(r"youtu\.be/([\w-]{11})", url)
        if m:
            return m.group(1), extra
    return "", extra


def identify(raw_input: str) -> Identity:
    """Normalize user input (bare URL or full share text) into an Identity."""
    text = (raw_input or "").strip()
    url = text if text.startswith("http") else extract_first_url(text)
    ident = Identity(original_input=text, share_text=text if not text.startswith("http") else "")
    if not url:
        raise ValueError("no http(s) URL found in input")
    ident.original_url = url
    ident.platform = detect_platform(url)
    if ident.platform == "douyin":
        # RED LINE: WSL never contacts douyin, not even redirect resolution.
        # The browser tab resolves the short link during capture.
        ident.resolved_url = ""
        ident.canonical_id = ""
        ident.platform_id = ""
        return ident
    resolved, err = resolve_url(url)
    ident.resolved_url = resolved
    if not err:
        ident.platform = detect_platform(resolved) or ident.platform
    cid, _ = canonical_from_url(resolved, ident.platform)
    ident.canonical_id = cid
    ident.platform_id = cid
    return ident


def cache_key(ident: Identity) -> str:
    cid = ident.canonical_id or uuid.uuid4().hex[:12]
    return ident.platform + "_" + cid