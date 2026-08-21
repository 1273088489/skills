from __future__ import annotations

import json
import re
import shutil
import uuid
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .config import RuntimePaths, tool_map
from .models import Attempt, Manifest, TranscriptSegment
from .runner import CommandError, command_version, run_command, write_json
from .subtitles import calculate_coverage, parse_subtitle, write_transcript
from .urls import VideoIdentity, identify

RETRYABLE = {"network_timeout", "rate_limited", "extractor_outdated", "media_unavailable", "asr_failed"}
VISUAL_CUE_RE = re.compile(
    r"(?:看这里|看一下|屏幕|画面|图中|这张图|这个图|如下图|左边|右边|点击|界面|参数|代码|表格|设置|演示|see here|screen|on screen|shown here|click|chart|table|code)",
    re.IGNORECASE,
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def classify_error(text: str) -> str:
    lowered = text.lower()
    if "captcha" in lowered:
        return "captcha_required"
    if "sign in" in lowered or "login" in lowered or "cookies" in lowered or "authentication" in lowered:
        return "login_required"
    if "rate limit" in lowered or "too many requests" in lowered or "http error 429" in lowered:
        return "rate_limited"
    if "geo" in lowered or "not available in your country" in lowered:
        return "geo_restricted"
    if "unsupported url" in lowered or "no suitable extractor" in lowered:
        return "unsupported_url"
    if "timed out" in lowered or "timeout" in lowered or "connection" in lowered:
        return "network_timeout"
    if "signature" in lowered or "nsig" in lowered or "extractor" in lowered:
        return "extractor_outdated"
    if "private" in lowered or "members-only" in lowered or "payment" in lowered:
        return "access_restricted"
    return "media_unavailable"


def item_directory(paths: RuntimePaths, identity: VideoIdentity) -> Path:
    return paths.cache / identity.platform / identity.cache_key


def manifest_path(paths: RuntimePaths, identity: VideoIdentity) -> Path:
    return item_directory(paths, identity) / "manifest.json"


def load_manifest(path: Path) -> Manifest | None:
    if not path.is_file():
        return None
    try:
        return Manifest.from_dict(json.loads(path.read_text(encoding="utf-8")))
    except (OSError, ValueError, TypeError):
        return None


def add_attempt(manifest: Manifest, stage: str, route: str, status: str, **kwargs: Any) -> Attempt:
    attempt = Attempt(stage=stage, route=route, status=status, finished_at=utc_now(), **kwargs)
    manifest.attempts.append(attempt)
    manifest.acquisition_chain.append(f"{route}:{status}")
    return attempt


def ytdlp_args(paths: RuntimePaths, yt_dlp: Path, url: str, *, timeout: int = 45) -> list[str]:
    args = [
        str(yt_dlp),
        "--ignore-config",
        "--no-playlist",
        "--no-warnings",
        "--socket-timeout",
        str(min(timeout, 30)),
        "--retries",
        "2",
        "--fragment-retries",
        "2",
        "--extractor-retries",
        "2",
    ]
    deno = tool_map(paths).get("deno")
    if deno:
        args += ["--js-runtimes", f"deno:{deno}"]
    return args + [url]


def probe_metadata(paths: RuntimePaths, manifest: Manifest, url: str, yt_dlp: Path) -> dict[str, Any] | None:
    args = ytdlp_args(paths, yt_dlp, url)[:-1] + ["--dump-single-json", "--skip-download", url]
    try:
        result = run_command(args, timeout=60)
        metadata = json.loads(result.stdout)
    except (CommandError, json.JSONDecodeError) as exc:
        output = getattr(exc, "result", None)
        details = ((output.stderr if output else "") + "\n" + (output.stdout if output else "")) if output else str(exc)
        code = classify_error(details)
        add_attempt(manifest, "metadata", "yt-dlp", "failed", error_code=code, limitation=details[-1000:])
        manifest.failure_reason = code
        return None

    add_attempt(manifest, "metadata", "yt-dlp", "success", details={"duration_seconds": result.duration_seconds})
    manifest.title = str(metadata.get("title") or manifest.title)
    manifest.uploader = str(metadata.get("uploader") or metadata.get("channel") or manifest.uploader)
    manifest.published = str(metadata.get("upload_date") or metadata.get("release_date") or manifest.published)
    manifest.description = str(metadata.get("description") or manifest.description)
    manifest.duration = float(metadata["duration"]) if metadata.get("duration") is not None else manifest.duration
    manifest.resolved_url = str(metadata.get("webpage_url") or metadata.get("original_url") or url)
    resolved_identity = identify(manifest.resolved_url)
    if resolved_identity.platform == manifest.platform and resolved_identity.canonical_id:
        manifest.canonical_id = resolved_identity.canonical_id
    return metadata


def subtitle_candidates(metadata: dict[str, Any]) -> list[tuple[str, str, bool]]:
    candidates: list[tuple[str, str, bool]] = []
    manual = metadata.get("subtitles") or {}
    automatic = metadata.get("automatic_captions") or {}

    def sort_languages(source: dict[str, Any]) -> list[str]:
        def language_rank(language: str) -> int:
            lowered = language.lower()
            if lowered.startswith("zh"):
                return 0
            if lowered.startswith("en"):
                return 1
            return 2

        return sorted(source, key=lambda language: (language_rank(language), language))

    for language in sort_languages(manual):
        if manual.get(language):
            candidates.append((language, "official-subtitle", False))
    for language in sort_languages(automatic):
        if automatic.get(language):
            candidates.append((language, "automatic-subtitle", True))
    return candidates


def fetch_subtitle(paths: RuntimePaths, manifest: Manifest, metadata: dict[str, Any], yt_dlp: Path, cache_dir: Path) -> list[TranscriptSegment] | None:
    candidates = subtitle_candidates(metadata)
    if not candidates:
        add_attempt(manifest, "subtitle", "subtitle-inventory", "skipped", error_code="subtitle_unavailable")
        return None

    subtitle_dir = cache_dir / "subtitles"
    subtitle_dir.mkdir(parents=True, exist_ok=True)
    for language, source, automatic in candidates:
        for existing in subtitle_dir.glob(f"*{language}*.*"):
            try:
                segments = parse_subtitle(existing)
                if segments:
                    return _persist_transcript(manifest, segments, source, language, cache_dir)
            except Exception:
                pass

        output = subtitle_dir / "subtitle.%(ext)s"
        args = ytdlp_args(paths, yt_dlp, manifest.resolved_url or manifest.original_url)[:-1]
        args += ["--skip-download", "--sub-langs", language, "--sub-format", "vtt/best", "--force-overwrites"]
        args += ["--write-auto-subs" if automatic else "--write-subs", "--output", str(output), manifest.resolved_url or manifest.original_url]
        try:
            result = run_command(args, timeout=90)
            files = sorted(subtitle_dir.glob("subtitle.*"), key=lambda item: item.stat().st_mtime, reverse=True)
            for file in files:
                segments = parse_subtitle(file)
                if segments:
                    add_attempt(manifest, "subtitle", source, "success", details={"language": language, "duration_seconds": result.duration_seconds})
                    return _persist_transcript(manifest, segments, source, language, cache_dir)
            add_attempt(manifest, "subtitle", source, "failed", error_code="subtitle_empty", limitation="subtitle file had no usable cues")
        except CommandError as exc:
            code = classify_error(exc.result.stderr)
            add_attempt(manifest, "subtitle", source, "failed", error_code=code, limitation=exc.result.stderr[-1000:])
    return None


def _persist_transcript(manifest: Manifest, segments: list[TranscriptSegment], source: str, language: str, cache_dir: Path) -> list[TranscriptSegment]:
    text_path = cache_dir / "transcript.txt"
    json_path = cache_dir / "transcript.segments.json"
    write_transcript(segments, text_path, json_path)
    manifest.transcript_source = source
    manifest.transcript_language = language
    manifest.transcript_coverage = calculate_coverage(segments, manifest.duration)
    manifest.transcript_path = str(text_path)
    manifest.transcript_segments_path = str(json_path)
    manifest.acquisition_method = "yt-dlp"
    return segments


def download_audio(paths: RuntimePaths, manifest: Manifest, yt_dlp: Path, cache_dir: Path) -> Path | None:
    temp_dir = paths.temp / manifest.task_id
    temp_dir.mkdir(parents=True, exist_ok=True)
    template = temp_dir / "audio.%(ext)s"
    args = ytdlp_args(paths, yt_dlp, manifest.resolved_url or manifest.original_url)[:-1]
    args += [
        "--format",
        "bestaudio/best",
        "--max-filesize",
        "500M",
        "--output",
        str(template),
        manifest.resolved_url or manifest.original_url,
    ]
    try:
        result = run_command(args, timeout=300)
    except CommandError as exc:
        code = classify_error(exc.result.stderr)
        add_attempt(manifest, "audio", "yt-dlp-audio", "failed", error_code=code, limitation=exc.result.stderr[-1000:])
        manifest.failure_reason = code
        return None
    candidates = [path for path in temp_dir.glob("audio.*") if path.suffix.lower() not in {".part", ".ytdl"}]
    if not candidates:
        add_attempt(manifest, "audio", "yt-dlp-audio", "failed", error_code="media_unavailable", limitation="yt-dlp reported success without output")
        return None
    audio_path = max(candidates, key=lambda item: item.stat().st_size)
    add_attempt(manifest, "audio", "yt-dlp-audio", "success", details={"file": audio_path.name, "bytes": audio_path.stat().st_size, "duration_seconds": result.duration_seconds})
    return audio_path


def transcribe_audio(paths: RuntimePaths, manifest: Manifest, audio_path: Path, cache_dir: Path, model_name: str = "small") -> list[TranscriptSegment] | None:
    try:
        from faster_whisper import WhisperModel  # type: ignore
    except ImportError:
        add_attempt(manifest, "asr", "faster-whisper", "skipped", error_code="asr_not_installed")
        return None

    try:
        model = WhisperModel(model_name, device="cpu", compute_type="int8", download_root=str(paths.models))
        segments_iter, info = model.transcribe(str(audio_path), vad_filter=True, beam_size=5)
        segments = [TranscriptSegment(float(item.start), float(item.end), item.text.strip()) for item in segments_iter if item.text.strip()]
    except Exception as exc:
        add_attempt(manifest, "asr", "faster-whisper", "failed", error_code="asr_failed", limitation=str(exc)[-1000:])
        manifest.failure_reason = "asr_failed"
        return None

    if not segments:
        add_attempt(manifest, "asr", "faster-whisper", "failed", error_code="asr_empty")
        return None
    language = getattr(info, "language", "") or ""
    add_attempt(manifest, "asr", "faster-whisper", "success", details={"model": model_name, "language": language, "segments": len(segments)})
    _persist_transcript(manifest, segments, "asr", language, cache_dir)
    manifest.acquisition_method = "yt-dlp-audio"
    return segments


def needs_visual_review(segments: list[TranscriptSegment]) -> bool:
    return any(VISUAL_CUE_RE.search(segment.text) for segment in segments)


def is_partial_download(name: str) -> bool:
    lowered = name.lower()
    return lowered.endswith(".part") or lowered.endswith(".ytdl") or ".part-" in lowered


def cleanup_task_temp(paths: RuntimePaths, manifest: Manifest) -> None:
    """自动清理当前任务的临时目录：空目录或只剩半成品（.part/.ytdl）时删除。"""
    temp_dir = paths.temp / manifest.task_id
    if not temp_dir.is_dir():
        return
    files = list(temp_dir.rglob("*"))
    if not files:
        try:
            shutil.rmtree(temp_dir)
        except OSError:
            pass
    elif all(item.is_file() and is_partial_download(item.name) for item in files):
        try:
            shutil.rmtree(temp_dir)
        except OSError:
            pass


def queue_retry(paths: RuntimePaths, manifest: Manifest) -> None:
    if manifest.failure_reason not in RETRYABLE:
        return
    path = paths.state / "retry-queue.json"
    try:
        queue = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else []
    except ValueError:
        queue = []
    if any(item.get("task_id") == manifest.task_id for item in queue):
        return
    queue.append(
        {
            "task_id": manifest.task_id,
            "url": manifest.resolved_url or manifest.original_url,
            "platform": manifest.platform,
            "reason": manifest.failure_reason,
            "attempts": 0,
            "next_retry_at": (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat(),
            "manifest_path": str(manifest_path(paths, identify(manifest.original_url))),
        }
    )
    write_json(path, queue)
    manifest.retry_status = "queued"


def write_browser_request(paths: RuntimePaths, manifest: Manifest) -> Path:
    path = paths.browser_requests / f"{manifest.task_id}.json"
    write_json(
        path,
        {
            "task_id": manifest.task_id,
            "url": manifest.resolved_url or manifest.original_url,
            "platform": manifest.platform,
            "canonical_id": manifest.canonical_id,
            "failure_reason": manifest.failure_reason,
            "requested_content": ["resolved_url", "metadata", "subtitle", "duration", "media_or_frame_evidence"],
            "created_at": utc_now(),
        },
    )
    manifest.browser_request_path = str(path)
    return path


def finalise_status(manifest: Manifest, segments: list[TranscriptSegment] | None) -> None:
    if segments:
        coverage = manifest.transcript_coverage
        manifest.evidence_grade = "high" if manifest.transcript_source == "official-subtitle" else "medium"
        manifest.analysis_status = "complete" if coverage is None or coverage >= 0.85 else "partial"
        manifest.visual_required = needs_visual_review(segments)
        return
    if manifest.failure_reason in {"login_required", "captcha_required", "access_restricted", "unsupported_url", "geo_restricted"}:
        manifest.analysis_status = "needs-review"
        manifest.evidence_grade = "unverified"
    else:
        manifest.analysis_status = "needs-review"
        manifest.evidence_grade = "unverified"


def acquire(paths: RuntimePaths, input_text: str, url: str, *, force: bool = False, asr_model: str = "small", keep_temp: bool = False) -> tuple[Manifest, Path]:
    paths.ensure()
    identity = identify(url)
    cache_dir = item_directory(paths, identity)
    cache_dir.mkdir(parents=True, exist_ok=True)
    saved_path = manifest_path(paths, identity)
    existing = load_manifest(saved_path)
    if existing and existing.analysis_status in {"complete", "partial"} and not force:
        existing.cache_hit = True
        existing.acquisition_chain.append("cache:hit")
        existing.save(saved_path)
        return existing, saved_path

    manifest = existing or Manifest(
        task_id=str(uuid.uuid4()),
        original_input=input_text,
        original_url=url,
        resolved_url=url,
        platform=identity.platform,
        canonical_id=identity.canonical_id,
    )
    manifest.cache_hit = False
    tools = tool_map(paths)
    manifest.tool_versions = {name: command_version(path) for name, path in tools.items()}
    yt_dlp = tools.get("yt-dlp")
    if not yt_dlp:
        add_attempt(manifest, "metadata", "yt-dlp", "skipped", error_code="tool_missing", limitation="yt-dlp was not found")
        manifest.failure_reason = "tool_missing"
        finalise_status(manifest, None)
        manifest.save(saved_path)
        return manifest, saved_path

    metadata = probe_metadata(paths, manifest, url, yt_dlp)
    segments: list[TranscriptSegment] | None = None
    if metadata:
        segments = fetch_subtitle(paths, manifest, metadata, yt_dlp, cache_dir)
    if not segments:
        audio = download_audio(paths, manifest, yt_dlp, cache_dir)
        if audio:
            segments = transcribe_audio(paths, manifest, audio, cache_dir, asr_model)
            if segments and not keep_temp:
                try:
                    shutil.rmtree(audio.parent)
                except OSError:
                    pass
    finalise_status(manifest, segments)
    if not segments:
        if manifest.failure_reason in {"login_required", "captcha_required", "access_restricted", "unsupported_url", "geo_restricted", "media_unavailable"}:
            write_browser_request(paths, manifest)
        queue_retry(paths, manifest)
    cleanup_task_temp(paths, manifest)
    manifest.save(saved_path)
    return manifest, saved_path
