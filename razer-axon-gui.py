#!/usr/bin/env python3
"""
Razer Axon GUI — native GTK4/Adwaita wallpaper browser.

Browse, download, and apply Razer Axon wallpapers on Linux.
Supports KDE Plasma, GNOME, and other DEs.
"""

import hashlib
import hmac
import json
import logging
import os
import shutil
import subprocess
import sys
import threading
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path, PureWindowsPath

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, GdkPixbuf, Gio, GLib, Gtk

log = logging.getLogger(__name__)

API_BASE = "https://axon-api.razer.com/v1"
API_VERSION = "2.6.2.0"
HMAC_KEY = b"j6l-aUmhCc@tN%T_"

CONFIG_DIR = Path(os.environ.get("RAZER_AXON_DIR", Path.home() / ".config/razer-axon"))
TOKEN_FILE = CONFIG_DIR / "token.json"
SETTINGS_FILE = CONFIG_DIR / "settings.json"
CACHE_DIR = CONFIG_DIR / "cache"
DOWNLOAD_DIR = Path.home() / "RazerAxonWallpapers"

_WINE_TOKEN = (Path(os.environ.get("WINEPREFIX", Path.home() / ".wine"))
               / "drive_c/users" / os.environ.get("USER", "user")
               / "AppData/Local/Razer/RazerAxon/wine_login_token.json")
if not TOKEN_FILE.exists() and _WINE_TOKEN.exists():
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copy2(_WINE_TOKEN, TOKEN_FILE)


# ── Localization ─────────────────────────────────────────────────────

STRINGS = {
    "en": {
        "gallery": "GALLERY", "create": "CREATE", "community": "COMMUNITY", "library": "LIBRARY",
        "wallpapers": "WALLPAPERS", "series": "SERIES", "authors": "AUTHORS",
        "audio": "Audio", "favorites": "Favorites", "ai": "AI",
        "dynamic": "Dynamic", "static": "Static", "interactive": "Interactive",
        "clear": "CLEAR", "search": "Search wallpapers...", "all": "All",
        "download": "Download", "apply": "Apply", "retry": "Retry",
        "load_more": "Load more", "remaining": "remaining",
        "loading": "Loading...", "failed": "Failed to load",
        "downloaded": "Downloaded", "applied": "Applied", "failed_apply": "Failed to apply",
        "no_library": "No downloaded wallpapers yet.\nUse Gallery to download.",
        "coming_soon": "Coming soon", "settings": "Settings", "language": "Language",
        "not_logged_in": "Not logged in", "run_login": "Run razer-login first to authenticate.",
        "login_failed": "Login failed", "token_expired": "Token may be expired. Run razer-login to refresh.",
        "installed": "Installed! Razer Axon should appear in your app menu.",
        "uninstalled": "Uninstalled.", "installing": "Installing Razer Axon...",
        "uninstalling": "Uninstalling Razer Axon...",
        "connecting": "Connecting...", "extracting": "Extracting...", "applying": "Applying...",
        "artist_prefix": "Artist",
    },
    "ru": {
        "gallery": "ГАЛЕРЕЯ", "create": "СОЗДАТЬ", "community": "СООБЩЕСТВО", "library": "БИБЛИОТЕКА",
        "wallpapers": "ОБОИ", "series": "СЕРИЯ", "authors": "АВТОРЫ",
        "audio": "Со звуком", "favorites": "Избранное", "ai": "ИИ-обои",
        "dynamic": "Динамические", "static": "Статичные", "interactive": "Интерактивные",
        "clear": "ОЧИСТИТЬ", "search": "Поиск обоев...", "all": "Все",
        "download": "Скачать", "apply": "Применить", "retry": "Повторить",
        "load_more": "Загрузить ещё", "remaining": "осталось",
        "loading": "Загрузка...", "failed": "Ошибка загрузки",
        "downloaded": "Скачано", "applied": "Применено", "failed_apply": "Не удалось применить",
        "no_library": "Нет скачанных обоев.\nИспользуйте Галерею для скачивания.",
        "coming_soon": "Скоро", "settings": "Настройки", "language": "Язык",
        "not_logged_in": "Не авторизован", "run_login": "Сначала запустите razer-login для авторизации.",
        "login_failed": "Ошибка входа", "token_expired": "Токен истёк. Запустите razer-login для обновления.",
        "installed": "Установлено! Razer Axon должен появиться в меню приложений.",
        "uninstalled": "Удалено.", "installing": "Установка Razer Axon...",
        "uninstalling": "Удаление Razer Axon...",
        "connecting": "Подключение...", "extracting": "Извлечение...", "applying": "Применение...",
        "artist_prefix": "Автор",
    },
}


def _detect_lang() -> str:
    """Auto-detect language from system locale."""
    lang = os.environ.get("LANG", "") + os.environ.get("LANGUAGE", "")
    return "ru" if "ru" in lang.lower() else "en"


def _load_settings() -> dict:
    if SETTINGS_FILE.exists():
        try:
            return json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _save_settings(settings: dict):
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    SETTINGS_FILE.write_text(json.dumps(settings, indent=2, ensure_ascii=False), encoding="utf-8")


def _get_lang() -> str:
    settings = _load_settings()
    return settings.get("language", _detect_lang())


def tr(key: str) -> str:
    """Get translated string."""
    lang = _get_lang()
    return STRINGS.get(lang, STRINGS["en"]).get(key, STRINGS["en"].get(key, key))


# ── API helpers ──────────────────────────────────────────────────────

def load_token() -> dict:
    if TOKEN_FILE.exists():
        return json.loads(TOKEN_FILE.read_text(encoding="utf-8"))
    return {}


def api_get(endpoint: str, params: dict, auth: str = "") -> dict | None:
    url = f"{API_BASE}/{endpoint}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    headers = {"Content-Type": "application/json", "X-Version": API_VERSION, "X-Language": "en"}
    if auth:
        headers["Authorization"] = auth
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read())
    except Exception:
        return None


def api_login(token_data: dict) -> tuple[str, str, str]:
    """Returns (auth, user_id, country) or empty strings."""
    body = json.dumps({
        "token": token_data.get("token", ""),
        "is_guest": str(token_data.get("isGuest", False)).lower(),
        "uuid": token_data.get("uuid", ""),
    }).encode()
    headers = {"Content-Type": "application/json", "X-Version": API_VERSION, "X-Language": "en"}
    req = urllib.request.Request(f"{API_BASE}/login", data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            r = json.loads(resp.read())
            if r.get("code") == 200:
                d = r["data"]
                return d["authorization"], str(d.get("user_id", "")), d.get("country", "")
    except Exception:
        pass
    return "", "", ""


def hmac_request(endpoint: str, params: dict, uuid: str, is_guest: bool,
                 method: str = "GET") -> dict | None:
    url = f"{API_BASE}/{endpoint}"
    sorted_params = sorted(params.items(), key=lambda x: x[0])
    raw_qs = "&".join(f"{k}={v}" for k, v in sorted_params)
    auth_hash = hmac.new(HMAC_KEY, raw_qs.encode(), hashlib.sha256).hexdigest()
    encoded_qs = "&".join(f"{k}={urllib.parse.quote(str(v), safe='')}" for k, v in sorted_params)

    headers = {
        "UserID": uuid, "Authorization": auth_hash,
        "Isguest": "true" if is_guest else "false",
        "Token": "", "accept": "text/json, application/json",
    }
    if method == "GET":
        url = f"{url}?{encoded_qs}"
        data = None
    else:
        data = encoded_qs.encode()
        headers["Content-Type"] = "application/x-www-form-urlencoded"

    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read())
    except Exception:
        return None


