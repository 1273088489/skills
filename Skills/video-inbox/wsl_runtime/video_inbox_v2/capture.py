from __future__ import annotations

"""Browser-only Douyin capture (Plan B).

RED LINES enforced by this module's shape:
- identity lives ONLY in the user's Edge tab; nothing here exports cookies;
- scripts never call douyin APIs directly - they only READ responses the page
  itself fetched (equivalent to reading DevTools);
- the single outbound request outside the browser is downloading the exact
  signed CDN audio URL the player loaded, with Referer/UA only, NO cookies;
- every wait is bounded; failures stop for a human instead of retrying.
"""

import json
import re
import time
from pathlib import Path

import requests

from .config import USER_AGENT

DAEMON = "http://127.0.0.1:10086/command"
SESSION = "video-inbox-douyin"
GROUP_TITLE = "抖音视频采集"

NOISE_WORDS = {"下一章", "倍速", "智能", "清屏", "连播", "展开", "收起", "举报", "分享", "回复"}
STOP_MARKERS = ("扫码登录", "验证码", "拖动滑块", "完成拼图")
TIME_RE = re.compile(r"^\d{1,3}:\d{2}$")


class CaptureError(Exception):
    def __init__(self, code: str, detail: str = ""):
        super().__init__(code)
        self.code = code
        self.detail = detail


_loopback = requests.Session()
_loopback.trust_env = False  # never route 127.0.0.1 through any proxy


def _post(payload: dict, timeout: int = 45) -> dict:
    # NOTE: the daemon maps business errors to HTTP 502 with a JSON body;
    # only transport-level failures mean "unreachable".
    try:
        r = _loopback.post(DAEMON, data=json.dumps(payload),
                           headers={"Content-Type": "application/json"}, timeout=timeout)
    except Exception as exc:
        raise CaptureError("daemon_unreachable", f"WebBridge daemon/extension unavailable: {exc}") from exc
    try:
        return r.json()
    except Exception as exc:
        raise CaptureError("daemon_bad_response", f"HTTP {r.status_code}: {r.text[:200]}") from exc


def _tree_texts(tree) -> list:
    out: list = []

    def walk(n):
        if isinstance(n, dict):
            name = n.get("name")
            role = n.get("role")
            if isinstance(name, str) and name.strip() and role != "InlineTextBox":
                out.append((role, " ".join(name.split())))
            for c in n.get("children") or []:
                walk(c)
        elif isinstance(n, list):
            for c in n:
                walk(c)

    walk(tree)
    seen: set = set()
    uniq: list = []
    for item in out:
        if item not in seen:
            seen.add(item)
            uniq.append(item)
    return uniq


def _parse_chapters(texts: list) -> tuple[str, list]:
    """Returns (overall_summary, chapters[{start,title,desc}]) from DOM chapter panel."""
    header_idx = None
    total = 0
    for i, (_role, t) in enumerate(texts):
        m = re.match(r"章节要点[：:]?\s*共(\d+)个", t)
        if m:
            header_idx, total = i, int(m.group(1))
            break
    if header_idx is None:
        return "", []
    summary = ""
    chapters: list = []
    j = header_idx + 1
    while j < len(texts) and len(chapters) < (total or 12):
        _role, t = texts[j]
        if TIME_RE.match(t):
            title = texts[j + 1][1] if j + 1 < len(texts) else ""
            desc = ""
            if j + 2 < len(texts):
                nxt = texts[j + 2][1]
                if not TIME_RE.match(nxt) and nxt not in NOISE_WORDS and not nxt.startswith("..."):
                    desc = nxt
            if title and title not in NOISE_WORDS:
                chapters.append({"start": t, "title": title, "desc": desc})
            j += 3 if desc else 2
            continue
        if not summary and len(t) >= 25 and t not in NOISE_WORDS and "个人观点" not in t:
            summary = t
        j += 1
    return summary, chapters


def _extract_publish(texts: list) -> str:
    for _role, t in texts:
        m = re.search(r"\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}", t)
        if m:
            return m.group(0)
        if t.startswith("发布时间"):
            continue
    return ""


def _detect_wall(texts: list) -> str | None:
    joined = " ".join(t for _r, t in texts)
    for marker in STOP_MARKERS:
        if marker in joined:
            return marker
    return None


