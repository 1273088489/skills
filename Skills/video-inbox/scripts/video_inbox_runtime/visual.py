from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .acquire import VISUAL_CUE_RE, ytdlp_args
from .config import RuntimePaths
from .models import Manifest, TranscriptSegment
from .runner import CommandError, run_command, write_json


@dataclass
class FramePlanItem:
    time: float
    reason: str
    cue_text: str = ""
    path: str = ""

    def to_dict(self) -> dict:
        return {
            "time": self.time,
            "reason": self.reason,
            "cue_text": self.cue_text[:300],
            "path": self.path,
        }


def plan_frames(segments: list[TranscriptSegment], duration: float | None = None, max_frames: int = 6) -> list[FramePlanItem]:
    max_frames = max(1, min(int(max_frames), 20))
    cues = [segment for segment in segments if VISUAL_CUE_RE.search(segment.text)]
    if cues:
        times = sorted({round(segment.start, 2) for segment in cues})
    else:
        end = duration if duration and duration > 0 else max((s.end for s in segments), default=0)
        times = [round(index * end / (max_frames + 1), 2) for index in range(1, max_frames + 1)]

    plan: list[FramePlanItem] = []
    for time_value in times[:max_frames]:
        near = next((s for s in segments if abs(s.start - time_value) < 1.5), None)
        if near and VISUAL_CUE_RE.search(near.text):
            plan.append(FramePlanItem(time_value, "visual-cue", near.text))
        else:
            plan.append(FramePlanItem(time_value, "coverage", near.text if near else ""))
    return plan


def save_frame_plan(paths: RuntimePaths, manifest: Manifest, plan: list[FramePlanItem], cache_dir: Path) -> Path:
    path = cache_dir / "frame-plan.json"
    write_json(path, {"task_id": manifest.task_id, "frames": [item.to_dict() for item in plan]})
    manifest.frame_plan_path = str(path)
    return path


def download_preview(paths: RuntimePaths, manifest: Manifest, yt_dlp: Path, max_bytes: int = 300_000_000) -> Path | None:
    temp_dir = paths.temp / manifest.task_id
    temp_dir.mkdir(parents=True, exist_ok=True)
    template = temp_dir / "preview.%(ext)s"
    args = ytdlp_args(paths, yt_dlp, manifest.resolved_url or manifest.original_url)[:-1]
    args += [
        "--format",
        "best[height<=480]/bestvideo[height<=480]+bestaudio/best",
        "--max-filesize",
        str(max_bytes),
        "--output",
        str(template),
        manifest.resolved_url or manifest.original_url,
    ]
    try:
        run_command(args, timeout=300)
    except CommandError:
        return None
    candidates = [path for path in temp_dir.glob("preview.*") if path.suffix.lower() not in {".part", ".ytdl"}]
    return max(candidates, key=lambda item: item.stat().st_size) if candidates else None


def extract_frames(paths: RuntimePaths, manifest: Manifest, video_path: Path, plan: list[FramePlanItem], ffmpeg: Path) -> list[Path]:
    frames_dir = paths.temp / manifest.task_id / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)
    extracted: list[Path] = []
    for index, item in enumerate(plan):
        output = frames_dir / f"frame_{index + 1:02d}_{item.time:.1f}s.png"
        try:
            run_command(
                [
                    str(ffmpeg),
                    "-y",
                    "-ss",
                    f"{item.time:.2f}",
                    "-i",
                    str(video_path),
                    "-frames:v",
                    "1",
                    "-vf",
                    "scale=-2:480",
                    str(output),
                ],
                timeout=90,
            )
            if output.is_file():
                item.path = str(output)
                extracted.append(output)
        except CommandError:
            continue
    return extracted
