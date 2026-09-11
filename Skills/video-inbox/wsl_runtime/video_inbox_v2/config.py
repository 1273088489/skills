from __future__ import annotations

import os
from pathlib import Path

WSL_RUNTIME_DIR = Path(__file__).resolve().parents[1]
SKILL_DIR = WSL_RUNTIME_DIR.parent
CACHE_DIR = WSL_RUNTIME_DIR / "cache"
MODELS_DIR = WSL_RUNTIME_DIR / "models"
TEMP_DIR = WSL_RUNTIME_DIR / "temp"

VAULT = Path(os.environ.get("VIDEO_INBOX_VAULT", "/mnt/d/Open-brain-obsidian"))
INBOX = VAULT / "00_Inbox"

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)

DEFAULT_ASR_MODEL = "small"

# Flag-only glossary: ASR mishear candidates for creator-economy jargon.
# Never auto-replace; surfaced in reports so the summarizing agent can correct.
SUSPECT_TERMS = {
    "艺人公司": "一人公司(疑似)",
    "牧强": "慕强(疑似)",
    "坦单": "谈单(疑似)",
    "假方": "甲方(疑似)",
    "懒危": "蓝V(疑似)",
    "必还": "闭环(疑似)",
    "磕掺": "磕碜(疑似)",
}


def ensure_dirs() -> None:
    for p in (CACHE_DIR, MODELS_DIR, TEMP_DIR):
        p.mkdir(parents=True, exist_ok=True)