def _aweme_detail(max_wait_s: int = 18) -> dict | None:
    """Read the aweme/detail response THE PAGE fetched, ASAP after reload.

    CDP getResponseBody loses buffered resources quickly (-32000), so poll
    briefly instead of calling once late. Never request the API ourselves.
    """
    import datetime
    deadline = time.time() + max_wait_s
    while time.time() < deadline:
        lst = _post({"action": "network", "args": {"cmd": "list", "filter": "aweme/detail"}, "session": SESSION})
        reqs = ((lst.get("data") or {}).get("requests")) or []
        if reqs:
            rid = reqs[-1].get("requestId")
            det = _post({"action": "network", "args": {"cmd": "detail", "requestId": rid},
                         "session": SESSION}, timeout=60)
            body = ((det.get("data") or {}).get("body"))
            if isinstance(body, str) and body:
                try:
                    body = json.loads(body)
                except Exception:
                    body = None
            if isinstance(body, dict):
                det_j = body.get("aweme_detail") or {}
                if det_j:
                    ct = det_j.get("create_time")
                    author = det_j.get("author") or {}
                    v = det_j.get("video") or {}
                    st = det_j.get("statistics") or {}
                    dur_ms = v.get("duration")
                    media_candidates: list[str] = []
                    for addr_key in ("play_addr", "download_addr"):
                        addr = v.get(addr_key) or {}
                        for u in addr.get("url_list") or []:
                            if isinstance(u, str) and u.startswith("http"):
                                media_candidates.append(u)
                    for br in v.get("bit_rate") or []:
                        for u in ((br.get("play_addr") or {}).get("url_list")) or []:
                            if isinstance(u, str) and u.startswith("http"):
                                media_candidates.append(u)
                    meta = {
                        "id": det_j.get("aweme_id") or "",
                        "title": (det_j.get("desc") or "").split("\n")[0].strip(),
                        "uploader": author.get("nickname") or "",
                        "published": datetime.datetime.fromtimestamp(int(ct)).strftime("%Y-%m-%d %H:%M") if ct else "",
                        "duration": round(dur_ms / 1000, 3) if dur_ms else None,
                        "description": (det_j.get("desc") or "").strip(),
                        "stats": {k: st.get(k) for k in ("digg_count", "comment_count", "collect_count", "share_count") if st.get(k)},
                        "chapters": [],
                    }
                    meta["_media_candidates"] = media_candidates
                    return meta
        time.sleep(3)
    return None


def _scan_media_url() -> str:
    lst = _post({"action": "network", "args": {"cmd": "list", "filter": "douyinvod"}, "session": SESSION})
    reqs = ((lst.get("data") or {}).get("requests")) or []
    audio = [r for r in reqs if "media-audio" in (r.get("url") or "")]
    if audio:
        return audio[-1]["url"]
    return ""


def _start_network() -> None:
    _post({"action": "network", "args": {"cmd": "start"}, "session": SESSION})


def _stop_network() -> None:
    try:
        _post({"action": "network", "args": {"cmd": "stop"}, "session": SESSION}, timeout=15)
    except CaptureError:
        pass


def _recover_session() -> None:
    """Stale current-tab pointers (user closed a tab) poison the old session;
    move this run to a fresh session so navigation gets a clean slate."""
    global SESSION
    SESSION = f"{SESSION}-r{int(time.time()) % 10000}"


def _navigate(url: str) -> None:
    res = _post({"action": "find_tab", "args": {"url": url}, "session": SESSION}, timeout=15)
    opened = bool(res.get("ok") and (res.get("data") or {}).get("success"))
    if not opened:
        res = _post({"action": "navigate",
                     "args": {"url": url, "newTab": True, "group_title": GROUP_TITLE},
                     "session": SESSION}, timeout=30)
        d = res.get("data") or {}
        if not (res.get("ok") and d.get("success")):
            err = json.dumps(res, ensure_ascii=False)
            # A closed-tab pointer breaks the whole session - recover once.
            if "No tab with given id" in err or "extension_error" in err:
                _recover_session()
                res = _post({"action": "navigate",
                             "args": {"url": url, "newTab": True, "group_title": GROUP_TITLE},
                             "session": SESSION}, timeout=30)
                d = res.get("data") or {}
                if res.get("ok") and d.get("success"):
                    return
            raise CaptureError("navigate_failed", err[:300])


def _snapshot() -> dict:
    res = _post({"action": "snapshot", "args": {}, "session": SESSION}, timeout=60)
    return res.get("data") or {}


def _extract_article_text() -> dict:
    """Read visible 图文正文 from an /article/ page. No extra network."""
    code = (
        "(() => {"
        " const raw = (document.body && document.body.innerText) || '';"
        " const v = document.querySelector('video');"
        " const src = v ? (v.currentSrc || v.src || '') : '';"
        " const nl = String.fromCharCode(10);"
        " let start = raw.indexOf('阅读需要');"
        " if (start < 0) start = 0;"
        " const head = raw.slice(0, start).split(nl).map(s => s.trim()).filter(Boolean);"
        " const title = [...head].reverse().find(s => s.length >= 4 && !/^[0-9]{4}-/.test(s)) || '';"
        " const dm = raw.match(/([0-9]{4}-[0-9]{2}-[0-9]{2})/);"
        " const date = dm ? dm[1] : '';"
        " let body = raw.slice(start);"
        " for (const m of ['全部评论', '推荐视频', '发布时间']) {"
        "   const i = body.indexOf(m, 40);"
        "   if (i > 0) body = body.slice(0, i);"
        " }"
        " const slash = body.indexOf(nl + '00:');"
        " if (slash > 0) body = body.slice(0, slash);"
        " return {title, date, body: body.trim(), videoDur: v ? v.duration : null, videoSrc: src, hasVideo: !!v};"
        "})()"
    )
    res = _post({"action": "evaluate", "args": {"code": code}, "session": SESSION}, timeout=30)
    val = (res.get("data") or {}).get("value")
    return val if isinstance(val, dict) else {}


