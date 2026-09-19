#!/usr/bin/env python3
"""Check v3 evidence structure and arithmetic using file bytes, never image content.

Counts describe unique, structurally valid evidence rows, not verified visual reads.
Percentages use every indexed sample as the denominator and are null on errors.
An uncertain category contributes to unknown_count and the possible upper bound.
video_sha256 is checked for format only: the index supplies no source-video path.
"""

import argparse
import hashlib
import json
import math
from pathlib import Path
import re


CATEGORIES = (
    "product", "ingredient", "use_detail", "environment", "person",
    "ui", "text", "black", "uncertain",
)
CLOSE_UP_CATEGORIES = ("product", "ingredient", "use_detail")
PLACEHOLDER = re.compile(
    r"^(?:同上|同前|延续|据范式|沿用(?:上|前)|与(?:上|前)一帧相同"
    r"|same\s+as\s+(?:above|previous)\b|ditto\b|todo\b|tbd\b|待补充)",
    re.IGNORECASE,
)


def nonempty_text(value):
    return isinstance(value, str) and bool(value.strip())


def finite_number(value):
    return type(value) is int or (type(value) is float and math.isfinite(value))


def valid_sha256(value):
    return isinstance(value, str) and re.fullmatch(r"[0-9a-fA-F]{64}", value) is not None


