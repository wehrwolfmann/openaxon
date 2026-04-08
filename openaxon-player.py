#!/usr/bin/env python3
"""
OpenAxon Wallpaper Player — native Linux wallpaper daemon.

Manages video and static wallpapers with playback control,
per-monitor assignment, visual effects, and playlist support.

Protocol-compatible with Razer Axon WallpaperPlayer pipe commands
(Play, Switch, Stop, Pause, Resume, Volume, PlayEffect, Terminate).

Usage:
    openaxon-player                    # start daemon
    openaxon-player --status           # show current state
    openaxon-player --play FILE        # play wallpaper
    openaxon-player --stop             # stop playback
    openaxon-player --pause            # pause
    openaxon-player --resume           # resume
    openaxon-player --volume 50        # set volume (0-100)
    openaxon-player --terminate        # stop daemon
"""

import argparse
import json
import logging
import os
import shutil
import signal
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Optional

log = logging.getLogger("openaxon-player")

# ── Config ──

SOCKET_PATH = Path(os.environ.get(
    "OPENAXON_SOCKET",
    Path.home() / ".config/razer-axon/player.sock"
))
PID_FILE = SOCKET_PATH.with_suffix(".pid")


# ── Wallpaper Types ──

def detect_media_type(path: str) -> str:
    """Detect wallpaper type from file extension."""
    ext = Path(path).suffix.lower()
    if ext in (".mp4", ".webm", ".mkv", ".avi", ".mov"):
        return "Video"
    if ext in (".html", ".htm"):
        return "Web"
    return "Image"


def detect_session() -> str:
    return os.environ.get("XDG_SESSION_TYPE", "x11")


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
    return de


# ── Monitor Player ──

