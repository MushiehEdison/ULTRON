"""macOS implementation of AutomationAdapter. Uses `open` for launching
apps/files and AppleScript (via osascript) where finer control is needed."""

import subprocess
import urllib.parse

from app.automation.base import AutomationAdapter

# Common spoken name -> actual macOS application name (as Spotlight/`open -a` sees it).
APP_MAP = {
    "chrome": "Google Chrome",
    "safari": "Safari",
    "firefox": "Firefox",
    "finder": "Finder",
    "terminal": "Terminal",
    "notes": "Notes",
    "settings": "System Settings",
    "preferences": "System Settings",
}

# Only these settings can be changed by voice — anything else is rejected.
# Opens the relevant System Settings pane rather than silently changing a
# value, so the user still confirms the actual change.
ALLOWED_SETTINGS = {
    "wifi": "Network",
    "bluetooth": "Bluetooth",
    "display": "Displays",
    "sound": "Sound",
    "battery": "Battery",
}


class MacAdapter(AutomationAdapter):

    def open_app(self, name: str) -> dict:
        app_name = APP_MAP.get(name.strip().lower(), name)
        try:
            subprocess.run(["open", "-a", app_name], check=True)
            return self.ok(f"Opened {name}")
        except Exception as exc:
            return self.error(f"Could not open {name}: {exc}")

    def web_search(self, app: str, query: str) -> dict:
        app_name = APP_MAP.get(app.strip().lower(), app)
        url = "https://www.google.com/search?q=" + urllib.parse.quote(query)
        try:
            subprocess.run(["open", "-a", app_name, url], check=True)
            return self.ok(f"Searched '{query}' in {app}")
        except Exception as exc:
            return self.error(f"Could not search in {app}: {exc}")

    def type_text(self, text: str) -> dict:
        try:
            import pyautogui
            pyautogui.write(text, interval=0.02)
            return self.ok("Text typed")
        except Exception as exc:
            return self.error(f"Could not type text: {exc}")

    def open_file(self, path: str) -> dict:
        try:
            subprocess.run(["open", path], check=True)
            return self.ok(f"Opened {path}")
        except Exception as exc:
            return self.error(f"Could not open {path}: {exc}")

    def change_setting(self, key: str, value: str) -> dict:
        setting_key = key.strip().lower()
        if setting_key not in ALLOWED_SETTINGS:
            return self.error(f"'{key}' is not an allowed setting")
        pane = ALLOWED_SETTINGS[setting_key]
        script = f'tell application "System Settings" to reveal pane "{pane}"'
        try:
            subprocess.run(["osascript", "-e", script], check=True)
            return self.ok(f"Opened {key} settings")
        except Exception as exc:
            return self.error(f"Could not open {key} settings: {exc}")