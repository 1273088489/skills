from __future__ import annotations

import argparse
import json
import re
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path

from .config import CACHE_DIR, DEFAULT_ASR_MODEL, INBOX, VAULT, ensure_dirs
from .identity import Identity, cache_key, identify
from .manifest import Attempt, Manifest

EXIT_OK = 0
EXIT_USAGE = 1
EXIT_ACCESS = 2
EXIT_ASR = 3


def _out(obj: dict) -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    print(json.dumps(obj, ensure_ascii=False))


def safe_title(title: str, limit: int = 42) -> str:
    t = re.sub(r'[\\/:*?"<>|]+', "", title or "").strip()
    return t[:limit] or "未命名"


def suggested_filename(title: str) -> str:
    today = datetime.now().strftime("%Y-%m-%d")
    return f"{today}-视频-{safe_title(title)}.md"


def find_existing_notes(ident: Identity) -> list[str]:
    if not INBOX.is_dir():
        return []
    needles = [n for n in {ident.canonical_id, ident.original_url, ident.resolved_url} if n]
    if not needles:
        return []
    hits: list[str] = []
    for p in sorted(INBOX.glob("*.md")):
        try:
            text = p.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        if any(n and n in text for n in needles):
            hits.append(p.name)
    return hits


def _apply_meta(m: Manifest, meta: dict, route: str) -> None:
    m.title = meta.get("title") or m.title
    m.uploader = meta.get("uploader") or m.uploader
    m.published = meta.get("published") or m.published
    m.duration = meta.get("duration") or m.duration
    m.description = meta.get("description") or m.description
    m.stats = meta.get("stats") or {}
    m.chapters = meta.get("chapters") or []
    m.provenance.metadata_route = route


def _set_transcript(m: Manifest, segs: list, source: str, lang: str, txt: Path, jsp: Path, quality: dict) -> None:
    m.transcript.source = source
    m.transcript.language = lang
    m.transcript.path = str(txt)
    m.transcript.segments_path = str(jsp)
    m.transcript.segment_count = len(segs)
    m.quality.span_coverage = quality.get("span_coverage")
    m.quality.talk_ratio = quality.get("talk_ratio")
    m.quality.max_repeat_run = quality.get("max_repeat_run")
    m.quality.suspect_terms = quality.get("suspect_terms", {})
    m.quality.flags = quality.get("flags", [])
    gates_pass = not any(f.startswith(("low_span", "high_rep")) for f in m.quality.flags)
    m.status = "complete" if gates_pass else "partial"
    m.evidence_grade = "high" if source == "official-subtitle" else "medium"


def _brief(m: Manifest) -> dict:
    return {
        "title": m.title, "uploader": m.uploader, "published": m.published,
        "duration": m.duration, "platform": m.platform, "canonical_id": m.canonical_id,
        "resolved_url": m.resolved_url, "stats": m.stats, "chapters": m.chapters,
        "description_head": (m.description or "")[:280],
        "status": m.status, "evidence_grade": m.evidence_grade,
        "provenance": m.provenance.__dict__,
        "quality": m.quality.__dict__,
        "transcript": m.transcript.__dict__,
        "failure_reason": m.failure_reason,
    }