class MonitorPlayer:
    """Manages wallpaper playback on a single monitor."""

    def __init__(self, monitor_id: str = "*"):
        self.monitor_id = monitor_id
        self.process: Optional[subprocess.Popen] = None
        self.source: Optional[str] = None
        self.media_type: Optional[str] = None
        self.paused = False
        self.volume = 0.0  # 0.0-1.0
        self.effects: dict = {}

    def play(self, source: str, media_type: str, effects: dict = None):
        """Start wallpaper playback."""
        self.stop()
        self.source = source
        self.media_type = media_type
        self.paused = False
        if effects:
            self.effects = effects

        if media_type == "Video":
            self._play_video(source)
        elif media_type == "Web":
            self._play_web(source)
        else:
            self._play_image(source)

        log.info(f"Playing {media_type}: {source} on {self.monitor_id}")

    def _play_video(self, path: str):
        """Play video wallpaper via mpv."""
        session = detect_session()

        if session == "wayland" and shutil.which("mpvpaper"):
            cmd = ["mpvpaper", "-o", f"no-audio loop", self.monitor_id, path]
            self.process = subprocess.Popen(
                cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return

        # X11: use mpv with --wid on root window, or xwinwrap
        if shutil.which("xwinwrap") and shutil.which("mpv"):
            mpv_args = [
                "--no-osc", "--no-osd-bar", "--no-input-default-bindings",
                "--loop", f"--volume={int(self.volume * 100)}",
                "--panscan=1.0",
            ]
            # Apply effects
            vf_filters = self._build_vf_filters()
            if vf_filters:
                mpv_args.append(f"--vf={','.join(vf_filters)}")

            speed = self.effects.get("PlayRate", "1.0")
            if speed != "1.0":
                mpv_args.append(f"--speed={speed}")

            cmd = [
                "xwinwrap", "-g", "1920x1080+0+0", "-ov", "-ni", "-s",
                "-nf", "-b", "-un", "-argb", "--",
                "mpv", "--wid", "WID", *mpv_args, path
            ]
            self.process = subprocess.Popen(
                cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return

        # Fallback: plain mpv
        if shutil.which("mpv"):
            cmd = ["mpv", "--no-audio", "--loop", "--fs",
                   "--no-osc", "--no-osd-bar", path]
            self.process = subprocess.Popen(
                cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def _play_web(self, path: str):
        """Play web wallpaper. Requires a WebKit renderer (future)."""
        log.warning(f"Web wallpapers not yet supported: {path}")
        # TODO: launch webkitgtk-based renderer

    def _play_image(self, path: str):
        """Set static image wallpaper."""
        de = detect_de()
        fill_mode = self.effects.get("WallpaperFillingMode", "Fill")

        if de == "kde":
            if shutil.which("plasma-apply-wallpaperimage"):
                subprocess.run(["plasma-apply-wallpaperimage", path],
                              capture_output=True)
                return
        elif de == "gnome":
            uri = f"file://{path}"
            subprocess.run(["gsettings", "set", "org.gnome.desktop.background",
                          "picture-uri", uri], capture_output=True)
            subprocess.run(["gsettings", "set", "org.gnome.desktop.background",
                          "picture-uri-dark", uri], capture_output=True)
            return
        elif de == "xfce":
            subprocess.run(["xfconf-query", "-c", "xfce4-desktop", "-p",
                          "/backdrop/screen0/monitor0/workspace0/last-image",
                          "-s", path], capture_output=True)
            return
        elif de in ("hyprland", "sway"):
            if shutil.which("swaybg"):
                mode_map = {"Fill": "fill", "Fit": "fit", "Stretch": "stretch",
                           "Center": "center", "Tile": "tile"}
                sway_mode = mode_map.get(fill_mode, "fill")
                self.stop()
                self.process = subprocess.Popen(
                    ["swaybg", "-i", path, "-m", sway_mode],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return

        # Fallback
        if shutil.which("feh"):
            feh_mode = {"Fill": "--bg-fill", "Fit": "--bg-max",
                       "Stretch": "--bg-scale", "Center": "--bg-center",
                       "Tile": "--bg-tile"}.get(fill_mode, "--bg-fill")
            subprocess.run(["feh", feh_mode, path], capture_output=True)

    def _build_vf_filters(self) -> list:
        """Build mpv video filters from effects."""
        filters = []
        brightness = self.effects.get("Brightness")
        contrast = self.effects.get("Contrast")
        hue = self.effects.get("Hue")
        saturation = self.effects.get("Saturation")

        eq_parts = []
        if brightness and brightness != "1.0":
            # mpv eq brightness is -1 to 1, Axon is 0-2 (1.0 = normal)
            val = float(brightness) - 1.0
            eq_parts.append(f"brightness={val:.2f}")
        if contrast and contrast != "1.0":
            val = float(contrast) - 1.0
            eq_parts.append(f"contrast={val:.2f}")
        if saturation and saturation != "1.0":
            val = float(saturation) - 1.0
            eq_parts.append(f"saturation={val:.2f}")
        if eq_parts:
            filters.append(f"eq={':'.join(eq_parts)}")

        if hue and hue != "0":
            filters.append(f"hue=h={hue}")

        return filters

    def stop(self):
        """Stop playback."""
        if self.process:
            try:
                self.process.terminate()
                self.process.wait(timeout=3)
            except (ProcessLookupError, subprocess.TimeoutExpired):
                try:
                    self.process.kill()
                except ProcessLookupError:
                    pass
            self.process = None
        self.paused = False
        log.info(f"Stopped on {self.monitor_id}")

    def pause(self):
        """Pause video playback (SIGSTOP)."""
        if self.process and not self.paused:
            try:
                os.kill(self.process.pid, signal.SIGSTOP)
                self.paused = True
                log.info(f"Paused on {self.monitor_id}")
            except ProcessLookupError:
                pass

    def resume(self):
        """Resume video playback (SIGCONT)."""
        if self.process and self.paused:
            try:
                os.kill(self.process.pid, signal.SIGCONT)
                self.paused = False
                log.info(f"Resumed on {self.monitor_id}")
            except ProcessLookupError:
                pass

    def set_volume(self, volume: float):
        """Set volume (0.0-1.0). Only for mpv-based playback."""
        self.volume = max(0.0, min(1.0, volume))
        # TODO: send volume command to mpv via IPC socket

    def set_effects(self, effects: dict):
        """Update visual effects. Requires restart for mpv."""
        self.effects.update(effects)
        # For live effect changes, would need mpv JSON IPC
        log.info(f"Effects updated: {effects}")

    def status(self) -> dict:
        running = self.process is not None and self.process.poll() is None
        return {
            "monitor": self.monitor_id,
            "source": self.source,
            "type": self.media_type,
            "playing": running and not self.paused,
            "paused": self.paused,
            "volume": int(self.volume * 100),
            "effects": self.effects,
        }


# ── Player Daemon ──

class PlayerDaemon:
    """Background daemon managing wallpaper playback."""

    def __init__(self):
        self.players: dict[str, MonitorPlayer] = {}
        self.running = False
        self._server_socket: Optional[socket.socket] = None

    def get_player(self, monitor_id: str = "*") -> MonitorPlayer:
        if monitor_id not in self.players:
            self.players[monitor_id] = MonitorPlayer(monitor_id)
        return self.players[monitor_id]

    def handle_command(self, data: str) -> str:
        """Handle a JSON command and return response."""
        try:
            cmd = json.loads(data)
        except json.JSONDecodeError:
            return json.dumps({"error": "invalid JSON"})

        command = cmd.get("Command", cmd.get("command", ""))
        monitor = cmd.get("MonitorId", cmd.get("monitor", "*"))
        source = cmd.get("Source", cmd.get("source", ""))
        media_type = cmd.get("Type", cmd.get("type", ""))

        if command == "Play" or command == "Switch":
            if not source:
                return json.dumps({"error": "no source"})
            if not media_type:
                media_type = detect_media_type(source)
            effects = {}
            pe = cmd.get("PlayEffects", cmd.get("effects", ""))
            if pe and isinstance(pe, str):
                try:
                    effects = json.loads(pe)
                except json.JSONDecodeError:
                    pass
            elif isinstance(pe, dict):
                effects = pe
            player = self.get_player(monitor)
            player.play(source, media_type, effects)
            return json.dumps({"ok": True, "playing": source})

        elif command == "Stop":
            self.get_player(monitor).stop()
            return json.dumps({"ok": True})

        elif command == "Pause":
            self.get_player(monitor).pause()
            return json.dumps({"ok": True})

        elif command == "Resume":
            self.get_player(monitor).resume()
            return json.dumps({"ok": True})

        elif command == "Volume":
            vol = float(source) if source else float(cmd.get("value", 0.5))
            self.get_player(monitor).set_volume(vol)
            return json.dumps({"ok": True, "volume": int(vol * 100)})

        elif command == "PlayEffect":
            effects = {}
            pe = cmd.get("PlayEffects", cmd.get("effects", ""))
            if pe and isinstance(pe, str):
                try:
                    effects = json.loads(pe)
                except json.JSONDecodeError:
                    pass
            elif isinstance(pe, dict):
                effects = pe
            self.get_player(monitor).set_effects(effects)
            return json.dumps({"ok": True})

        elif command == "Terminate":
            self.stop_all()
            self.running = False
            return json.dumps({"ok": True, "terminated": True})

        elif command == "Status":
            statuses = {mid: p.status() for mid, p in self.players.items()}
            return json.dumps({"players": statuses})

        else:
            return json.dumps({"error": f"unknown command: {command}"})

    def stop_all(self):
        for player in self.players.values():
            player.stop()

    def start(self):
        """Start the daemon, listening on Unix socket."""
        SOCKET_PATH.parent.mkdir(parents=True, exist_ok=True)

        # Clean up stale socket
        if SOCKET_PATH.exists():
            try:
                SOCKET_PATH.unlink()
            except OSError:
                pass

        self._server_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self._server_socket.bind(str(SOCKET_PATH))
        self._server_socket.listen(5)
        self._server_socket.settimeout(1.0)
        self.running = True

        # Write PID file
        PID_FILE.write_text(str(os.getpid()))

        log.info(f"Player daemon started on {SOCKET_PATH}")

        signal.signal(signal.SIGTERM, lambda s, f: self._shutdown())
        signal.signal(signal.SIGINT, lambda s, f: self._shutdown())

        try:
            while self.running:
                try:
                    conn, _ = self._server_socket.accept()
                    threading.Thread(target=self._handle_client, args=(conn,),
                                   daemon=True).start()
                except socket.timeout:
                    continue
        finally:
            self._cleanup()

    def _handle_client(self, conn: socket.socket):
        try:
            data = b""
            while True:
                chunk = conn.recv(4096)
                if not chunk:
                    break
                data += chunk
                if b"\n" in data or len(data) > 65536:
                    break

            if data:
                response = self.handle_command(data.decode("utf-8").strip())
                conn.sendall((response + "\n").encode("utf-8"))
        except Exception as e:
            log.error(f"Client error: {e}")
        finally:
            conn.close()

    def _shutdown(self):
        log.info("Shutting down...")
        self.running = False

    def _cleanup(self):
        self.stop_all()
        if self._server_socket:
            self._server_socket.close()
        try:
            SOCKET_PATH.unlink(missing_ok=True)
            PID_FILE.unlink(missing_ok=True)
        except OSError:
            pass
        log.info("Player daemon stopped")


# ── Client ──

def send_command(cmd: dict) -> dict:
    """Send a command to the running daemon."""
    try:
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.connect(str(SOCKET_PATH))
        sock.sendall((json.dumps(cmd) + "\n").encode("utf-8"))
        data = sock.recv(65536).decode("utf-8").strip()
        sock.close()
        return json.loads(data) if data else {}
    except (ConnectionRefusedError, FileNotFoundError):
        return {"error": "daemon not running"}


def is_daemon_running() -> bool:
    if not PID_FILE.exists():
        return False
    try:
        pid = int(PID_FILE.read_text().strip())
        os.kill(pid, 0)
        return True
    except (ProcessLookupError, ValueError):
        PID_FILE.unlink(missing_ok=True)
        return False


def ensure_daemon():
    """Start daemon if not running."""
    if is_daemon_running():
        return
    pid = os.fork()
    if pid == 0:
        # Child — become daemon
        os.setsid()
        daemon = PlayerDaemon()
        daemon.start()
        sys.exit(0)
    else:
        # Parent — wait for socket
        for _ in range(20):
            time.sleep(0.25)
            if SOCKET_PATH.exists():
                return
        print("Warning: daemon may not have started", file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(description="OpenAxon Wallpaper Player")
    parser.add_argument("--daemon", action="store_true",
                       help="Run as foreground daemon")
    parser.add_argument("--play", metavar="FILE",
                       help="Play wallpaper file")
    parser.add_argument("--stop", action="store_true",
                       help="Stop playback")
    parser.add_argument("--pause", action="store_true",
                       help="Pause playback")
    parser.add_argument("--resume", action="store_true",
                       help="Resume playback")
    parser.add_argument("--volume", type=int, metavar="0-100",
                       help="Set volume")
    parser.add_argument("--status", action="store_true",
                       help="Show current status")
    parser.add_argument("--terminate", action="store_true",
                       help="Stop daemon")
    parser.add_argument("--monitor", default="*",
                       help="Target monitor ID (default: all)")
    parser.add_argument("--type", choices=["Video", "Image", "Web"],
                       help="Force media type")
    parser.add_argument("--effects", type=json.loads, default={},
                       help='JSON effects: \'{"Brightness":"0.8"}\'')
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO,
                       format="%(asctime)s %(name)s %(levelname)s %(message)s")

    if args.daemon:
        daemon = PlayerDaemon()
        daemon.start()
        return

    # Client mode — send command to daemon
    if args.play:
        ensure_daemon()
        media_type = args.type or detect_media_type(args.play)
        result = send_command({
            "Command": "Play",
            "MonitorId": args.monitor,
            "Type": media_type,
            "Source": str(Path(args.play).resolve()),
            "PlayEffects": json.dumps(args.effects) if args.effects else "",
        })
        print(json.dumps(result, indent=2))
    elif args.stop:
        result = send_command({"Command": "Stop", "MonitorId": args.monitor})
        print(json.dumps(result, indent=2))
    elif args.pause:
        result = send_command({"Command": "Pause", "MonitorId": args.monitor})
        print(json.dumps(result, indent=2))
    elif args.resume:
        result = send_command({"Command": "Resume", "MonitorId": args.monitor})
        print(json.dumps(result, indent=2))
    elif args.volume is not None:
        result = send_command({
            "Command": "Volume", "MonitorId": args.monitor,
            "Source": str(args.volume / 100.0)
        })
        print(json.dumps(result, indent=2))
    elif args.terminate:
        result = send_command({"Command": "Terminate"})
        print(json.dumps(result, indent=2))
    elif args.status:
        if not is_daemon_running():
            print("Daemon not running")
            return
        result = send_command({"Command": "Status"})
        print(json.dumps(result, indent=2))
    else:
        # No args — start daemon in background
        if is_daemon_running():
            print("Daemon already running")
            result = send_command({"Command": "Status"})
            print(json.dumps(result, indent=2))
        else:
            ensure_daemon()
            print(f"Daemon started (socket: {SOCKET_PATH})")


if __name__ == "__main__":
    main()
