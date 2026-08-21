from __future__ import annotations

import json
from pathlib import Path

from .acquire import item_directory, load_manifest
from .chapters import write_chunks
from .config import RuntimePaths, tool_map
from .models import Manifest, TranscriptSegment
from .urls import identify
from .visual import download_preview, extract_frames, plan_frames, save_frame_plan


def _load_segments(manifest: Manifest) -> list[TranscriptSegment]:
    if not manifest.transcript_segments_path:
        return []
    path = Path(manifest.transcript_segments_path)
    if not path.is_file():
        return []
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    return [TranscriptSegment(float(item["start"]), float(item["end"]), str(item["text"])) for item in raw if item.get("text")]


def enrich(
    paths: RuntimePaths,
    manifest_path: Path,
    *,
    max_frames: int = 6,
    chunk_minutes: float = 10.0,
    force_visual: bool = False,
    keep_preview: bool = False,
) -> Manifest:
    manifest = load_manifest(manifest_path)
    if manifest is None:
        raise FileNotFoundError(f"manifest 不存在：{manifest_path}")

    segments = _load_segments(manifest)
    cache_dir = item_directory(paths, identify(manifest.original_url))
    if segments:
        _, chunk_dir = write_chunks(segments, cache_dir, chunk_minutes)
        manifest.chunks_path = str(chunk_dir / "chunks.json")

    if segments and (manifest.visual_required or force_visual):
        plan = plan_frames(segments, manifest.duration, max_frames)
        save_frame_plan(paths, manifest, plan, cache_dir)
        tools = tool_map(paths)
        yt_dlp, ffmpeg = tools.get("yt-dlp"), tools.get("ffmpeg")
        if yt_dlp and ffmpeg:
            preview = download_preview(paths, manifest, yt_dlp)
            if preview:
                frame_paths = extract_frames(paths, manifest, preview, plan, ffmpeg)
                manifest.frame_paths = [str(path) for path in frame_paths]
                if not keep_preview:
                    try:
                        import shutil

                        shutil.rmtree(preview.parent)
                    except OSError:
                        pass

    manifest.save(manifest_path)
    return manifest
