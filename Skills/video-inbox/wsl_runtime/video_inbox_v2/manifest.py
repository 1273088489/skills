from __future__ import annotations

import json
import os
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_task_id() -> str:
    return str(uuid.uuid4())


@dataclass
class Attempt:
    stage: str
    route: str
    status: str
    started_at: str = field(default_factory=utc_now)
    finished_at: str | None = None
    error_code: str | None = None
    detail: str | None = None


@dataclass
class Quality:
    span_coverage: float | None = None
    talk_ratio: float | None = None
    max_repeat_run: int | None = None
    suspect_terms: dict = field(default_factory=dict)
    flags: list[str] = field(default_factory=list)


@dataclass
class TranscriptInfo:
    source: str = "none"  # official-subtitle | auto-subtitle | asr | browser | none
    language: str = ""
    path: str = ""
    segments_path: str = ""
    segment_count: int = 0


@dataclass
class Provenance:
    metadata_route: str = "none"
    subtitles_route: str = "none"
    audio_route: str = "none"
    asr_model: str = ""


@dataclass
class Manifest:
    schema_version: int = 3
    task_id: str = field(default_factory=new_task_id)
    created_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)
    original_input: str = ""
    share_text: str = ""
    original_url: str = ""
    resolved_url: str = ""
    platform: str = "other"
    platform_id: str = ""
    canonical_id: str = ""
    cache_dir: str = ""
    title: str = ""
    uploader: str = ""
    published: str = ""
    duration: float | None = None
    description: str = ""
    stats: dict = field(default_factory=dict)
    chapters: list = field(default_factory=list)
    provenance: Provenance = field(default_factory=Provenance)
    transcript: TranscriptInfo = field(default_factory=TranscriptInfo)
    quality: Quality = field(default_factory=Quality)
    status: str = "needs-review"       # complete | partial | needs-review
    evidence_grade: str = "unverified"  # high | medium | unverified
    failure_reason: str = "none"
    attempts: list[Attempt] = field(default_factory=list)

    def add_attempt(self, stage: str, route: str, status: str, error_code: str | None = None, detail: str | None = None) -> None:
        self.attempts.append(Attempt(stage=stage, route=route, status=status, error_code=error_code, detail=(detail or "")[-800:] or None))

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Manifest":
        allowed = set(cls.__dataclass_fields__)
        copied = {k: v for k, v in data.items() if k in allowed}
        obj = cls(**copied)
        obj.provenance = Provenance(**{k: v for k, v in (data.get("provenance") or {}).items()})
        obj.transcript = TranscriptInfo(**{k: v for k, v in (data.get("transcript") or {}).items()})
        obj.quality = Quality(**{k: v for k, v in (data.get("quality") or {}).items()})
        obj.attempts = [Attempt(**a) for a in data.get("attempts", [])]
        return obj

    def save(self, path) -> None:
        self.updated_at = utc_now()
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(self.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, path)

    @staticmethod
    def load(path):
        p = Path(path)
        if not p.is_file():
            return None
        try:
            return Manifest.from_dict(json.loads(p.read_text(encoding="utf-8")))
        except Exception:
            return None