def cmd_acquire(args) -> int:
    ensure_dirs()
    started = time.time()
    ident = identify(args.input)
    key = cache_key(ident)
    cache_dir = CACHE_DIR / key
    manifest_path = cache_dir / "manifest.json"

    existing_notes = [] if args.force else find_existing_notes(ident)
    prior = Manifest.load(manifest_path)
    if prior and prior.status in ("complete", "partial") and not args.force:
        _out({"ok": True, "result": "cache_hit", "cache_dir": str(cache_dir),
              "existing_notes": existing_notes, "summary": _brief(prior)})
        return EXIT_OK

    m = Manifest(task_id=(prior.task_id if prior else uuid.uuid4().hex[:12]))
    m.original_input = ident.original_input
    m.share_text = ident.share_text
    m.original_url = ident.original_url
    m.resolved_url = ident.resolved_url or ""
    m.platform = ident.platform
    m.canonical_id = ident.canonical_id
    m.platform_id = ident.platform_id
    m.cache_dir = str(cache_dir)

    meta: dict | None = None

    # ================= Douyin: Plan B - browser-only capture =================
    if m.platform == "douyin":
        try:
            from .capture import capture_douyin, fetch_media
            cap = capture_douyin(m.original_url)
        except Exception as exc:
            code = getattr(exc, "code", "capture_failed")
            detail = str(getattr(exc, "detail", "") or exc)
            m.add_attempt("browser", "edge-webbridge-page", "failed", error_code=code, detail=detail)
            m.failure_reason = code
            m.save(manifest_path)
            hints = {
                "daemon_unreachable": "start the Kimi WebBridge daemon and Edge, then rerun acquire",
                "user_verification_required": "finish the login/CAPTCHA manually in the Edge tab, then rerun acquire",
                "navigate_failed": "check the Edge tab/extension, then rerun acquire",
            }
            _out({"ok": False, "result": "capture_failed", "failure_reason": code,
                  "hint": hints.get(code, "see attempts"), "attempts": [a.__dict__ for a in m.attempts]})
            return EXIT_ACCESS

        m.resolved_url = cap["resolved_url"]
        m.canonical_id = cap["canonical_id"]
        m.platform_id = cap["canonical_id"]
        new_dir = CACHE_DIR / f"douyin_{m.canonical_id}" if m.canonical_id else cache_dir
        if new_dir != cache_dir:
            cache_dir = new_dir
            cache_dir.mkdir(parents=True, exist_ok=True)
            manifest_path = cache_dir / "manifest.json"
        m.cache_dir = str(cache_dir)
        _apply_meta(m, cap["meta"], "edge-webbridge-page")
        m.add_attempt("browser", "edge-webbridge-page", "success",
                      detail=f"canonical={m.canonical_id} evidence={cap['evidence']['source_of_meta']}")

        media_url = cap.get("media_url") or ""
        article_text = (cap.get("article_text") or "").strip()
        if article_text:
            ap = cache_dir / "article.txt"
            ap.write_text(article_text, encoding="utf-8")
            m.add_attempt("article", "edge-webbridge-page-text", "success",
                          detail=f"chars={len(article_text)}")
            # 图文页配视频几乎都是 BGM/演示画面，ASR 当证据会污染笔记。
            media_url = ""
        if not media_url:
            if article_text:
                m.failure_reason = "none"
                m.status = "complete"
                m.evidence_grade = "medium"
                m.save(manifest_path)
                _out({"ok": True, "result": "acquired_article", "elapsed_s": round(time.time() - started, 1),
                      "cache_dir": str(cache_dir), "existing_notes": existing_notes,
                      "article_path": str(cache_dir / "article.txt"),
                      "suggested_note_filename": suggested_filename(m.title),
                      "report": _brief(m),
                      "note_next": "agent summarizes from article.txt and writes the Inbox note itself"})
                return EXIT_OK
            article_page = "/article/" in (m.resolved_url or "")
            m.failure_reason = "unsupported_article" if article_page else "no_media_stream"
            m.status = "needs-review"
            m.evidence_grade = "unverified"
            m.save(manifest_path)
            _out({"ok": True,
                  "result": "unsupported_article" if article_page else "page_only_needs_review",
                  "cache_dir": str(cache_dir),
                  "existing_notes": existing_notes, "report": _brief(m),
                  "note_next": "article page with no media" if article_page else "page evidence only; agent may write a lightweight note"})
            return EXIT_OK

        audio_file = cache_dir / "audio.m4a"
        try:
            fetch_media(media_url, audio_file)
            m.provenance.audio_route = "webbridge-signed-url(no-cookie)"
            m.add_attempt("audio", "edge-webbridge-media-url", "success",
                          detail=f"file={audio_file.name} bytes={audio_file.stat().st_size}")
        except Exception as exc:
            m.add_attempt("audio", "edge-webbridge-media-url", "failed", error_code="download_failed", detail=str(exc))
            m.failure_reason = "download_failed"
            m.status = "needs-review"
            m.evidence_grade = "unverified"
            m.save(manifest_path)
            _out({"ok": False, "result": "audio_failed", "failure_reason": "download_failed", "meta": _brief(m)})
            return EXIT_ACCESS

    # ================= Other platforms: public yt-dlp fast path =================
    else:
        try:
            from .probe import probe_metadata
            meta, route, atts = probe_metadata(m.resolved_url or m.original_url, m.platform)
            for a in atts:
                m.attempts.append(Attempt(stage=a.get("stage"), route=a.get("route"), status=a.get("status"),
                                          error_code=a.get("error_code"), detail=(a.get("detail") or "")[-400:] or None))
            _apply_meta(m, meta, route)
        except Exception as exc:
            code = getattr(exc, "code", "probe_failed")
            for a in getattr(exc, "attempts", []):
                m.attempts.append(Attempt(stage=a.get("stage"), route=a.get("route"), status=a.get("status"),
                                          error_code=a.get("error_code"), detail=(a.get("detail") or "")[-400:] or None))
            m.add_attempt("metadata", "yt-dlp-ladder", "failed", error_code=code, detail=str(exc))
            m.failure_reason = code
            m.save(manifest_path)
            _out({"ok": False, "result": "metadata_failed", "failure_reason": code,
                  "hint": "public extraction failed; use Stage-2 browser capture then finalize",
                  "attempts": [a.__dict__ for a in m.attempts]})
            return EXIT_ACCESS

    # ================= subtitles =================
    segs: list | None = None
    if meta:
        from .content import fetch_subtitles
        sub_segs, sub_source, sub_lang = fetch_subtitles(meta, cache_dir)
        if sub_segs:
            segs = sub_segs
            m.provenance.subtitles_route = sub_source
            from .asr import assess_quality, persist
            q = assess_quality(sub_segs, m.duration, sub_lang)
            txt, jsp = persist(sub_segs, cache_dir)
            _set_transcript(m, sub_segs, sub_source, sub_lang, txt, jsp, q)

    # ================= audio download (non-douyin only) =================
    audio_file: Path | None = None
    if not segs and m.platform != "douyin":
        try:
            from .content import download_audio
            out_base = cache_dir / "audio"
            audio_file = download_audio(meta.get("webpage_url") or m.resolved_url or m.original_url, out_base)
            m.provenance.audio_route = "yt-dlp:" + audio_file.suffix.lower().lstrip(".")
            m.add_attempt("audio", "yt-dlp-bestaudio", "success",
                          detail=f"file={audio_file.name} bytes={audio_file.stat().st_size}")
        except Exception as exc:
            code = getattr(exc, "code", "download_failed")
            m.add_attempt("audio", "yt-dlp-bestaudio", "failed", error_code=code, detail=str(exc))
            m.failure_reason = code
            m.status = "needs-review"
            m.evidence_grade = "unverified"
            m.save(manifest_path)
            _out({"ok": False, "result": "audio_failed", "failure_reason": code, "meta": _brief(m),
                  "hint": "run Stage-2 browser capture, save structured JSON, then finalize"})
            return EXIT_ACCESS

    # ================= ASR =================
    if not segs:
        target_audio = audio_file if audio_file is not None else (cache_dir / "audio.m4a")
        try:
            from .asr import assess_quality, persist, transcribe
            t0 = time.time()
            segs, info = transcribe(target_audio, args.asr_model)
            q = assess_quality(segs, info.get("duration") or m.duration, info.get("language", ""))
            txt, jsp = persist(segs, cache_dir)
            m.provenance.asr_model = args.asr_model
            _set_transcript(m, segs, "asr", info.get("language", ""), txt, jsp, q)
            m.add_attempt("asr", f"faster-whisper:{args.asr_model}", "success",
                          detail=f"segments={len(segs)} elapsed={time.time()-t0:.0f}s lang={info.get('language')}")
        except Exception as exc:
            m.add_attempt("asr", f"faster-whisper:{args.asr_model}", "failed", detail=str(exc))
            m.failure_reason = "asr_failed"
            m.status = "needs-review"
            m.save(manifest_path)
            _out({"ok": False, "result": "asr_failed", "detail": str(exc)[-400:], "meta": _brief(m)})
            return EXIT_ASR

    m.failure_reason = "none"
    m.save(manifest_path)
    _out({"ok": True, "result": "acquired", "elapsed_s": round(time.time() - started, 1),
          "cache_dir": str(cache_dir), "existing_notes": existing_notes,
          "suggested_note_filename": suggested_filename(m.title),
          "transcript_path": m.transcript.path, "report": _brief(m),
          "note_next": "agent summarizes from transcript and writes the Inbox note itself"})
    return EXIT_OK


