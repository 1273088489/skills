from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class RuntimePaths:
    home: Path
    bin: Path
    cache: Path
    models: Path
    temp: Path
    logs: Path
    state: Path
    browser_requests: Path
    browser_results: Path
    vault: Path
    inbox: Path

    @classmethod
    def discover(cls) -> "RuntimePaths":
        local = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
        home = Path(os.environ.get("VIDEO_INBOX_HOME", local / "video-inbox"))
        vault = Path(os.environ.get("VIDEO_INBOX_VAULT", r"D:\Open-brain-obsidian"))
        return cls(
            home=home,
            bin=home / "bin",
            cache=home / "cache",
            models=home / "models",
            temp=home / "temp",
            logs=home / "logs",
            state=home / "state",
            browser_requests=home / "browser-bridge" / "requests",
            browser_results=home / "browser-bridge" / "results",
            vault=vault,
            inbox=vault / "00_Inbox",
        )

    def ensure(self) -> None:
        for path in (
            self.home,
            self.bin,
            self.cache,
            self.models,
            self.temp,
            self.logs,
            self.state,
            self.browser_requests,
            self.browser_results,
        ):
            path.mkdir(parents=True, exist_ok=True)


def discover_tool(name: str, paths: RuntimePaths, env_name: str | None = None) -> Path | None:
    env_name = env_name or f"VIDEO_INBOX_{name.upper().replace('-', '_')}"
    explicit = os.environ.get(env_name)
    if explicit and Path(explicit).is_file():
        return Path(explicit)

    candidates = [paths.bin / name]
    if not name.lower().endswith(".exe"):
        candidates.insert(0, paths.bin / f"{name}.exe")
    for candidate in candidates:
        if candidate.is_file():
            return candidate

    located = shutil.which(name) or shutil.which(f"{name}.exe")
    return Path(located) if located else None


def tool_map(paths: RuntimePaths) -> dict[str, Path | None]:
    return {
        "yt-dlp": discover_tool("yt-dlp", paths, "VIDEO_INBOX_YTDLP"),
        "ffmpeg": discover_tool("ffmpeg", paths, "VIDEO_INBOX_FFMPEG"),
        "ffprobe": discover_tool("ffprobe", paths, "VIDEO_INBOX_FFPROBE"),
        "deno": discover_tool("deno", paths, "VIDEO_INBOX_DENO"),
    }
