from __future__ import annotations

import json
import os
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


SENSITIVE_MARKERS = ("cookie", "authorization", "x-bogus", "signature", "token=")


@dataclass
class CommandResult:
    args: list[str]
    returncode: int
    stdout: str
    stderr: str
    duration_seconds: float


class CommandError(RuntimeError):
    def __init__(self, message: str, result: CommandResult):
        super().__init__(message)
        self.result = result


def redact(text: str) -> str:
    lines: list[str] = []
    for line in text.splitlines():
        lowered = line.lower()
        if any(marker in lowered for marker in SENSITIVE_MARKERS):
            lines.append("[redacted sensitive line]")
        else:
            lines.append(line)
    return "\n".join(lines)


def run_command(
    args: Iterable[str | os.PathLike[str]],
    *,
    timeout: int = 60,
    cwd: Path | None = None,
    check: bool = True,
) -> CommandResult:
    argv = [str(item) for item in args]
    started = time.monotonic()
    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0
    try:
        completed = subprocess.run(
            argv,
            cwd=str(cwd) if cwd else None,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            shell=False,
            creationflags=creationflags,
        )
    except subprocess.TimeoutExpired as exc:
        result = CommandResult(argv, -1, exc.stdout or "", exc.stderr or "", time.monotonic() - started)
        raise CommandError(f"command timed out after {timeout}s", result) from exc

    result = CommandResult(
        args=argv,
        returncode=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
        duration_seconds=time.monotonic() - started,
    )
    if check and result.returncode != 0:
        raise CommandError(f"command failed with exit code {result.returncode}", result)
    return result


def command_version(path: Path | None, args: list[str] | None = None) -> str:
    if not path:
        return "missing"
    try:
        result = run_command([path, *(args or ["--version"])], timeout=15, check=False)
        output = (result.stdout or result.stderr).strip().splitlines()
        return output[0][:200] if output else f"exit:{result.returncode}"
    except Exception as exc:  # doctor must not crash
        return f"error:{type(exc).__name__}"


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(path)
