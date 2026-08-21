# Windows Runtime

## Layout

Resolve the runtime root as `%VIDEO_INBOX_HOME%` when set, otherwise `%LOCALAPPDATA%\video-inbox`.

```text
%LOCALAPPDATA%\video-inbox\
├── bin\          # portable yt-dlp, ffmpeg, ffprobe, deno when used
├── cache\        # metadata, subtitles, transcripts, manifests
├── models\       # local ASR models
├── temp\         # disposable audio/video and extracted frames
├── logs\         # redacted attempt logs
├── state\        # retry queue and locks
└── browser-bridge\
    ├── requests\
    └── results\
```

Keep dependencies and generated media out of the skill folder. Keep the skill folder source-only.

## Tool discovery

Search in this order:

1. explicit environment variable (`VIDEO_INBOX_YTDLP`, `VIDEO_INBOX_FFMPEG`, etc.)
2. `%VIDEO_INBOX_HOME%\bin`
3. Windows `PATH`

Never call WSL, Bash, `/mnt/*`, or Linux executables.

## Vision bridge (Stage 3)

Frame OCR uses the `deepseek-vision` skill at `%USERPROFILE%\.codex\skills\deepseek-vision` through `node`; it calls an external vision model (default `glm-4.6v-flash`) and requires the `ZHIPU_API_KEY` environment variable (optional: `VISION_MODEL`, `VISION_BASE_URL`). Configure it once with `node "%USERPROFILE%\.codex\skills\deepseek-vision\scripts\vision.js" --setup`. If it is unconfigured, record frames as unavailable instead of fabricating OCR.

## Process rules

- Pass subprocess arguments as arrays; do not construct shell command strings from URLs.
- Use UTF-8 for stdout, stderr, JSON, subtitles, and notes.
- Add timeouts and terminate the child process tree on timeout.
- Redact cookies, authorization headers, signed media query strings, and browser profile data from logs.
- Record executable versions in each manifest.
- Do not update tools during a normal capture. Update explicitly, preserve the previous binary, and test `doctor` afterward.

## Temporary data

- Do not download full-resolution video unless Stage 3 visual evidence requires it.
- Delete temporary audio after successful transcription.
- Keep failed audio only while a retry is pending; the `cleanup` command removes stale temp media beyond its TTL.
- `acquire` auto-deletes its own empty or partial-only temp dir after every run (failed runs included).
- Run `scripts\video-inbox.ps1 cleanup` (dry-run by default) to sweep invalid files; add `--apply` to delete, and `--ttl <days>` to set the age threshold (default 7).
- Keep metadata, normalized transcript, manifest, and short frame plan in cache.
- Never place raw cookies, full transcripts, audio, or temporary video in the Obsidian Vault by default.

## ASR default

Use `faster-whisper` on CPU with `int8` as the first local backend. Start with a multilingual `small` model and allow configuration through environment variables. Do not make CUDA a Stage 1 requirement on the current MX350 2 GB system.
