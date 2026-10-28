import json
import queue
import sys
import subprocess
import threading
import traceback
import time
import webbrowser
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from youtube_to_mp3 import (
    DownloadCancelled, DownloadError, QUALITIES, VIDEO_HEIGHTS,
    configure_bundled_ffmpeg, download_media, resource_path, update_engine,
)


from app_settings import load_settings, save_settings
from windows_icon import WindowsWindowIcon
from media_sources import SOURCE_HOME, detect_source, extract_media_links, is_supported_url


APP_NAME = "OneCorsair"
MAX_LOG_LINES = 800

I18N = {
    "en": {
        "language_button": "Русский",
        "links_hint": "YouTube · TikTok · Instagram. The site is detected automatically.",
        "activity": "Download activity",
        "settings_error": "Could not save preferences: ",
        "format_hint": "MP3 audio · MP4 video",
        "idle_detail": "Waiting for a link",
        "complete_detail": "Files are ready",
        "progress_detail": "{percent} · {speed}",
        "download": "↓ Download",
        "links": "Link",
        "detected_sources": "Detected: {sources}.",
        "save_to": "Save to",
        "browse": "Browse",
        "mode": "Format",
        "audio_mode": "Audio · MP3",
        "video_mode": "Video + audio · MP4",
        "quality": "MP3 bitrate",
        "video_quality": "Maximum resolution",
        "best_quality": "Best available",
        "update": "Update yt-dlp",
        "stop": "Stop",
        "clear_log": "Clear log",
        "ready": "Ready",
        "ready_log": "Paste links, choose MP3 or MP4 and a folder, then press Download. If needed, select cookies.txt.",
        "cookies_file": "cookies.txt (optional)",
        "choose_cookies": "Choose",
        "clear_cookies": "Clear",
        "cookies_help": "Cookies help",
        "cookies_help_title": "How to get cookies.txt",
        "choose_cookies_file": "Choose cookies.txt",
        "invalid_cookies": "The selected cookies.txt file does not exist. Choose an existing file or clear the field.",
        "cookies_help_text": "1. Open {site} in Chrome and sign in if needed.\n2. Install a cookies.txt exporter from the Chrome Web Store.\n3. Export cookies for that site in Netscape cookies.txt format.\n4. Press Choose beside cookies.txt and select the exported file.\n\nAfter closing this tip, the site and the extension store will open in your browser. Leave the cookies field empty to download without cookies.",
        "missing_links": "Paste at least one video link.",
        "missing_output": "Choose an output folder.",
        "choose_output": "Choose output folder",
        "downloading": "Downloading...",
        "starting": "Starting download...",
        "stopping": "Stopping...",
        "stopped": "Download stopped.",
        "done": "Done.",
        "download_error": "Download error: ",
        "bot_hint": "If the site requires confirmation or sign-in, choose cookies.txt exported from a signed-in session on that site. If a file is already selected, refresh it.",
        "unsupported_site": "Supported sites: YouTube, TikTok and Instagram.",
        "error": "Error:",
        "downloading_file": "Downloading",
        "processing_file": "Processing downloaded media...",
        "checking_update": "Checking the latest yt-dlp nightly release...",
        "installing_update": "Downloading yt-dlp {version} and checking SHA-256...",
        "engine_ready": "yt-dlp {version} is ready.",
        "update_unavailable": "Could not check/install the update: {error}. Using yt-dlp {version}.",
        "saved_file": "Saved: {filename}",
        "updating": "Updating yt-dlp...",
        "updated": "yt-dlp is ready.",
        "failed": "Finished with errors.",
        "built_in": "bundled version",
    },
    "ru": {
        "language_button": "English",
        "links_hint": "YouTube · TikTok · Instagram. Ресурс определяется автоматически.",
        "activity": "Ход скачивания",
        "settings_error": "Не удалось сохранить настройки: ",
        "format_hint": "MP3 — аудио · MP4 — видео",
        "idle_detail": "Ожидание ссылки",
        "complete_detail": "Файлы готовы",
        "progress_detail": "{percent} · {speed}",
        "download": "↓ Скачать",
        "links": "Ссылка",
        "detected_sources": "Ресурс: {sources}.",
        "save_to": "Сохранить в",
        "browse": "Обзор",
        "mode": "Формат",
        "audio_mode": "Аудио · MP3",
        "video_mode": "Видео со звуком · MP4",
        "quality": "Битрейт MP3",
        "video_quality": "Макс. разрешение",
        "best_quality": "Лучшее доступное",
        "update": "Обновить yt-dlp",
        "stop": "Остановить",
        "clear_log": "Очистить журнал",
        "ready": "Готово",
        "ready_log": "Вставьте ссылки, выберите MP3 или MP4 и папку, затем нажмите «Скачать». При необходимости выберите cookies.txt.",
        "cookies_file": "cookies.txt (необяз.)",
        "choose_cookies": "Выбрать",
        "clear_cookies": "Очистить",
        "cookies_help": "Помощь с cookies",
        "cookies_help_title": "Как получить cookies.txt",
        "choose_cookies_file": "Выберите cookies.txt",
        "invalid_cookies": "Выбранный файл cookies.txt не существует. Выберите существующий файл или очистите поле.",
        "cookies_help_text": "1. Откройте {site} в Chrome и при необходимости войдите в аккаунт.\n2. Установите расширение для экспорта cookies.txt из Chrome Web Store.\n3. Экспортируйте cookies именно этого сайта в формате Netscape cookies.txt.\n4. Нажмите «Выбрать» рядом с cookies.txt и укажите этот файл.\n\nПосле закрытия подсказки откроются сайт и магазин расширений. Для скачивания без cookies оставьте поле пустым.",
        "missing_links": "Вставьте хотя бы одну ссылку на видео.",
        "missing_output": "Выберите папку для сохранения.",
        "choose_output": "Выберите папку для сохранения",
        "downloading": "Скачивание...",
        "starting": "Запуск скачивания...",
        "stopping": "Остановка...",
        "stopped": "Скачивание остановлено.",
        "done": "Готово.",
        "download_error": "Ошибка скачивания: ",
        "bot_hint": "Если сервис требует подтверждение или вход, выберите cookies.txt из браузера с входом именно на этот сайт. Если файл уже выбран, обновите его.",
        "unsupported_site": "Поддерживаются ссылки YouTube, TikTok и Instagram.",
        "error": "Ошибка:",
        "downloading_file": "Скачивается",
        "processing_file": "Обработка скачанных файлов...",
        "checking_update": "Проверка последней версии yt-dlp nightly...",
        "installing_update": "Скачивание yt-dlp {version} и проверка SHA-256...",
        "engine_ready": "yt-dlp {version} готов к работе.",
        "update_unavailable": "Не удалось проверить/установить обновление: {error}. Используется yt-dlp {version}.",
        "saved_file": "Сохранено: {filename}",
        "updating": "Обновление yt-dlp...",
        "updated": "yt-dlp готов к работе.",
        "failed": "Завершено с ошибками.",
        "built_in": "встроенная версия",
    },
}