def cmd_transcribe(args) -> int:
    ensure_dirs()
    audio = Path(args.audio).expanduser()
    if not audio.is_file():
        _out({"ok": False, "result": "audio_not_found", "path": str(audio)})
        return EXIT_USAGE
    cache_dir = Path(args.cache_dir).expanduser() if args.cache_dir else CACHE_DIR / ("manual_" + re.sub(r"\W+", "_", audio.stem)[:40])
    cache_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = Path(args.manifest).expanduser() if args.manifest else cache_dir / "manifest.json"
    m = Manifest.load(manifest_path) or Manifest()
    m.cache_dir = str(cache_dir)
    if not m.original_url and args.url:
        m.original_url = args.url
    from .asr import assess_quality, persist, transcribe
    t0 = time.time()
    segs, info = transcribe(audio, args.asr_model)
    q = assess_quality(segs, info.get("duration"), info.get("language", ""))
    txt, jsp = persist(segs, cache_dir)
    m.provenance.asr_model = args.asr_model
    m.duration = m.duration or info.get("duration")
    _set_transcript(m, segs, "asr", info.get("language", ""), txt, jsp, q)
    m.failure_reason = "none"
    m.add_attempt("asr", f"faster-whisper:{args.asr_model}", "success",
                  detail=f"segments={len(segs)} elapsed={time.time()-t0:.0f}s")
    m.save(manifest_path)
    _out({"ok": True, "result": "transcribed", "cache_dir": str(cache_dir),
          "transcript_path": str(txt), "report": _brief(m)})
    return EXIT_OK


