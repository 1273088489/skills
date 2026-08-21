# Platform Routing

## Shared fast path

1. Normalize and resolve the URL.
2. Identify a canonical platform ID.
3. Check cache.
4. Probe metadata and subtitle inventory with bounded retries.
5. Fetch creator subtitles when available.
6. Fetch automatic subtitles when creator subtitles are unavailable.
7. Validate transcript coverage.
8. Download temporary audio and run ASR only when needed.
9. Return `needs-browser` when access depends on the user's active Edge session.

## YouTube

- Prefer creator subtitles, then automatic captions.
- Use an external JavaScript runtime when required by the extractor.
- Do not use browser cookies by default.
- If public extraction fails because login/session is required, enter Stage 2 rather than repeatedly changing extractor arguments.
- Download audio only; do not fetch the normal video format for ASR.

## Bilibili

- Preserve `bvid`/`avid`, `cid`, and page/part number when available.
- Treat each multi-part page as a separate content unit unless the user asks for the whole collection.
- Prefer a usable platform subtitle track, with yt-dlp as the generic extractor.
- Danmaku is optional context and never a substitute for transcript or video evidence.

## Douyin

- Preserve the original share text and short URL.
- Follow public redirects and derive the canonical work ID when possible.
- Attempt public metadata/media extraction once with bounded retry.
- Move to Stage 2 when the public page requires login, CAPTCHA, a signed browser session, or interactive playback.
- Do not use third-party download sites as a normal route.

## Other platforms

Use the generic extractor. If unsupported, classify the failure and enter Stage 2. Do not broaden into general web research for the video's substance.
