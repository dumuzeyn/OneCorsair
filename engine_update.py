"""Verified, atomic updates of the official Windows yt-dlp nightly binary."""

import hashlib
import json
import os
import re
import tempfile
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.request import Request, urlopen


REPOSITORY = "yt-dlp/yt-dlp-nightly-builds"
RELEASE_API = f"https://api.github.com/repos/{REPOSITORY}/releases/latest"
ASSET_PREFIX = f"https://github.com/{REPOSITORY}/releases/download/"
CHECK_INTERVAL = 3600
MAX_BINARY_SIZE = 100 * 1024 * 1024
_update_lock = threading.Lock()


class UpdateCancelled(RuntimeError):
    pass


@dataclass(frozen=True)
class Engine:
    path: Path
    version: str


def cache_directory():
    base = Path(os.environ.get("LOCALAPPDATA", Path.home() / ".cache"))
    return base / "MP3Ship" / "yt-dlp"


def check_cancelled(cancel_event):
    if cancel_event is not None and cancel_event.is_set():
        raise UpdateCancelled("Cancelled by user.")


def _sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _read_state(directory):
    try:
        state = json.loads((directory / "engine.json").read_text(encoding="utf-8"))
        filename = state["filename"]
        if not re.fullmatch(r"yt-dlp-[0-9a-f]{64}\.exe", filename):
            return None
        binary = directory / filename
        if _sha256(binary) != state["sha256"]:
            return None
        float(state["checked_at"])
        if not isinstance(state["version"], str):
            return None
        return state
    except (OSError, ValueError, KeyError, TypeError):
        return None


def _write_state(directory, state):
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=directory,
                                     suffix=".json.tmp", delete=False) as target:
        temporary = Path(target.name)
        json.dump(state, target)
    try:
        os.replace(temporary, directory / "engine.json")
    finally:
        temporary.unlink(missing_ok=True)


def _read_url(url, limit, cancel_event):
    check_cancelled(cancel_event)
    request = Request(url, headers={"User-Agent": "MP3Ship", "Accept": "application/json"})
    with urlopen(request, timeout=15) as response:
        data = response.read(limit + 1)
    check_cancelled(cancel_event)
    if len(data) > limit:
        raise ValueError("Update metadata is too large.")
    return data


def _download_binary(url, destination, expected_hash, cancel_event):
    digest = hashlib.sha256()
    request = Request(url, headers={"User-Agent": "MP3Ship"})
    size = 0
    with urlopen(request, timeout=15) as response, destination.open("wb") as target:
        while True:
            check_cancelled(cancel_event)
            block = response.read(1024 * 1024)
            if not block:
                break
            size += len(block)
            if size > MAX_BINARY_SIZE:
                raise ValueError("yt-dlp binary is too large.")
            digest.update(block)
            target.write(block)
    check_cancelled(cancel_event)
    if digest.hexdigest() != expected_hash:
        raise ValueError("yt-dlp SHA-256 verification failed.")
    with destination.open("rb") as source:
        if source.read(2) != b"MZ":
            raise ValueError("The update is not a Windows executable.")


def ensure_latest_engine(bundled_path=None, *, bundled_version="bundled", force=False, cancel_event=None,
                         report=None, directory=None):
    """Keep the last verified engine if GitHub is unreachable.

    Versioned files let another app instance finish its current download while
    an update is installed without replacing its running executable.
    """
    report = report or (lambda _key, **_values: None)
    directory = Path(directory) if directory is not None else cache_directory()
    check_cancelled(cancel_event)
    with _update_lock:
        check_cancelled(cancel_event)
        state = _read_state(directory)
        fallback = Engine(directory / state["filename"], state["version"]) if state else None
        if fallback is None and bundled_path and Path(bundled_path).is_file():
            fallback = Engine(Path(bundled_path), bundled_version)
        if state and not force and 0 <= time.time() - float(state["checked_at"]) < CHECK_INTERVAL:
            report("engine_ready", version=state["version"])
            return fallback
        try:
            report("checking_update")
            release = json.loads(_read_url(RELEASE_API, 2 * 1024 * 1024, cancel_event))
            version = release["tag_name"]
            assets = {asset["name"]: asset["browser_download_url"] for asset in release["assets"]}
            for name in ("SHA2-256SUMS", "yt-dlp.exe"):
                if not assets[name].startswith(ASSET_PREFIX):
                    raise ValueError("Unexpected yt-dlp release source.")
            sums = _read_url(assets["SHA2-256SUMS"], 64 * 1024, cancel_event).decode("utf-8")
            hashes = {}
            for line in sums.splitlines():
                parts = line.split()
                if len(parts) == 2:
                    hashes[parts[1].lstrip("*")] = parts[0]
            expected_hash = hashes["yt-dlp.exe"]
            if not re.fullmatch(r"[0-9a-f]{64}", expected_hash):
                raise ValueError("Invalid yt-dlp checksum.")
            directory.mkdir(parents=True, exist_ok=True)
            binary = directory / f"yt-dlp-{expected_hash}.exe"
            if not binary.is_file() or _sha256(binary) != expected_hash:
                report("installing_update", version=version)
                with tempfile.NamedTemporaryFile(dir=directory, suffix=".download", delete=False) as target:
                    temporary = Path(target.name)
                try:
                    _download_binary(assets["yt-dlp.exe"], temporary, expected_hash, cancel_event)
                    os.replace(temporary, binary)
                finally:
                    temporary.unlink(missing_ok=True)
            check_cancelled(cancel_event)
            _write_state(directory, {"filename": binary.name, "version": version,
                                     "sha256": expected_hash, "checked_at": time.time()})
            report("engine_ready", version=version)
            return Engine(binary, version)
        except UpdateCancelled:
            raise
        except (OSError, ValueError, KeyError, TypeError) as error:
            if fallback is None:
                raise RuntimeError(f"Cannot download yt-dlp from GitHub: {error}") from error
            report("update_unavailable", version=fallback.version, error=str(error))
            return fallback