COLORS = {
    "bg": "#fff5f9",
    "panel": "#ffffff",
    "field": "#f8faff",
    "border": "#dce5f2",
    "text": "#203659",
    "muted": "#697b98",
    "accent": "#e62c54",
    "accent_hot": "#fa426b",
    "button": "#ffe8f0",
    "button_active": "#ffd5e4",
    "error": "#cd2548",
    "blue": "#2d61dd",
    "blue_soft": "#edf3ff",
    "pink": "#f9a2c3",
    "shadow": "#f0e5ed",
}

def enable_high_dpi():
    if sys.platform != "win32":
        return
    try:
        import ctypes

        try:
            # Let Windows report each monitor's actual scale to the native icon
            # loader instead of stretching a system-DPI bitmap on another screen.
            if ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4)):
                return
        except (AttributeError, OSError):
            pass
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except Exception:
            ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass


def desktop_work_area(window):
    """Keep the initial window inside the desktop area above the taskbar."""
    if sys.platform == "win32":
        try:
            import ctypes
            from ctypes import wintypes

            area = wintypes.RECT()
            if ctypes.windll.user32.SystemParametersInfoW(48, 0, ctypes.byref(area), 0):
                return area.left, area.top, area.right, area.bottom
        except (AttributeError, OSError):
            pass
    return 0, 0, window.winfo_screenwidth(), window.winfo_screenheight()


class GuiLogger:
    def __init__(self, log_queue):
        self.log_queue = log_queue

    def debug(self, message):
        pass

    def warning(self, message):
        self.log_queue.put(message + "\n")

    def error(self, message):
        self.log_queue.put(message + "\n")


class RoundedCard(tk.Canvas):
    """A light native Tk card; no web engine or extra UI dependency."""

    def __init__(self, parent, padding=20, **kwargs):
        super().__init__(parent, bg=COLORS["bg"], highlightthickness=0, borderwidth=0, **kwargs)
        self.padding = padding
        self.content = ttk.Frame(self, style="Panel.TFrame")
        self.window = self.create_window(padding, padding, anchor="nw", window=self.content)
        self.bind("<Configure>", self._resize)
        self.content.bind("<Configure>", self._content_size)
        self._natural_height = 0

    def _content_size(self, _event=None):
        height = self.content.winfo_reqheight() + self.padding * 2 + 4
        if height != self._natural_height:
            self._natural_height = height
            self.configure(height=height)

    def set_padding(self, padding):
        self.padding = padding
        self.coords(self.window, padding, padding)
        self._natural_height = 0
        self._content_size()
        self._resize()

    def _resize(self, event=None):
        width = event.width if event is not None else self.winfo_width()
        height = event.height if event is not None else self.winfo_height()
        self.itemconfigure(self.window, width=max(1, width - self.padding * 2),
                           height=max(1, height - self.padding * 2 - 4))
        self.delete("card")
        for x, y, right, bottom, color in (
            (2, 4, width - 2, height - 1, COLORS["shadow"]),
            (0, 0, width, height - 5, COLORS["panel"]),
        ):
            radius = min(22, max(2, min(right - x, bottom - y) / 4))
            points = (x + radius, y, right - radius, y, right, y, right, y + radius,
                      right, bottom - radius, right, bottom, right - radius, bottom,
                      x + radius, bottom, x, bottom, x, bottom - radius, x, y + radius, x, y)
            self.create_polygon(points, fill=color, outline="", smooth=True, splinesteps=24, tags="card")
        self.tag_lower("card")


