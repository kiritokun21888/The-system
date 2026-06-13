"""System control module — ZERO's hands on the operating system.

Cross-platform (macOS / Windows / Linux) helpers for launching and killing
applications, inspecting the machine, file operations, clipboard, and power
management. Destructive operations are gated behind an explicit ``confirmed``
flag so the UI can present a confirmation modal first.
"""
from __future__ import annotations

import logging
import os
import platform
import shutil
import subprocess
import webbrowser
from pathlib import Path
from typing import Any

import psutil

logger = logging.getLogger("zero.system")

SYSTEM = platform.system()  # 'Darwin', 'Windows', 'Linux'

# Friendly name -> per-platform launch target.
APP_MAP: dict[str, dict[str, str]] = {
    "spotify": {"Darwin": "Spotify", "Windows": "spotify.exe", "Linux": "spotify"},
    "chrome": {
        "Darwin": "Google Chrome",
        "Windows": "chrome.exe",
        "Linux": "google-chrome",
    },
    "safari": {"Darwin": "Safari", "Windows": "", "Linux": ""},
    "firefox": {"Darwin": "Firefox", "Windows": "firefox.exe", "Linux": "firefox"},
    "code": {"Darwin": "Visual Studio Code", "Windows": "code", "Linux": "code"},
    "vscode": {"Darwin": "Visual Studio Code", "Windows": "code", "Linux": "code"},
    "terminal": {"Darwin": "Terminal", "Windows": "cmd.exe", "Linux": "gnome-terminal"},
    "finder": {"Darwin": "Finder", "Windows": "explorer.exe", "Linux": "nautilus"},
    "notes": {"Darwin": "Notes", "Windows": "notepad.exe", "Linux": "gedit"},
    "slack": {"Darwin": "Slack", "Windows": "slack.exe", "Linux": "slack"},
}

DESTRUCTIVE_ACTIONS = {"delete_file", "lock_screen", "sleep_computer", "restart"}


