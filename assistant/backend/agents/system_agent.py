"""System agent — real control of the host machine.

Implements app/file/system control. Windows-specific libraries are imported
lazily inside each method and wrapped in try/except so the module imports on any
OS (the server still boots on Linux for development); on Windows the calls do the
real thing. ``psutil`` / ``webbrowser`` work cross-platform.

Every method returns a ``{"ok": bool, "message": str, ...}`` dict so the command
processor can report a clean result to the UI and voice.
"""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
from typing import Any

from .base import Agent

IS_WINDOWS = platform.system() == "Windows"

# Common app name -> candidate executables / launch strategies.
_KNOWN_APPS = {
    "notepad": ["notepad.exe"],
    "calculator": ["calc.exe"],
    "calc": ["calc.exe"],
    "explorer": ["explorer.exe"],
    "file explorer": ["explorer.exe"],
    "paint": ["mspaint.exe"],
    "cmd": ["cmd.exe"],
    "powershell": ["powershell.exe"],
    "task manager": ["taskmgr.exe"],
    "settings": ["start", "ms-settings:"],
    "chrome": [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    ],
    "edge": [r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe", "msedge.exe"],
    "firefox": [r"C:\Program Files\Mozilla Firefox\firefox.exe"],
    "vs code": ["code"],
    "vscode": ["code"],
    "code": ["code"],
    "spotify": [
        os.path.expanduser(r"~\AppData\Roaming\Spotify\Spotify.exe"),
        "spotify.exe",
    ],
    "discord": [os.path.expanduser(r"~\AppData\Local\Discord\Update.exe")],
}


class SystemAgent(Agent):
    """Controls apps, files, and system state on the host."""

    name = "system"

    # ------------------------------------------------------------------ #
    # App control
    # ------------------------------------------------------------------ #
    def open_app(self, app: str) -> dict[str, Any]:
        """Open an application by friendly name."""
        app = app.strip().lower()
        candidates = _self_app_paths().get(app) or _KNOWN_APPS.get(app)
        try:
            if candidates:
                # ms-settings: style launch
                if candidates[0] == "start":
                    if IS_WINDOWS:
                        os.startfile(candidates[1])  # type: ignore[attr-defined]
                        return self._ok(f"Opened {app}")
                for path in candidates:
                    if os.path.exists(path):
                        subprocess.Popen([path])
                        return self._ok(f"Opened {app}")
                    found = shutil.which(path)
                    if found:
                        subprocess.Popen([found])
                        return self._ok(f"Opened {app}")
            # Fallback: try the registry / PATH, then a generic start.
            exe = shutil.which(app) or shutil.which(f"{app}.exe")
            if exe:
                subprocess.Popen([exe])
                return self._ok(f"Opened {app}")
            if IS_WINDOWS:
                os.startfile(app)  # type: ignore[attr-defined]
                return self._ok(f"Opened {app}")
            return self._fail(f"Could not locate '{app}'. Add a path override in Settings.")
        except Exception as exc:  # noqa: BLE001
            return self._fail(f"Failed to open {app}: {exc}")

    def close_app(self, app: str) -> dict[str, Any]:
        """Terminate processes whose name matches ``app``."""
        try:
            import psutil

            target = app.strip().lower().replace(".exe", "")
            killed = 0
            for proc in psutil.process_iter(["name"]):
                pname = (proc.info.get("name") or "").lower()
                if target in pname:
                    try:
                        proc.terminate()
                        killed += 1
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        pass
            if killed:
                return self._ok(f"Closed {killed} '{app}' process(es)")
            return self._fail(f"No running process matched '{app}'")
        except Exception as exc:  # noqa: BLE001
            return self._fail(f"Failed to close {app}: {exc}")

    def list_open_apps(self) -> dict[str, Any]:
        """Snapshot of notable running processes."""
        try:
            import psutil

            seen: dict[str, int] = {}
            for proc in psutil.process_iter(["name"]):
                n = proc.info.get("name") or ""
                if n:
                    seen[n] = seen.get(n, 0) + 1
            apps = sorted(seen.items(), key=lambda kv: -kv[1])[:40]
            return {"ok": True, "message": f"{len(seen)} processes running",
                    "apps": [{"name": n, "count": c} for n, c in apps]}
        except Exception as exc:  # noqa: BLE001
            return self._fail(f"Could not list apps: {exc}")

    def focus_app(self, app: str) -> dict[str, Any]:
        """Bring a window matching ``app`` to the foreground (Windows)."""
        try:
            import pygetwindow as gw

            wins = [w for w in gw.getAllWindows() if app.lower() in (w.title or "").lower()]
            if not wins:
                return self._fail(f"No window titled like '{app}'")
            wins[0].activate()
            return self._ok(f"Focused {app}")
        except Exception as exc:  # noqa: BLE001
            return self._fail(f"Focus needs Windows + pygetwindow: {exc}")

    # ------------------------------------------------------------------ #
    # Files
    # ------------------------------------------------------------------ #
    def open_file(self, path: str) -> dict[str, Any]:
        """Open a file with its default program."""
        path = os.path.expanduser(path)
        if not os.path.exists(path):
            return self._fail(f"File not found: {path}")
        try:
            if IS_WINDOWS:
                os.startfile(path)  # type: ignore[attr-defined]
            elif platform.system() == "Darwin":
                subprocess.Popen(["open", path])
            else:
                subprocess.Popen(["xdg-open", path])
            return self._ok(f"Opened {os.path.basename(path)}")
        except Exception as exc:  # noqa: BLE001
            return self._fail(str(exc))

    def list_files(self, directory: str) -> dict[str, Any]:
        """List entries in a directory."""
        directory = os.path.expanduser(directory)
        if not os.path.isdir(directory):
            return self._fail(f"Not a directory: {directory}")
        entries = []
        for name in sorted(os.listdir(directory))[:200]:
            full = os.path.join(directory, name)
            entries.append({"name": name, "dir": os.path.isdir(full),
                            "size": os.path.getsize(full) if os.path.isfile(full) else 0})
        return {"ok": True, "message": f"{len(entries)} items", "entries": entries}

    def search_files(self, query: str, directory: str) -> dict[str, Any]:
        """Recursive filename search."""
        directory = os.path.expanduser(directory)
        q = query.lower()
        hits = []
        for dirpath, _dirs, files in os.walk(directory):
            for name in files:
                if q in name.lower():
                    hits.append(os.path.join(dirpath, name))
                    if len(hits) >= 100:
                        break
        return {"ok": True, "message": f"{len(hits)} matches", "files": hits}

    def read_file(self, path: str) -> dict[str, Any]:
        """Read a text file's content (truncated)."""
        path = os.path.expanduser(path)
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as fh:
                return {"ok": True, "message": "read", "content": fh.read(20000)}
        except OSError as exc:
            return self._fail(str(exc))

    def create_file(self, path: str, content: str = "") -> dict[str, Any]:
        """Create/overwrite a text file."""
        path = os.path.expanduser(path)
        try:
            os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(content)
            return self._ok(f"Created {path}")
        except OSError as exc:
            return self._fail(str(exc))

    def move_file(self, src: str, dst: str) -> dict[str, Any]:
        """Move/rename a file."""
        try:
            shutil.move(os.path.expanduser(src), os.path.expanduser(dst))
            return self._ok(f"Moved to {dst}")
        except OSError as exc:
            return self._fail(str(exc))

    def delete_file(self, path: str) -> dict[str, Any]:
        """Delete a file (destructive — UI confirms before calling)."""
        path = os.path.expanduser(path)
        try:
            os.remove(path)
            return self._ok(f"Deleted {os.path.basename(path)}")
        except OSError as exc:
            return self._fail(str(exc))

    # ------------------------------------------------------------------ #
    # System
    # ------------------------------------------------------------------ #
    def get_system_stats(self) -> dict[str, Any]:
        """CPU / RAM / disk / battery snapshot via psutil."""
        try:
            import psutil

            battery = None
            try:
                b = psutil.sensors_battery()
                battery = round(b.percent) if b else None
            except Exception:  # noqa: BLE001
                battery = None
            disk = psutil.disk_usage(os.path.abspath(os.sep))
            return {
                "ok": True,
                "cpu": psutil.cpu_percent(interval=0.0),
                "ram": psutil.virtual_memory().percent,
                "disk": disk.percent,
                "disk_free_gb": round(disk.free / 1e9, 1),
                "battery": battery,
            }
        except Exception as exc:  # noqa: BLE001
            return self._fail(str(exc))

    def take_screenshot(self) -> dict[str, Any]:
        """Capture the screen to the vault's screenshots folder."""
        try:
            from .. import memory

            import pyautogui

            root = memory.ensure_vault()
            import time as _t

            path = os.path.join(root, "screenshots", f"shot-{int(_t.time())}.png")
            pyautogui.screenshot(path)
            return {"ok": True, "message": "Screenshot saved", "path": path}
        except Exception as exc:  # noqa: BLE001
            return self._fail(f"Screenshot needs a display + pyautogui: {exc}")

    def type_text(self, text: str) -> dict[str, Any]:
        """Type text via the keyboard."""
        try:
            import pyautogui

            pyautogui.typewrite(text, interval=0.01)
            return self._ok("Typed text")
        except Exception as exc:  # noqa: BLE001
            return self._fail(f"Typing needs pyautogui: {exc}")

    def click_at(self, x: int, y: int) -> dict[str, Any]:
        """Click at screen coordinates."""
        try:
            import pyautogui

            pyautogui.click(x, y)
            return self._ok(f"Clicked ({x}, {y})")
        except Exception as exc:  # noqa: BLE001
            return self._fail(f"Click needs pyautogui: {exc}")

    def get_clipboard(self) -> dict[str, Any]:
        """Read the clipboard text."""
        try:
            import pyperclip

            return {"ok": True, "message": "clipboard read", "content": pyperclip.paste()}
        except Exception as exc:  # noqa: BLE001
            return self._fail(f"Clipboard needs pyperclip: {exc}")

    def set_clipboard(self, text: str) -> dict[str, Any]:
        """Set the clipboard text."""
        try:
            import pyperclip

            pyperclip.copy(text)
            return self._ok("Clipboard set")
        except Exception as exc:  # noqa: BLE001
            return self._fail(f"Clipboard needs pyperclip: {exc}")

    def set_volume(self, level: int) -> dict[str, Any]:
        """Set master volume 0-100 (Windows, via pycaw)."""
        try:
            from ctypes import cast, POINTER
            from comtypes import CLSCTX_ALL
            from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume

            devices = AudioUtilities.GetSpeakers()
            iface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
            vol = cast(iface, POINTER(IAudioEndpointVolume))
            vol.SetMasterVolumeLevelScalar(max(0, min(100, level)) / 100.0, None)
            return self._ok(f"Volume set to {level}%")
        except Exception as exc:  # noqa: BLE001
            return self._fail(f"Volume needs Windows + pycaw: {exc}")

    def open_url(self, url: str) -> dict[str, Any]:
        """Open a URL in the default browser."""
        import webbrowser

        if not url.startswith(("http://", "https://")):
            url = "https://" + url
        webbrowser.open(url)
        return self._ok(f"Opened {url}")

    # ------------------------------------------------------------------ #
    def _ok(self, message: str) -> dict[str, Any]:
        self.set_status("active", last_action=message)
        return {"ok": True, "message": message}

    def _fail(self, message: str) -> dict[str, Any]:
        self.set_status("error", last_action=message)
        return {"ok": False, "message": message}


def _self_app_paths() -> dict[str, list[str]]:
    """User-configured app path overrides from config."""
    from .. import config

    overrides = config.load().get("app_paths", {}) or {}
    return {k.lower(): [v] for k, v in overrides.items()}
