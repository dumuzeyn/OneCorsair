import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

import runtime_tools
from app_settings import load_settings, save_settings
from engine_update import UpdateCancelled


class RuntimeToolsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.sources = {}
        for name in runtime_tools.TOOL_NAMES:
            path = self.root / name
            path.write_bytes(b"MZ" + name.encode() * 20)
            self.sources[name] = path
        self.archive = runtime_tools.build_archive(self.root / "bundle.zip", self.sources)
        self.directory = self.root / "installed"

    def test_verified_install_and_fast_reuse(self):
        installed = runtime_tools.install_tools(self.archive, directory=self.directory)
        for name, source in self.sources.items():
            self.assertEqual((installed / name).read_bytes(), source.read_bytes())
        with patch.object(runtime_tools, "_digest", side_effect=AssertionError("Do not rehash unchanged tools")):
            self.assertEqual(runtime_tools.install_tools(self.archive, directory=self.directory), installed)

    def test_corrupt_tool_is_repaired_even_when_size_did_not_change(self):
        installed = runtime_tools.install_tools(self.archive, directory=self.directory)
        target = installed / "ffmpeg.exe"
        target.write_bytes(b"X" * target.stat().st_size)
        runtime_tools.install_tools(self.archive, directory=self.directory)
        self.assertEqual(target.read_bytes(), self.sources["ffmpeg.exe"].read_bytes())

    def test_new_bundle_has_separate_directory(self):
        previous = runtime_tools.install_tools(self.archive, directory=self.directory)
        self.sources["deno.exe"].write_bytes(b"MZnew deno")
        runtime_tools.build_archive(self.archive, self.sources)
        current = runtime_tools.install_tools(self.archive, directory=self.directory)
        self.assertNotEqual(previous, current)
        self.assertTrue((previous / "deno.exe").is_file())

    def test_cancelled_install_creates_no_tools(self):
        cancel = threading.Event()
        cancel.set()
        with self.assertRaises(UpdateCancelled):
            runtime_tools.install_tools(self.archive, directory=self.directory, cancel_event=cancel)
        self.assertFalse(self.directory.exists())


class SettingsTests(unittest.TestCase):
    def test_invalid_settings_fall_back_without_overriding_valid_paths(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "settings.json"
            path.write_text(json.dumps({"quality": "invalid", "mode": "other", "height": [],
                                        "output": "C:/downloads", "cookies": "C:/cookies.txt"}), encoding="utf-8")
            settings = load_settings(path)
            self.assertEqual(settings["quality"], "192")
            self.assertEqual(settings["mode"], "audio")
            self.assertEqual(settings["output"], "C:/downloads")
            self.assertEqual(settings["cookies"], "C:/cookies.txt")
            path.write_text("broken", encoding="utf-8")
            self.assertEqual(load_settings(path)["height"], "1080")

    def test_unknown_data_is_not_saved(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "settings.json"
            settings = load_settings(path)
            settings["cookie_contents"] = "sensitive"
            save_settings(settings, path)
            self.assertNotIn("cookie_contents", json.loads(path.read_text(encoding="utf-8")))
