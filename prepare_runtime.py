"""Prepare the reusable compressed runtime bundle before building the app."""

from pathlib import Path

from runtime_tools import build_archive


if __name__ == "__main__":
    root = Path(__file__).resolve().parent
    archive = build_archive(root / "vendor" / "runtime-tools.zip", {
        "ffmpeg.exe": Path("C:/ffmpeg/bin/ffmpeg.exe"),
        "ffprobe.exe": Path("C:/ffmpeg/bin/ffprobe.exe"),
        "deno.exe": root / "vendor" / "deno" / "deno.exe",
    })
    print(f"Runtime bundle: {archive} ({archive.stat().st_size / 1024 / 1024:.1f} MB)")
