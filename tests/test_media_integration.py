"""Opt-in end-to-end checks against local media using the real yt-dlp/FFmpeg."""

import functools
import json
import os
import subprocess
import tempfile
import threading
import unittest
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import youtube_to_mp3 as downloader


@unittest.skipUnless(os.environ.get("MP3SHIP_INTEGRATION") == "1", "Set MP3SHIP_INTEGRATION=1 for real media checks")
class MediaIntegrationTests(unittest.TestCase):
    def test_audio_video_merging_and_independent_archives(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            fixtures = directory / "fixtures"
            fixtures.mkdir()
            source = fixtures / "test.mp4"
            subprocess.run([
                "ffmpeg", "-hide_banner", "-loglevel", "error", "-f", "lavfi",
                "-i", "testsrc=size=320x240:rate=24", "-f", "lavfi", "-i", "sine=frequency=440",
                "-t", "1.5", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", str(source),
            ], check=True, timeout=30)
            subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-i", str(source),
                            "-an", "-c:v", "copy", str(fixtures / "video.mp4")], check=True, timeout=30)
            subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-i", str(source),
                            "-vn", "-c:a", "copy", str(fixtures / "audio.m4a")], check=True, timeout=30)

            received_cookies = []

            class QuietHandler(SimpleHTTPRequestHandler):
                def do_GET(self):
                    received_cookies.append(self.headers.get("Cookie", ""))
                    super().do_GET()

                def log_message(self, *_args):
                    pass

            server = ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(QuietHandler, directory=str(fixtures)))
            serving = threading.Thread(target=server.serve_forever, daemon=True)
            serving.start()
            try:
                base = f"http://127.0.0.1:{server.server_port}"
                output = directory / "Скачанное видео"
                events = []

                def report(key, **values):
                    events.append((key, values))

                # Same URL in both modes must produce both files, not skip video.
                downloader.download_media([base + "/test.mp4"], output, "192", report=report)
                # A direct HTTP file has no height metadata until FFprobe reads it.
                downloader.download_media([base + "/test.mp4"], output, mode="video", height="best", report=report)
                mp3 = list(output.glob("*.mp3"))
                mp4 = list(output.glob("*.mp4"))
                self.assertEqual(len(mp3), 1)
                self.assertEqual(len(mp4), 1)
                self.assertEqual(self.probe(mp3[0])["streams"][0]["codec_name"], "mp3")
                self.assertEqual({stream["codec_type"] for stream in self.probe(mp4[0])["streams"]}, {"video", "audio"})
                video_timestamp = mp4[0].stat().st_mtime_ns
                downloader.download_media([base + "/test.mp4"], output, mode="video", height="best", report=report)
                self.assertEqual(mp4[0].stat().st_mtime_ns, video_timestamp)

                # YouTube commonly supplies video and audio as separate streams.
                info = directory / "separate-streams.json"
                info.write_text(json.dumps({
                    "id": "merge-fixture", "title": "Separate audio and video", "extractor": "generic",
                    "extractor_key": "Generic", "webpage_url": base + "/test.mp4",
                    "formats": [
                        {"format_id": "v", "url": base + "/video.mp4", "ext": "mp4", "vcodec": "h264",
                         "acodec": "none", "width": 320, "height": 240},
                        {"format_id": "a", "url": base + "/audio.m4a", "ext": "m4a", "vcodec": "none", "acodec": "aac"},
                    ],
                }), encoding="utf-8")
                command = downloader.build_command(downloader.bundled_engine_path(), [], output,
                                                   mode="video", height="720")
                command[-1:-1] = ["--load-info-json", str(info)]
                downloader.run_command(command, report=report)
                merged = next(output.glob("*merge-fixture*.mp4"))
                self.assertEqual({stream["codec_type"] for stream in self.probe(merged)["streams"]}, {"video", "audio"})
                self.assertTrue(any(key == "saved_file" for key, _values in events))
                cookies = directory / "test cookies.txt"
                cookies.write_text("# Netscape HTTP Cookie File\n"
                                   "127.0.0.1\tFALSE\t/\tFALSE\t2147483647\tmp3ship_test\tallowed\n",
                                   encoding="utf-8")
                downloader.download_media([base + "/test.mp4"], output, "256", cookies_file=cookies)
                self.assertTrue(any("mp3ship_test=allowed" in header for header in received_cookies))
                print("Real media checks: MP3, MP4 with sound, stream merging, archives, selected cookies: OK")
            finally:
                server.shutdown()
                server.server_close()
                serving.join(timeout=2)

    @staticmethod
    def probe(path):
        result = subprocess.run(["ffprobe", "-v", "error", "-show_streams", "-of", "json", str(path)],
                                capture_output=True, encoding="utf-8", check=True, timeout=15)
        return json.loads(result.stdout)
