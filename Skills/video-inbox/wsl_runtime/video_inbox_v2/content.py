from __future__ import annotations

import re
from pathlib import Path

import requests

from .config import USER_AGENT
from .probe import ProbeError, base_opts, classify_error

LANG_PREFS = ("zh", "en")


def ts_to_seconds(ts: str) -> float:
    ts = ts.strip()
    parts = re.split(r":|,", ts)
    parts = [float(p) for p in parts]
    while len(parts) < 3:
        parts.insert(0, 0.0)
    h, m, s = parts[-3], parts[-2], parts[-1]
    return h * 3600 + m * 60 + s


_TIME_RE = re.compile(r"(\d{1,2}:)?\d{1,2}:\d{2}[.,]\d{3}\s*-->\s*(\d{1,2}:)?\d{1,2}:\d{2}[.,]\d{3}")
_TAG_RE = re.compile(r"</?[^>]+>")
_INLINE_TS_RE = re.compile(r"<\d{2}:\d{2}:\d{2}\.\d{3}>")


def parse_subtitle(text: str) -> list[dict]:
    """Minimal VTT/SRT parser with rolling-caption de-duplication."""
    raw_segments: list[dict] = []
    block: list[str] = []
    for line in text.splitlines() + [""]:
        if line.strip() == "":
            if block:
                joined = "\n".join(block)
                m = _TIME_RE.search(joined)
                if m:
                    a, b = m.group(0).split("-->")
                    body = _TIME_RE.sub("", joined)
                    body = _INLINE_TS_RE.sub("", body)
                    body = _TAG_RE.sub("", body)
                    body = "\n".join(
                        ln.strip() for ln in body.splitlines()
                        if ln.strip() and not re.fullmatch(r"[\d\s]+", ln.strip())
                    )
                    if body:
                        raw_segments.append({"start": ts_to_seconds(a), "end": ts_to_seconds(b), "text": body.strip()})
                block = []
        else:
            block.append(line)
    # merge rolling duplicates (auto captions repeat the previous line)
    merged: list[dict] = []
    for seg in raw_segments:
        t = seg["text"]
        if merged and t in merged[-1]["text"]:
            merged[-1]["end"] = seg["end"]
            continue
        if merged and merged[-1]["text"].endswith(t):
            continue
        merged.append(seg)
    return merged


def pick_subtitle_track(meta: dict):
    for source, key in (("official-subtitle", "subtitles"), ("auto-subtitle", "automatic_captions")):
        tracks = meta.get(key) or {}
        if not isinstance(tracks, dict):
            continue
        for pref in LANG_PREFS:
            for lang, items in tracks.items():
                if lang.lower().startswith(pref) and items:
                    return source, lang, items
        for lang, items in sorted(tracks.items()):
            if items:
                return source, lang, items
    return None


def fetch_subtitles(meta: dict, cache_dir: Path) -> tuple[list[dict] | None, str, str]:
    """Download the best subtitle track directly. Returns (segments, source, lang)."""
    picked = pick_subtitle_track(meta)
    if not picked:
        return None, "none", ""
    source, lang, items = picked
    ranked = sorted(items, key=lambda x: (x.get("ext") != "vtt", x.get("ext") != "srt"))
    for item in ranked:
        url = item.get("url")
        if not url:
            continue
        try:
            resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=30)
            resp.raise_for_status()
            segs = parse_subtitle(resp.text)
            if segs:
                sub_dir = cache_dir / "subtitles"
                sub_dir.mkdir(parents=True, exist_ok=True)
                (sub_dir / f"subtitle.{lang}.{item.get('ext', 'vtt')}").write_text(resp.text, encoding="utf-8")
                return segs, source, lang
        except Exception:
            continue
    return None, source, lang


def download_audio(url: str, out_base: Path) -> Path:
    """Download bestaudio (original container; faster-whisper decodes via PyAV)."""
    import yt_dlp
    from yt_dlp.utils import DownloadError

    opts = base_opts()
    opts.pop("skip_download", None)
    opts.update({
        "format": "bestaudio/best",
        "outtmpl": str(out_base) + ".%(ext)s",
        "max_filesize": 800 * 1024 * 1024,
    })
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.extract_info(url, download=True)
    except DownloadError as exc:
        raise ProbeError(classify_error(str(exc)), str(exc)) from exc
    candidates = [p for p in out_base.parent.glob(out_base.name + ".*") if p.suffix.lower() not in {".part", ".ytdl"}]
    if not candidates:
        raise ProbeError("no_streams", "download reported success but produced no file")
    return max(candidates, key=lambda p: p.stat().st_size)