class SystemAgent:
    """Stateless wrapper around OS-level capabilities."""

    # --- Applications ---

    def open_application(self, name: str) -> dict[str, Any]:
        key = name.strip().lower()
        target = APP_MAP.get(key, {}).get(SYSTEM, name)
        if not target:
            return {"ok": False, "error": f"'{name}' is not mapped for {SYSTEM}."}
        try:
            if SYSTEM == "Darwin":
                subprocess.Popen(["open", "-a", target])
            elif SYSTEM == "Windows":
                subprocess.Popen(target, shell=True)
            else:  # Linux
                subprocess.Popen([target])
            return {"ok": True, "message": f"Launching {name}."}
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": str(exc)}

    def close_application(self, name: str) -> dict[str, Any]:
        key = name.strip().lower()
        killed = 0
        for proc in psutil.process_iter(["name"]):
            pname = (proc.info.get("name") or "").lower()
            if key in pname:
                try:
                    proc.terminate()
                    killed += 1
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
        if killed:
            return {"ok": True, "message": f"Terminated {killed} '{name}' process(es)."}
        return {"ok": False, "error": f"No running process matched '{name}'."}

    def list_running_apps(self, limit: int = 40) -> dict[str, Any]:
        seen: dict[str, dict] = {}
        for proc in psutil.process_iter(["name", "pid", "cpu_percent", "memory_percent"]):
            name = proc.info.get("name")
            if not name:
                continue
            entry = seen.setdefault(name, {"name": name, "count": 0, "memory_percent": 0.0})
            entry["count"] += 1
            entry["memory_percent"] += proc.info.get("memory_percent") or 0.0
        apps = sorted(seen.values(), key=lambda a: a["memory_percent"], reverse=True)
        return {"ok": True, "apps": apps[:limit]}

    # --- Machine stats ---

    def get_system_stats(self) -> dict[str, Any]:
        mem = psutil.virtual_memory()
        disk = psutil.disk_usage("/")
        battery = None
        try:
            batt = psutil.sensors_battery()
            if batt is not None:
                battery = {"percent": batt.percent, "plugged": batt.power_plugged}
        except Exception:  # noqa: BLE001
            battery = None
        return {
            "ok": True,
            "cpu_percent": psutil.cpu_percent(interval=0.2),
            "cpu_count": psutil.cpu_count(),
            "memory": {"percent": mem.percent, "used_gb": round(mem.used / 1e9, 2),
                       "total_gb": round(mem.total / 1e9, 2)},
            "disk": {"percent": disk.percent, "used_gb": round(disk.used / 1e9, 2),
                     "total_gb": round(disk.total / 1e9, 2)},
            "battery": battery,
            "platform": SYSTEM,
        }

    # --- Files & URLs ---

    def open_file(self, path: str) -> dict[str, Any]:
        p = Path(path).expanduser()
        if not p.exists():
            return {"ok": False, "error": f"Path does not exist: {p}"}
        try:
            if SYSTEM == "Darwin":
                subprocess.Popen(["open", str(p)])
            elif SYSTEM == "Windows":
                os.startfile(str(p))  # type: ignore[attr-defined]
            else:
                subprocess.Popen(["xdg-open", str(p)])
            return {"ok": True, "message": f"Opened {p}"}
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": str(exc)}

    def open_url(self, url: str) -> dict[str, Any]:
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
        webbrowser.open(url)
        return {"ok": True, "message": f"Opening {url}"}

    def list_files(self, directory: str) -> dict[str, Any]:
        p = Path(directory).expanduser()
        if not p.is_dir():
            return {"ok": False, "error": f"Not a directory: {p}"}
        items = []
        for child in sorted(p.iterdir()):
            try:
                items.append({
                    "name": child.name,
                    "is_dir": child.is_dir(),
                    "size": child.stat().st_size if child.is_file() else None,
                })
            except OSError:
                continue
        return {"ok": True, "path": str(p), "items": items}

    def move_file(self, src: str, dst: str) -> dict[str, Any]:
        try:
            shutil.move(str(Path(src).expanduser()), str(Path(dst).expanduser()))
            return {"ok": True, "message": f"Moved {src} -> {dst}"}
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": str(exc)}

    def delete_file(self, path: str, confirmed: bool = False) -> dict[str, Any]:
        if not confirmed:
            return {"ok": False, "needs_confirmation": True,
                    "action": "delete_file", "target": path,
                    "message": f"Confirm deletion of {path}"}
        p = Path(path).expanduser()
        try:
            if p.is_dir():
                shutil.rmtree(p)
            else:
                p.unlink()
            return {"ok": True, "message": f"Deleted {p}"}
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": str(exc)}

    # --- Clipboard ---

    def get_clipboard(self) -> dict[str, Any]:
        try:
            import pyperclip
            return {"ok": True, "text": pyperclip.paste()}
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": f"Clipboard unavailable: {exc}"}

    def set_clipboard(self, text: str) -> dict[str, Any]:
        try:
            import pyperclip
            pyperclip.copy(text)
            return {"ok": True, "message": "Clipboard updated."}
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": f"Clipboard unavailable: {exc}"}

    # --- Screen automation (optional deps) ---

    def take_screenshot(self, save_dir: str | None = None) -> dict[str, Any]:
        try:
            import pyautogui
            from datetime import datetime
            target = Path(save_dir or Path.home() / "Pictures").expanduser()
            target.mkdir(parents=True, exist_ok=True)
            fname = target / f"zero_shot_{datetime.now():%Y%m%d_%H%M%S}.png"
            pyautogui.screenshot(str(fname))
            return {"ok": True, "path": str(fname)}
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": f"Screenshot unavailable: {exc}"}

    def type_text(self, text: str) -> dict[str, Any]:
        try:
            import pyautogui
            pyautogui.typewrite(text, interval=0.01)
            return {"ok": True, "message": "Typed text."}
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": f"Typing unavailable: {exc}"}

    # --- Power management (destructive) ---

    def lock_screen(self, confirmed: bool = False) -> dict[str, Any]:
        if not confirmed:
            return {"ok": False, "needs_confirmation": True, "action": "lock_screen",
                    "message": "Confirm screen lock."}
        try:
            if SYSTEM == "Darwin":
                subprocess.Popen(["pmset", "displaysleepnow"])
            elif SYSTEM == "Windows":
                subprocess.Popen("rundll32.exe user32.dll,LockWorkStation", shell=True)
            else:
                subprocess.Popen(["loginctl", "lock-session"])
            return {"ok": True, "message": "Locking screen."}
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": str(exc)}

    def sleep_computer(self, confirmed: bool = False) -> dict[str, Any]:
        if not confirmed:
            return {"ok": False, "needs_confirmation": True, "action": "sleep_computer",
                    "message": "Confirm putting the computer to sleep."}
        try:
            if SYSTEM == "Darwin":
                subprocess.Popen(["pmset", "sleepnow"])
            elif SYSTEM == "Windows":
                subprocess.Popen("rundll32.exe powrprof.dll,SetSuspendState 0,1,0", shell=True)
            else:
                subprocess.Popen(["systemctl", "suspend"])
            return {"ok": True, "message": "Sleeping."}
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": str(exc)}

    def restart(self, confirmed: bool = False) -> dict[str, Any]:
        if not confirmed:
            return {"ok": False, "needs_confirmation": True, "action": "restart",
                    "message": "Confirm system restart."}
        try:
            if SYSTEM == "Darwin":
                subprocess.Popen(["osascript", "-e", 'tell app "System Events" to restart'])
            elif SYSTEM == "Windows":
                subprocess.Popen("shutdown /r /t 0", shell=True)
            else:
                subprocess.Popen(["systemctl", "reboot"])
            return {"ok": True, "message": "Restarting."}
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": str(exc)}


system_agent = SystemAgent()