def cmd_finalize(args) -> int:
    ensure_dirs()
    br_path = Path(args.browser_result).expanduser()
    if not br_path.is_file():
        _out({"ok": False, "result": "browser_result_not_found", "path": str(br_path)})
        return EXIT_USAGE
    data = json.loads(br_path.read_text(encoding="utf-8"))
    target = None
    if args.manifest:
        target = Manifest.load(Path(args.manifest).expanduser())
    elif args.url:
        from .identity import canonical_from_url, detect_platform, resolve_url
        resolved, _ = resolve_url(args.url)
        plat = detect_platform(resolved or args.url)
        cid, _ = canonical_from_url(resolved or args.url, plat)
        target = Manifest.load(CACHE_DIR / f"{plat}_{cid}" / "manifest.json")
    if target is None:
        _out({"ok": False, "result": "manifest_not_found", "hint": "pass --manifest explicitly"})
        return EXIT_USAGE
    cache_dir = Path(target.cache_dir) if target.cache_dir else CACHE_DIR / f"{target.platform}_{target.canonical_id}"
    merged_path = cache_dir / "browser_result.json"
    merged_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    target.add_attempt("browser", str(data.get("source", "kimi-webbridge")), "success",
                       detail=f"evidence_type={data.get('evidence_type')} saved={merged_path}")
    if target.transcript.source == "none":
        target.status = "needs-review"
        target.evidence_grade = "unverified"
    target.failure_reason = "none"
    target.save(cache_dir / "manifest.json")
    _out({"ok": True, "result": "finalized", "browser_result": str(merged_path), "report": _brief(target)})
    return EXIT_OK


