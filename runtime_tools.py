"""Install large bundled tools once, instead of unpacking them on every launch."""

import hashlib
import json
import os
import tempfile
import threading
import zipfile
from pathlib import Path

from engine_update import cache_directory, check_cancelled


_lock = threading.Lock()
TOOL_NAMES = ("ffmpeg.exe", "ffprobe.exe", "deno.exe")


def _digest(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _is_executable(path):
    with Path(path).open("rb") as source:
        return source.read(2) == b"MZ"


def install_tools(archive_path, *, directory=None, cancel_event=None):
    """Versioned directories keep already-running instances working during updates."""
    directory = Path(directory) if directory else cache_directory().parent / "runtime"
    check_cancelled(cancel_event)
    with _lock, zipfile.ZipFile(archive_path) as archive:
        manifest = json.loads(archive.read("manifest.json"))
        if set(manifest) != set(TOOL_NAMES):
            raise ValueError("Unexpected runtime tools manifest.")
        for metadata in manifest.values():
            if not isinstance(metadata["sha256"], str) or len(metadata["sha256"]) != 64:
                raise ValueError("Invalid runtime tool checksum.")
            if not isinstance(metadata["size"], int) or not 0 < metadata["size"] < 300 * 1024 * 1024:
                raise ValueError("Invalid runtime tool size.")
        identity = hashlib.sha256(json.dumps(manifest, sort_keys=True).encode()).hexdigest()[:24]
        destination = directory / identity
        # Marker is committed only after each binary passes a complete SHA-256 check.
        try:
            ready = json.loads((destination / "ready.json").read_text(encoding="utf-8"))
            if ready["manifest"] == manifest and all(
                    (destination / name).is_file()
                    and (destination / name).stat().st_size == manifest[name]["size"]
                    and (destination / name).stat().st_mtime_ns == ready["mtimes"][name]
                    and _is_executable(destination / name)
                    for name in TOOL_NAMES):
                return destination
        except (OSError, ValueError, KeyError, TypeError):
            pass
        directory.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="install-", dir=directory) as staging:
            staging = Path(staging)
            for name in TOOL_NAMES:
                check_cancelled(cancel_event)
                target = staging / name
                digest = hashlib.sha256()
                with archive.open(name) as source, target.open("wb") as output:
                    for block in iter(lambda: source.read(1024 * 1024), b""):
                        check_cancelled(cancel_event)
                        digest.update(block)
                        output.write(block)
                if target.stat().st_size != manifest[name]["size"] or digest.hexdigest() != manifest[name]["sha256"]:
                    raise ValueError(f"Bundled {name} failed SHA-256 verification.")
                if not _is_executable(target):
                    raise ValueError(f"Bundled {name} is not a Windows executable.")
            destination.mkdir(parents=True, exist_ok=True)
            for name in TOOL_NAMES:
                target = destination / name
                # Another app instance may have completed this same install.
                if target.is_file() and _digest(target) == manifest[name]["sha256"]:
                    continue
                os.replace(staging / name, target)
            marker = staging / "ready.json"
            marker.write_text(json.dumps({"manifest": manifest, "mtimes": {
                name: (destination / name).stat().st_mtime_ns for name in TOOL_NAMES}}), encoding="utf-8")
            os.replace(marker, destination / "ready.json")
        return destination


def build_archive(destination, sources):
    destination = Path(destination)
    sources = {name: Path(sources[name]) for name in TOOL_NAMES}
    manifest = {name: {"sha256": _digest(path), "size": path.stat().st_size} for name, path in sources.items()}
    if destination.is_file():
        try:
            with zipfile.ZipFile(destination) as previous:
                if json.loads(previous.read("manifest.json")) == manifest:
                    return destination
        except (OSError, ValueError, KeyError, zipfile.BadZipFile):
            pass
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=destination.parent, suffix=".zip.tmp", delete=False) as target:
        temporary = Path(target.name)
    try:
        with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
            archive.writestr("manifest.json", json.dumps(manifest, sort_keys=True))
            for name, source in sources.items():
                archive.write(source, arcname=name)
        os.replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)
    return destination
