"""Windows implementation of AutomationAdapter."""

import os
import subprocess
import urllib.parse

import pyautogui

from app.automation.base import AutomationAdapter

# Common app name -> launch command. Extend as needed.
APP_MAP = {
    "chrome": "chrome",
    "firefox": "firefox",
    "edge": "msedge",
    "notepad": "notepad",
    "calculator": "calc",
    "explorer": "explorer",
    "file explorer": "explorer",
    "paint": "mspaint",
    "word": "winword",
    "excel": "excel",
    "settings": "ms-settings:",
}

# Only these settings can be changed by voice — anything else is rejected.
# Maps to the Windows ms-settings: URI scheme (opens the settings page,
# does not silently change values without user interaction).
ALLOWED_SETTINGS = {
    "wifi": "ms-settings:network-wifi",
    "bluetooth": "ms-settings:bluetooth",
    "display": "ms-settings:display",
    "sound": "ms-settings:sound",
    "battery": "ms-settings:batterysaver",
}


class WindowsAdapter(AutomationAdapter):

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
            subprocess.Popen(f'{browser_cmd} "{url}"', shell=True)
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
            os.startfile(path)
            return self.ok(f"Opened {path}")
        except Exception as exc:
            return self.error(f"Could not open {path}: {exc}")

    def change_setting(self, key: str, value: str) -> dict:
        setting_key = key.strip().lower()
        if setting_key not in ALLOWED_SETTINGS:
            return self.error(f"'{key}' is not an allowed setting")
        try:
            os.startfile(ALLOWED_SETTINGS[setting_key])
            return self.ok(f"Opened {key} settings")
        except Exception as exc:
            return self.error(f"Could not open {key} settings: {exc}")