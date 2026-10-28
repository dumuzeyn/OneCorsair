import hashlib
import io
import json
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import URLError

import engine_update as updater
import youtube_to_mp3 as downloader


class UpdateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name) / "cache"
        self.binary = b"MZverified test executable"
        self.digest = hashlib.sha256(self.binary).hexdigest()
        self.version = "2026.09.27.232945"
        self.base = updater.ASSET_PREFIX + self.version + "/"
        self.events = []

    def response(self, request, **_kwargs):
        if request.full_url == updater.RELEASE_API:
            body = json.dumps({"tag_name": self.version, "assets": [
                {"name": name, "browser_download_url": self.base + name}
                for name in ("yt-dlp.exe", "SHA2-256SUMS")
            ]}).encode()
        elif request.full_url.endswith("SHA2-256SUMS"):
            body = f"{self.digest}  yt-dlp.exe\n".encode()
        else:
            body = self.binary
        return io.BytesIO(body)

    def report(self, key, **values):
        self.events.append((key, values))

    def install(self):
        with patch.object(updater, "urlopen", side_effect=self.response):
            return updater.ensure_latest_engine(directory=self.directory, report=self.report)

    def test_verified_install_and_cached_check(self):
        engine = self.install()
        self.assertEqual(engine.version, self.version)
        self.assertEqual(engine.path.read_bytes(), self.binary)
        with patch.object(updater, "urlopen") as request:
            self.assertEqual(updater.ensure_latest_engine(directory=self.directory), engine)
            request.assert_not_called()
        self.assertFalse(list(self.directory.glob("*.download")))

    def test_force_rechecks_without_redownloading_same_binary(self):
        self.install()
        with patch.object(updater, "urlopen", side_effect=self.response) as request:
            updater.ensure_latest_engine(directory=self.directory, force=True)
        self.assertEqual(request.call_count, 2)

    def test_offline_keeps_verified_cache(self):
        previous = self.install()
        with patch.object(updater, "urlopen", side_effect=URLError("offline")):
            engine = updater.ensure_latest_engine(directory=self.directory, force=True, report=self.report)
        self.assertEqual(engine, previous)
        self.assertEqual(self.events[-1][0], "update_unavailable")

    def test_bad_update_does_not_replace_previous_binary(self):
        previous = self.install()
        previous_state = (self.directory / "engine.json").read_bytes()
        self.digest = hashlib.sha256(b"different expected binary").hexdigest()
        with patch.object(updater, "urlopen", side_effect=self.response):
            engine = updater.ensure_latest_engine(directory=self.directory, force=True)
        self.assertEqual(engine, previous)
        self.assertEqual(previous.path.read_bytes(), self.binary)
        self.assertEqual((self.directory / "engine.json").read_bytes(), previous_state)
        self.assertFalse(list(self.directory.glob("*.download")))

    def test_corrupt_cache_uses_bundled_fallback_when_offline(self):
        installed = self.install()
        installed.path.write_bytes(b"corrupted")
        bundled = Path(self.temp.name) / "bundled.exe"
        bundled.write_bytes(self.binary)
        with patch.object(updater, "urlopen", side_effect=URLError("offline")):
            engine = updater.ensure_latest_engine(bundled, directory=self.directory)
        self.assertEqual(engine.path, bundled)

    def test_missing_engine_reports_network_failure(self):
        with patch.object(updater, "urlopen", side_effect=URLError("offline")):
            with self.assertRaisesRegex(RuntimeError, "Cannot download yt-dlp"):
                updater.ensure_latest_engine(directory=self.directory)

    def test_unofficial_asset_is_rejected(self):
        self.base = "https://example.com/releases/"
        with patch.object(updater, "urlopen", side_effect=self.response):
            with self.assertRaisesRegex(RuntimeError, "Unexpected yt-dlp release source"):
                updater.ensure_latest_engine(directory=self.directory)

    def test_cancelled_update_does_not_start_network_request(self):
        cancel = threading.Event()
        cancel.set()
        with patch.object(updater, "urlopen") as request:
            with self.assertRaises(updater.UpdateCancelled):
                updater.ensure_latest_engine(directory=self.directory, cancel_event=cancel)
            request.assert_not_called()

    def test_cancel_during_update_preserves_previous_engine(self):
        previous = self.install()
        self.digest = hashlib.sha256(b"MZnew version").hexdigest()
        cancel = threading.Event()

        def response(request, **kwargs):
            result = self.response(request, **kwargs)
            if request.full_url.endswith("yt-dlp.exe"):
                cancel.set()
            return result

        with patch.object(updater, "urlopen", side_effect=response):
            with self.assertRaises(updater.UpdateCancelled):
                updater.ensure_latest_engine(directory=self.directory, force=True, cancel_event=cancel)
        self.assertEqual(previous.path.read_bytes(), self.binary)
        self.assertFalse(list(self.directory.glob("*.download")))