def file_sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def check_evidence(sample_dir, evidence_path):
    sample_dir = Path(sample_dir)
    errors = []
    counts = dict.fromkeys(CATEGORIES, 0)
    result = {
        "structure_pass": False,
        "errors": errors,
        "sample_frame_count": 0,
        "reviewed_frame_count": 0,
        "category_counts": counts,
        "close_up_count": 0,
        "unknown_count": 0,
        "close_up_ratio": None,
        "lower_bound": None,
        "upper_bound": None,
        "not_visual_verification": True,
    }

    def asset_path(value, label):
        if not nonempty_text(value):
            errors.append(f"{label}: expected a nonempty file path")
            return None
        path = sample_dir / value
        try:
            if path.is_file():
                return path.resolve()
        except (OSError, ValueError, RuntimeError) as exc:
            errors.append(f"{label}: {exc}")
            return None
        errors.append(f"{label}: file does not exist or is not a file: {path}")
        return None

    try:
        index = json.loads((sample_dir / "frame_index.json").read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        errors.append(f"frame_index.json: {exc}")
        return result
    if not isinstance(index, dict):
        errors.append("frame_index.json: expected an object")
        return result
    if not nonempty_text(index.get("video_id")):
        errors.append("frame_index.json: video_id must be nonempty text")
    duration = index.get("duration_s")
    duration_valid = finite_number(duration) and duration > 0
    if not duration_valid:
        errors.append("frame_index.json: duration_s must be a positive finite number")
    if not valid_sha256(index.get("video_sha256")):
        errors.append("frame_index.json: video_sha256 must contain 64 hexadecimal characters")
    frames = index.get("frames")
    if not isinstance(frames, list) or not frames:
        errors.append("frame_index.json: frames must be a nonempty list")
        return result

    result["sample_frame_count"] = len(frames)
    indexed = {}
    previous_source_index = None
    previous_timestamp = None
    for position, frame in enumerate(frames, 1):
        label = f"frame_index.json frames[{position}]"
        if not isinstance(frame, dict):
            errors.append(f"{label}: expected an object")
            continue
        frame_id = frame.get("frame_id")
        if not nonempty_text(frame_id):
            errors.append(f"{label}: frame_id must be nonempty text")
        elif frame_id in indexed:
            errors.append(f"{label}: duplicate frame_id {frame_id!r}")
        else:
            indexed[frame_id] = frame
        source_index = frame.get("source_frame_index")
        if type(source_index) is not int or source_index < 0:
            errors.append(f"{label}: source_frame_index must be a nonnegative integer")
        else:
            if previous_source_index is not None and source_index <= previous_source_index:
                errors.append(f"{label}: source_frame_index must be strictly increasing")
            previous_source_index = source_index
        timestamp = frame.get("timestamp_s")
        if not finite_number(timestamp) or timestamp < 0:
            errors.append(f"{label}: timestamp_s must be a nonnegative finite number")
        else:
            if previous_timestamp is not None and timestamp <= previous_timestamp:
                errors.append(f"{label}: timestamp_s must be strictly increasing")
            previous_timestamp = timestamp
            if duration_valid and timestamp > duration:
                errors.append(f"{label}: timestamp_s exceeds duration_s")
        path = asset_path(frame.get("file"), f"{label} file")
        expected_hash = frame.get("sha256")
        if not valid_sha256(expected_hash):
            errors.append(f"{label}: sha256 must contain 64 hexadecimal characters")
        elif path is not None:
            try:
                if file_sha256(path) != expected_hash.lower():
                    errors.append(f"{label}: SHA256 mismatch for {path}")
            except OSError as exc:
                errors.append(f"{label}: cannot hash {path}: {exc}")

    try:
        lines = Path(evidence_path).read_text(encoding="utf-8").splitlines()
    except (OSError, ValueError) as exc:
        errors.append(f"frames.jsonl: {exc}")
        lines = []
    seen = set()
    for line_number, line in enumerate(lines, 1):
        label = f"frames.jsonl line {line_number}"
        error_count = len(errors)
        try:
            row = json.loads(line)
        except ValueError as exc:
            errors.append(f"{label}: invalid JSON: {exc}")
            continue
        if not isinstance(row, dict):
            errors.append(f"{label}: expected an object")
            continue
        frame_id = row.get("frame_id")
        expected = None
        if not nonempty_text(frame_id):
            errors.append(f"{label}: frame_id must be nonempty text")
        else:
            if frame_id in seen:
                errors.append(f"{label}: duplicate frame_id {frame_id!r}")
            seen.add(frame_id)
            expected = indexed.get(frame_id)
            if expected is None:
                errors.append(f"{label}: unindexed frame_id {frame_id!r}")
        timestamp = row.get("timestamp_s")
        if not finite_number(timestamp) or timestamp < 0:
            errors.append(f"{label}: timestamp_s must be a nonnegative finite number")
        elif expected is not None and timestamp != expected.get("timestamp_s"):
            errors.append(f"{label}: timestamp_s mismatch for {frame_id!r}")
        read_method = row.get("read_method")
        if read_method not in ("single_frame", "contact_sheet"):
            errors.append(f"{label}: read_method must be single_frame or contact_sheet")
        read_asset = asset_path(row.get("read_asset"), f"{label} read_asset")
        if expected is not None:
            target_field = None
            if read_method == "single_frame":
                target_field = "file"
            elif read_method == "contact_sheet" and "board" in expected:
                target_field = "board"
            if target_field is not None:
                target = asset_path(expected.get(target_field), f"{label} indexed {target_field}")
                if read_asset is not None and target is not None and read_asset != target:
                    errors.append(f"{label}: read_asset must resolve to indexed {target_field}")
        observation = row.get("observation")
        if isinstance(observation, str):
            observation = re.sub(r"^[\W_]+", "", observation)
        if not nonempty_text(observation) or PLACEHOLDER.match(observation):
            errors.append(f"{label}: observation must be nonempty and not a placeholder")
        category = row.get("category")
        if category not in CATEGORIES:
            errors.append(f"{label}: category must be one of {', '.join(CATEGORIES)}")
        close_up = row.get("close_up")
        if type(close_up) is not bool:
            errors.append(f"{label}: close_up must be a JSON boolean")
        elif close_up and category not in CLOSE_UP_CATEGORIES:
            errors.append(f"{label}: close_up=true requires product, ingredient or use_detail")
        for field in ("visible_text", "uncertainty"):
            if not isinstance(row.get(field), str):
                errors.append(f"{label}: {field} must be text (empty is allowed)")
        if len(errors) == error_count:
            result["reviewed_frame_count"] += 1
            counts[category] += 1
            result["close_up_count"] += int(close_up)
    for frame_id in sorted(indexed.keys() - seen):
        errors.append(f"frames.jsonl: missing frame_id {frame_id!r}")

    result["unknown_count"] = counts["uncertain"]
    result["structure_pass"] = not errors
    if not errors:
        total = len(frames)
        close_count = result["close_up_count"]
        unknown_count = result["unknown_count"]
        result["lower_bound"] = round(100 * close_count / total, 1)
        result["upper_bound"] = round(100 * (close_count + unknown_count) / total, 1)
        if not unknown_count:
            result["close_up_ratio"] = result["lower_bound"]
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("sample_dir", type=Path)
    parser.add_argument("frames_jsonl", type=Path)
    args = parser.parse_args()
    result = check_evidence(args.sample_dir, args.frames_jsonl)
    print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
    return 0 if result["structure_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
