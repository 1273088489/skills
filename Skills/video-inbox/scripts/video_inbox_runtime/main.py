from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from video_inbox_runtime import __version__  # noqa: E402
from video_inbox_runtime.acquire import acquire  # noqa: E402
from video_inbox_runtime.browser_fallback import load_browser_result, validate_browser_result  # noqa: E402
from video_inbox_runtime.config import RuntimePaths  # noqa: E402
from video_inbox_runtime.doctor import report_to_text, run_doctor, save_report  # noqa: E402
from video_inbox_runtime.enrich import enrich  # noqa: E402
from video_inbox_runtime.retry import run_retries  # noqa: E402
from video_inbox_runtime.cleanup import format_cleanup_report, run_cleanup  # noqa: E402


def default_asr_model() -> str:
    return os.environ.get("VIDEO_INBOX_ASR_MODEL", "small")


def cmd_doctor(_: argparse.Namespace) -> int:
    paths = RuntimePaths.discover()
    report = run_doctor(paths)
    print(report_to_text(report))
    print(f"\n报告已保存：{save_report(paths, report)}")
    return 0 if report.ok else 1


def cmd_acquire(args: argparse.Namespace) -> int:
    paths = RuntimePaths.discover()
    manifest, manifest_path = acquire(
        paths,
        args.input or args.url,
        args.url,
        force=args.force,
        asr_model=args.asr_model,
        keep_temp=args.keep_temp,
    )
    print(f"平台：{manifest.platform}  规范ID：{manifest.canonical_id}")
    print(f"标题：{manifest.title or '未获取'}")
    print(f"状态：{manifest.analysis_status}  证据等级：{manifest.evidence_grade}")
    print(f"字幕来源：{manifest.transcript_source}  覆盖率：{manifest.transcript_coverage or '未知'}")
    print(f"失败原因：{manifest.failure_reason}")
    print("采集链：" + " -> ".join(manifest.acquisition_chain) if manifest.acquisition_chain else "采集链：（空）")
    for attempt in manifest.attempts:
        error = f" ({attempt.error_code})" if attempt.error_code else ""
        print(f"  - [{attempt.stage}] {attempt.route}: {attempt.status}{error}")
    if manifest.browser_request_path:
        print(f"浏览器兜底请求：{manifest.browser_request_path}")
    if manifest.retry_status == "queued":
        print("已加入延迟重试队列")
    print(f"Manifest：{manifest_path}")
    return 0 if manifest.analysis_status in {"complete", "partial"} else 2


def cmd_enrich(args: argparse.Namespace) -> int:
    paths = RuntimePaths.discover()
    manifest = enrich(
        paths,
        Path(args.manifest),
        max_frames=args.frames,
        chunk_minutes=args.chunk_minutes,
        force_visual=args.force_visual,
        keep_preview=args.keep_preview,
    )
    print(f"状态：{manifest.analysis_status}")
    print(f"分章：{manifest.chunks_path or '未生成'}")
    print(f"帧计划：{manifest.frame_plan_path or '未生成'}")
    print(f"关键帧：{len(manifest.frame_paths)} 张")
    return 0


def cmd_validate_browser(args: argparse.Namespace) -> int:
    data = load_browser_result(Path(args.input))
    ok, issues = validate_browser_result(data)
    print(f"任务：{data.get('task_id')}  URL：{data.get('url')}")
    print(f"证据类型：{data.get('evidence_type')}  内容访问：{data.get('actual_content_access')}  覆盖率：{data.get('coverage')}")
    if ok:
        print("校验通过")
    else:
        print("校验失败：")
        for issue in issues:
            print(f"  - {issue}")
    return 0 if ok else 1


def cmd_retry(args: argparse.Namespace) -> int:
    paths = RuntimePaths.discover()
    results = run_retries(paths, once=not args.all, asr_model=args.asr_model)
    if not results:
        print("没有到期的重试任务")
    for url, status in results:
        print(f"{status}: {url}")
    return 0


def cmd_cleanup(args: argparse.Namespace) -> int:
    paths = RuntimePaths.discover()
    report = run_cleanup(paths, ttl_days=args.ttl, apply=args.apply)
    print(format_cleanup_report(report))
    return 0


def cmd_version(_: argparse.Namespace) -> int:
    print(f"video-inbox runtime {__version__}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="video-inbox", description="Windows 原生视频采集运行时")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    subparsers = parser.add_subparsers(dest="command", required=True)

    doctor = subparsers.add_parser("doctor", help="检查运行环境")
    doctor.set_defaults(handler=cmd_doctor)

    acquire_parser = subparsers.add_parser("acquire", help="采集视频字幕/音频/ASR")
    acquire_parser.add_argument("--url", required=True)
    acquire_parser.add_argument("--input", default="")
    acquire_parser.add_argument("--force", action="store_true")
    acquire_parser.add_argument("--asr-model", default=default_asr_model())
    acquire_parser.add_argument("--keep-temp", action="store_true")
    acquire_parser.set_defaults(handler=cmd_acquire)

    enrich_parser = subparsers.add_parser("enrich", help="关键帧与长视频分章")
    enrich_parser.add_argument("--manifest", required=True)
    enrich_parser.add_argument("--frames", type=int, default=6)
    enrich_parser.add_argument("--chunk-minutes", type=float, default=10.0)
    enrich_parser.add_argument("--force-visual", action="store_true")
    enrich_parser.add_argument("--keep-preview", action="store_true")
    enrich_parser.set_defaults(handler=cmd_enrich)

    validate_parser = subparsers.add_parser("validate-browser-result", help="校验浏览器兜底结果契约")
    validate_parser.add_argument("--input", required=True)
    validate_parser.set_defaults(handler=cmd_validate_browser)

    retry_parser = subparsers.add_parser("retry", help="处理延迟重试队列")
    retry_parser.add_argument("--all", action="store_true")
    retry_parser.add_argument("--asr-model", default=default_asr_model())
    retry_parser.set_defaults(handler=cmd_retry)

    cleanup_parser = subparsers.add_parser("cleanup", help="清理失效/过期文件（默认仅预览，--apply 才真正删除）")
    cleanup_parser.add_argument("--ttl", type=float, default=7.0, help="过期阈值天数（默认 7）")
    cleanup_parser.add_argument("--apply", action="store_true", help="真正执行删除（默认仅预览）")
    cleanup_parser.set_defaults(handler=cmd_cleanup)

    subparsers.add_parser("version", help="显示版本").set_defaults(handler=cmd_version)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.handler(args))


if __name__ == "__main__":
    raise SystemExit(main())
