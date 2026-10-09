"""Download audio or video with an independently updatable yt-dlp engine."""

import argparse
import json
import os
import queue
import shutil
import subprocess
import sys
import threading
from collections import deque
from pathlib import Path

from engine_update import UpdateCancelled, ensure_latest_engine
from runtime_tools import install_tools


QUALITIES = ("128", "192", "256", "320")
VIDEO_HEIGHTS = ("best", "2160", "1440", "1080", "720", "480", "360")
BROWSERS = ("brave", "chrome", "chromium", "edge", "firefox", "opera", "vivaldi")
PROGRESS_PREFIX = "__MP3SHIP_PROGRESS__"
FILE_PREFIX = "__MP3SHIP_FILE__"


class DownloadError(RuntimeError):
    pass


class DownloadCancelled(DownloadError):
    pass


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Download YouTube audio (MP3) or video (MP4), optionally using cookies.")
    parser.add_argument("output_dir", help="Folder where media will be saved.")
    parser.add_argument("urls", nargs="+", help="Video or playlist links.")
    parser.add_argument("--mode", choices=("audio", "video"), default="audio")
    parser.add_argument("--quality", default="192", choices=QUALITIES, help="MP3 bitrate in kbps.")
    parser.add_argument("--height", default="1080", choices=VIDEO_HEIGHTS, help="Maximum video height, or best.")
    parser.add_argument("--update", action="store_true", help="Force checking for a fresh yt-dlp nightly release.")
    cookies = parser.add_mutually_exclusive_group()
    cookies.add_argument("--cookies", help="Path to an exported Netscape cookies.txt file.")
    cookies.add_argument("--cookies-from-browser", choices=BROWSERS, help="Explicitly use cookies from this browser.")
    return parser.parse_args(argv)


def resource_path(relative_path):
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return base / relative_path


def bundled_ffmpeg_dir(cancel_event=None):
    for archive in (resource_path("runtime-tools.zip"), resource_path("vendor/runtime-tools.zip")):
        if archive.is_file():
            return install_tools(archive, cancel_event=cancel_event)
    for directory in (resource_path("ffmpeg"), Path(__file__).resolve().parent / "vendor" / "ffmpeg"):
        if (directory / "ffmpeg.exe").is_file():
            return directory
    return None


def bundled_deno_path(cancel_event=None):
    for archive in (resource_path("runtime-tools.zip"), resource_path("vendor/runtime-tools.zip")):
        if archive.is_file():
            return install_tools(archive, cancel_event=cancel_event) / "deno.exe"
    for path in (resource_path("deno/deno.exe"), resource_path("vendor/deno/deno.exe")):
        if path.is_file():
            return path
    return None


def bundled_engine_path():
    for path in (resource_path("yt-dlp/yt-dlp.exe"), resource_path("vendor/yt-dlp/yt-dlp.exe")):
        if path.is_file():
            return path
    return None


def configure_bundled_ffmpeg(cancel_event=None):
    directory = bundled_ffmpeg_dir(cancel_event=cancel_event)
    if directory is not None and str(directory) not in os.environ.get("PATH", "").split(os.pathsep):
        os.environ["PATH"] = str(directory) + os.pathsep + os.environ.get("PATH", "")
    return directory


def update_engine(*, force=False, cancel_event=None, report=None):
    bundled = bundled_engine_path()
    version = "bundled"
    if bundled:
        try:
            version = (bundled.parent / "version.txt").read_text(encoding="utf-8").strip() or version
        except OSError:
            pass
    try:
        return ensure_latest_engine(bundled, bundled_version=version, force=force,
                                    cancel_event=cancel_event, report=report)
    except UpdateCancelled as error:
        raise DownloadCancelled(str(error)) from error


def build_command(engine, urls, output_path, quality="192", mode="audio", height="1080", *,
                  cookies_file=None, cookies_from_browser=None):
    if mode not in ("audio", "video"):
        raise ValueError("Unknown download mode.")
    if quality not in QUALITIES or height not in VIDEO_HEIGHTS:
        raise ValueError("Unknown media quality.")
    if cookies_file and cookies_from_browser:
        raise ValueError("Choose either a cookies file or browser cookies.")
    if cookies_from_browser and cookies_from_browser not in BROWSERS:
        raise ValueError("Unknown browser.")
    profile = f"mp3_{quality}" if mode == "audio" else f"mp4_{height}"
    command = [
        str(engine), "--ignore-config", "--no-plugin-dirs",
        "--encoding", "utf-8", "--no-colors", "--newline", "--progress", "--progress-delta", "0.5",
        "--no-abort-on-error", "--yes-playlist", "--windows-filenames", "--continue",
        "--retries", "5", "--fragment-retries", "5", "--extractor-retries", "3",
        "--socket-timeout", "20", "--retry-sleep", "http:exp=1:10",
        "--sleep-interval", "5", "--max-sleep-interval", "10",
        "--download-archive", str(output_path / f".mp3ship_{profile}_downloaded.txt"),
        "--output", str(output_path / f"%(title).160B [%(id)s] [{profile}].%(ext)s"),
        "--progress-template", f"download:{PROGRESS_PREFIX}%(progress)j",
        "--print", f"after_move:{FILE_PREFIX}%(filepath)j",
        "--no-simulate",
    ]
    if cookies_file:
        command.extend(["--cookies", str(Path(cookies_file).expanduser().resolve()), "--no-cookies-from-browser"])
    elif cookies_from_browser:
        command.extend(["--no-cookies", "--cookies-from-browser", cookies_from_browser])
    else:
        command.extend(["--no-cookies", "--no-cookies-from-browser"])
    ffmpeg_dir = configure_bundled_ffmpeg()
    if ffmpeg_dir:
        command.extend(["--ffmpeg-location", str(ffmpeg_dir)])
    deno = bundled_deno_path()
    if deno:
        command.extend(["--js-runtimes", f"deno:{deno}"])
    else:
        # Deno is enabled by default; Node is a fallback for source installations.
        command.extend(["--js-runtimes", "node"])
    if mode == "audio":
        command.extend(["--format", "bestaudio/best", "--extract-audio",
                        "--audio-format", "mp3", "--audio-quality", quality])
    else:
        cap = "" if height == "best" else f"[height<={height}]"
        formats = f"bv[ext=mp4]{cap}+ba[ext=m4a]/b[ext=mp4]{cap}/bv{cap}+ba/b{cap}"
        command.extend(["--format", formats, "--format-sort", "res,vcodec:h264,acodec:aac",
                        "--merge-output-format", "mp4", "--recode-video", "mp4"])
    command.extend(["--", *urls])
    return command


