from __future__ import annotations

import re
from dataclasses import dataclass
from hashlib import sha256
from urllib.parse import parse_qs, urlparse

URL_RE = re.compile(r"https?://[^\s<>\]\[\)\(\"']+", re.IGNORECASE)


@dataclass(frozen=True)
class VideoIdentity:
    original_url: str
    platform: str
    canonical_id: str
    cache_key: str


def extract_urls(text: str) -> list[str]:
    return [url.rstrip(".,;!?，。；！？") for url in URL_RE.findall(text)]


def identify(url: str) -> VideoIdentity:
    parsed = urlparse(url)
    host = parsed.netloc.lower().split(":")[0]
    path = parsed.path.strip("/")
    query = parse_qs(parsed.query)
    platform = "other"
    canonical_id = ""

    if host in {"youtu.be", "www.youtu.be"}:
        platform = "youtube"
        canonical_id = path.split("/")[0]
    elif "youtube.com" in host:
        platform = "youtube"
        if path == "watch":
            canonical_id = (query.get("v") or [""])[0]
        elif path.startswith("shorts/") or path.startswith("live/") or path.startswith("embed/"):
            canonical_id = path.split("/")[1] if "/" in path else ""
    elif "bilibili.com" in host or host in {"b23.tv", "www.b23.tv"}:
        platform = "bilibili"
        match = re.search(r"(?i)(BV[0-9A-Za-z]+|av\d+)", url)
        canonical_id = match.group(1) if match else ""
        page = (query.get("p") or [""])[0]
        if canonical_id and page:
            canonical_id = f"{canonical_id}:p{page}"
    elif "douyin.com" in host or host in {"v.douyin.com", "iesdouyin.com"}:
        platform = "douyin"
        match = re.search(r"/(?:video|note)/(\d+)", parsed.path)
        canonical_id = match.group(1) if match else ""

    if not canonical_id:
        canonical_id = sha256(url.encode("utf-8")).hexdigest()[:20]
    cache_key = re.sub(r"[^0-9A-Za-z._-]+", "_", f"{platform}_{canonical_id}")
    return VideoIdentity(url, platform, canonical_id, cache_key)
