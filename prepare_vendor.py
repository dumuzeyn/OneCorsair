"""Fetch the verified official yt-dlp binary before building OneCorsair.exe."""

import shutil
from pathlib import Path

from engine_update import ensure_latest_engine


def main():
    directory = Path(__file__).resolve().parent / "vendor" / "yt-dlp"

    def report(key, **values):
        print(key, values, flush=True)

    engine = ensure_latest_engine(force=True, directory=directory / "cache", report=report)
    directory.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(engine.path, directory / "yt-dlp.exe")
    (directory / "version.txt").write_text(engine.version + "\n", encoding="utf-8")
    print(f"Bundled yt-dlp: {engine.version}")


if __name__ == "__main__":
    main()
