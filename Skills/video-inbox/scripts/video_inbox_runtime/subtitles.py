from __future__ import annotations

import html
import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path

from .models import TranscriptSegment

TIMESTAMP_RE = re.compile(
    r"(?P<h1>\d{1,2}):(?P<m1>\d{2}):(?P<s1>\d{2}[\.,]\d{3})\s*-->\s*"
    r"(?P<h2>\d{1,2}):(?P<m2>\d{2}):(?P<s2>\d{2}[\.,]\d{3})"
)
SHORT_TIMESTAMP_RE = re.compile(
    r"(?P<m1>\d{1,2}):(?P<s1>\d{2}[\.,]\d{3})\s*-->\s*"
    r"(?P<m2>\d{1,2}):(?P<s2>\d{2}[\.,]\d{3})"
)
TAG_RE = re.compile(r"<[^>]+>")


def _seconds(hours: str, minutes: str, seconds: str) -> float:
    return int(hours) * 3600 + int(minutes) * 60 + float(seconds.replace(",", "."))


def clean_text(value: str) -> str:
    value = TAG_RE.sub("", html.unescape(value))
    value = re.sub(r"\s+", " ", value).strip()
    return value


def parse_vtt_srt(text: str) -> list[TranscriptSegment]:
    lines = text.replace("\r\n", "\n").split("\n")
    segments: list[TranscriptSegment] = []
    index = 0
    while index < len(lines):
        line = lines[index].strip()
        match = TIMESTAMP_RE.search(line) or SHORT_TIMESTAMP_RE.search(line)
        if not match:
            index += 1
            continue
        groups = match.groupdict()
        if groups.get("h1") is None:
            start = _seconds("0", groups["m1"], groups["s1"])
            end = _seconds("0", groups["m2"], groups["s2"])
        else:
            start = _seconds(groups["h1"], groups["m1"], groups["s1"])
            end = _seconds(groups["h2"], groups["m2"], groups["s2"])
        index += 1
        body: list[str] = []
        while index < len(lines) and lines[index].strip():
            candidate = clean_text(lines[index])
            if candidate and not candidate.isdigit():
                body.append(candidate)
            index += 1
        combined = clean_text(" ".join(body))
        if combined and (not segments or combined != segments[-1].text):
            segments.append(TranscriptSegment(start, end, combined))
        index += 1
    return segments


def parse_json3(text: str) -> list[TranscriptSegment]:
    data = json.loads(text)
    segments: list[TranscriptSegment] = []
    for event in data.get("events", []):
        pieces = event.get("segs") or []
        body = clean_text("".join(piece.get("utf8", "") for piece in pieces))
        if not body:
            continue
        start = float(event.get("tStartMs", 0)) / 1000
        end = start + float(event.get("dDurationMs", 0)) / 1000
        if not segments or body != segments[-1].text:
            segments.append(TranscriptSegment(start, end, body))
    return segments


def parse_ttml(text: str) -> list[TranscriptSegment]:
    root = ET.fromstring(text)
    segments: list[TranscriptSegment] = []

    def parse_time(value: str) -> float:
        if value.endswith("s"):
            return float(value[:-1])
        parts = value.replace(",", ".").split(":")
        if len(parts) == 3:
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
        return 0.0

    for element in root.iter():
        if element.tag.rsplit("}", 1)[-1] != "p":
            continue
        body = clean_text("".join(element.itertext()))
        if not body:
            continue
        start = parse_time(element.attrib.get("begin", "0s"))
        end = parse_time(element.attrib.get("end", element.attrib.get("dur", "0s")))
        if "dur" in element.attrib and "end" not in element.attrib:
            end = start + parse_time(element.attrib["dur"])
        segments.append(TranscriptSegment(start, end, body))
    return segments


def parse_subtitle(path: Path) -> list[TranscriptSegment]:
    text = path.read_text(encoding="utf-8-sig", errors="replace")
    suffix = path.suffix.lower()
    if suffix in {".vtt", ".srt"}:
        return parse_vtt_srt(text)
    if suffix in {".json", ".json3"}:
        return parse_json3(text)
    if suffix in {".ttml", ".xml", ".srv3"}:
        return parse_ttml(text)
    return parse_vtt_srt(text)


def write_transcript(segments: list[TranscriptSegment], text_path: Path, json_path: Path) -> None:
    text_path.write_text("\n".join(item.text for item in segments), encoding="utf-8")
    json_path.write_text(
        json.dumps([item.__dict__ for item in segments], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def calculate_coverage(segments: list[TranscriptSegment], duration: float | None) -> float | None:
    if not segments or not duration or duration <= 0:
        return None
    end = max(item.end for item in segments)
    return round(min(1.0, max(0.0, end / duration)), 4)
