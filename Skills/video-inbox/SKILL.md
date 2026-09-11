---
name: video-inbox
description: Capture public YouTube, Bilibili, Douyin (video/note/article) links as evidence-aware Obsidian Inbox notes. Use when the user shares a video URL/share message, asks to analyze or save a video to Obsidian, requests subtitle or ASR extraction, or explicitly invokes $video-inbox. Process in WSL; write only the final Markdown note to the Windows vault. Automatically create a new Inbox note unless the user says not to save, the link is only an example, or an existing note would be overwritten.
---

# Video Inbox

Turn public video/article links into evidence-aware Obsidian notes.

Work in WSL. Download, probe, ASR, and cache stay on the Linux filesystem. The only Windows write is the Inbox Markdown file.

## Layout

- Skill: `~/.dsh/skills/video-inbox`
- Runtime: `~/.dsh/skills/video-inbox/wsl_runtime` (venv + `video_inbox_v2`)
- Cache: `~/.dsh/skills/video-inbox/wsl_runtime/cache`
- Vault: `/mnt/d/Open-brain-obsidian` (`D:\Open-brain-obsidian`)
- Inbox: `/mnt/d/Open-brain-obsidian/00_Inbox`

The vault is the directory that contains both `AGENTS.md` and `.obsidian/`. Never ingest into a newly created empty vault. Never treat `D:\Obsidian` (app install) as the vault.

## Commands

From `wsl_runtime`:

```bash
.venv/bin/python -m video_inbox_v2 doctor
.venv/bin/python -m video_inbox_v2 acquire '<url-or-share-text>'
```

If `.venv` is missing (fresh clone — it is not versioned, being 451 MB), rebuild it
from [references/wsl-runtime-bootstrap.md](references/wsl-runtime-bootstrap.md):
three top-level packages (`faster-whisper`, `yt-dlp`, `static-ffmpeg`) plus the ASR
model, which downloads itself on first use. That document also records the
DSH-injected `NO_PROXY=[::1]` that breaks httpx inside the harness (fixed in
`config.py`).

Read the JSON report, then summarize from `transcript.txt` or `article.txt`. The CLI does not write Obsidian notes.

## Routing

### Public platforms (YouTube, Bilibili, others)

yt-dlp, no cookies: metadata → creator/auto subtitles → audio ASR (faster-whisper in WSL).

### Douyin — Plan B (default)

Browser-only. WSL never contacts Douyin (not even short-link redirects). Cookie export and session-jar reuse (Plan C) are disabled.

1. Open the share URL in the user's Edge via Kimi WebBridge (session `video-inbox-douyin`).
2. Read the resolved URL. Canonical ID from `/video/`, `/note/`, or `/article/`.
3. Reload with cache bypass; read the `aweme/detail` body **the page itself fetched** (do not call Douyin APIs).
4. **Video/note:** take `play_addr`, one cookie-less CDN download (Referer + UA only), then WSL ASR.
5. **Article (`/article/`):** read visible page body into `article.txt`. That is the evidence. **Do not ASR the embedded clip** — it is usually BGM or a silent demo.
6. CAPTCHA/login/slider: stop for a human. No retry loops. No cookie export.

If daemon/extension is down: start WebBridge, ensure Edge is running, rerun acquire.

### Stage 3 — visual enrichment

Only when essential information is on screen, the clip is silent/visual, or the user asks. Bounded frames + `deepseek-vision`. Prefer platform chapters.

## Evidence order

1. Douyin article page body (`article.txt`)
2. Creator subtitles
3. Platform automatic subtitles
4. Audio ASR (not for Douyin `/article/` BGM)
5. Inspected frames/OCR
6. Browser page/video evidence
7. Share text / metadata only (including Tavily)

Titles, comments, covers, and AI summaries do not replace actual content.

## Status

- `complete`: real body or transcript covers the main argument
- `partial`: some real content, coverage incomplete
- `needs-review`: metadata/share text only, or human action required

Keep `acquisition_method`, `transcript_source`, `analysis_method`, `analysis_status` separate.

## Note

Template: `assets/video-inbox-note.md`.

- Filename: `YYYY-MM-DD-视频-简短标题.md`
- Capture date in `created`; confirmed publish date in `published`, else `待确认`
- Tags: exactly `type/video` and `status/待处理`, plus at most three topic tags
- Write only to `00_Inbox`. Do not ingest, move, or edit Wiki without confirmation
- Do not overwrite an existing note; ask first
- Do not dump the full transcript into the note; keep it in runtime cache
- Failed acquisition: do **not** write a hollow note unless the user asks. Say it failed.

Separate in the note: `视频明确展示或表达的内容` / `AI 分析与推断` / `辅助验证` / `待验证问题`.

## Report

- created/existing file path
- original/resolved URL and canonical ID
- platform, duration, acquisition chain
- subtitle/ASR **or** article-text source and coverage
- browser usage and reason
- confirmation that no Wiki ingest occurred
