import ctypes
import sys
import tempfile
import unittest
from ctypes import wintypes
from pathlib import Path


@unittest.skipUnless(sys.platform == "win32", "Native taskbar icons require Windows")
class NativeTaskbarIconTests(unittest.TestCase):
    def test_real_window_exposes_icons_large_enough_for_taskbar(self):
        from mp3_ship_gui import MP3ShipApp

        class IconInfo(ctypes.Structure):
            _fields_ = [("is_icon", wintypes.BOOL), ("x", wintypes.DWORD), ("y", wintypes.DWORD),
                        ("mask", wintypes.HANDLE), ("color", wintypes.HANDLE)]

        class Bitmap(ctypes.Structure):
            _fields_ = [("type", wintypes.LONG), ("width", wintypes.LONG), ("height", wintypes.LONG),
                        ("stride", wintypes.LONG), ("planes", wintypes.WORD), ("depth", wintypes.WORD),
                        ("bits", ctypes.c_void_p)]

        user = ctypes.WinDLL("user32", use_last_error=True)
        gdi = ctypes.WinDLL("gdi32", use_last_error=True)
        user.SendMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
        user.SendMessageW.restype = ctypes.c_ssize_t
        user.GetIconInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(IconInfo)]
        gdi.GetObjectW.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p]
        gdi.DeleteObject.argtypes = [wintypes.HANDLE]
        with tempfile.TemporaryDirectory() as temporary:
            app = MP3ShipApp(settings_path=Path(temporary) / "settings.json")
            try:
                app.withdraw()
                app.update_idletasks()
                hwnd = int(app.wm_frame(), 16)
                dimensions = []
                for slot in (0, 1):
                    # WM_GETICON must return a real per-window HICON, rather than
                    # forcing the shell to use Tk's small class icon as fallback.
                    handle = user.SendMessageW(hwnd, 0x7F, slot, 0)
                    self.assertTrue(handle, f"Missing native icon in slot {slot}")
                    info = IconInfo()
                    self.assertTrue(user.GetIconInfo(handle, ctypes.byref(info)))
                    try:
                        bitmap = Bitmap()
                        self.assertTrue(gdi.GetObjectW(info.color, ctypes.sizeof(bitmap), ctypes.byref(bitmap)))
                        self.assertEqual(bitmap.depth, 32)
                        self.assertEqual(bitmap.width, bitmap.height)
                        dimensions.append(bitmap.width)
                    finally:
                        gdi.DeleteObject(info.color)
                        gdi.DeleteObject(info.mask)
                self.assertGreaterEqual(dimensions[0], user.GetSystemMetrics(11))
                self.assertGreater(dimensions[1], dimensions[0])
            finally:
                for callback in app.tk.call("after", "info"):
                    app.after_cancel(callback)
                app.destroy()
