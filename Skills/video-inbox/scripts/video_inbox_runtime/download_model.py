from __future__ import annotations

import argparse


def main() -> None:
    parser = argparse.ArgumentParser(description="预下载 faster-whisper 模型")
    parser.add_argument("--model", default="small")
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--download-root", required=True)
    args = parser.parse_args()

    from faster_whisper import WhisperModel  # type: ignore

    WhisperModel(
        args.model,
        device=args.device,
        compute_type="int8",
        download_root=args.download_root,
    )
    print(f"model {args.model} ready at {args.download_root}")


if __name__ == "__main__":
    main()
