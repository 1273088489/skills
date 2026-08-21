from __future__ import annotations

import json
import shutil
import socket
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path

from .config import RuntimePaths, tool_map
from .runner import command_version


@dataclass
class DoctorReport:
    ok: bool
    python: str
    python_version: str
    uv: str
    tools: dict[str, str] = field(default_factory=dict)
    asr: str = "missing"
    model: str = "missing"
    vault: str = "missing"
    inbox: str = "missing"
    kimi_daemon: str = "unreachable"
    issues: list[str] = field(default_factory=list)


def _kimi_reachable(timeout: float = 2.0) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", 10086), timeout=timeout):
            return True
    except OSError:
        return False


def find_model_dir(paths: RuntimePaths) -> str | None:
    candidates = [
        paths.models / "Systran" / "faster-whisper-small",
        paths.models / "models--Systran--faster-whisper-small",
    ]
    for candidate in candidates:
        if candidate.is_dir() and any(candidate.rglob("model.bin")):
            return str(candidate)
    return None


def run_doctor(paths: RuntimePaths) -> DoctorReport:
    issues: list[str] = []
    tools = tool_map(paths)
    tool_versions = {name: command_version(path) for name, path in tools.items()}

    if not tools.get("yt-dlp"):
        issues.append("yt-dlp 未找到（先运行 bootstrap.ps1）")
    if not tools.get("ffmpeg") or not tools.get("ffprobe"):
        issues.append("ffmpeg/ffprobe 未找到（先运行 bootstrap.ps1）")

    asr = "missing"
    try:
        import faster_whisper  # type: ignore

        asr = getattr(faster_whisper, "__version__", "installed")
    except ImportError:
        issues.append("faster-whisper 未安装（先运行 bootstrap.ps1）")

    model = "missing"
    found_model = find_model_dir(paths)
    if found_model:
        model = found_model
    else:
        issues.append("ASR 模型 small 尚未下载（运行 bootstrap.ps1 或首次转写时自动下载）")

    vault = "missing"
    inbox = "missing"
    if paths.vault.is_dir():
        vault = str(paths.vault)
    else:
        issues.append(f"Obsidian Vault 不存在：{paths.vault}")
    if paths.inbox.is_dir():
        inbox = str(paths.inbox)
    else:
        issues.append(f"Inbox 不存在：{paths.inbox}")

    kimi = "reachable" if _kimi_reachable() else "unreachable"
    if kimi == "unreachable":
        issues.append("Kimi WebBridge daemon 未运行或不可达（仅 Stage 2 需要）")

    uv_path = shutil.which("uv")
    if not uv_path:
        user_uv = Path.home() / ".local" / "bin" / "uv.exe"
        uv_path = str(user_uv) if user_uv.is_file() else ""

    report = DoctorReport(
        ok=not issues,
        python=sys.executable,
        python_version=f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        uv=uv_path,
        tools=tool_versions,
        asr=asr,
        model=model,
        vault=vault,
        inbox=inbox,
        kimi_daemon=kimi,
        issues=issues,
    )
    return report


def report_to_text(report: DoctorReport) -> str:
    lines = [
        f"Python: {report.python_version} ({report.python})",
        f"uv: {report.uv or 'missing'}",
        f"yt-dlp: {report.tools.get('yt-dlp', 'missing')}",
        f"ffmpeg: {report.tools.get('ffmpeg', 'missing')}",
        f"ffprobe: {report.tools.get('ffprobe', 'missing')}",
        f"deno: {report.tools.get('deno', 'missing')}",
        f"ASR: {report.asr}",
        f"ASR model: {report.model}",
        f"Vault: {report.vault}",
        f"Inbox: {report.inbox}",
        f"Kimi WebBridge: {report.kimi_daemon}",
    ]
    if report.issues:
        lines.append("")
        lines.append("发现的问题：")
        lines.extend(f"- {issue}" for issue in report.issues)
    return "\n".join(lines)


def save_report(paths: RuntimePaths, report: DoctorReport) -> Path:
    path = paths.logs / "doctor.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(report), ensure_ascii=False, indent=2), encoding="utf-8")
    return path
