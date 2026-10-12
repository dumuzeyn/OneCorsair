"""Assign native Windows icons without upscaling Tk's 16-pixel class icon."""

import ctypes
from ctypes import wintypes


ICON_SIZES = (16, 20, 24, 28, 32, 40, 48, 64, 96, 128, 256)


def icon_sizes_for_taskbar(large_metric):
    """Keep both icon slots large enough for the taskbar at the current DPI."""
    def available_size(required):
        return next((size for size in ICON_SIZES if size >= required), ICON_SIZES[-1])

    return available_size(large_metric), available_size(large_metric * 2)


class WindowsWindowIcon:
    def __init__(self, path):
        self.path = str(path)
        self._icons = ()
        self._key = None
        self.user = ctypes.WinDLL("user32", use_last_error=True)
        self.user.LoadImageW.argtypes = [wintypes.HINSTANCE, wintypes.LPCWSTR, wintypes.UINT,
                                        ctypes.c_int, ctypes.c_int, wintypes.UINT]
        self.user.LoadImageW.restype = wintypes.HANDLE
        self.user.SendMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
        self.user.SendMessageW.restype = ctypes.c_ssize_t
        self.user.DestroyIcon.argtypes = [wintypes.HANDLE]
        self.user.DestroyIcon.restype = wintypes.BOOL
        if hasattr(self.user, "GetDpiForWindow"):
            self.user.GetDpiForWindow.argtypes = [wintypes.HWND]
            self.user.GetDpiForWindow.restype = wintypes.UINT
        if hasattr(self.user, "GetSystemMetricsForDpi"):
            self.user.GetSystemMetricsForDpi.argtypes = [ctypes.c_int, wintypes.UINT]
            self.user.GetSystemMetricsForDpi.restype = ctypes.c_int

    def apply(self, hwnd, force=False):
        dpi = self.user.GetDpiForWindow(hwnd) if hasattr(self.user, "GetDpiForWindow") else 96
        dpi = dpi or 96
        key = (hwnd, dpi)
        if key == self._key and not force:
            return
        if key != self._key:
            metric = (self.user.GetSystemMetricsForDpi(11, dpi)
                      if hasattr(self.user, "GetSystemMetricsForDpi") else self.user.GetSystemMetrics(11))
            icons = []
            try:
                for size in icon_sizes_for_taskbar(metric):
                    # IMAGE_ICON, LR_LOADFROMFILE: Windows loads the matching ICO
                    # frame directly, including its alpha channel.
                    handle = self.user.LoadImageW(None, self.path, 1, size, size, 0x10)
                    if not handle:
                        raise ctypes.WinError(ctypes.get_last_error())
                    icons.append(handle)
            except OSError:
                for handle in icons:
                    self.user.DestroyIcon(handle)
                raise
            previous = self._icons
            self._icons = tuple(icons)
            self._key = key
        else:
            previous = ()
        # WM_SETICON: explicitly set the root window's small and large slots.
        # The smaller slot may also be used by the taskbar, so it must not be 16px.
        for slot, handle in enumerate(self._icons):
            self.user.SendMessageW(hwnd, 0x80, slot, handle)
        for handle in previous:
            self.user.DestroyIcon(handle)

    def close(self):
        """Release owned handles after the Tk window has been destroyed."""
        for handle in self._icons:
            self.user.DestroyIcon(handle)
        self._icons = ()
        self._key = None
