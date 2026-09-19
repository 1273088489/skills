"""Offline regression check: python3 -B -m unittest discover -s <this directory>."""

import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from check_ad_evidence import check_evidence


class EvidenceCheckTest(unittest.TestCase):
    def test_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            sample_dir = Path(directory)
            evidence_path = sample_dir / "frames.jsonl"
            index = {
                "video_id": "synthetic-test",
                "duration_s": 100.0,
                "video_sha256": hashlib.sha256(b"synthetic video").hexdigest(),
                "frames": [],
            }
            rows = []
            categories = (
                ["product"] * 60 + ["ingredient"] * 5 + ["use_detail"] * 5
                + ["ui"] * 12 + ["environment"] * 5 + ["person"] * 4
                + ["text"] * 4 + ["black"] * 5
            )
            # Synthetic bytes deliberately need no image decoder or network.
            for number, category in enumerate(categories):
                frame_id = f"u{number + 1:03}"
                path = sample_dir / f"{frame_id}.bin"
                # Equal frame bytes are allowed when source indices differ.
                data = f"synthetic frame {number // 2}".encode()
                path.write_bytes(data)
                index["frames"].append({
                    "frame_id": frame_id, "source_frame_index": number * 30,
                    "timestamp_s": float(number), "file": path.name,
                    "sha256": hashlib.sha256(data).hexdigest(),
                })
                rows.append({
                    "frame_id": frame_id, "timestamp_s": float(number),
                    "read_method": "single_frame", "read_asset": path.name,
                    "observation": f"测试观察 {number}：中央有一个矩形。",
                    "category": category, "close_up": number < 70,
                    "visible_text": "", "uncertainty": "",
                })
            board = sample_dir / "board.bin"
            board.write_bytes(b"synthetic contact sheet")
            board_alias = sample_dir / "board-alias.bin"
            board_alias.symlink_to(board.name)
            index["frames"][0]["board"] = board.name
            rows[0].update(read_method="contact_sheet", read_asset=str(board_alias))
            rows[1]["read_asset"] = str(sample_dir / "u002.bin")
            # Legacy contact sheets without an indexed board remain valid.
            rows[2].update(read_method="contact_sheet", read_asset=board.name)
            frame_alias = sample_dir / "frame-alias.bin"
            frame_alias.symlink_to("u004.bin")
            rows[3]["read_asset"] = frame_alias.name

            def run(changed_rows=None, changed_index=None):
                (sample_dir / "frame_index.json").write_text(
                    json.dumps(index if changed_index is None else changed_index),
                    encoding="utf-8",
                )
                evidence_path.write_text("".join(
                    json.dumps(row, ensure_ascii=False) + "\n"
                    for row in (rows if changed_rows is None else changed_rows)
                ), encoding="utf-8")
                return check_evidence(sample_dir, evidence_path)

            result = run()
            self.assertTrue(result["structure_pass"], result["errors"])
            self.assertEqual(result["reviewed_frame_count"], 100)
            self.assertEqual(result["category_counts"]["ui"], 12)
            self.assertEqual(sum(result["category_counts"].values()), 100)
            self.assertEqual(result["close_up_count"], 70)
            self.assertEqual(result["close_up_ratio"], 70.0)
            self.assertEqual((result["lower_bound"], result["upper_bound"]), (70.0, 70.0))
            self.assertEqual(result["unknown_count"], 0)
            self.assertIs(result["not_visual_verification"], True)

            command = [sys.executable, "-B", str(Path(__file__).with_name(
                "check_ad_evidence.py")), str(sample_dir), str(evidence_path)]
            process = subprocess.run(command, capture_output=True, text=True, check=False)
            self.assertEqual(process.returncode, 0, process.stderr)
            self.assertEqual(json.loads(process.stdout), result)

            unknown_rows = copy.deepcopy(rows)
            unknown_rows[0].update(category="uncertain", close_up=False)
            unknown_rows[70].update(category="uncertain", close_up=False)
            result = run(unknown_rows)
            self.assertTrue(result["structure_pass"], result["errors"])
            self.assertIsNone(result["close_up_ratio"])
            self.assertEqual(result["unknown_count"], 2)
            self.assertEqual(result["category_counts"]["uncertain"], 2)
            self.assertEqual((result["lower_bound"], result["upper_bound"]), (69.0, 71.0))

            short_index = copy.deepcopy(index)
            short_index["frames"] = [index["frames"][i] for i in (0, 1, 70)]
            result = run([unknown_rows[i] for i in (0, 1, 70)], short_index)
            self.assertTrue(result["structure_pass"], result["errors"])
            self.assertEqual((result["lower_bound"], result["upper_bound"]), (33.3, 100.0))

            bad_cases = [
                ("missing row", rows[:-1], index, "missing frame_id"),
                ("duplicate row", rows + [rows[0]], index, "duplicate frame_id"),
            ]
            row_changes = [
                ("unindexed ID", 0, {"frame_id": "extra"}, "unindexed frame_id"),
                ("timestamp mismatch", 0, {"timestamp_s": 0.1}, "timestamp_s mismatch"),
                ("missing read asset", 0, {"read_asset": "missing.bin"}, "read_asset"),
                ("single frame mismatch", 1, {"read_asset": "u001.bin"},
                 "read_asset must resolve to indexed file"),
                ("contact sheet mismatch", 0, {"read_asset": "u001.bin"},
                 "read_asset must resolve to indexed board"),
                ("single frame pointing at board", 0, {"read_method": "single_frame"},
                 "read_asset must resolve to indexed file"),
                ("bad method", 0, {"read_method": "claimed_read"}, "read_method"),
                ("bad category", 0, {"category": "unknown"}, "category"),
            ]
            row_changes += [
                (f"{category} counted as close-up", 0,
                 {"category": category, "close_up": True}, "close_up=true")
                for category in ("ui", "environment", "person", "text", "black", "uncertain")
            ]
            row_changes += [
                (f"invalid boolean {value!r}", 0, {"close_up": value}, "JSON boolean")
                for value in (0, 1, "false", "true", None, [], {})
            ]
            row_changes += [
                (f"placeholder {value!r}", 0, {"observation": value}, "placeholder")
                for value in ("", "  ", "同上", "延续上一帧", "据范式补写",
                              "same as above", "TBD", "...", "（同上）")
            ]
            for name, position, fields, error in row_changes:
                changed = copy.deepcopy(rows)
                changed[position].update(fields)
                bad_cases.append((name, changed, index, error))
            for name, fields, error in (
                ("duplicate indexed ID", {"frame_id": "u002"}, "duplicate frame_id"),
                ("wrong hash", {"sha256": "0" * 64}, "SHA256 mismatch"),
                ("missing frame file", {"file": "missing.bin"}, "file does not exist"),
                ("boolean timestamp", {"timestamp_s": False}, "timestamp_s"),
                ("boolean source index", {"source_frame_index": True}, "source_frame_index"),
                ("empty indexed board", {"board": ""}, "board"),
            ):
                changed = copy.deepcopy(index)
                changed["frames"][0].update(fields)
                bad_cases.append((name, rows, changed, error))
            for field, values in (
                ("source_frame_index", (30, 15)),
                ("timestamp_s", (1.0, 0.5)),
            ):
                for value in values:
                    changed_index = copy.deepcopy(index)
                    changed_rows = copy.deepcopy(rows)
                    changed_index["frames"][2][field] = value
                    if field == "timestamp_s":
                        changed_rows[2][field] = value
                    bad_cases.append((f"nonincreasing {field}: {value}", changed_rows,
                                      changed_index, f"{field} must be strictly increasing"))
            for name, changed_rows, changed_index, expected_error in bad_cases:
                with self.subTest(name=name):
                    result = run(changed_rows, changed_index)
                    self.assertFalse(result["structure_pass"])
                    self.assertIn(expected_error, "\n".join(result["errors"]))
                    for field in ("close_up_ratio", "lower_bound", "upper_bound"):
                        self.assertIsNone(result[field])
                    self.assertIs(result["not_visual_verification"], True)

            run(rows[:-1])
            process = subprocess.run(command, capture_output=True, text=True, check=False)
            self.assertEqual(process.returncode, 1, process.stderr)
            self.assertFalse(json.loads(process.stdout)["structure_pass"])


if __name__ == "__main__":
    unittest.main()