class DownloadTests(unittest.TestCase):
    def command(self, mode="audio", height="1080", quality="192"):
        return downloader.build_command(Path("yt-dlp.exe"), ["https://youtu.be/test"],
                                        Path("output"), quality, mode, height)

    def test_cookie_free_and_separate_archives(self):
        audio = self.command()
        video = self.command("video")
        for command in (audio, video):
            self.assertIn("--ignore-config", command)
            self.assertIn("--no-cookies", command)
            self.assertIn("--no-cookies-from-browser", command)
            self.assertNotIn("--ignore-errors", command)
            self.assertEqual(command[-2:], ["--", "https://youtu.be/test"])
        self.assertNotEqual(audio[audio.index("--download-archive") + 1],
                            video[video.index("--download-archive") + 1])
        other_quality = self.command(quality="320")
        self.assertNotEqual(audio[audio.index("--output") + 1],
                            other_quality[other_quality.index("--output") + 1])

    def test_video_has_audio_and_all_fallbacks_obey_resolution_limit(self):
        command = self.command("video", "720")
        formats = command[command.index("--format") + 1]
        for option in formats.split("/"):
            self.assertIn("[height<=?720]", option)
        self.assertIn("+ba[ext=m4a]", formats)
        self.assertNotIn("--extract-audio", command)
        self.assertEqual(command[command.index("--merge-output-format") + 1], "mp4")
        best = self.command("video", "best")
        self.assertNotIn("height<=", best[best.index("--format") + 1])

    def test_cookies_are_used_only_when_explicitly_selected(self):
        cookie_file = Path("cookies with spaces.txt").resolve()
        command = downloader.build_command("yt-dlp.exe", [], Path("output"), cookies_file=cookie_file)
        self.assertEqual(command[command.index("--cookies") + 1], str(cookie_file))
        self.assertNotIn("--no-cookies", command)
        self.assertIn("--no-cookies-from-browser", command)
        browser = downloader.build_command("yt-dlp.exe", [], Path("output"), cookies_from_browser="firefox")
        self.assertEqual(browser[browser.index("--cookies-from-browser") + 1], "firefox")
        self.assertNotIn("--no-cookies-from-browser", browser)
        with self.assertRaises(ValueError):
            downloader.build_command("yt-dlp.exe", [], Path("output"),
                                     cookies_file=cookie_file, cookies_from_browser="firefox")

    def test_missing_cookie_file_fails_before_network_or_engine_start(self):
        with tempfile.TemporaryDirectory() as temporary, patch.object(downloader, "update_engine") as update:
            with self.assertRaisesRegex(downloader.DownloadError, "cookies.txt file does not exist"):
                downloader.download_media(["https://youtu.be/test"], temporary,
                                          cookies_file=Path(temporary) / "missing.txt")
            update.assert_not_called()

    def test_social_video_does_not_require_a_youtube_javascript_runtime(self):
        for url, source in (("https://www.tiktok.com/@demo/video/123", "TikTok"),
                            ("https://instagram.com/reel/demo/", "Instagram")):
            with self.subTest(source=source), tempfile.TemporaryDirectory() as temporary, \
                    patch.object(downloader, "configure_bundled_ffmpeg", return_value=None), \
                    patch.object(downloader, "bundled_deno_path", return_value=None), \
                    patch.object(downloader.shutil, "which", side_effect=lambda name: name if name in ("ffmpeg", "ffprobe") else None), \
                    patch.object(downloader, "update_engine", return_value=updater.Engine(Path("yt-dlp.exe"), "test")), \
                    patch.object(downloader, "run_command", return_value=0) as run:
                events = []
                downloader.download_media([url], temporary, mode="video",
                                          report=lambda key, **values: events.append((key, values)))
                self.assertEqual(run.call_args.args[0][-1], url)
                self.assertIn(("detected_sources", {"sources": source}), events)
                self.assertNotIn("--js-runtimes", run.call_args.args[0])

    def test_unsupported_remote_site_fails_before_network_or_engine_start(self):
        with tempfile.TemporaryDirectory() as temporary, patch.object(downloader, "update_engine") as update:
            with self.assertRaisesRegex(downloader.DownloadError, "Supported sites:"):
                downloader.download_media(["https://example.net/video/123"], temporary)
            update.assert_not_called()

    def test_cancel_during_first_runtime_install_stops_before_engine_update(self):
        cancel = threading.Event()
        with tempfile.TemporaryDirectory() as temporary, \
                patch.object(downloader, "configure_bundled_ffmpeg", side_effect=updater.UpdateCancelled("Stopped")) as setup, \
                patch.object(downloader, "update_engine") as update:
            with self.assertRaises(downloader.DownloadCancelled):
                downloader.download_media(["https://youtu.be/test"], temporary, cancel_event=cancel)
            setup.assert_called_once_with(cancel_event=cancel)
            update.assert_not_called()

    def test_structured_progress_and_saved_file(self):
        hooks, reports = [], []
        payload = {"status": "downloading", "downloaded_bytes": 42}
        lines = [downloader.PROGRESS_PREFIX + json.dumps(payload),
                 downloader.FILE_PREFIX + json.dumps("Тест.mp4", ensure_ascii=False)]
        script = "import sys; sys.stdout.reconfigure(encoding='utf-8'); " + "; ".join(
            f"print({line!r}, flush=True)" for line in lines)
        downloader.run_command([sys.executable, "-c", script], progress_hooks=[hooks.append],
                               report=lambda key, **values: reports.append((key, values)))
        self.assertEqual(hooks, [payload])
        self.assertEqual(reports, [("saved_file", {"filename": "Тест.mp4"})])

    def test_failed_postprocessing_is_not_success(self):
        with self.assertRaisesRegex(downloader.DownloadError, "conversion failed"):
            downloader.run_command([sys.executable, "-c",
                                    "import sys; print('ERROR: conversion failed'); sys.exit(1)"])

    def test_stop_works_while_process_is_silent(self):
        cancel = threading.Event()
        timer = threading.Timer(0.3, cancel.set)
        timer.start()
        started = time.monotonic()
        try:
            with self.assertRaises(downloader.DownloadCancelled):
                downloader.run_command([sys.executable, "-c", "import time; time.sleep(30)"],
                                       cancel_event=cancel)
        finally:
            timer.cancel()
        self.assertLess(time.monotonic() - started, 5)


