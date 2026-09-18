"""Linux implementation of AutomationAdapter. Targets GNOME/Fedora by
default (gnome-control-center) — adjust ALLOWED_SETTINGS if your desktop
environment differs (KDE, XFCE, etc.)."""

import subprocess
import urllib.parse

import pyautogui

from app.automation.base import AutomationAdapter

# Common app name -> launch command. Extend as needed.
APP_MAP = {
    "chrome": "google-chrome",
    "firefox": "firefox",
    "files": "nautilus",
    "file explorer": "nautilus",
    "terminal": "gnome-terminal",
    "settings": "gnome-control-center",
    "text editor": "gedit",
}

# Only these settings can be changed by voice — anything else is rejected.
# Opens the relevant panel in gnome-control-center rather than silently
# changing a value, so the user still confirms the actual change.
ALLOWED_SETTINGS = {
    "wifi": "wifi",
    "bluetooth": "bluetooth",
    "display": "display",
    "sound": "sound",
    "battery": "power",
}


class LinuxAdapter(AutomationAdapter):

    def open_app(self, name: str) -> dict:
        key = name.strip().lower()
        command = APP_MAP.get(key, key)
        try:
            subprocess.Popen(command, shell=True)
            return self.ok(f"Opened {name}")
        except Exception as exc:
            return self.error(f"Could not open {name}: {exc}")

    def web_search(self, app: str, query: str) -> dict:
        key = app.strip().lower()
        browser_cmd = APP_MAP.get(key, key)
        url = "https://www.google.com/search?q=" + urllib.parse.quote(query)
        try:
            subprocess.Popen([browser_cmd, url])
            return self.ok(f"Searched '{query}' in {app}")
        except Exception as exc:
            return self.error(f"Could not search in {app}: {exc}")

    def type_text(self, text: str) -> dict:
        try:
            pyautogui.write(text, interval=0.02)
            return self.ok("Text typed")
        except Exception as exc:
            return self.error(f"Could not type text: {exc}")

    def open_file(self, path: str) -> dict:
        try:
            subprocess.Popen(["xdg-open", path])
            return self.ok(f"Opened {path}")
        except Exception as exc:
            return self.error(f"Could not open {path}: {exc}")

    def change_setting(self, key: str, value: str) -> dict:
        setting_key = key.strip().lower()
        if setting_key not in ALLOWED_SETTINGS:
            return self.error(f"'{key}' is not an allowed setting")
        try:
            subprocess.Popen(["gnome-control-center", ALLOWED_SETTINGS[setting_key]])
            return self.ok(f"Opened {key} settings")
        except Exception as exc:
            return self.error(f"Could not open {key} settings: {exc}")