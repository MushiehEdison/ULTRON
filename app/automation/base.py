"""
Abstract interface every platform adapter must implement.

One method per command in docs/COMMAND_SCHEMA.md. The router calls these
by name after validating the command against the schema — it never touches
subprocess/pyautogui/etc. directly, only through this interface.

Each adapter returns a plain dict: {"status": "ok" | "error", "message": str}
so the GUI can display something meaningful regardless of which OS ran it.
"""

from abc import ABC, abstractmethod


class AutomationAdapter(ABC):

    @abstractmethod
    def open_app(self, name: str) -> dict:
        """Launch an installed application by name."""
        raise NotImplementedError

    @abstractmethod
    def web_search(self, app: str, query: str) -> dict:
        """Open a browser (app) and search for query."""
        raise NotImplementedError

    @abstractmethod
    def type_text(self, text: str) -> dict:
        """Type text at the current cursor/focus position."""
        raise NotImplementedError

    @abstractmethod
    def open_file(self, path: str) -> dict:
        """Open a file with its OS default application."""
        raise NotImplementedError

    @abstractmethod
    def change_setting(self, key: str, value: str) -> dict:
        """Change a system setting. Only keys in ALLOWED_SETTINGS may be used —
        this is the destructive-action boundary, so adapters must reject
        anything not explicitly whitelisted rather than trying to guess."""
        raise NotImplementedError

    # ---- shared helpers ----

    def ok(self, message: str) -> dict:
        return {"status": "ok", "message": message}

    def error(self, message: str) -> dict:
        return {"status": "error", "message": message}


def get_adapter() -> AutomationAdapter:
    
    import platform

    system = platform.system()
    if system == "Windows":
        from app.automation.windows_adapter import WindowsAdapter
        return WindowsAdapter()
    elif system == "Linux":
        from app.automation.linux_adapter import LinuxAdapter
        return LinuxAdapter()
    elif system == "Darwin":
        from app.automation.mac_adapter import MacAdapter
        return MacAdapter()
    else:
        raise RuntimeError(f"Unsupported platform: {system}")