class GuiTests(unittest.TestCase):
    def setUp(self):
        from mp3_ship_gui import MP3ShipApp
        self.settings_temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.settings_temp.cleanup)
        self.app = MP3ShipApp(settings_path=Path(self.settings_temp.name) / "settings.json")
        self.app.withdraw()

    def tearDown(self):
        for callback in self.app.tk.call("after", "info"):
            self.app.after_cancel(callback)
        self.app.destroy()

    def test_mode_quality_and_translation_stay_in_sync(self):
        app = self.app
        app.mode_combo.current(1)
        app._change_mode()
        app.video_quality_combo.current(4)
        app._change_video_quality()
        self.assertEqual(app.mode, "video")
        self.assertEqual(app.height_var.get(), "720")
        app._toggle_language()
        self.assertEqual(app.mode_combo.get(), "Video + audio · MP4")
        self.assertEqual(app.video_quality_combo.get(), "720p")
        self.assertEqual(app.quality_label.cget("text"), "Maximum resolution")

    def test_links_clear_only_after_success(self):
        app = self.app
        app.urls_text.insert("1.0", "https://youtu.be/test")
        app.log_queue.put(("__DONE__", "failed"))
        app._drain_log_queue()
        self.assertIn("https://youtu.be/test", app.urls_text.get("1.0", "end"))
        self.assertEqual(app.status_var.get(), app.t("failed"))
        app.log_queue.put(("__DONE__", "done"))
        app._drain_log_queue()
        self.assertEqual(app.urls_text.get("1.0", "end").strip(), "")

    def test_large_log_and_frequent_progress_do_not_grow_without_limit(self):
        from mp3_ship_gui import MAX_LOG_LINES
        app = self.app
        app._write_log("entry\n" * 5000)
        self.assertLessEqual(int(app.log.index("end-1c").split(".")[0]), MAX_LOG_LINES)
        before = app.log_queue.qsize()
        for value in range(1000):
            app._progress_hook({"status": "downloading", "downloaded_bytes": value, "total_bytes": 1000})
        self.assertEqual(app.log_queue.qsize(), before)
        app._drain_log_queue()
        self.assertAlmostEqual(float(app.progress.cget("value")), 99.9)

    def test_preferences_restore_cookie_path_and_format(self):
        from app_settings import load_settings
        app = self.app
        app.cookies_file_var.set("C:/example/cookies.txt")
        app.output_var.set("C:/example/downloads")
        app.mode_combo.current(1)
        app._change_mode()
        app._save_preferences()
        saved = load_settings(app.settings_path)
        self.assertEqual(saved["cookies"], "C:/example/cookies.txt")
        self.assertEqual(saved["output"], "C:/example/downloads")
        self.assertEqual(saved["mode"], "video")


if __name__ == "__main__":
    unittest.main()