def _check_cancelled(cancel_event):
    if cancel_event is not None and cancel_event.is_set():
        raise DownloadCancelled("Cancelled by user.")


def _terminate_process(process):
    if process.poll() is not None:
        return
    if sys.platform == "win32":
        # yt-dlp starts FFmpeg/Deno children; stop the entire tree on Windows.
        try:
            subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                           creationflags=subprocess.CREATE_NO_WINDOW, timeout=10, check=False)
        except (OSError, subprocess.TimeoutExpired):
            pass
    if process.poll() is None:
        process.kill()
    process.wait(timeout=10)


def run_command(command, *, progress_hooks=None, logger=None, cancel_event=None, report=None):
    """Read output on a separate thread so Stop also works during extraction."""
    _check_cancelled(cancel_event)
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                               stdin=subprocess.DEVNULL, encoding="utf-8", errors="replace",
                               bufsize=1, creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0)
    lines = queue.Queue()
    errors = deque(maxlen=8)

    def read_output():
        try:
            for line in process.stdout:
                lines.put(line.rstrip("\r\n"))
        finally:
            lines.put(None)

    reader = threading.Thread(target=read_output, daemon=True)
    reader.start()
    try:
        while True:
            _check_cancelled(cancel_event)
            try:
                line = lines.get(timeout=0.1)
            except queue.Empty:
                continue
            if line is None:
                break
            if line.startswith(PROGRESS_PREFIX):
                try:
                    info = json.loads(line[len(PROGRESS_PREFIX):])
                except ValueError:
                    continue
                for hook in progress_hooks or ():
                    hook(info)
            elif line.startswith(FILE_PREFIX):
                try:
                    filename = json.loads(line[len(FILE_PREFIX):])
                except ValueError:
                    continue
                if report:
                    report("saved_file", filename=filename)
            elif line:
                if line.startswith("ERROR:"):
                    errors.append(line)
                    if logger:
                        logger.error(line)
                elif logger:
                    logger.warning(line)
                else:
                    print(line)
        returncode = process.wait()
        _check_cancelled(cancel_event)
        if returncode:
            raise DownloadError("\n".join(errors) or f"yt-dlp exited with code {returncode}.")
        return 0
    finally:
        try:
            _terminate_process(process)
        finally:
            reader.join(timeout=2)
            process.stdout.close()


def download_media(urls, output_dir, quality="192", *, mode="audio", height="1080",
                   progress_hooks=None, logger=None, cancel_event=None, report=None, force_update=False,
                   cookies_file=None, cookies_from_browser=None):
    _check_cancelled(cancel_event)
    if cookies_file and cookies_from_browser:
        raise ValueError("Choose either a cookies file or browser cookies.")
    if cookies_file and not Path(cookies_file).expanduser().is_file():
        raise DownloadError("The selected cookies.txt file does not exist.")
    try:
        configure_bundled_ffmpeg(cancel_event=cancel_event)
        if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
            raise DownloadError("FFmpeg and FFprobe are required. Use the bundled OneCorsair.exe or install both in PATH.")
        if not bundled_deno_path(cancel_event=cancel_event) and not (shutil.which("deno") or shutil.which("node")):
            raise DownloadError("Deno is required for YouTube. Use the bundled OneCorsair.exe or install Deno.")
    except UpdateCancelled as error:
        raise DownloadCancelled(str(error)) from error
    urls = list(urls)
    if not urls:
        raise ValueError("At least one URL is required.")
    output_path = Path(output_dir).expanduser().resolve()
    output_path.mkdir(parents=True, exist_ok=True)
    engine = update_engine(force=force_update, cancel_event=cancel_event, report=report)
    command = build_command(engine.path, urls, output_path, quality, mode, height,
                            cookies_file=cookies_file, cookies_from_browser=cookies_from_browser)
    return run_command(command, progress_hooks=progress_hooks, logger=logger,
                       cancel_event=cancel_event, report=report)


def download_mp3(urls, output_dir, quality="192", **kwargs):
    """Compatibility entry point for scripts using the old audio downloader."""
    return download_media(urls, output_dir, quality, mode="audio", **kwargs)


def main():
    args = parse_args()

    def report(key, **values):
        print(key + (": " + ", ".join(f"{k}={v}" for k, v in values.items()) if values else ""))

    try:
        download_media(args.urls, args.output_dir, args.quality, mode=args.mode,
                       height=args.height, force_update=args.update, report=report,
                       cookies_file=args.cookies, cookies_from_browser=args.cookies_from_browser)
    except (KeyboardInterrupt, DownloadCancelled):
        print("Download cancelled.", file=sys.stderr)
        return 130
    except Exception as error:
        print(f"Download error: {error}", file=sys.stderr)
        return 1
    print("Done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
