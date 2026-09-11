from __future__ import annotations

import json
from pathlib import Path

from .config import MODELS_DIR, SUSPECT_TERMS

_model_cache: dict = {}


def get_model(name: str):
    from faster_whisper import WhisperModel

    if name not in _model_cache:
        _model_cache[name] = WhisperModel(name, device="cpu", compute_type="int8", download_root=str(MODELS_DIR))
    return _model_cache[name]


def transcribe(audio_path: Path, model_name: str = "small") -> tuple[list[dict], dict]:
    """Returns (segments, info). Segments: [{start,end,text}]."""
    model = get_model(model_name)
    iter_, info = model.transcribe(str(audio_path), vad_filter=True, beam_size=5)
    segments = [
        {"start": float(s.start), "end": float(s.end), "text": s.text.strip()}
        for s in iter_
        if s.text and s.text.strip()
    ]
    return segments, {"language": getattr(info, "language", "") or "", "duration": float(getattr(info, "duration", 0) or 0)}


def assess_quality(segments: list[dict], duration: float | None, language: str = "") -> dict:
    q: dict = {"span_coverage": None, "talk_ratio": None, "max_repeat_run": None, "flags": [], "suspect_terms": {}}
    if not segments:
        q["flags"].append("empty_transcript")
        return q
    span = (segments[-1]["end"] - segments[0]["start"]) if duration else None
    if span is not None and duration:
        q["span_coverage"] = round(min(span / duration, 1.0), 3)
        q["talk_ratio"] = round(min(sum(s["end"] - s["start"] for s in segments) / duration, 1.0), 3)
    run = best = 1
    for prev, cur in zip(segments, segments[1:]):
        run = run + 1 if cur["text"] == prev["text"] else 1
        best = max(best, run)
    q["max_repeat_run"] = best
    full_text = "".join(s["text"] for s in segments)
    suspects = {k: full_text.count(k) for k in SUSPECT_TERMS if full_text.count(k) > 0}
    q["suspect_terms"] = {k: {"count": v, "likely": SUSPECT_TERMS[k]} for k, v in suspects.items()}
    if duration and q["span_coverage"] is not None and q["span_coverage"] < 0.6:
        q["flags"].append("low_span_coverage(<0.6)")
    if best >= 5:
        q["flags"].append(f"high_repetition(run={best}, possible hallucination)")
    if language.startswith("zh") and full_text and not any("\u4e00" <= ch <= "\u9fff" for ch in full_text):
        q["flags"].append("expected_cjk_but_none_found")
    return q


def persist(segments: list[dict], cache_dir: Path) -> tuple[Path, Path]:
    txt_path = cache_dir / "transcript.txt"
    json_path = cache_dir / "transcript.segments.json"

    def fmt(sec: float) -> str:
        sec = int(round(sec))
        return f"{sec // 60:02d}:{sec % 60:02d}"

    lines = [f"[{fmt(s['start'])}-{fmt(s['end'])}] {s['text']}" for s in segments]
    txt_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    json_path.write_text(json.dumps(segments, ensure_ascii=False), encoding="utf-8")
    return txt_path, json_path
