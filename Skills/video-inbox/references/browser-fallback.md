# Edge and Kimi WebBridge Fallback

Use this only after the native Windows acquisition manifest returns `needs-browser`, or when the user explicitly requests browser analysis.

## Preferred browser acquisition order

1. Open the public URL in a new task-specific Edge tab through `$kimi-webbridge`.
2. Inspect the accessibility snapshot for title, duration, transcript controls, and visible captions.
3. If necessary, inspect network requests for subtitle manifests or public media resources.
4. Capture a bounded number of screenshots only when visible information is essential.
5. Save structured evidence to `%LOCALAPPDATA%\video-inbox\browser-bridge\results\<task-id>.json`.
6. Validate the result with `video-inbox.ps1 validate-browser-result`.

Do not copy browser cookies, authorization headers, signed URLs, personal profile data, or unrelated page content into logs, notes, or prompts.

## Direct Kimi analysis

Use only when browser evidence acquisition is insufficient. Start a new Kimi conversation for each video and send only:

- public video URL
- original share text
- `references\kimi-prompt.md`

Do not send Vault notes, local paths, cookies, private context, or analyses of other videos.

## Result contract

```json
{
  "task_id": "...",
  "url": "...",
  "actual_content_access": true,
  "evidence_type": "visible-transcript|video-playback|screenshots|page-only|ai-only",
  "coverage": 0.0,
  "timestamps": [{"time": "00:10", "claim": "..."}],
  "explicit_content": ["..."],
  "inferences": ["..."],
  "unavailable": ["..."],
  "source": "kimi-webbridge"
}
```

## Stop conditions

Pause for the user rather than bypassing:

- login or account authorization
- CAPTCHA
- payment
- sensitive local-file upload
- a request to expose browser credentials

If Kimi is unavailable, retain a `needs-review` capture and queue only genuinely retryable technical failures.
