from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path

from .models import TranscriptSegment
from .runner import write_json


@dataclass
class Chunk:
    index: int
    start: float
    end: float
    text: str
    segment_count: int


def build_chunks(segments: list[TranscriptSegment], max_minutes: float = 10.0, max_chars: int = 12000) -> list[Chunk]:
    chunks: list[Chunk] = []
    current: list[TranscriptSegment] = []
    start = 0.0
    char_count = 0
    for segment in segments:
        if current and ((segment.end - start) > max_minutes * 60 or char_count + len(segment.text) > max_chars):
            chunks.append(_make_chunk(len(chunks), current))
            current = []
            char_count = 0
        if not current:
            start = segment.start
        current.append(segment)
        char_count += len(segment.text)
    if current:
        chunks.append(_make_chunk(len(chunks), current))
    return chunks


def _make_chunk(index: int, segments: list[TranscriptSegment]) -> Chunk:
    return Chunk(
        index=index,
        start=segments[0].start,
        end=segments[-1].end,
        text="\n".join(segment.text for segment in segments),
        segment_count=len(segments),
    )


def write_chunks(segments: list[TranscriptSegment], cache_dir: Path, max_minutes: float = 10.0, max_chars: int = 12000) -> tuple[list[Chunk], Path]:
    chunks = build_chunks(segments, max_minutes, max_chars)
    chunk_dir = cache_dir / "chunks"
    chunk_dir.mkdir(parents=True, exist_ok=True)
    for chunk in chunks:
        (chunk_dir / f"chunk_{chunk.index + 1:02d}.txt").write_text(chunk.text, encoding="utf-8")
    write_json(chunk_dir / "chunks.json", [asdict(chunk) for chunk in chunks])
    return chunks, chunk_dir