def _click_play_once() -> str:
    code = ("(() => { const v = document.querySelector('video');"
            " if (v) { try { const p = v.play(); if (p && p.catch) p.catch(() => {}); return v.paused ? 'paused-after-play' : 'playing'; } catch (e) { return 'blocked:' + e.message; } }"
            " const b = document.querySelector('.xgplayer-start, .xgplayer-is-start .xgplayer-start');"
            " if (b) { b.click(); return 'clicked-start-button'; }"
            " return 'no-video-element'; })()")
    res = _post({"action": "evaluate", "args": {"code": code}, "session": SESSION}, timeout=30)
    return str((res.get("data") or {}).get("value") or "")


def capture_douyin(share_url: str, settle_seconds: int = 10) -> dict:
    """Full Plan-B capture. Raises CaptureError on stop conditions.

    Order matters: open the tab FIRST (the daemon refuses session-wide
    commands before any tab exists), then start network capture and reload
    so both the detail API call and the media streams are recorded.
    """
    try:
        _navigate(share_url)
        time.sleep(settle_seconds)
        snap = _snapshot()
        final_url = snap.get("url") or ""
        if "v.douyin.com" in final_url:
            time.sleep(5)
            snap = _snapshot()
            final_url = snap.get("url") or ""
        m = re.search(r"/(?:video|note|article)/(\d+)", final_url)
        canonical = m.group(1) if m else ""

        texts = _tree_texts(snap.get("tree") or [])
        wall = _detect_wall(texts)
        if wall:
            raise CaptureError("user_verification_required",
                               f"page shows '{wall}' - finish it manually in Edge, then rerun acquire")

        # second pass WITH capture so nothing is missed.
        # CRITICAL: reload must BYPASS the HTTP disk cache. This tab often
        # visited the video before, and cache-served responses produce no
        # network entries and no readable response bodies.
        _start_network()
        try:
            res = _post({"action": "cdp",
                         "args": {"method": "Page.reload", "params": {"ignoreCache": True}},
                         "session": SESSION}, timeout=30)
            if not res.get("ok"):
                raise CaptureError("cdp_reload_failed", json.dumps(res)[:200])
        except CaptureError:
            # fallback: plain JS reload (may serve from cache)
            _post({"action": "evaluate",
                   "args": {"code": "location.reload(); 'reloading'"},
                   "session": SESSION}, timeout=30)
        time.sleep(6)

        # read the detail body EARLY - buffered responses expire quickly
        meta = _aweme_detail() or {}
        summary, chapters = _parse_chapters(texts)
        publish_page = _extract_publish(texts)

        meta.setdefault("id", canonical)
        meta.setdefault("title", "")
        meta["chapters"] = [{"start": c["start"], "title": c["title"]} for c in chapters]
        if not meta.get("published") and publish_page:
            meta["published"] = publish_page

        media_candidates = meta.pop("_media_candidates", [])
        media_url = media_candidates[0] if media_candidates else ""
        if not media_url:
            media_url = _scan_media_url()
        if not media_url:
            _click_play_once()
            time.sleep(8)
            media_url = _scan_media_url()

        article = {}
        if "/article/" in (final_url or ""):
            article = _extract_article_text()
            body = (article.get("body") or "").strip()
            if body and len(body) >= 80:
                if not meta.get("title"):
                    meta["title"] = (article.get("title") or body.splitlines()[0]).strip()[:80]
                if not meta.get("published") and article.get("date"):
                    meta["published"] = article["date"]
                if not meta.get("description"):
                    meta["description"] = body
            vsrc = article.get("videoSrc") or ""
            if not media_url and isinstance(vsrc, str) and vsrc.startswith("http"):
                media_url = vsrc

        return {
            "resolved_url": final_url or share_url,
            "canonical_id": canonical,
            "meta": meta,
            "media_url": media_url,
            "article_text": (article.get("body") or "").strip(),
            "evidence": {
                "chapter_summary": summary,
                "chapters_detail": chapters,
                "source_of_meta": "page-aweme-detail-response" if meta.get("uploader") else "page-snapshot",
                "article_chars": len((article.get("body") or "").strip()),
            },
        }
    finally:
        _stop_network()


def fetch_media(url: str, dest: Path, max_bytes: int = 800 * 1024 * 1024) -> Path:
    """One cookie-less fetch of the signed CDN URL the player itself loaded."""
    headers = {"User-Agent": USER_AGENT, "Referer": "https://www.douyin.com/"}
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    done = False
    try:
        with requests.get(url, headers=headers, stream=True, timeout=(15, 300)) as r:
            r.raise_for_status()
            written = 0
            with open(tmp, "wb") as fh:
                for chunk in r.iter_content(chunk_size=256 * 1024):
                    written += len(chunk)
                    if written > max_bytes:
                        raise CaptureError("file_too_large", "media exceeded size cap")
                    fh.write(chunk)
        done = True
    finally:
        if not done and tmp.exists():
            tmp.unlink(missing_ok=True)
    tmp.replace(dest)
    return dest