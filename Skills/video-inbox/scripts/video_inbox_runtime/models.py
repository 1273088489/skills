from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class Attempt:
    stage: str
    route: str
    status: str
    started_at: str = field(default_factory=utc_now)
    finished_at: str | None = None
    duration_seconds: float | None = None
    error_code: str | None = None
    limitation: str | None = None
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class TranscriptSegment:
    start: float
    end: float
    text: str


@dataclass
class Manifest:
    schema_version: int = 2
    task_id: str = ""
    original_input: str = ""
    original_url: str = ""
    resolved_url: str = ""
    platform: str = "other"
    canonical_id: str = ""
    title: str = ""
    uploader: str = ""
    published: str = ""
    duration: float | None = None
    description: str = ""
    acquisition_method: str = "none"
    acquisition_chain: list[str] = field(default_factory=list)
    transcript_source: str = "none"
    transcript_language: str = ""
    transcript_coverage: float | None = None
    transcript_path: str = ""
    transcript_segments_path: str = ""
    evidence_grade: str = "unverified"
    analysis_status: str = "needs-review"
    visual_required: bool = False
    frame_plan_path: str = ""
    frame_paths: list[str] = field(default_factory=list)
    chunks_path: str = ""
    browser_request_path: str = ""
    retry_status: str = "none"
    failure_reason: str = "none"
    cache_hit: bool = False
    tool_versions: dict[str, str] = field(default_factory=dict)
    attempts: list[Attempt] = field(default_factory=list)
    created_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["attempts"] = [asdict(item) for item in self.attempts]
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Manifest":
        copied = dict(data)
        copied["attempts"] = [Attempt(**item) for item in copied.get("attempts", [])]
        allowed = cls.__dataclass_fields__.keys()
        return cls(**{key: value for key, value in copied.items() if key in allowed})

    def save(self, path: Path) -> None:
        import json

        self.updated_at = utc_now()
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(json.dumps(self.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(path)