def cmd_doctor(_args) -> int:
    ensure_dirs()
    checks: dict = {}
    checks["python"] = sys.version.split()[0]
    try:
        import yt_dlp
        checks["yt_dlp"] = yt_dlp.version.__version__
    except Exception as e:
        checks["yt_dlp"] = f"missing ({e})"
    try:
        import faster_whisper
        checks["faster_whisper"] = getattr(faster_whisper, "__version__", "installed")
    except Exception as e:
        checks["faster_whisper"] = f"missing ({e})"
    snaps = list((CACHE_DIR.parent / "models").glob("models--Systran--faster-whisper-small/snapshots/*"))
    checks["asr_model_cached"] = bool(snaps)
    checks["vault_exists"] = VAULT.is_dir()
    checks["inbox_exists"] = INBOX.is_dir()
    checks["douyin_route"] = "browser-only(Plan B); cookie reuse disabled by policy"
    try:
        import requests as rq
        for name, url in (("bilibili", "https://www.bilibili.com/"), ("youtube", "https://www.youtube.com/")):
            try:
                r = rq.head(url, timeout=6, allow_redirects=True)
                checks["net_" + name] = r.status_code
            except Exception:
                checks["net_" + name] = "unreachable"
    except Exception:
        pass
    _out({"ok": True, "checks": checks})
    return EXIT_OK


def cmd_dedupe(args) -> int:
    ensure_dirs()
    ident = identify(args.input)
    hits = find_existing_notes(ident)
    _out({"ok": True, "canonical_id": ident.canonical_id, "matches": hits})
    return EXIT_OK


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="video_inbox_v2", description="WSL-native video inbox pipeline")
    sub = p.add_subparsers(dest="cmd", required=True)

    acq = sub.add_parser("acquire", help="resolve -> metadata/capture -> subtitles/audio -> ASR -> manifest")
    acq.add_argument("input", help="URL or full share text")
    acq.add_argument("--force", action="store_true", help="ignore cache and rerun")
    acq.add_argument("--asr-model", default=DEFAULT_ASR_MODEL, choices=["tiny", "base", "small", "medium"])
    acq.set_defaults(func=cmd_acquire)

    tr = sub.add_parser("transcribe", help="ASR for a local audio/video file")
    tr.add_argument("--audio", required=True)
    tr.add_argument("--cache-dir")
    tr.add_argument("--manifest")
    tr.add_argument("--url", default="")
    tr.add_argument("--asr-model", default=DEFAULT_ASR_MODEL, choices=["tiny", "base", "small", "medium"])
    tr.set_defaults(func=cmd_transcribe)

    fin = sub.add_parser("finalize", help="merge a browser-result JSON into an existing manifest")
    fin.add_argument("--browser-result", required=True)
    fin.add_argument("--manifest")
    fin.add_argument("--url")
    fin.set_defaults(func=cmd_finalize)

    doc = sub.add_parser("doctor", help="environment health check")
    doc.set_defaults(func=cmd_doctor)

    de = sub.add_parser("dedupe", help="check whether this video already has an Inbox note")
    de.add_argument("input")
    de.set_defaults(func=cmd_dedupe)

    args = p.parse_args(argv)
    try:
        return args.func(args)
    except ValueError as e:
        _out({"ok": False, "result": "bad_input", "detail": str(e)})
        return EXIT_USAGE