class MP3ShipApp(tk.Tk):
    def __init__(self, settings_path=None):
        if sys.platform == "win32":
            try:
                import ctypes

                ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("OneCorsair.Downloader")
            except (AttributeError, OSError):
                pass
        super().__init__()
        self.withdraw()
        self.title(APP_NAME)
        left, top, right, bottom = desktop_work_area(self)
        width, height = min(800, right - left - 40), min(640, bottom - top - 60)
        self.minsize(min(740, width), min(620, height))
        self.geometry(f"{width}x{height}")
        self.configure(bg=COLORS["bg"])

        icon = resource_path("assets/download_icon.ico")
        self._native_icon = None
        if icon.exists():
            self.iconbitmap(default=str(icon))
            if sys.platform == "win32":
                self._native_icon = WindowsWindowIcon(icon)
        self._window_icon_sizes = []
        for size in (256, 128, 96, 64, 48, 40, 32, 28, 24, 20, 16):
            frame = resource_path(f"assets/window-icons/icon-{size}.png")
            if frame.exists():
                self._window_icon_sizes.append(tk.PhotoImage(file=str(frame)))
        if self._window_icon_sizes:
            self.iconphoto(True, *self._window_icon_sizes)

        self.settings_path = settings_path
        preferences = load_settings(settings_path)
        self.output_var = tk.StringVar(value=preferences["output"])
        self.quality_var = tk.StringVar(value=preferences["quality"])
        self.cookies_file_var = tk.StringVar(value=preferences["cookies"])
        self.mode = preferences["mode"]
        self.mode_var = tk.StringVar()
        self.height_var = tk.StringVar(value=preferences["height"])
        self.video_quality_var = tk.StringVar(value="1080p")
        self.closing = False
        self.language = preferences["language"]
        self.localized_widgets = []
        self.status_var = tk.StringVar()
        self.detail_var = tk.StringVar()
        self._progress_lock = threading.Lock()
        self._latest_progress = None
        self._settings_warning_shown = False
        self._log_lines = 0
        self.worker = None
        self.cancel_event = threading.Event()
        self.log_queue = queue.Queue()

        self._configure_style()
        self._bind_edit_shortcuts()
        self._build_ui()
        self._compact = None
        self.bind("<Configure>", self._resize_window, add="+")
        self.bind("<Configure>", self._refresh_native_icon, add="+")
        self.bind("<Map>", self._refresh_native_icon, add="+")
        self._apply_language(clear_log=True)
        self.update_idletasks()
        self._refresh_native_icon()
        self.geometry(f"+{left + (right - left - width) // 2}+{top + (bottom - top - height) // 2}")
        self.deiconify()
        self.after(100, self._drain_log_queue)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _refresh_native_icon(self, event=None):
        if self._native_icon is None or (event is not None and event.widget is not self):
            return
        try:
            self._native_icon.apply(int(self.wm_frame(), 16), force=event is not None and event.type == tk.EventType.Map)
        except (OSError, tk.TclError):
            # Keep Tk's bundled icon as a fallback if a native API is unavailable.
            pass

    def destroy(self):
        try:
            super().destroy()
        finally:
            if getattr(self, "_native_icon", None) is not None:
                self._native_icon.close()

    def t(self, key):
        return I18N[self.language][key]

    def _configure_style(self):
        self.style = ttk.Style(self)
        self.style.theme_use("clam")
        self.style.configure(".", background=COLORS["bg"], foreground=COLORS["text"], font=("Segoe UI", 10))
        for name, background in (("TFrame", COLORS["bg"]), ("Panel.TFrame", COLORS["panel"]),
                                 ("Soft.TFrame", COLORS["blue_soft"])):
            self.style.configure(name, background=background)
        self.style.configure("TLabel", background=COLORS["bg"], foreground=COLORS["text"])
        self.style.configure("Muted.TLabel", foreground=COLORS["muted"], background=COLORS["bg"])
        self.style.configure("Panel.TLabel", background=COLORS["panel"], foreground=COLORS["text"], font=("Segoe UI", 10, "bold"))
        self.style.configure("PanelMuted.TLabel", background=COLORS["panel"], foreground=COLORS["muted"], font=("Segoe UI", 9))
        self.style.configure("Activity.TLabel", background=COLORS["panel"], foreground=COLORS["blue"], font=("Segoe UI", 11, "bold"))
        self.style.configure("Badge.TLabel", background=COLORS["blue_soft"], foreground=COLORS["blue"], padding=(12, 6), font=("Segoe UI", 9, "bold"))
        self.style.configure("TButton", background=COLORS["button"], foreground=COLORS["accent"], borderwidth=0,
                             padding=(11, 6), font=("Segoe UI", 10, "bold"), focuscolor=COLORS["button"])
        self.style.map("TButton", background=[("disabled", "#f2edf2"), ("pressed", "#ffc5d8"), ("active", COLORS["button_active"])],
                       foreground=[("disabled", "#a49bac")])
        self.style.configure("Blue.TButton", background=COLORS["blue_soft"], foreground=COLORS["blue"])
        self.style.map("Blue.TButton", background=[("disabled", "#eef0f5"), ("active", "#dce8ff")],
                       foreground=[("disabled", "#a0acc1")])
        self.style.configure("Link.TButton", background=COLORS["panel"], foreground=COLORS["blue"], padding=(2, 4),
                             font=("Segoe UI", 9))
        self.style.map("Link.TButton", background=[("active", COLORS["blue_soft"])])
        self.style.configure("Accent.TButton", background=COLORS["accent"], foreground="#ffffff", padding=(20, 9),
                             font=("Segoe UI", 11, "bold"), focuscolor=COLORS["accent"])
        self.style.map("Accent.TButton", background=[("disabled", "#f1b4c5"), ("active", COLORS["accent_hot"]), ("pressed", "#c91c43")],
                       foreground=[("disabled", "#ffffff")])
        self.style.configure("TEntry", fieldbackground=COLORS["field"], foreground=COLORS["text"],
                             insertcolor=COLORS["blue"], bordercolor=COLORS["border"], lightcolor=COLORS["border"],
                             darkcolor=COLORS["border"], padding=(9, 6))
        self.style.map("TEntry", bordercolor=[("focus", COLORS["blue"])], fieldbackground=[("disabled", "#f2f4f8")])
        self.style.configure("TCombobox", fieldbackground=COLORS["field"], background=COLORS["field"],
                             foreground=COLORS["text"], arrowcolor=COLORS["blue"], bordercolor=COLORS["border"],
                             lightcolor=COLORS["border"], darkcolor=COLORS["border"], padding=(9, 6))
        self.style.map("TCombobox", fieldbackground=[("readonly", COLORS["field"]), ("disabled", "#f2f4f8")],
                       foreground=[("readonly", COLORS["text"]), ("disabled", COLORS["muted"])],
                       bordercolor=[("focus", COLORS["blue"])])
        self.style.configure("Horizontal.TProgressbar", background=COLORS["accent"], troughcolor=COLORS["blue_soft"],
                             bordercolor=COLORS["blue_soft"], lightcolor=COLORS["blue_soft"],
                             darkcolor=COLORS["blue_soft"], borderwidth=0, thickness=7)
        self.style.configure("Vertical.TScrollbar", background=COLORS["blue_soft"], troughcolor=COLORS["panel"],
                             arrowcolor=COLORS["blue"], bordercolor=COLORS["panel"], lightcolor=COLORS["panel"],
                             darkcolor=COLORS["panel"], borderwidth=0)
        self.style.map("Vertical.TScrollbar", background=[("active", "#dce8ff"), ("!active", COLORS["blue_soft"])])
        self.option_add("*TCombobox*Listbox.background", "#ffffff")
        self.option_add("*TCombobox*Listbox.foreground", COLORS["text"])
        self.option_add("*TCombobox*Listbox.selectBackground", COLORS["blue"])

    def _localized(self, parent, key, style="Panel.TLabel", **kwargs):
        widget = ttk.Label(parent, style=style, **kwargs)
        self.localized_widgets.append((widget, key))
        return widget

    def _build_ui(self):
        root = ttk.Frame(self, padding=(14, 12))
        self.root_frame = root
        root.pack(fill=tk.BOTH, expand=True)
        root.columnconfigure(0, weight=1)
        root.rowconfigure(2, weight=1)

        self.form_card = RoundedCard(root, padding=14)
        self.form_card.grid(row=0, column=0, sticky="ew")
        form = self.form_card.content
        form.columnconfigure(0, weight=1)
        form.columnconfigure(1, weight=1)

        self.links_label = self._localized(form, "links")
        self.links_label.grid(row=0, column=0, sticky="w", pady=(0, 4))
        self.language_button = ttk.Button(form, command=self._toggle_language, style="Link.TButton")
        self.language_button.grid(row=0, column=1, sticky="e", pady=(0, 4))
        self.localized_widgets.append((self.language_button, "language_button"))
        self.urls_text = tk.Text(form, height=2, wrap="word", undo=True, bg=COLORS["field"], fg=COLORS["text"],
                                insertbackground=COLORS["blue"], relief="flat", borderwidth=0,
                                highlightthickness=1, highlightbackground=COLORS["border"], highlightcolor=COLORS["blue"],
                                padx=10, pady=6, font=("Segoe UI", 10))
        self.urls_text.grid(row=1, column=0, columnspan=2, sticky="ew")
        self.links_hint_label = self._localized(form, "links_hint", "PanelMuted.TLabel")
        self.links_hint_label.grid(row=2, column=0, columnspan=2, sticky="w", pady=(3, 7))

        self.save_to_label = self._localized(form, "save_to")
        self.save_to_label.grid(row=3, column=0, columnspan=2, sticky="w", pady=(0, 4))
        destination = ttk.Frame(form, style="Panel.TFrame")
        self.destination_frame = destination
        destination.grid(row=4, column=0, columnspan=2, sticky="ew", pady=(0, 8))
        destination.columnconfigure(0, weight=1)
        self.output_entry = ttk.Entry(destination, textvariable=self.output_var)
        self.output_entry.grid(row=0, column=0, sticky="ew", padx=(0, 10))
        self.output_entry.bind("<FocusOut>", self._save_preferences)
        self.browse_button = ttk.Button(destination, command=self._choose_output, style="Blue.TButton")
        self.browse_button.grid(row=0, column=1)
        self.localized_widgets.append((self.browse_button, "browse"))

        self.mode_label = self._localized(form, "mode")
        self.mode_label.grid(row=5, column=0, sticky="w", pady=(0, 4))
        self.quality_label = ttk.Label(form, style="Panel.TLabel")
        self.quality_label.grid(row=5, column=1, sticky="w", padx=(12, 0), pady=(0, 4))
        self.mode_combo = ttk.Combobox(form, textvariable=self.mode_var, state="readonly", width=28)
        self.mode_combo.grid(row=6, column=0, sticky="ew", pady=(0, 8))
        self.mode_combo.bind("<<ComboboxSelected>>", self._change_mode)
        self.quality_combo = ttk.Combobox(form, textvariable=self.quality_var, values=QUALITIES, state="readonly", width=20)
        self.quality_combo.grid(row=6, column=1, sticky="ew", padx=(12, 0), pady=(0, 8))
        self.quality_combo.bind("<<ComboboxSelected>>", self._save_preferences)
        self.video_quality_combo = ttk.Combobox(form, textvariable=self.video_quality_var, state="readonly", width=20)
        self.video_quality_combo.grid(row=6, column=1, sticky="ew", padx=(12, 0), pady=(0, 8))
        self.video_quality_combo.bind("<<ComboboxSelected>>", self._change_video_quality)

        self.cookies_file_label = self._localized(form, "cookies_file")
        self.cookies_file_label.grid(row=7, column=0, columnspan=2, sticky="w", pady=(0, 4))
        cookie_row = ttk.Frame(form, style="Panel.TFrame")
        cookie_row.grid(row=8, column=0, columnspan=2, sticky="ew")
        cookie_row.columnconfigure(0, weight=1)
        self.cookies_entry = ttk.Entry(cookie_row, textvariable=self.cookies_file_var)
        self.cookies_entry.grid(row=0, column=0, sticky="ew", padx=(0, 10))
        self.cookies_entry.bind("<FocusOut>", self._save_preferences)
        self.choose_cookies_button = ttk.Button(cookie_row, command=self._choose_cookies_file, style="Blue.TButton")
        self.choose_cookies_button.grid(row=0, column=1, padx=(0, 6))
        self.localized_widgets.append((self.choose_cookies_button, "choose_cookies"))
        self.clear_cookies_button = ttk.Button(cookie_row, command=self._clear_cookies_file)
        self.clear_cookies_button.grid(row=0, column=2)
        self.localized_widgets.append((self.clear_cookies_button, "clear_cookies"))
        self.cookies_help_button = ttk.Button(form, command=self._show_cookies_help, style="Link.TButton")
        self.cookies_help_button.grid(row=9, column=0, columnspan=2, sticky="w", pady=(3, 0))
        self.localized_widgets.append((self.cookies_help_button, "cookies_help"))

        buttons = ttk.Frame(root)
        self.buttons_frame = buttons
        buttons.grid(row=1, column=0, sticky="ew", pady=8)
        buttons.columnconfigure(0, weight=1)
        self.status_label = ttk.Label(buttons, textvariable=self.status_var, style="Badge.TLabel")
        self.status_label.grid(row=0, column=0, sticky="w")
        self.update_button = ttk.Button(buttons, command=self._update_engine, style="Blue.TButton")
        self.update_button.grid(row=0, column=1, padx=(0, 8))
        self.localized_widgets.append((self.update_button, "update"))
        self.stop_button = ttk.Button(buttons, command=self._stop_download, state=tk.DISABLED)
        self.stop_button.grid(row=0, column=2, padx=(0, 8))
        self.localized_widgets.append((self.stop_button, "stop"))
        self.run_button = ttk.Button(buttons, command=self._run, style="Accent.TButton")
        self.run_button.grid(row=0, column=3)
        self.localized_widgets.append((self.run_button, "download"))

        self.activity_card = RoundedCard(root, padding=12)
        self.activity_card.grid(row=2, column=0, sticky="nsew")
        log_frame = self.activity_card.content
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(3, weight=1)
        self._localized(log_frame, "activity", "Activity.TLabel").grid(row=0, column=0, sticky="w")
        self.clear_button = ttk.Button(log_frame, command=self._clear_log, style="Link.TButton")
        self.clear_button.grid(row=0, column=1, sticky="e")
        self.localized_widgets.append((self.clear_button, "clear_log"))
        ttk.Label(log_frame, textvariable=self.detail_var, style="PanelMuted.TLabel").grid(row=1, column=0, columnspan=2, sticky="w", pady=(4, 7))
        self.progress = ttk.Progressbar(log_frame, mode="determinate", maximum=100)
        self.progress.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(0, 10))
        self.log = tk.Text(log_frame, height=6, wrap="word", undo=False, state=tk.DISABLED, bg=COLORS["panel"],
                           fg=COLORS["muted"], relief="flat", borderwidth=0, highlightthickness=0,
                           padx=0, pady=0, font=("Segoe UI", 9))
        self.log.tag_configure("error", foreground=COLORS["error"])
        self.log.tag_configure("success", foreground=COLORS["blue"])
        self.log.grid(row=3, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(log_frame, command=self.log.yview)
        scrollbar.grid(row=3, column=1, sticky="ns")
        self.log.configure(yscrollcommand=scrollbar.set)

    def _resize_window(self, event):
        if event.widget is not self:
            return
        compact = event.height < 680
        if compact == self._compact:
            return
        self._compact = compact
        self.urls_text.configure(height=2 if compact else 3)
        self.form_card.set_padding(14 if compact else 16)

    def _bind_edit_shortcuts(self):
        for sequence, handler in {
            "<Control-a>": self._select_all,
            "<Control-A>": self._select_all,
            "<Control-c>": self._copy,
            "<Control-C>": self._copy,
            "<Control-x>": self._cut,
            "<Control-X>": self._cut,
            "<Control-v>": self._paste,
            "<Control-V>": self._paste,
            "<Control-z>": self._undo,
            "<Control-Z>": self._undo,
            "<Shift-Insert>": self._paste,
        }.items():
            self.bind_all(sequence, handler, add="+")
        self.bind_all("<Control-KeyPress>", self._keycode_fallback, add="+")

    def _keycode_fallback(self, event):
        if not event.state & 0x4:
            return None
        keycode_map = {
            65: self._select_all,
            67: self._copy,
            86: self._paste,
            88: self._cut,
            90: self._undo,
        }
        handler = keycode_map.get(event.keycode)
        if handler:
            return handler(event)
        return None

    def _focused_edit_widget(self):
        widget = self.focus_get()
        if widget is not None and widget.winfo_class() in {"Entry", "TEntry", "Text", "TCombobox"}:
            return widget
        return None

    def _select_all(self, _event=None):
        widget = self._focused_edit_widget()
        if widget is None:
            return None
        if widget.winfo_class() == "Text":
            widget.tag_add("sel", "1.0", "end-1c")
        else:
            widget.selection_range(0, tk.END)
            widget.icursor(tk.END)
        return "break"

    def _copy(self, _event=None):
        widget = self._focused_edit_widget()
        if widget is None:
            return None
        try:
            if widget.winfo_class() == "Text":
                selected = widget.get("sel.first", "sel.last")
            else:
                selected = widget.selection_get()
            self.clipboard_clear()
            self.clipboard_append(selected)
            return "break"
        except tk.TclError:
            return None

    def _cut(self, _event=None):
        widget = self._focused_edit_widget()
        if widget is None:
            return None
        try:
            if widget.winfo_class() == "Text":
                selected = widget.get("sel.first", "sel.last")
                widget.delete("sel.first", "sel.last")
            else:
                selected = widget.selection_get()
                widget.delete("sel.first", "sel.last")
            self.clipboard_clear()
            self.clipboard_append(selected)
            return "break"
        except tk.TclError:
            return None

    def _paste(self, _event=None):
        widget = self._focused_edit_widget()
        if widget is None:
            return None
        try:
            text = self.clipboard_get()
            if widget.winfo_class() == "Text":
                try:
                    widget.delete("sel.first", "sel.last")
                except tk.TclError:
                    pass
                widget.insert(tk.INSERT, text)
            else:
                try:
                    widget.delete("sel.first", "sel.last")
                except tk.TclError:
                    pass
                widget.insert(tk.INSERT, text)
            return "break"
        except tk.TclError:
            return None

    def _undo(self, _event=None):
        return self._generate_edit_event("<<Undo>>")

    def _generate_edit_event(self, event_name):
        widget = self._focused_edit_widget()
        if widget is None:
            return None
        widget.event_generate(event_name)
        return "break"

    def _choose_output(self):
        path = filedialog.askdirectory(title=self.t("choose_output"))
        if path:
            self.output_var.set(path)
            self._save_preferences()

    def _choose_cookies_file(self):
        path = filedialog.askopenfilename(
            title=self.t("choose_cookies_file"),
            filetypes=[("cookies.txt", "*.txt"), ("All files", "*.*")],
        )
        if path:
            self.cookies_file_var.set(path)
            self._save_preferences()

    def _clear_cookies_file(self):
        self.cookies_file_var.set("")
        self._save_preferences()

    def _show_cookies_help(self):
        site = next((source for url in self._extract_urls() if (source := detect_source(url))), "YouTube")
        messagebox.showinfo(self.t("cookies_help_title"), self.t("cookies_help_text").format(site=site), parent=self)
        webbrowser.open(SOURCE_HOME[site])
        webbrowser.open("https://chromewebstore.google.com/search/cookies.txt")

    def _change_mode(self, _event=None):
        self.mode = "audio" if self.mode_combo.current() == 0 else "video"
        self._sync_format_controls()
        self._save_preferences()

    def _change_video_quality(self, _event=None):
        self.height_var.set(VIDEO_HEIGHTS[self.video_quality_combo.current()])
        self._save_preferences()

    def _sync_format_controls(self):
        self.mode_combo.configure(values=(self.t("audio_mode"), self.t("video_mode")))
        self.mode_combo.current(0 if self.mode == "audio" else 1)
        self.video_quality_combo.configure(values=(self.t("best_quality"), *(height + "p" for height in VIDEO_HEIGHTS[1:])))
        self.video_quality_combo.current(VIDEO_HEIGHTS.index(self.height_var.get()))
        self.quality_label.configure(text=self.t("quality" if self.mode == "audio" else "video_quality"))
        if self.mode == "audio":
            self.video_quality_combo.grid_remove()
            self.quality_combo.grid()
        else:
            self.quality_combo.grid_remove()
            self.video_quality_combo.grid()

    def _set_busy(self, status):
        self.run_button.configure(state=tk.DISABLED)
        self.update_button.configure(state=tk.DISABLED)
        self.mode_combo.configure(state=tk.DISABLED)
        self.quality_combo.configure(state=tk.DISABLED)
        self.video_quality_combo.configure(state=tk.DISABLED)
        self.stop_button.configure(state=tk.NORMAL)
        self.cancel_event.clear()
        self.urls_text.configure(state=tk.DISABLED)
        for widget in (self.output_entry, self.browse_button, self.cookies_entry, self.choose_cookies_button, self.clear_cookies_button):
            widget.configure(state=tk.DISABLED)
        with self._progress_lock:
            self._latest_progress = None
        self.progress.configure(mode="indeterminate", value=0)
        self.progress.start(18)
        self.detail_var.set(self.t(status))
        self.status_var.set(self.t(status))

    def _update_engine(self):
        if self.worker and self.worker.is_alive():
            return
        self._set_busy("updating")
        self.worker = threading.Thread(target=self._worker_update, daemon=True)
        self.worker.start()

    def _worker_update(self):
        outcome = "updated"
        try:
            update_engine(force=True, cancel_event=self.cancel_event, report=self._report)
        except DownloadCancelled:
            outcome = "stopped"
            self.log_queue.put(self.t("stopped") + "\n")
        except Exception as error:
            outcome = "failed"
            self.log_queue.put(self.t("error") + " " + str(error) + "\n")
        finally:
            self.log_queue.put(("__DONE__", outcome))

    def _report(self, key, **values):
        if values.get("version") == "bundled":
            values["version"] = self.t("built_in")
        self.log_queue.put(self.t(key).format(**values) + "\n")

    def _on_close(self):
        if not self.closing:
            self._save_preferences()
        self.closing = True
        if self.worker and self.worker.is_alive():
            self.cancel_event.set()
            self.status_var.set(self.t("stopping"))
            self.after(100, self._on_close)
        else:
            self.destroy()

    def _extract_urls(self):
        return extract_media_links(self.urls_text.get("1.0", tk.END))

    def _run(self):
        if self.worker and self.worker.is_alive():
            return
        urls = self._extract_urls()
        output = self.output_var.get().strip()
        if not urls:
            messagebox.showerror(APP_NAME, self.t("missing_links"))
            return
        if not all(is_supported_url(url) for url in urls):
            messagebox.showerror(APP_NAME, self.t("unsupported_site"))
            return
        if not output:
            messagebox.showerror(APP_NAME, self.t("missing_output"))
            return
        cookies_file = self.cookies_file_var.get().strip() or None
        if cookies_file and not Path(cookies_file).expanduser().is_file():
            messagebox.showerror(APP_NAME, self.t("invalid_cookies"))
            return

        self._save_preferences()
        self._set_busy("downloading")
        self._write_log("\n" + self.t("starting") + "\n")
        args = (urls, output, self.quality_var.get(), self.mode, self.height_var.get(), cookies_file)
        self.worker = threading.Thread(target=self._worker_run, args=args, daemon=True)
        self.worker.start()

    def _stop_download(self):
        if self.worker and self.worker.is_alive():
            self.cancel_event.set()
            self.status_var.set(self.t("stopping"))
            self._write_log("\n" + self.t("stopping") + "\n")
            self.stop_button.configure(state=tk.DISABLED)

    def _worker_run(self, urls, output, quality, mode, height, cookies_file=None):
        outcome = "done"
        try:
            download_media(
                urls, output, quality, mode=mode, height=height,
                cookies_file=cookies_file,
                progress_hooks=[self._progress_hook],
                logger=GuiLogger(self.log_queue),
                cancel_event=self.cancel_event,
                report=self._report,
            )
            self.log_queue.put("\n" + self.t("done") + "\n")
        except DownloadCancelled:
            outcome = "stopped"
            self.log_queue.put("\n" + self.t("stopped") + "\n")
        except DownloadError as error:
            outcome = "failed"
            message = str(error)
            self.log_queue.put("\n" + self.t("download_error") + message + "\n")
            if self._is_bot_check_error(message):
                self.log_queue.put(self.t("bot_hint") + "\n")
        except Exception:
            outcome = "failed"
            self.log_queue.put("\n" + self.t("error") + "\n" + traceback.format_exc())
        finally:
            self.log_queue.put(("__DONE__", outcome))

    def _progress_hook(self, info):
        if self.cancel_event.is_set():
            raise DownloadCancelled("Cancelled by user.")
        # Replace the last progress sample; never queue a log line for every chunk.
        with self._progress_lock:
            self._latest_progress = dict(info)

    def _apply_progress(self, info):
        if info.get("status") == "downloading":
            total = info.get("total_bytes") or info.get("total_bytes_estimate") or 0
            downloaded = info.get("downloaded_bytes") or 0
            if total:
                self.progress.stop()
                self.progress.configure(mode="determinate", value=min(100, downloaded * 100 / total))
            percent = f"{downloaded * 100 / total:.1f}%" if total else "…"
            speed = info.get("speed")
            speed_text = f"{speed / 1024 / 1024:.1f} MB/s" if speed else ""
            filename = Path(info.get("filename") or info.get("tmpfilename") or "").name
            self.detail_var.set(f"{filename[:70]}   {percent}   {speed_text}".strip())
        elif info.get("status") == "finished":
            self.progress.configure(mode="determinate", value=100)
            self.detail_var.set(self.t("processing_file"))

    def _drain_log_queue(self):
        with self._progress_lock:
            latest = self._latest_progress
            self._latest_progress = None
        if latest is not None:
            self._apply_progress(latest)
        deadline = time.monotonic() + 0.012
        messages = []
        try:
            for _ in range(200):
                item = self.log_queue.get_nowait()
                if isinstance(item, tuple) and item[0] == "__DONE__":
                    self.progress.stop()
                    self.run_button.configure(state=tk.NORMAL)
                    self.update_button.configure(state=tk.NORMAL)
                    self.mode_combo.configure(state="readonly")
                    self.quality_combo.configure(state="readonly")
                    self.video_quality_combo.configure(state="readonly")
                    self.urls_text.configure(state=tk.NORMAL)
                    for widget in (self.output_entry, self.browse_button, self.cookies_entry, self.choose_cookies_button, self.clear_cookies_button):
                        widget.configure(state=tk.NORMAL)
                    self.stop_button.configure(state=tk.DISABLED)
                    self.status_var.set(self.t(item[1]))
                    self.status_label.configure(foreground=COLORS["error"] if item[1] == "failed" else COLORS["blue"])
                    self.detail_var.set(self.t("complete_detail") if item[1] == "done" else self.t(item[1]))
                    self.progress.configure(mode="determinate", value=100 if item[1] == "done" else 0)
                    if item[1] == "done":
                        self.urls_text.delete("1.0", tk.END)
                else:
                    messages.append(item)
                if time.monotonic() >= deadline:
                    break
        except queue.Empty:
            pass
        if messages:
            self._write_log("".join(messages))
        if not self.closing:
            self.after(100, self._drain_log_queue)

    def _write_log(self, text):
        at_bottom = self.log.yview()[1] >= 0.98
        self.log.configure(state=tk.NORMAL)
        self.log.insert(tk.END, text)
        lines = int(self.log.index("end-1c").split(".")[0])
        if lines > MAX_LOG_LINES:
            self.log.delete("1.0", f"{lines - MAX_LOG_LINES + 1}.0")
        self.log.configure(state=tk.DISABLED)
        if at_bottom:
            self.log.see(tk.END)

    def _clear_log(self):
        self.log.configure(state=tk.NORMAL)
        self.log.delete("1.0", tk.END)
        self.log.configure(state=tk.DISABLED)

    def _save_preferences(self, _event=None):
        try:
            save_settings({
                "output": self.output_var.get(), "quality": self.quality_var.get(),
                "height": self.height_var.get(), "mode": self.mode,
                "language": self.language, "cookies": self.cookies_file_var.get(),
            }, self.settings_path)
        except OSError as error:
            if not self._settings_warning_shown:
                self._settings_warning_shown = True
                self.log_queue.put(self.t("settings_error") + str(error) + "\n")

    def _is_bot_check_error(self, message):
        lowered = message.lower()
        return any(hint in lowered for hint in ("not a bot", "sign in", "log in", "login", "cookies"))

    def _toggle_language(self):
        self.language = "en" if self.language == "ru" else "ru"
        self._apply_language(clear_log=False)
        self._save_preferences()

    def _apply_language(self, clear_log=False):
        self.title(APP_NAME)
        for widget, key in self.localized_widgets:
            widget.configure(text=self.t(key))
        self._sync_format_controls()
        if not self.worker or not self.worker.is_alive():
            self.status_var.set(self.t("ready"))
            self.detail_var.set(self.t("idle_detail"))
        if clear_log:
            self._clear_log()
            self._write_log(self.t("ready_log") + "\n")


def run_self_test(report_path):
    """Verify the packaged UI and binary dependencies without opening a window."""
    from youtube_to_mp3 import bundled_deno_path, bundled_engine_path, bundled_ffmpeg_dir

    results = {}
    app = None
    try:
        app = MP3ShipApp(settings_path=Path(report_path).with_suffix(".settings.json"))
        app.withdraw()
        app.mode_combo.current(1)
        app._change_mode()
        app._toggle_language()
        if app.mode != "video" or app.height_var.get() != "1080":
            raise RuntimeError("Format selection is not working.")
        results["ui"] = "ok"
        if sys.platform == "win32":
            native = app._native_icon
            hwnd = int(app.wm_frame(), 16)
            if native is None or not native._icons:
                raise RuntimeError("Native taskbar icons are missing.")
            if any(native.user.SendMessageW(hwnd, 0x7F, slot, 0) != handle
                   for slot, handle in enumerate(native._icons)):
                raise RuntimeError("Windows did not retain the native taskbar icons.")
            results["taskbar_icon"] = "native"
        ffmpeg_dir = bundled_ffmpeg_dir()
        binaries = {
            "yt-dlp": bundled_engine_path(), "deno": bundled_deno_path(),
            "ffmpeg": ffmpeg_dir / "ffmpeg.exe" if ffmpeg_dir else None,
            "ffprobe": ffmpeg_dir / "ffprobe.exe" if ffmpeg_dir else None,
        }
        for name, path in binaries.items():
            if path is None or not path.is_file():
                raise RuntimeError(f"Missing bundled {name}.")
            flag = "-version" if name in ("ffmpeg", "ffprobe") else "--version"
            result = subprocess.run([str(path), flag], capture_output=True, encoding="utf-8",
                                    errors="replace", timeout=30, check=True,
                                    creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0)
            results[name] = result.stdout.splitlines()[0]
        catalog = subprocess.run([str(binaries["yt-dlp"]), "--ignore-config", "--no-plugin-dirs", "--list-extractors"],
                                 capture_output=True, encoding="utf-8", errors="replace", timeout=30, check=True,
                                 creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0)
        names = {line.split(" ", 1)[0].casefold() for line in catalog.stdout.splitlines() if line}
        if not {"youtube", "tiktok", "instagram"}.issubset(names):
            raise RuntimeError("The bundled downloader does not support all three media sources.")
        results["sources"] = ["YouTube", "TikTok", "Instagram"]
        results["ok"] = True
    except Exception:
        results["ok"] = False
        results["error"] = traceback.format_exc()
    finally:
        if app is not None:
            for callback in app.tk.call("after", "info"):
                app.after_cancel(callback)
            app.destroy()
        Path(report_path).write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0 if results["ok"] else 1


if __name__ == "__main__":
    enable_high_dpi()
    if len(sys.argv) == 3 and sys.argv[1] == "--self-test":
        raise SystemExit(run_self_test(sys.argv[2]))
    else:
        app = MP3ShipApp()
        app.mainloop()