def download_thumbnail(url: str, wallpaper_id: str) -> Path | None:
    """Download and cache a thumbnail image."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    ext = ".jpg"
    if ".webp" in url:
        ext = ".webp"
    elif ".png" in url:
        ext = ".png"
    cached = CACHE_DIR / f"{wallpaper_id}_thumb{ext}"
    if cached.exists() and cached.stat().st_size > 0:
        return cached
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "RazerAxon/2.6.2.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            cached.write_bytes(resp.read())
        return cached
    except Exception:
        return None


def detect_de() -> str:
    de = os.environ.get("XDG_CURRENT_DESKTOP", "").lower()
    if "kde" in de or "plasma" in de:
        return "kde"
    if "gnome" in de:
        return "gnome"
    if "xfce" in de:
        return "xfce"
    if "hyprland" in de:
        return "hyprland"
    if "sway" in de:
        return "sway"
    return de or "generic"


def detect_session() -> str:
    return os.environ.get("XDG_SESSION_TYPE", "x11").lower()


def apply_wallpaper(path: str, is_video: bool = False) -> bool:
    """Apply wallpaper via openaxon-player daemon. Falls back to direct apply."""
    import socket as _socket

    sock_path = CONFIG_DIR / "player.sock"
    media_type = "Video" if is_video else "Image"

    # Try daemon first
    try:
        sock = _socket.socket(_socket.AF_UNIX, _socket.SOCK_STREAM)
        sock.connect(str(sock_path))
        cmd = json.dumps({"Command": "Play", "Type": media_type,
                          "Source": str(Path(path).resolve())}) + "\n"
        sock.sendall(cmd.encode())
        resp = sock.recv(4096).decode().strip()
        sock.close()
        result = json.loads(resp) if resp else {}
        if result.get("ok"):
            return True
    except (ConnectionRefusedError, FileNotFoundError, OSError):
        pass  # daemon not running, fall through to direct apply

    # Direct fallback (no daemon)
    return _apply_wallpaper_direct(path, is_video)


def _apply_wallpaper_direct(path: str, is_video: bool = False) -> bool:
    """Direct wallpaper apply without daemon. Supports KDE, GNOME, Wayland, X11."""
    de = detect_de()
    session = detect_session()

    if is_video:
        if session == "wayland":
            if shutil.which("mpvpaper"):
                subprocess.Popen(
                    ["mpvpaper", "-o", "no-audio loop", "*", path],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return True
        else:
            if shutil.which("xwinwrap") and shutil.which("mpv"):
                subprocess.Popen(
                    ["xwinwrap", "-g", "1920x1080+0+0", "-ov", "-ni", "-s",
                     "-nf", "-b", "-un", "-argb", "--",
                     "mpv", "--wid", "WID", "--no-audio", "--loop",
                     "--no-osc", "--no-input-default-bindings", path],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return True
        return False

    if de == "kde":
        if shutil.which("plasma-apply-wallpaperimage"):
            r = subprocess.run(["plasma-apply-wallpaperimage", path], capture_output=True)
            return r.returncode == 0
        if shutil.which("qdbus"):
            script = f'''
                var a = desktops();
                for (var i = 0; i < a.length; i++) {{
                    a[i].wallpaperPlugin = "org.kde.image";
                    a[i].currentConfigGroup = ["Wallpaper", "org.kde.image", "General"];
                    a[i].writeConfig("Image", "file://{path}");
                }}
            '''
            r = subprocess.run(
                ["qdbus", "org.kde.plasmashell", "/PlasmaShell",
                 "org.kde.PlasmaShell.evaluateScript", script],
                capture_output=True)
            return r.returncode == 0
    elif de == "gnome":
        uri = f"file://{path}"
        subprocess.run(["gsettings", "set", "org.gnome.desktop.background",
                       "picture-uri", uri], capture_output=True)
        subprocess.run(["gsettings", "set", "org.gnome.desktop.background",
                       "picture-uri-dark", uri], capture_output=True)
        return True
    elif de == "xfce":
        subprocess.run(["xfconf-query", "-c", "xfce4-desktop", "-p",
                       "/backdrop/screen0/monitor0/workspace0/last-image",
                       "-s", path], capture_output=True)
        return True

    if shutil.which("feh"):
        subprocess.run(["feh", "--bg-fill", path], capture_output=True)
        return True
    return False


# ── Wallpaper card widget ────────────────────────────────────────────

class WallpaperCard(Gtk.Box):
    """Card matching original Axon design: thumbnail, icon row, title, author."""

    def __init__(self, wp_data: dict, app: "AxonApp"):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.wp = wp_data
        self.app = app
        self.add_css_class("axon-card")
        self.set_size_request(200, -1)

        # Thumbnail
        self.picture = Gtk.Picture()
        self.picture.set_content_fit(Gtk.ContentFit.COVER)
        self.picture.set_size_request(200, 112)
        overlay = Gtk.Overlay()
        overlay.set_child(self.picture)

        # Hover overlay with Download button (hidden by default)
        self._hover_box = Gtk.Box()
        self._hover_box.set_halign(Gtk.Align.CENTER)
        self._hover_box.set_valign(Gtk.Align.CENTER)
        self._hover_box.set_visible(False)
        dl_btn = Gtk.Button(label=tr("download"))
        dl_btn.add_css_class("axon-dl-btn")
        self._dl_handler = dl_btn.connect("clicked", self._on_download)
        self._dl_btn = dl_btn
        self._media_path = ""
        self._hover_box.append(dl_btn)

        # Progress bar (hidden)
        self.progress = Gtk.ProgressBar()
        self.progress.set_visible(False)
        self.progress.set_hexpand(True)
        self.progress.add_css_class("axon-progress")
        self.progress.set_valign(Gtk.Align.END)
        self.progress.set_margin_bottom(4)
        self.progress.set_margin_start(4)
        self.progress.set_margin_end(4)

        overlay.add_overlay(self._hover_box)
        overlay.add_overlay(self.progress)

        # Hover detection
        hover = Gtk.EventControllerMotion()
        hover.connect("enter", lambda *a: self._hover_box.set_visible(True))
        hover.connect("leave", lambda *a: self._hover_box.set_visible(False))
        overlay.add_controller(hover)

        # Click on thumbnail → detail dialog
        click = Gtk.GestureClick()
        click.connect("released", self._on_thumb_click)
        overlay.add_controller(click)
        overlay.set_cursor(Gdk.Cursor.new_from_name("pointer"))

        self.append(overlay)

        # Icon row (play, audio, chroma icons — like original)
        icon_row = Gtk.Box(spacing=4)
        icon_row.set_margin_start(4)
        icon_row.set_margin_top(4)

        wp_type = wp_data.get("type", "")
        audible = wp_data.get("audible", "0") == "1"
        chroma = bool(wp_data.get("chroma_support", 0))
        resolutions = wp_data.get("resolutions", "")

        if wp_type == "VIDEO":
            icon_row.append(self._make_icon("media-playback-start-symbolic"))
        if audible:
            icon_row.append(self._make_icon("audio-volume-high-symbolic"))
        if chroma or (isinstance(resolutions, str) and resolutions):
            icon_row.append(self._make_icon("preferences-color-symbolic"))

        self.append(icon_row)

        # Title
        title = Gtk.Label(label=wp_data.get("title", "?"))
        title.set_xalign(0)
        title.set_ellipsize(3)
        title.add_css_class("axon-title")
        title.set_margin_start(4)
        title.set_margin_end(4)
        self.append(title)

        # Author
        author = wp_data.get("author_name", "")
        if author:
            auth_label = Gtk.Label(label=author)
            auth_label.set_xalign(0)
            auth_label.add_css_class("axon-author")
            auth_label.set_ellipsize(3)
            auth_label.set_margin_start(4)
            auth_label.set_margin_bottom(6)
            self.append(auth_label)

        # Load thumbnail async
        thumb_url = wp_data.get("thumbnail", "")
        if thumb_url:
            threading.Thread(target=self._load_thumb, args=(thumb_url,), daemon=True).start()

    @staticmethod
    def _make_icon(icon_name: str) -> Gtk.Image:
        img = Gtk.Image.new_from_icon_name(icon_name)
        img.set_pixel_size(14)
        img.add_css_class("axon-card-icon")
        return img

    def _load_thumb(self, url: str):
        wid = self.wp.get("wallpaper_id", "")
        path = download_thumbnail(url, wid)
        if path:
            GLib.idle_add(self._set_thumb, str(path))

    def _set_thumb(self, path: str):
        try:
            self.picture.set_filename(path)
        except Exception:
            pass

    def _on_download(self, btn):
        print(f"[download] clicked for {self.wp.get('wallpaper_id')}", flush=True)
        btn.set_visible(False)
        self.progress.set_visible(True)
        self.progress.set_fraction(0)
        self.progress.set_text(tr("connecting"))
        self.progress.set_show_text(True)
        threading.Thread(target=self._do_download, args=(btn,), daemon=True).start()

    def _update_progress(self, fraction: float, text: str = ""):
        self.progress.set_fraction(fraction)
        if text:
            self.progress.set_text(text)

    def _do_download(self, btn):
        wid = self.wp["wallpaper_id"]
        token_data = load_token()
        uuid = token_data.get("uuid", "")
        is_guest = token_data.get("isGuest", False)

        # Get detail for resolutions
        detail = api_get("wallpaper/detail", {"wallpaper_id": wid}, auth=self.app.auth)
        if not detail or detail.get("code") != 200:
            GLib.idle_add(self._dl_done, btn, False, "")
            return

        resolutions = detail["data"].get("resolution", [])
        # Pick highest resolution
        best = resolutions[-1] if resolutions else {"width": 1920, "height": 1080}
        w, h = best.get("width", 1920), best.get("height", 1080)

        # Get download URL
        resp = hmac_request("wallpaper/resource", {
            "wallpaper_id": wid, "width": str(w), "height": str(h), "resource_type": "0",
        }, uuid, is_guest)

        if not resp or resp.get("code") != 200:
            GLib.idle_add(self._dl_done, btn, False, "")
            return

        dl_url = resp["data"]["resource"]
        resource_id = resp["data"].get("resource_id", "")

        # Download with progress
        wp_dir = DOWNLOAD_DIR / wid
        wp_dir.mkdir(parents=True, exist_ok=True)
        zip_path = wp_dir / f"{w}x{h}.zip"

        try:
            req = urllib.request.Request(dl_url)
            with urllib.request.urlopen(req, timeout=300) as r:
                total = int(r.headers.get("Content-Length", 0))
                downloaded = 0
                with open(zip_path, "wb") as f:
                    while chunk := r.read(256 * 1024):
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total > 0:
                            frac = downloaded / total
                            mb = downloaded / 1024 / 1024
                            total_mb = total / 1024 / 1024
                            GLib.idle_add(self._update_progress, frac,
                                          f"{mb:.1f}/{total_mb:.1f} MB")
        except Exception:
            GLib.idle_add(self._dl_done, btn, False, "")
            return

        GLib.idle_add(self._update_progress, 1.0, "Extracting...")

        # Extract & decrypt
        extracted_media = ""
        try:
            if zipfile.is_zipfile(zip_path):
                with zipfile.ZipFile(zip_path) as zf:
                    zf.extractall(wp_dir)

            config_path = wp_dir / "ResourceConfig.txt"
            if config_path.exists():
                try:
                    sys.path.insert(0, str(Path(__file__).parent))
                    from axon import parse_resource_config, derive_password, extract
                    parsed = parse_resource_config(config_path)
                    if parsed:
                        content, config = parsed
                        source_str = config.get("Source", "")
                        if source_str and config.get("SourceEncryptedTypes", "").upper() == "ZIP":
                            source = PureWindowsPath(source_str)
                            archive = wp_dir / Path(*source.parts)
                            if archive.exists():
                                password = derive_password(content)
                                extract_dir = wp_dir / "Extracted"
                                extract(archive, password, extract_dir)
                                for f in extract_dir.rglob("*"):
                                    if f.suffix.lower() in (".mp4", ".webm", ".jpg", ".png"):
                                        extracted_media = str(f)
                                        break
                except ImportError:
                    pass
        except Exception:
            pass

        # Report download
        try:
            hmac_request("wallpaper/downloaded", {
                "wallpaper_id": wid, "resource_id": resource_id,
            }, uuid, is_guest, method="POST")
        except Exception:
            pass

        GLib.idle_add(self._dl_done, btn, True, extracted_media)

    def _dl_done(self, btn, success: bool, media_path: str):
        self.progress.set_visible(False)
        btn.set_visible(True)
        if success:
            self._media_path = media_path
            btn.set_label(tr("apply"))
            btn.remove_css_class("axon-dl-btn")
            btn.add_css_class("axon-apply-btn")
            btn.set_sensitive(True)
            btn.disconnect(self._dl_handler)
            self._dl_handler = btn.connect("clicked", self._on_apply)
            self.app.toast(f"{tr("downloaded")}: {self.wp.get('title', '?')}")
        else:
            btn.set_label(tr("retry"))
            btn.set_sensitive(True)
            btn.add_css_class("destructive-action")

    def _on_apply(self, btn):
        path = self._media_path
        print(f"[apply] path={path}", flush=True)
        if not path:
            self.app.toast(tr("failed_apply"))
            return
        is_video = path.lower().endswith((".mp4", ".webm"))
        print(f"[apply] is_video={is_video}, calling apply_wallpaper...", flush=True)
        result = apply_wallpaper(path, is_video=is_video)
        print(f"[apply] result={result}", flush=True)
        if result:
            self.app.toast(f"{tr("applied")}: {self.wp.get('title', '?')}")
        else:
            self.app.toast(tr("failed_apply"))

    def _on_thumb_click(self, gesture, n_press, x, y):
        if n_press == 1:
            DetailDialog(self.wp, self.app).show()

    def _on_fav(self, btn):
        fav = self.wp.get("is_favorite", 0)
        action = "cancel" if fav else "add"
        threading.Thread(target=self._do_fav, args=(action, btn), daemon=True).start()

    def _do_fav(self, action: str, btn):
        wid = self.wp["wallpaper_id"]
        resp = api_get(f"wallpaper/favorite/{action}", {}, auth="")
        # Use the web API with auth
        url = f"{API_BASE}/wallpaper/favorite/{action}"
        body = json.dumps({"wallpaper_id": wid}).encode()
        headers = {"Content-Type": "application/json", "X-Version": API_VERSION,
                    "X-Language": "en", "Authorization": self.app.auth}
        req = urllib.request.Request(url, data=body, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                r = json.loads(resp.read())
                if r.get("code") == 200:
                    new_fav = action == "add"
                    self.wp["is_favorite"] = 1 if new_fav else 0
                    GLib.idle_add(btn.set_icon_name,
                                  "starred-symbolic" if new_fav else "non-starred-symbolic")
        except Exception:
            pass


# ── Detail dialog ────────────────────────────────────────────────────

class DetailDialog:
    """Full-screen detail view with large preview, info, and resolution picker."""

    def __init__(self, wp_data: dict, app: "AxonApp"):
        self.wp = wp_data
        self.app = app
        self._detail = None
        self._selected_res = ""

    def show(self):
        threading.Thread(target=self._load_detail, daemon=True).start()

    def _load_detail(self):
        wid = self.wp["wallpaper_id"]
        resp = api_get("wallpaper/detail", {"wallpaper_id": wid}, auth=self.app.auth)
        if resp and resp.get("code") == 200:
            self._detail = resp["data"]
            GLib.idle_add(self._build_dialog)
        else:
            GLib.idle_add(lambda: self.app.toast("Failed to load details"))

    def _build_dialog(self):
        d = self._detail
        wid = d.get("wallpaper_id", "")
        title = d.get("title", "?")
        author_info = d.get("author", {})
        author = author_info.get("author_name", "")
        resolutions = d.get("resolution", [])
        tags = d.get("all_tags", "")
        downloads = d.get("downloads", 0)
        wp_type = d.get("type", "")
        effect = d.get("effect_type", "")
        audible = d.get("audible", "0") == "1"
        chroma = bool(d.get("chroma_support", 0))
        preview_url = d.get("preview_pic", "") or d.get("thumbnail", "")

        dialog = Adw.Dialog()
        dialog.set_title(title)
        dialog.set_content_width(700)
        dialog.set_content_height(600)

        toolbar = Adw.ToolbarView()
        header = Adw.HeaderBar()
        toolbar.add_top_bar(header)

        scroll = Gtk.ScrolledWindow(vexpand=True)
        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        content.set_margin_start(16)
        content.set_margin_end(16)
        content.set_margin_top(8)
        content.set_margin_bottom(16)

        # Large preview
        self.preview_pic = Gtk.Picture()
        self.preview_pic.set_content_fit(Gtk.ContentFit.CONTAIN)
        self.preview_pic.set_size_request(-1, 350)
        preview_frame = Gtk.Frame()
        preview_frame.set_child(self.preview_pic)
        content.append(preview_frame)

        # Load preview async
        if preview_url:
            threading.Thread(target=self._load_preview, args=(preview_url, wid), daemon=True).start()

        # Title + Author
        title_label = Gtk.Label(label=title)
        title_label.add_css_class("title-1")
        title_label.set_xalign(0)
        content.append(title_label)

        if author:
            author_label = Gtk.Label(label=f"by {author}")
            author_label.add_css_class("dim-label")
            author_label.set_xalign(0)
            content.append(author_label)

        # Info chips
        chips = Gtk.FlowBox()
        chips.set_selection_mode(Gtk.SelectionMode.NONE)
        chips.set_max_children_per_line(10)
        chips.set_row_spacing(4)
        chips.set_column_spacing(4)

        for label_text in [
            f"{wp_type} ({effect})",
            f"{downloads:,} downloads",
            *(([f"Audio"]) if audible else []),
            *(([f"Chroma"]) if chroma else []),
        ]:
            chip = Gtk.Label(label=label_text)
            chip.add_css_class("caption")
            chip.add_css_class("card")
            chip.set_margin_start(6)
            chip.set_margin_end(6)
            chip.set_margin_top(2)
            chip.set_margin_bottom(2)
            chips.append(chip)

        content.append(chips)

        if tags:
            tags_label = Gtk.Label(label=tags.strip())
            tags_label.set_xalign(0)
            tags_label.add_css_class("dim-label")
            tags_label.set_wrap(True)
            content.append(tags_label)

        # Resolution picker
        res_group = Adw.PreferencesGroup(title="Resolution")
        self._res_buttons = {}

        if resolutions:
            self._selected_res = resolutions[-1].get("resolution", "1920x1080")

        for r in resolutions:
            res = r.get("resolution", "")
            w = r.get("width", 0)
            h = r.get("height", 0)
            size_mb = r.get("size", 0)
            row = Adw.ActionRow(title=res)
            if size_mb:
                row.set_subtitle(f"~{size_mb} MB")

            check = Gtk.CheckButton()
            if res == self._selected_res:
                check.set_active(True)
            check.connect("toggled", self._on_res_toggled, res)
            row.add_prefix(check)

            # Link radio group
            if self._res_buttons:
                first_check = list(self._res_buttons.values())[0]
                check.set_group(first_check)
            self._res_buttons[res] = check

            res_group.add(row)

        content.append(res_group)

        # Download button
        btn_box = Gtk.Box(spacing=8)
        btn_box.set_halign(Gtk.Align.CENTER)
        btn_box.set_margin_top(8)

        dl_btn = Gtk.Button(label="Download & Apply")
        dl_btn.add_css_class("suggested-action")
        dl_btn.add_css_class("pill")
        dl_btn.set_size_request(200, -1)
        dl_btn.connect("clicked", lambda b: self._on_download(b, dialog))
        btn_box.append(dl_btn)

        self.detail_progress = Gtk.ProgressBar()
        self.detail_progress.set_visible(False)
        self.detail_progress.set_hexpand(True)
        self.detail_progress.set_show_text(True)
        btn_box.append(self.detail_progress)

        content.append(btn_box)

        scroll.set_child(content)
        toolbar.set_content(scroll)
        dialog.set_child(toolbar)
        dialog.present(self.app.win)

    def _load_preview(self, url: str, wid: str):
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        ext = ".webp" if ".webp" in url else ".jpg"
        cached = CACHE_DIR / f"{wid}_preview{ext}"
        if not cached.exists() or cached.stat().st_size == 0:
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "RazerAxon/2.6.2.0"})
                with urllib.request.urlopen(req, timeout=15) as resp:
                    cached.write_bytes(resp.read())
            except Exception:
                return
        GLib.idle_add(self.preview_pic.set_filename, str(cached))

    def _on_res_toggled(self, check, res: str):
        if check.get_active():
            self._selected_res = res

    def _on_download(self, btn, dialog):
        btn.set_visible(False)
        self.detail_progress.set_visible(True)
        self.detail_progress.set_fraction(0)
        self.detail_progress.set_text(tr("connecting"))
        threading.Thread(target=self._do_download, args=(btn, dialog), daemon=True).start()

    def _do_download(self, btn, dialog):
        wid = self.wp["wallpaper_id"]
        token_data = load_token()
        uuid = token_data.get("uuid", "")
        is_guest = token_data.get("isGuest", False)

        res = self._selected_res
        if "x" in res:
            w, h = res.split("x")
        else:
            w, h = "1920", "1080"

        # Get resource URL
        resp = hmac_request("wallpaper/resource", {
            "wallpaper_id": wid, "width": w, "height": h, "resource_type": "0",
        }, uuid, is_guest)

        if not resp or resp.get("code") != 200:
            GLib.idle_add(self._dl_failed, btn)
            return

        dl_url = resp["data"]["resource"]
        resource_id = resp["data"].get("resource_id", "")

        # Download
        wp_dir = DOWNLOAD_DIR / wid
        wp_dir.mkdir(parents=True, exist_ok=True)
        zip_path = wp_dir / f"{res}.zip"

        try:
            req = urllib.request.Request(dl_url)
            with urllib.request.urlopen(req, timeout=300) as r:
                total = int(r.headers.get("Content-Length", 0))
                downloaded = 0
                with open(zip_path, "wb") as f:
                    while chunk := r.read(256 * 1024):
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total > 0:
                            frac = downloaded / total
                            mb = downloaded / 1024 / 1024
                            total_mb = total / 1024 / 1024
                            GLib.idle_add(self._set_progress, frac, f"{mb:.1f}/{total_mb:.1f} MB")
        except Exception:
            GLib.idle_add(self._dl_failed, btn)
            return

        GLib.idle_add(self._set_progress, 1.0, "Extracting...")

        # Extract & decrypt
        media_path = ""
        try:
            if zipfile.is_zipfile(zip_path):
                with zipfile.ZipFile(zip_path) as zf:
                    zf.extractall(wp_dir)

            config_path = wp_dir / "ResourceConfig.txt"
            if config_path.exists():
                try:
                    sys.path.insert(0, str(Path(__file__).parent))
                    from axon import parse_resource_config, derive_password, extract
                    parsed = parse_resource_config(config_path)
                    if parsed:
                        content, config = parsed
                        source_str = config.get("Source", "")
                        if source_str and config.get("SourceEncryptedTypes", "").upper() == "ZIP":
                            source = PureWindowsPath(source_str)
                            archive = wp_dir / Path(*source.parts)
                            if archive.exists():
                                password = derive_password(content)
                                extract_dir = wp_dir / "Extracted"
                                extract(archive, password, extract_dir)
                                for f_path in extract_dir.rglob("*"):
                                    if f_path.suffix.lower() in (".mp4", ".webm", ".jpg", ".png"):
                                        media_path = str(f_path)
                                        break
                except ImportError:
                    pass
        except Exception:
            pass

        # Report
        try:
            hmac_request("wallpaper/downloaded", {
                "wallpaper_id": wid, "resource_id": resource_id,
            }, uuid, is_guest, method="POST")
        except Exception:
            pass

        if media_path:
            GLib.idle_add(self._set_progress, 1.0, "Applying...")
            is_video = media_path.lower().endswith((".mp4", ".webm"))
            apply_wallpaper(media_path, is_video=is_video)
            GLib.idle_add(self._dl_success, btn, dialog, media_path)
        else:
            GLib.idle_add(self._dl_failed, btn)

    def _set_progress(self, frac: float, text: str):
        self.detail_progress.set_fraction(frac)
        self.detail_progress.set_text(text)

    def _dl_success(self, btn, dialog, media_path: str):
        self.detail_progress.set_visible(False)
        self.app.toast(f"{tr("applied")}: {self.wp.get('title', '?')}")
        dialog.close()

    def _dl_failed(self, btn):
        self.detail_progress.set_visible(False)
        btn.set_visible(True)
        btn.set_label(tr("retry"))
        btn.add_css_class("destructive-action")


# ── Artist page ──────────────────────────────────────────────────────

class ArtistPage:
    """Full artist page: banner, bio, social links, gallery, series."""

    def __init__(self, artist_summary: dict, app: "AxonApp"):
        self.artist_id = artist_summary["artist_id"]
        self.app = app
        self._detail = None

    def show(self):
        threading.Thread(target=self._load, daemon=True).start()

    def _load(self):
        detail = api_get("artist/detail", {"artist_id": self.artist_id}, auth=self.app.auth)
        wallpapers = api_get("wallpaper/list", {
            "pi": "1", "ps": "30", "artist_id": self.artist_id, "not_offical": "true"
        }, auth=self.app.auth)
        collections = api_get("collection/list", {
            "pi": "1", "ps": "10", "artist_id": self.artist_id
        }, auth=self.app.auth)

        if detail and detail.get("code") == 200:
            self._detail = detail["data"]
            wp_list = wallpapers["data"].get("list", []) if wallpapers and wallpapers.get("code") == 200 else []
            wp_count = wallpapers["data"].get("count", 0) if wallpapers and wallpapers.get("code") == 200 else 0
            coll_list = collections["data"].get("list", []) if collections and collections.get("code") == 200 else []
            GLib.idle_add(self._build, wp_list, wp_count, coll_list)

    def _build(self, wallpapers, wp_count, collections):
        d = self._detail

        dialog = Adw.Dialog()
        dialog.set_title(d.get("name", ""))
        dialog.set_content_width(900)
        dialog.set_content_height(700)

        scroll = Gtk.ScrolledWindow(vexpand=True)
        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)

        # ── Banner with overlay info ──
        banner_overlay = Gtk.Overlay()
        banner_overlay.set_size_request(-1, 200)

        # Background image
        self._banner_pic = Gtk.Picture()
        self._banner_pic.set_content_fit(Gtk.ContentFit.COVER)
        self._banner_pic.set_size_request(-1, 200)
        banner_overlay.set_child(self._banner_pic)

        bg_url = d.get("background", "")
        if bg_url:
            threading.Thread(target=self._load_img,
                             args=(bg_url, self._banner_pic, f"artist_bg_{self.artist_id}"),
                             daemon=True).start()

        # Info overlay on banner (left side)
        info_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        info_box.set_valign(Gtk.Align.END)
        info_box.set_halign(Gtk.Align.START)
        info_box.set_margin_start(20)
        info_box.set_margin_bottom(16)

        # Avatar + Name row
        name_row = Gtk.Box(spacing=10)
        name_row.set_valign(Gtk.Align.CENTER)
        self._avatar_pic = Gtk.Picture()
        self._avatar_pic.set_content_fit(Gtk.ContentFit.COVER)
        self._avatar_pic.set_size_request(40, 40)
        name_row.append(self._avatar_pic)

        avatar_url = d.get("avatar", "")
        if avatar_url:
            threading.Thread(target=self._load_img,
                             args=(avatar_url, self._avatar_pic, f"artist_av_{self.artist_id}"),
                             daemon=True).start()

        name_label = Gtk.Label(label=d.get("name", ""))
        name_label.set_markup(f'<b><span size="large" color="white">{GLib.markup_escape_text(d.get("name", ""))}</span></b>')
        name_row.append(name_label)
        info_box.append(name_row)

        # Follow status
        is_followed = d.get("is_followed", 0)
        follow_label = Gtk.Label()
        follow_label.set_markup(f'<span color="#44d62c" size="small">{"FOLLOWING" if is_followed else "FOLLOW"}</span>')
        follow_label.set_xalign(0)
        info_box.append(follow_label)

        # Social links row
        links = d.get("links", [])
        if links:
            links_box = Gtk.Box(spacing=8)
            for link in links:
                link_btn = Gtk.Button(label=link.get("icon_name", "🔗"))
                link_btn.add_css_class("flat")
                link_btn.set_tooltip_text(link.get("url", ""))
                url = link.get("url", "")
                link_btn.connect("clicked", lambda b, u=url: subprocess.Popen(
                    ["xdg-open", u], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
                links_box.append(link_btn)
            info_box.append(links_box)

        banner_overlay.add_overlay(info_box)
        page.append(banner_overlay)

        # ── Description ──
        desc = d.get("description", "") or d.get("brief_description", "")
        if desc:
            desc_box = Gtk.Box()
            desc_box.set_margin_start(20)
            desc_box.set_margin_end(20)
            desc_box.set_margin_top(12)
            desc_label = Gtk.Label(label=desc)
            desc_label.set_wrap(True)
            desc_label.set_xalign(0)
            desc_label.add_css_class("axon-author")
            desc_box.append(desc_label)
            page.append(desc_box)

        # ── Tabs: Gallery / Series ──
        tabs_box = Gtk.Box(spacing=0)
        tabs_box.add_css_class("axon-tabs")
        tabs_box.set_margin_top(8)

        gallery_btn = Gtk.Button(label=tr("gallery").upper() if tr("gallery") else "GALLERY")
        gallery_btn.add_css_class("tab-active")
        tabs_box.append(gallery_btn)

        series_btn = Gtk.Button(label=tr("series").upper() if tr("series") else "SERIES")
        tabs_box.append(series_btn)

        page.append(tabs_box)

        # ── Content stack for gallery/series ──
        stack = Gtk.Stack()
        stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)

        # Gallery grid
        gallery = Gtk.FlowBox()
        gallery.set_homogeneous(True)
        gallery.set_max_children_per_line(6)
        gallery.set_min_children_per_line(2)
        gallery.set_column_spacing(10)
        gallery.set_row_spacing(10)
        gallery.set_margin_start(20)
        gallery.set_margin_end(20)
        gallery.set_margin_top(12)
        gallery.set_margin_bottom(12)
        gallery.set_selection_mode(Gtk.SelectionMode.NONE)

        for wp in wallpapers:
            card = WallpaperCard(wp, self.app)
            gallery.append(card)
            fb_child = card.get_parent()
            if fb_child:
                fb_child.set_focusable(False)

        stack.add_named(gallery, "gallery")

        # Series list
        series_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        series_box.set_margin_start(20)
        series_box.set_margin_end(20)
        series_box.set_margin_top(12)

        if collections:
            for coll in collections:
                coll_row = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
                coll_title = Gtk.Label(label=coll.get("title", ""))
                coll_title.set_xalign(0)
                coll_title.add_css_class("axon-title")
                coll_row.append(coll_title)

                coll_desc = coll.get("brief_description", "")
                if coll_desc:
                    cd = Gtk.Label(label=coll_desc[:120])
                    cd.set_xalign(0)
                    cd.set_wrap(True)
                    cd.add_css_class("axon-author")
                    coll_row.append(cd)

                # Thumbnails
                thumb_scroll = Gtk.ScrolledWindow()
                thumb_scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.NEVER)
                thumb_scroll.set_size_request(-1, 100)
                thumb_box = Gtk.Box(spacing=6)
                coll_wallpapers = coll.get("wallpapers", [])
                if isinstance(coll_wallpapers, list):
                    for wp in coll_wallpapers[:8]:
                        if isinstance(wp, dict):
                            thumb = Gtk.Picture()
                            thumb.set_content_fit(Gtk.ContentFit.COVER)
                            thumb.set_size_request(160, 90)
                            thumb_box.append(thumb)
                            thumb_url = wp.get("thumbnail", "")
                            wid = wp.get("wallpaper_id", str(id(wp)))
                            if thumb_url:
                                threading.Thread(target=self._load_img,
                                                 args=(thumb_url, thumb, f"as_{wid}"),
                                                 daemon=True).start()
                thumb_scroll.set_child(thumb_box)
                coll_row.append(thumb_scroll)
                series_box.append(coll_row)
        else:
            no_series = Gtk.Label(label="No series")
            no_series.add_css_class("axon-status")
            series_box.append(no_series)

        stack.add_named(series_box, "series")
        page.append(stack)

        # Tab switching
        gallery_btn.connect("clicked", lambda b: (
            stack.set_visible_child_name("gallery"),
            gallery_btn.add_css_class("tab-active"),
            series_btn.remove_css_class("tab-active"),
        ))
        series_btn.connect("clicked", lambda b: (
            stack.set_visible_child_name("series"),
            series_btn.add_css_class("tab-active"),
            gallery_btn.remove_css_class("tab-active"),
        ))

        scroll.set_child(page)
        dialog.set_child(scroll)
        dialog.present(self.app.win)

    def _load_img(self, url, widget, cache_id):
        path = download_thumbnail(url, cache_id)
        if path:
            GLib.idle_add(widget.set_filename, str(path))


# ── Main application ─────────────────────────────────────────────────

class AxonApp(Adw.Application):
    def __init__(self):
        super().__init__(application_id="com.razer.axon.linux",
                         flags=Gio.ApplicationFlags.DEFAULT_FLAGS)
        self.auth = ""
        self._uuid = ""
        self._country = ""
        self._categories = []
        self._current_page = 1
        self._total_count = 0
        self._search_query = ""
        self._category_id = ""
        self._effect_type = ""
        self._fav_only = False
        self._artist_filter = ""
        self._lang_first_check = None

    def do_activate(self):
        # Force dark theme via Adwaita (suppress the GtkSettings warning)
        Adw.StyleManager.get_default().set_color_scheme(Adw.ColorScheme.FORCE_DARK)

        # Login
        token_data = load_token()
        if not token_data.get("token"):
            dialog = Adw.AlertDialog(heading=tr("not_logged_in"),
                                     body=tr("run_login"))
            dialog.add_response("ok", "OK")
            dialog.choose(None, None, None)
            return

        self.auth, self._uuid, self._country = api_login(token_data)
        self._uuid_raw = token_data.get("uuid", "")
        self._is_guest = token_data.get("isGuest", False)

        if not self.auth:
            dialog = Adw.AlertDialog(heading=tr("login_failed"),
                                     body=tr("token_expired"))
            dialog.add_response("ok", "OK")
            dialog.choose(None, None, None)
            return

        self.win = Adw.ApplicationWindow(application=self, title="Razer Axon",
                                         default_width=1200, default_height=800)
        self.win.set_decorated(False)  # No system titlebar — like original Axon

        # Toast overlay
        self.toast_overlay = Adw.ToastOverlay()

        # ── Razer Axon CSS — pixel-matched from original Sequoia 2.6.2.0 ──
        css = Gtk.CssProvider()
        css.load_from_string("""
            /* ── Base — body:#1a1a1a, font:14px Roboto/RazerF5 ── */
            window, .axon-main { background-color: #1a1a1a; color: #fff;
                                 font-family: "Roboto", "RazerF5", sans-serif; font-size: 14px; }

            /* ── Title bar — 32px #222, logo margin-left:28px ── */
            .axon-titlebar { background-color: #222; min-height: 32px; }
            .axon-titlebar-logo { color: #fff; margin-left: 28px; margin-right: 28px; }
            .axon-titlebar button { color: #fff; background: transparent; border: none;
                                    min-width: 48px; min-height: 32px; opacity: 0.6; border-radius: 0; }
            .axon-titlebar button:hover { opacity: 1; }
            .axon-titlebar button.close:hover { background-color: #f53333; }

            /* ── Nav bar — 48px #44d62c, font:21px RazerF5 ── */
            .axon-topbar { background-color: #44d62c; padding: 0; min-height: 48px; }
            .axon-topbar-logo { color: #000; font-family: "RazerF5"; font-weight: 800;
                                font-size: 16px; padding: 0 16px; margin-left: 12px; }
            .axon-topbar button { color: #107100; background: transparent; border: none;
                                  font-family: "RazerF5"; font-weight: 500;
                                  font-size: 21px; padding: 0 20px;
                                  min-height: 48px; border-radius: 0; }
            .axon-topbar button:hover { color: #000; background-color: rgba(0,0,0,0.1); }
            .axon-topbar-active { color: #000; font-weight: 800; }
            .axon-topbar-right button { color: rgba(0,0,0,0.5); padding: 0 8px;
                                        min-width: 48px; min-height: 48px; }
            .axon-topbar-right button:hover { color: #000; }

            /* ── Nav history arrows — 40px, opacity:0.3 ── */
            .axon-nav-history { min-width: 40px; min-height: 48px; opacity: 0.3; }
            .axon-nav-history:hover { opacity: 1; background-color: rgba(0,0,0,0.1); }

            /* ── Account avatar — 32px circle ── */
            .axon-avatar { border-radius: 100%; min-width: 32px; min-height: 32px; }
            .axon-nav-account-name { color: #44d62c; }

            /* ── Sub-tabs: height:48px; green underline on active ── */
            .axon-tabs { background-color: #1a1a1a; border-bottom: 1px solid #222;
                         padding: 0 48px; min-height: 48px; }
            .axon-tabs button { color: #909090; background: transparent; border: none;
                                font-weight: 700; font-size: 14px; padding: 0 20px;
                                min-height: 48px; border-bottom: 3px solid transparent; border-radius: 0; }
            .axon-tabs button:hover { color: #fff; }
            .axon-tabs button.tab-active { color: #fff; border-bottom-color: #44d62c; }

            /* ── Filter bar: #222, 46px ── */
            .axon-filters { background-color: #222; padding: 0 16px; min-height: 46px;
                            border-bottom: 1px solid #111; }
            .axon-filters checkbutton { color: #eee; font-size: 13px; }
            .axon-clear-btn { color: #909090; font-size: 13px; }
            .axon-clear-btn:hover { color: #fff; }

            /* ── Search: #161616, 32px height, border-radius:4px ── */
            .axon-search { background-color: #161616; border: 1px solid #333; border-radius: 4px;
                           color: #999; padding: 4px 12px; min-height: 32px; min-width: 200px; font-size: 13px; }
            .axon-search:focus { border-color: #44d62c; color: #fff; }

            /* ── Sidebar: #222, 260px, border-right:#111 ── */
            .axon-sidebar { background-color: #222; border-right: 1px solid #111;
                            padding-left: 8px; padding-right: 4px; }
            .axon-sidebar button { border-radius: 2px; padding: 0 8px; color: #fff; border: none;
                                   background: transparent; font-size: 13px; font-weight: 600;
                                   min-height: 36px; opacity: 0.6; }
            .axon-sidebar button:hover { background-color: rgba(0,0,0,0.3); opacity: 1; }
            .axon-sidebar button.active-cat { background-color: rgba(0,0,0,0.3); opacity: 1;
                                              color: #fff; }

            /* ── Sidebar collapse arrow: 32px, opacity:0.6, rotate on hide ── */
            .axon-sidebar-arrow { opacity: 0.6; min-width: 32px; min-height: 32px; }
            .axon-sidebar-arrow:hover { opacity: 1; background-color: rgba(0,0,0,0.3);
                                         border-radius: 2px; }

            /* ── Wallpaper cards — max-width:266px, min-width:240px ── */
            .axon-card { background-color: transparent; border-radius: 2px;
                         padding: 0; margin-bottom: 24px; }
            .axon-card:hover { background-color: rgba(255,255,255,0.03); }
            .axon-card image { border-radius: 2px; outline: 2px solid transparent;
                               outline-offset: -2px; }
            .axon-card:hover image { outline-color: #44d62c; }
            .axon-card-icon { color: #fff; opacity: 0.75; }
            .axon-card-icon:hover { opacity: 1; background-color: rgba(0,0,0,0.3); }

            /* ── Card text — title:#c8c8c8 14px Roboto, author:#909090 12px ── */
            .axon-title { color: #c8c8c8; font-family: "Roboto"; font-weight: 600;
                          font-size: 14px; line-height: 16px; }
            .axon-card:hover .axon-title { color: #fff; }
            .axon-author { color: #909090; font-family: "Roboto Medium", "Roboto";
                           font-size: 12px; line-height: 14px; }

            /* ── Card hover overlay with download button ── */
            .axon-hover-overlay { background-color: rgba(0,0,0,0.6); border-radius: 2px; }

            /* ── Download progress — 4px, green/orange/red ── */
            .axon-progress trough { background-color: #fff; border-radius: 2px; min-height: 4px; }
            .axon-progress progress { background-color: #44d62c; border-radius: 2px; min-height: 4px; }
            .axon-progress.paused progress { background-color: #ffb94f; }
            .axon-progress.error progress { background-color: #e72424; }

            /* ── "New" badge — #44d62c, 42x20, left:-4px ── */
            .axon-badge-new { background-color: #44d62c; color: #000; font-size: 12px;
                              padding: 0 6px; min-height: 20px; }
            .axon-badge-new:hover { background-color: #78e166; }

            /* ── Notification badge — #ba0404, 14px circle ── */
            .axon-badge-notif { background-color: #ba0404; color: #fff; font-size: 10px;
                                border-radius: 7px; min-width: 8px; min-height: 14px; padding: 0 4px; }

            /* ── Artist cards: #222, border:2px, hover:green ── */
            .axon-artist-card { background-color: #222; border-radius: 2px; border: 2px solid transparent;
                                min-height: 184px; padding: 8px 10px;
                                transition: border-color 0.35s ease, background-color 0.35s ease; }
            .axon-artist-card:hover { border-color: #44d62c; background-color: #000; }
            .axon-artist-desc { color: #909090; font-size: 12px; line-height: 16px; }
            .axon-artist-card:hover .axon-artist-desc { color: #fff; }

            /* ── Collection/Series: #000 panel ── */
            .axon-coll-info { background-color: #000; border-radius: 2px; padding: 8px 16px; }
            .axon-coll-follow { color: #44d62c; font-size: 12px; line-height: 24px; }
            .axon-coll-follow:hover { color: #7ce26b; }

            /* ── Buttons — primary:#44d62c, outline:#707070, delete ── */
            .axon-dl-btn { background-color: #44d62c; color: #000; font-weight: 700;
                           border-radius: 2px; padding: 6px 16px; font-size: 12px; border: none; }
            .axon-dl-btn:hover { background-color: #7ce26b; }
            .axon-apply-btn { background-color: #135708; color: #44d62c; font-weight: 700;
                              border-radius: 2px; padding: 6px 16px; font-size: 12px;
                              border: 1px solid #226916; }
            .axon-apply-btn:hover { background-color: #1a6e0e; }
            .axon-btn-outline { background-color: transparent; color: #909090;
                                border: 1px solid #555; border-radius: 2px;
                                padding: 6px 16px; font-size: 12px; }
            .axon-btn-outline:hover { color: #fff; border-color: #44d62c; }
            .axon-btn-delete:hover { background-color: #ba0404; color: #fff; }

            /* ── Modal/Dialog — center, #1a1a1a, shadow ── */
            .axon-modal { background-color: #1a1a1a; border-radius: 2px;
                          box-shadow: -3px 0 6px 0 rgba(0,0,0,0.12); }
            .axon-modal-mask { background-color: rgba(0,0,0,0.7); }

            /* ── Detail side panel — 400px slide-in, #1a1a1a ── */
            .axon-detail-panel { background-color: #1a1a1a; min-width: 400px;
                                 box-shadow: -3px 0 6px 0 rgba(0,0,0,0.12); }
            .axon-detail-title { color: #44d62c; font-size: 14px; font-weight: 600; }
            .axon-detail-desc { color: #909090; font-size: 12px; }

            /* ── Settings: menu 158px + content, #2e2e2e hover ── */
            .axon-settings-menu { min-width: 158px; background-color: #1a1a1a; }
            .axon-settings-menu button { color: #909090; border-radius: 0; min-height: 36px;
                                          background: transparent; border: none; }
            .axon-settings-menu button:hover { background-color: #2e2e2e; color: #fff; }
            .axon-settings-menu button.active { color: #fff; background-color: #2e2e2e; }

            /* ── Context menu — #000, border-radius:4px ── */
            .axon-context-menu { background-color: #000; border-radius: 4px;
                                 padding: 4px 0; min-width: 160px; }
            .axon-context-menu button { color: #bbb; background: transparent; border: none;
                                        padding: 8px 16px; font-size: 13px; border-radius: 0; }
            .axon-context-menu button:hover { background-color: #222; color: #fff; }

            /* ── Status & load more ── */
            .axon-status { color: #555; font-size: 12px; }
            .axon-loadmore { background-color: #222; color: #999; border-radius: 2px;
                             padding: 8px 24px; border: 1px solid #333; font-size: 13px; }
            .axon-loadmore:hover { background-color: #333; color: #fff; border-color: #44d62c; }

            /* ── Go-to-top — #44d62c, opacity:0.7 ── */
            .axon-go-top { background-color: #44d62c; border-radius: 0; min-width: 48px;
                           min-height: 40px; opacity: 0.7; color: #000; }
            .axon-go-top:hover { opacity: 1; }

            /* ── Scrollbar — 5px, #585858 thumb, #111 track, green hover ── */
            scrollbar { background-color: transparent; }
            scrollbar slider { background-color: #585858; border-radius: 5px;
                               min-width: 5px; min-height: 30px; }
            scrollbar slider:hover { background-color: #44d62c; }
            scrollbar slider:active { background-color: #359b24; }
            scrollbar trough { background-color: #111; border-radius: 10px; }

            /* ── Skeleton loading ── */
            .axon-skeleton { background-color: #555; border-radius: 2px;
                             animation: skeleton-pulse 1.5s ease-in-out infinite; }
            @keyframes skeleton-pulse { 0%, 100% { opacity: 0.4; } 50% { opacity: 0.8; } }

            /* ── Switch — 28x16, #787878 off, #44d62c on ── */
            switch { min-width: 28px; min-height: 16px; border-radius: 8px;
                     background-color: #787878; }
            switch:checked { background-color: #44d62c; }
            switch slider { min-width: 12px; min-height: 12px; border-radius: 100%;
                            background-color: #fff; margin: 2px; }

            /* ── Checkbox — 14px, #44d62c checked ── */
            checkbutton indicator { min-width: 14px; min-height: 14px; border-radius: 2px;
                                    border: 1px solid #555; background-color: transparent; }
            checkbutton indicator:checked { background-color: #44d62c; border-color: #44d62c; }

            /* ── Tooltip ── */
            tooltip { background-color: #222; color: #fff; border-radius: 2px;
                      padding: 4px 8px; font-size: 12px; }
        """)
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(), css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

        # ── Layout matching original Axon ──
        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        root.add_css_class("axon-main")

        # 1. Green top bar: logo + nav + window controls
        topbar = Gtk.Box(spacing=0)
        topbar.add_css_class("axon-topbar")

        # Logo
        logo = Gtk.Label()
        logo.set_markup("<b>⬡ AXON</b>")
        logo.add_css_class("axon-topbar-logo")
        topbar.append(logo)

        # Nav buttons
        self._nav_buttons = {}
        for nav_id in ["gallery", "create", "community", "library"]:
            btn = Gtk.Button(label=tr(nav_id))
            if nav_id == "gallery":
                btn.add_css_class("axon-topbar-active")
            btn.connect("clicked", lambda b, nid=nav_id: self._on_nav(b, nid))
            self._nav_buttons[nav_id] = btn
            topbar.append(btn)

        # Spacer — drag to move window only on empty space
        spacer = Gtk.Box()
        spacer.set_hexpand(True)
        drag = Gtk.GestureDrag()
        drag.connect("drag-begin", lambda g, x, y: self.win.get_surface().begin_move(
            g.get_device(), g.get_current_button(), x, y, GLib.get_monotonic_time() // 1000))
        spacer.add_controller(drag)
        topbar.append(spacer)

        # Search
        self.search_entry = Gtk.SearchEntry(placeholder_text=tr("search"))
        self.search_entry.add_css_class("axon-search")
        self.search_entry.set_valign(Gtk.Align.CENTER)
        self.search_entry.connect("activate", self._on_search)
        topbar.append(self.search_entry)

        # Settings gear + Window controls
        wc_box = Gtk.Box(spacing=0)
        wc_box.add_css_class("axon-topbar-right")
        wc_box.set_margin_start(8)
        settings_btn = Gtk.Button()
        settings_btn.set_icon_name("emblem-system-symbolic")
        settings_btn.set_tooltip_text(tr("settings"))
        settings_btn.connect("clicked", self._on_settings)
        wc_box.append(settings_btn)
        for icon, action in [("window-minimize-symbolic", "minimize"),
                              ("window-maximize-symbolic", "maximize"),
                              ("window-close-symbolic", "close")]:
            btn = Gtk.Button()
            btn.set_icon_name(icon)
            btn.connect("clicked", self._on_window_btn, action)
            wc_box.append(btn)
        topbar.append(wc_box)

        root.append(topbar)

        # 2. Tabs row
        tabs = Gtk.Box(spacing=0)
        tabs.add_css_class("axon-tabs")
        self._tab_buttons = {}
        self._active_tab = "wallpapers"
        for tab_id in ["wallpapers", "series", "authors"]:
            btn = Gtk.Button(label=tr(tab_id))
            if tab_id == "wallpapers":
                btn.add_css_class("tab-active")
            btn.connect("clicked", self._on_tab, tab_id)
            self._tab_buttons[tab_id] = btn
            tabs.append(btn)
        self._tabs_bar = tabs
        root.append(tabs)

        # 3. Filter bar
        filters = Gtk.Box(spacing=16)
        filters.add_css_class("axon-filters")
        self._filter_checks = {}
        for f_tr, f_key in [("audio", "audible"), ("favorites", "favorite_only"),
                             ("ai", "ai"), ("dynamic", "Dynamic"), ("static", "Static"),
                             ("interactive", "interactive")]:
            chk = Gtk.CheckButton(label=tr(f_tr))
            chk.connect("toggled", self._on_filter_check, f_key)
            filters.append(chk)
            self._filter_checks[f_key] = chk
        clear_btn = Gtk.Button(label=tr("clear"))
        clear_btn.add_css_class("flat")
        clear_btn.add_css_class("axon-clear-btn")
        clear_btn.connect("clicked", self._on_clear_filters)
        filters.append(clear_btn)
        self._filters_bar = filters
        root.append(filters)

        # 4. Main: sidebar + content
        body = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        body.set_vexpand(True)

        # Sidebar categories
        sidebar_scroll = Gtk.ScrolledWindow()
        sidebar_scroll.set_size_request(160, -1)
        sidebar_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.sidebar = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.sidebar.add_css_class("axon-sidebar")
        sidebar_scroll.set_child(self.sidebar)
        self._sidebar_scroll = sidebar_scroll
        body.append(sidebar_scroll)

        # Content stack (wallpapers / series / authors)
        self.content_stack = Gtk.Stack()
        self.content_stack.set_hexpand(True)
        self.content_stack.set_vexpand(True)
        self.content_stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        self.content_stack.set_transition_duration(150)

        # ── Wallpapers page ──
        wp_page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.scroll = Gtk.ScrolledWindow(vexpand=True)
        self.flowbox = Gtk.FlowBox()
        self.flowbox.set_homogeneous(True)
        self.flowbox.set_max_children_per_line(6)
        self.flowbox.set_min_children_per_line(2)
        self.flowbox.set_column_spacing(10)
        self.flowbox.set_row_spacing(10)
        self.flowbox.set_margin_start(12)
        self.flowbox.set_margin_end(12)
        self.flowbox.set_margin_top(8)
        self.flowbox.set_margin_bottom(8)
        self.flowbox.set_selection_mode(Gtk.SelectionMode.NONE)
        self.flowbox.set_activate_on_single_click(False)
        self.scroll.set_child(self.flowbox)
        wp_page.append(self.scroll)
        bottom = Gtk.Box(spacing=12)
        bottom.set_margin_start(12)
        bottom.set_margin_end(12)
        bottom.set_margin_bottom(6)
        self.status = Gtk.Label(label="Loading...")
        self.status.add_css_class("axon-status")
        self.status.set_xalign(0)
        self.status.set_hexpand(True)
        bottom.append(self.status)
        self.load_more_btn = Gtk.Button(label=tr("load_more"))
        self.load_more_btn.add_css_class("axon-loadmore")
        self.load_more_btn.connect("clicked", self._on_load_more)
        self.load_more_btn.set_visible(False)
        bottom.append(self.load_more_btn)
        wp_page.append(bottom)
        self.content_stack.add_named(wp_page, "wallpapers")

        # ── Series page ──
        self.series_scroll = Gtk.ScrolledWindow(vexpand=True)
        self.series_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        self.series_box.set_margin_start(16)
        self.series_box.set_margin_end(16)
        self.series_box.set_margin_top(12)
        self.series_box.set_margin_bottom(12)
        self.series_scroll.set_child(self.series_box)
        self.content_stack.add_named(self.series_scroll, "series")
        self._series_loaded = False

        # ── Authors page ──
        self.authors_scroll = Gtk.ScrolledWindow(vexpand=True)
        self.authors_flow = Gtk.FlowBox()
        self.authors_flow.set_homogeneous(True)
        self.authors_flow.set_max_children_per_line(5)
        self.authors_flow.set_min_children_per_line(2)
        self.authors_flow.set_column_spacing(12)
        self.authors_flow.set_row_spacing(12)
        self.authors_flow.set_margin_start(16)
        self.authors_flow.set_margin_end(16)
        self.authors_flow.set_margin_top(12)
        self.authors_flow.set_margin_bottom(12)
        self.authors_flow.set_selection_mode(Gtk.SelectionMode.NONE)
        self.authors_flow.set_activate_on_single_click(False)
        self.authors_scroll.set_child(self.authors_flow)
        self.content_stack.add_named(self.authors_scroll, "authors")
        self._authors_loaded = False

        # ── Community page ──
        self.community_scroll = Gtk.ScrolledWindow(vexpand=True)
        self.community_box = Gtk.FlowBox()
        self.community_box.set_homogeneous(True)
        self.community_box.set_max_children_per_line(6)
        self.community_box.set_min_children_per_line(2)
        self.community_box.set_column_spacing(10)
        self.community_box.set_row_spacing(10)
        self.community_box.set_margin_start(16)
        self.community_box.set_margin_end(16)
        self.community_box.set_margin_top(12)
        self.community_box.set_margin_bottom(12)
        self.community_box.set_selection_mode(Gtk.SelectionMode.NONE)
        self.community_scroll.set_child(self.community_box)
        self.content_stack.add_named(self.community_scroll, "community")
        self._community_loaded = False

        # ── Library page (downloaded wallpapers) ──
        self.library_scroll = Gtk.ScrolledWindow(vexpand=True)
        self.library_flow = Gtk.FlowBox()
        self.library_flow.set_homogeneous(True)
        self.library_flow.set_max_children_per_line(6)
        self.library_flow.set_min_children_per_line(2)
        self.library_flow.set_column_spacing(10)
        self.library_flow.set_row_spacing(10)
        self.library_flow.set_margin_start(16)
        self.library_flow.set_margin_end(16)
        self.library_flow.set_margin_top(12)
        self.library_flow.set_margin_bottom(12)
        self.library_flow.set_selection_mode(Gtk.SelectionMode.NONE)
        self.library_scroll.set_child(self.library_flow)
        self.content_stack.add_named(self.library_scroll, "library")
        self._library_loaded = False

        body.append(self.content_stack)
        root.append(body)

        self.toast_overlay.set_child(root)
        self.win.set_content(self.toast_overlay)

        self.win.present()

        # Load categories and first page
        threading.Thread(target=self._load_categories, daemon=True).start()
        self._load_wallpapers(page=1, clear=True)

    def _on_window_btn(self, btn, action):
        if action == "close":
            self.win.close()
        elif action == "minimize":
            self.win.minimize()
        elif action == "maximize":
            if self.win.is_maximized():
                self.win.unmaximize()
            else:
                self.win.maximize()

    def _on_settings(self, btn):
        dialog = Adw.Dialog()
        dialog.set_title(tr("settings"))
        dialog.set_content_width(400)
        dialog.set_content_height(200)

        toolbar = Adw.ToolbarView()
        header = Adw.HeaderBar()
        toolbar.add_top_bar(header)

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        content.set_margin_start(16)
        content.set_margin_end(16)
        content.set_margin_top(12)
        content.set_margin_bottom(16)

        # Language picker
        lang_group = Adw.PreferencesGroup(title=tr("language"))
        current_lang = _get_lang()

        for lang_code, lang_name in [("en", "English"), ("ru", "Русский")]:
            row = Adw.ActionRow(title=lang_name)
            check = Gtk.CheckButton()
            check.set_active(lang_code == current_lang)
            if lang_code != "en":
                check.set_group(self._lang_first_check)
            else:
                self._lang_first_check = check
            check.connect("toggled", self._on_lang_changed, lang_code)
            row.add_prefix(check)
            row.set_activatable_widget(check)
            lang_group.add(row)

        content.append(lang_group)

        toolbar.set_content(content)
        dialog.set_child(toolbar)
        dialog.present(self.win)

    def _on_lang_changed(self, check, lang_code):
        if check.get_active():
            settings = _load_settings()
            settings["language"] = lang_code
            _save_settings(settings)
            self.toast(f"{tr('language')}: {lang_code.upper()} — restart to apply")

    def _on_nav(self, btn, nav_id):
        for nid, nbtn in self._nav_buttons.items():
            if nid == nav_id:
                nbtn.add_css_class("axon-topbar-active")
            else:
                nbtn.remove_css_class("axon-topbar-active")

        # Show/hide gallery-specific UI
        is_gallery = nav_id == "gallery"
        self._tabs_bar.set_visible(is_gallery)
        self._filters_bar.set_visible(is_gallery)
        self._sidebar_scroll.set_visible(is_gallery)

        if nav_id == "gallery":
            self.content_stack.set_visible_child_name(self._active_tab)
        elif nav_id == "community":
            self.content_stack.set_visible_child_name("community")
            if not self._community_loaded:
                self._community_loaded = True
                threading.Thread(target=self._load_community, daemon=True).start()
        elif nav_id == "library":
            self.content_stack.set_visible_child_name("library")
            self._library_loaded = False
            threading.Thread(target=self._load_library, daemon=True).start()
        elif nav_id == "create":
            self.toast(tr("coming_soon"))

    def _load_community(self):
        """Load community/popular wallpapers (paper_source=community)."""
        resp = api_get("wallpaper/list", {
            "pi": "1", "ps": "30", "paper_source": "community", "not_offical": "true"
        }, auth=self.auth)
        if resp and resp.get("code") == 200:
            items = resp["data"].get("list") or []
            GLib.idle_add(self._show_community, items)

    def _show_community(self, items):
        child = self.community_box.get_first_child()
        while child:
            next_c = child.get_next_sibling()
            self.community_box.remove(child)
            child = next_c
        for wp in items:
            card = WallpaperCard(wp, self)
            self.community_box.append(card)
            fb_child = card.get_parent()
            if fb_child:
                fb_child.set_focusable(False)

    def _load_library(self):
        """Show locally downloaded wallpapers."""
        items = []
        if DOWNLOAD_DIR.exists():
            for d in sorted(DOWNLOAD_DIR.iterdir(), key=lambda x: x.stat().st_mtime, reverse=True):
                if not d.is_dir():
                    continue
                ext_dir = d / "Extracted"
                if not ext_dir.exists():
                    continue
                media = None
                for f in ext_dir.rglob("*"):
                    if f.suffix.lower() in (".mp4", ".webm", ".jpg", ".png"):
                        media = str(f)
                        break
                if media:
                    # Try to get title from API cache or wallpaper_id
                    wid = d.name
                    items.append({"wallpaper_id": wid, "media_path": media, "dir": d})
        GLib.idle_add(self._show_library, items)

    def _show_library(self, items):
        child = self.library_flow.get_first_child()
        while child:
            next_c = child.get_next_sibling()
            self.library_flow.remove(child)
            child = next_c

        if not items:
            label = Gtk.Label(label=tr("no_library"))
            label.add_css_class("axon-status")
            label.set_margin_top(40)
            self.library_flow.append(label)
            return

        for item in items:
            card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
            card.add_css_class("axon-card")
            card.set_size_request(200, -1)

            # Thumbnail from extracted media
            pic = Gtk.Picture()
            pic.set_content_fit(Gtk.ContentFit.COVER)
            pic.set_size_request(200, 112)
            media = item["media_path"]
            if media.lower().endswith((".jpg", ".png")):
                pic.set_filename(media)
            card.append(pic)

            # Title (wallpaper ID or folder name)
            title = Gtk.Label(label=f"#{item['wallpaper_id']}")
            title.set_xalign(0)
            title.add_css_class("axon-title")
            title.set_margin_start(6)
            card.append(title)

            # Apply button
            apply_btn = Gtk.Button(label=tr("apply"))
            apply_btn.add_css_class("axon-apply-btn")
            apply_btn.set_margin_start(6)
            apply_btn.set_margin_end(6)
            apply_btn.set_margin_bottom(6)
            path = media
            apply_btn.connect("clicked", lambda b, p=path: self._apply_library(p))
            card.append(apply_btn)

            self.library_flow.append(card)
            fb_child = card.get_parent()
            if fb_child:
                fb_child.set_focusable(False)

    def _apply_library(self, path):
        is_video = path.lower().endswith((".mp4", ".webm"))
        if apply_wallpaper(path, is_video=is_video):
            self.toast(f'{tr("applied")}: {Path(path).stem}')
        else:
            self.toast(tr("failed_apply"))

    def toast(self, msg: str):
        self.toast_overlay.add_toast(Adw.Toast(title=msg, timeout=3))

    def _load_categories(self):
        resp = api_get("wallpaper/setting", {}, auth=self.auth)
        if resp and resp.get("code") == 200:
            self._categories = resp["data"].get("category", [])
            GLib.idle_add(self._populate_categories)

    def _populate_categories(self):
        # Clear sidebar
        child = self.sidebar.get_first_child()
        while child:
            next_c = child.get_next_sibling()
            self.sidebar.remove(child)
            child = next_c

        # "All" button
        all_btn = Gtk.Button(label=tr("all"))
        all_btn.set_halign(Gtk.Align.FILL)
        all_btn.add_css_class("active-cat")
        all_btn.connect("clicked", self._on_cat_clicked, "")
        self.sidebar.append(all_btn)

        for cat in self._categories:
            cid = cat.get("category_id", "")
            name = cat.get("category_name", "")
            count = cat.get("wallpaper_count", 0)
            if cid:
                btn = Gtk.Button(label=f"{name} ({count})")
                btn.set_halign(Gtk.Align.FILL)
                btn.connect("clicked", self._on_cat_clicked, cid)
                self.sidebar.append(btn)

    def _on_cat_clicked(self, btn, cid):
        child = self.sidebar.get_first_child()
        while child:
            child.remove_css_class("active-cat")
            child = child.get_next_sibling()
        btn.add_css_class("active-cat")
        self._category_id = cid
        self._artist_filter = ""
        self._load_wallpapers(page=1, clear=True)

    def _on_search(self, entry):
        self._search_query = entry.get_text().strip()
        self._artist_filter = ""
        self._load_wallpapers(page=1, clear=True)

    def _on_fav_toggle(self, btn):
        self._fav_only = btn.get_active()
        self._load_wallpapers(page=1, clear=True)

    def _on_filter_check(self, chk, key):
        if key == "favorite_only":
            self._fav_only = chk.get_active()
        elif key == "audible":
            # API doesn't filter by audible directly, skip
            pass
        elif key in ("Dynamic", "Static"):
            self._effect_type = key if chk.get_active() else ""
            # Uncheck the other type
            other = "Static" if key == "Dynamic" else "Dynamic"
            if key != other and chk.get_active() and other in self._filter_checks:
                self._filter_checks[other].set_active(False)
        self._load_wallpapers(page=1, clear=True)

    def _on_clear_filters(self, btn):
        self._fav_only = False
        self._effect_type = ""
        self._search_query = ""
        self.search_entry.set_text("")
        for chk in self._filter_checks.values():
            chk.set_active(False)
        self._load_wallpapers(page=1, clear=True)

    def _on_tab(self, btn, tab_id):
        # Update tab styling
        for tid, tbtn in self._tab_buttons.items():
            if tid == tab_id:
                tbtn.add_css_class("tab-active")
            else:
                tbtn.remove_css_class("tab-active")
        self._active_tab = tab_id
        self.content_stack.set_visible_child_name(tab_id)

        if tab_id == "series" and not self._series_loaded:
            self._series_loaded = True
            threading.Thread(target=self._load_series, daemon=True).start()
        elif tab_id == "authors" and not self._authors_loaded:
            self._authors_loaded = True
            threading.Thread(target=self._load_authors, daemon=True).start()

    def _load_series(self):
        resp = api_get("collection/list", {"pi": "1", "ps": "20"}, auth=self.auth)
        if resp and resp.get("code") == 200:
            items = resp["data"].get("list") or []
            GLib.idle_add(self._show_series, items)

    def _show_series(self, items):
        for coll in items:
            row = self._build_series_row(coll)
            self.series_box.append(row)

    def _build_series_row(self, coll):
        """Build a horizontal series row like the original: info card + scrollable thumbnails."""
        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)

        # Title row
        title_box = Gtk.Box(spacing=8)
        icon_url = coll.get("icon", "")
        if icon_url:
            icon_pic = Gtk.Picture()
            icon_pic.set_size_request(24, 24)
            icon_pic.set_content_fit(Gtk.ContentFit.COVER)
            title_box.append(icon_pic)
            threading.Thread(target=self._load_series_icon, args=(icon_url, icon_pic, coll["collection_id"]), daemon=True).start()

        title = Gtk.Label(label=coll.get("title", "?"))
        title.add_css_class("axon-title")
        title.set_xalign(0)
        title_box.append(title)
        outer.append(title_box)

        # Horizontal scroll with info card + wallpaper thumbs
        hscroll = Gtk.ScrolledWindow()
        hscroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.NEVER)
        hscroll.set_size_request(-1, 160)
        hbox = Gtk.Box(spacing=8)

        # Info card (description + follow)
        info_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        info_card.set_size_request(180, 140)
        info_card.set_valign(Gtk.Align.START)

        desc = coll.get("brief_description", "")
        if desc:
            desc_label = Gtk.Label(label=desc[:120])
            desc_label.set_wrap(True)
            desc_label.set_xalign(0)
            desc_label.add_css_class("axon-author")
            info_card.append(desc_label)

        hbox.append(info_card)

        # Wallpaper thumbnails
        wallpapers = coll.get("wallpapers", [])
        if isinstance(wallpapers, list):
            for wp in wallpapers[:8]:
                thumb = Gtk.Picture()
                thumb.set_content_fit(Gtk.ContentFit.COVER)
                thumb.set_size_request(180, 100)
                hbox.append(thumb)
                thumb_url = wp.get("thumbnail", "") if isinstance(wp, dict) else ""
                wid = wp.get("wallpaper_id", str(id(wp))) if isinstance(wp, dict) else str(id(wp))
                if thumb_url:
                    threading.Thread(target=self._load_series_thumb, args=(thumb_url, thumb, wid), daemon=True).start()

        hscroll.set_child(hbox)
        outer.append(hscroll)
        return outer

    def _load_series_icon(self, url, widget, cid):
        path = download_thumbnail(url, f"coll_icon_{cid}")
        if path:
            GLib.idle_add(widget.set_filename, str(path))

    def _load_series_thumb(self, url, widget, wid):
        path = download_thumbnail(url, f"series_{wid}")
        if path:
            GLib.idle_add(widget.set_filename, str(path))

    def _load_authors(self):
        resp = api_get("artist/list", {"pi": "1", "ps": "30"}, auth=self.auth)
        if resp and resp.get("code") == 200:
            items = resp["data"].get("list") or []
            GLib.idle_add(self._show_authors, items)

    def _show_authors(self, items):
        for artist in items:
            card = self._build_author_card(artist)
            self.authors_flow.append(card)
            fb_child = card.get_parent()
            if fb_child:
                fb_child.set_focusable(False)

    def _build_author_card(self, artist):
        """Author card: avatar, name, bio."""
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        card.add_css_class("axon-artist-card")
        card.set_size_request(320, 184)

        # Avatar
        avatar = Gtk.Picture()
        avatar.set_content_fit(Gtk.ContentFit.COVER)
        avatar.set_size_request(300, 100)
        card.append(avatar)

        avatar_url = artist.get("avatar", "")
        if avatar_url:
            threading.Thread(target=self._load_author_avatar,
                             args=(avatar_url, avatar, artist["artist_id"]), daemon=True).start()

        # Name
        name = Gtk.Label(label=artist.get("name", "?"))
        name.set_xalign(0)
        name.add_css_class("axon-title")
        name.set_margin_start(6)
        name.set_margin_top(4)
        card.append(name)

        # Bio
        bio = artist.get("brief_description", "")
        if bio:
            bio_label = Gtk.Label(label=bio[:80])
            bio_label.set_xalign(0)
            bio_label.add_css_class("axon-artist-desc")
            bio_label.set_ellipsize(3)
            bio_label.set_wrap(True)
            bio_label.set_lines(2)
            bio_label.set_margin_start(6)
            bio_label.set_margin_end(6)
            bio_label.set_margin_bottom(6)
            card.append(bio_label)

        # Click → filter wallpapers by this artist
        click = Gtk.GestureClick()
        click.connect("released", lambda g, n, x, y: self._browse_artist(artist))
        card.add_controller(click)
        card.set_cursor(Gdk.Cursor.new_from_name("pointer"))

        return card

    def _load_author_avatar(self, url, widget, aid):
        path = download_thumbnail(url, f"artist_{aid}")
        if path:
            GLib.idle_add(widget.set_filename, str(path))

    def _browse_artist(self, artist):
        """Open artist page dialog."""
        ArtistPage(artist, self).show()

    def _on_load_more(self, btn):
        self._load_wallpapers(page=self._current_page + 1, clear=False)

    def _load_wallpapers(self, page: int = 1, clear: bool = True):
        self.status.set_label(tr("loading"))
        self.load_more_btn.set_sensitive(False)

        def _fetch():
            params = {"pi": str(page), "ps": "24", "not_offical": "true"}
            if self._category_id:
                params["category_id"] = self._category_id
            if self._search_query:
                params["title"] = self._search_query
                params["query_type"] = "2"
            if self._fav_only:
                params["favorite_only"] = "true"
            if self._effect_type:
                params["effect_type"] = self._effect_type
            if self._artist_filter:
                params["artist_id"] = self._artist_filter

            resp = api_get("wallpaper/list", params, auth=self.auth)
            if resp and resp.get("code") == 200:
                data = resp["data"]
                items = data.get("list") or []
                total = data.get("count", 0)
                GLib.idle_add(self._show_wallpapers, items, total, page, clear)
            else:
                GLib.idle_add(self.status.set_label, tr("failed"))

        threading.Thread(target=_fetch, daemon=True).start()

    def _show_wallpapers(self, items: list, total: int, page: int, clear: bool):
        if clear:
            child = self.flowbox.get_first_child()
            while child:
                next_child = child.get_next_sibling()
                self.flowbox.remove(child)
                child = next_child

        for wp in items:
            card = WallpaperCard(wp, self)
            self.flowbox.append(card)
            # Prevent FlowBoxChild from stealing button focus
            fb_child = card.get_parent()
            if fb_child:
                fb_child.set_focusable(False)

        self._current_page = page
        self._total_count = total
        shown = page * 24 if page * 24 < total else total
        self.status.set_label(f"{shown} / {total} wallpapers")

        has_more = page * 24 < total
        self.load_more_btn.set_visible(has_more)
        self.load_more_btn.set_sensitive(has_more)
        self.load_more_btn.set_label(f"Load more ({total - shown} remaining)")

        if clear:
            adj = self.scroll.get_vadjustment()
            if adj:
                adj.set_value(0)


DESKTOP_ENTRY = """\
[Desktop Entry]
Name=Razer Axon
Comment=Browse, download and apply Razer Axon wallpapers
Exec={exec_path}
Icon={icon_path}
Terminal=false
Type=Application
Categories=Graphics;Utility;
Keywords=wallpaper;razer;axon;desktop;
StartupWMClass=com.razer.axon.linux
"""

def install():
    """Install desktop entry, icon, and CLI symlinks."""
    script = Path(__file__).resolve()
    project = script.parent
    icon_src = project / "axon.png"

    bin_dir = Path.home() / ".local/bin"
    icon_dir = Path.home() / ".local/share/icons/hicolor/256x256/apps"
    desktop_dir = Path.home() / ".local/share/applications"

    bin_dir.mkdir(parents=True, exist_ok=True)
    icon_dir.mkdir(parents=True, exist_ok=True)
    desktop_dir.mkdir(parents=True, exist_ok=True)

    # Symlinks for CLI tools
    for name, target in [
        ("razer-axon-gui", project / "razer-axon-gui.py"),
        ("razer-login", project / "razer-login.py"),
        ("razer-sync", project / "razer-sync.py"),
        ("razer-axon-decrypt", project / "razer-axon-decrypt.py"),
    ]:
        link = bin_dir / name
        link.unlink(missing_ok=True)
        link.symlink_to(target)
        print(f"  {link} -> {target}")

    # Icon
    icon_dest = icon_dir / "razer-axon.png"
    if icon_src.exists():
        shutil.copy2(icon_src, icon_dest)
        print(f"  Icon: {icon_dest}")
    else:
        icon_dest = Path("razer-axon")  # fallback to theme icon name
        print(f"  Icon: axon.png not found, using fallback")

    # Desktop entry
    desktop_file = desktop_dir / "razer-axon.desktop"
    desktop_file.write_text(DESKTOP_ENTRY.format(
        exec_path=bin_dir / "razer-axon-gui",
        icon_path=icon_dest,
    ))
    desktop_file.chmod(0o755)
    print(f"  Desktop: {desktop_file}")

    # Desktop shortcut (on ~/Desktop or ~/Рабочий стол)
    for desktop_name in ["Desktop", "Рабочий стол"]:
        desktop_path = Path.home() / desktop_name
        if desktop_path.is_dir():
            shortcut = desktop_path / "razer-axon.desktop"
            shutil.copy2(desktop_file, shortcut)
            shortcut.chmod(0o755)
            print(f"  Shortcut: {shortcut}")

    # Update desktop database
    subprocess.run(["update-desktop-database", str(desktop_dir)],
                   capture_output=True)
    subprocess.run(["gtk-update-icon-cache", "-f", "-t",
                    str(Path.home() / ".local/share/icons/hicolor")],
                   capture_output=True)

    print("\n" + tr("installed"))


def uninstall():
    """Remove desktop entry, icon, and CLI symlinks."""
    bin_dir = Path.home() / ".local/bin"
    files = [
        bin_dir / "razer-axon-gui",
        bin_dir / "razer-login",
        bin_dir / "razer-sync",
        bin_dir / "razer-axon-decrypt",
        Path.home() / ".local/share/icons/hicolor/256x256/apps/razer-axon.png",
        Path.home() / ".local/share/applications/razer-axon.desktop",
    ]
    for desktop_name in ["Desktop", "Рабочий стол"]:
        files.append(Path.home() / desktop_name / "razer-axon.desktop")

    for f in files:
        if f.exists() or f.is_symlink():
            f.unlink()
            print(f"  Removed: {f}")

    subprocess.run(["update-desktop-database",
                    str(Path.home() / ".local/share/applications")],
                   capture_output=True)
    print("\n" + tr("uninstalled"))


def main():
    if "--install" in sys.argv:
        print(tr("installing"))
        install()
        return

    if "--uninstall" in sys.argv:
        print(tr("uninstalling"))
        uninstall()
        return

    if "--help" in sys.argv or "-h" in sys.argv:
        print("Usage: razer-axon-gui [--install | --uninstall]")
        print()
        print("Razer Axon wallpaper browser — native GTK4/Adwaita.")
        print("Browse, download, and apply wallpapers on Linux.")
        print()
        print("  --install    Install desktop entry, icon, and CLI commands")
        print("  --uninstall  Remove everything installed by --install")
        print()
        print("Supports: KDE Plasma, GNOME, Xfce, Hyprland, Sway")
        print("Requires: razer-login (first time auth)")
        return

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    os.environ.pop("GTK_THEME", None)
    GLib.log_set_handler("Adwaita", GLib.LogLevelFlags.LEVEL_WARNING | GLib.LogLevelFlags.LEVEL_MESSAGE, lambda *a: None)
    GLib.log_set_handler("Gtk", GLib.LogLevelFlags.LEVEL_WARNING, lambda *a: None)
    app = AxonApp()
    app.run(sys.argv)


if __name__ == "__main__":
    main()
