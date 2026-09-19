"""Linux implementation of AutomationAdapter with extended PC control.

Targets GNOME/Fedora by default. Adjust APP_MAP, ALLOWED_SETTINGS and
DE-specific commands if you use KDE, XFCE, etc.

Some methods require root (or passwordless sudo) — check ``self.is_root()``
before calling admin-only methods.
"""

import io
import os
import platform
import pwd
import shutil
import signal
import subprocess
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Optional, Union

from app.automation.base import AutomationAdapter

# ---------------------------------------------------------------------------
# Common app name -> launch command. Extend as needed.
# ---------------------------------------------------------------------------
APP_MAP = {
    "chrome": "google-chrome",
    "chromium": "chromium",
    "firefox": "firefox",
    "files": "nautilus",
    "file explorer": "nautilus",
    "terminal": "gnome-terminal",
    "settings": "gnome-control-center",
    "text editor": "gedit",
    "code": "code",
    "vs code": "code",
    "vscode": "code",
    "vlc": "vlc",
    "spotify": "spotify",
    "calculator": "gnome-calculator",
    "system monitor": "gnome-system-monitor",
    "task manager": "gnome-system-monitor",
    "disks": "gnome-disks",
    "screenshot": "gnome-screenshot",
    "gimp": "gimp",
    "libreoffice": "libreoffice",
    "writer": "libreoffice --writer",
    "calc": "libreoffice --calc",
    "impress": "libreoffice --impress",
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
    "power": "power",
    "network": "network",
    "privacy": "privacy",
    "applications": "applications",
    "apps": "applications",
    "keyboard": "keyboard",
    "mouse": "mouse",
    "printers": "printers",
    "region": "region",
    "language": "region",
    "sharing": "sharing",
    "users": "user-accounts",
    "accounts": "user-accounts",
    "date": "datetime",
    "time": "datetime",
    "universal access": "universal-access",
    "accessibility": "universal-access",
    "color": "color",
    "notifications": "notifications",
    "search": "search",
    "multitasking": "multitasking",
    "removable media": "removable-media",
    "default apps": "default-apps",
}

# Blocklist for destructive shell commands.
_DANGEROUS_TOKENS = (
    "rm -rf /", "rm -rf /*", "mkfs", "dd if=", ":(){:|:&};:",
    "> /dev/sda", "chmod -R 777 /", "chown -R", "/dev/sd",
)


class LinuxAdapter(AutomationAdapter):
    """High-privilege Linux automation adapter.

    Many methods work as a normal user. Admin-level methods use ``sudo``
    and require either a passwordless sudoers entry or an interactive
    password prompt (which will not work in headless contexts).
    """

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    @staticmethod
    def is_root() -> bool:
        try:
            return os.geteuid() == 0
        except Exception:
            return False

    @staticmethod
    def _sudo(args: list, password: Optional[str] = None,
    timeout: float = 60) -> subprocess.CompletedProcess:
        """Run a command with sudo.

        If ``password`` is given, it's piped to ``sudo -S``. Otherwise we
        rely on passwordless sudo or an existing sudo timestamp.
        """
        if LinuxAdapter.is_root():
            cmd = args
        else:
            cmd = ["sudo", "-n"] + args if password is None else ["sudo", "-S"] + args
            return subprocess.run(
        cmd,
        input=(password + "\n") if password else None,
        capture_output=True,
        text=True,
        timeout=timeout,
    )

    @staticmethod
    def _run(args: Union[str, list], shell: bool = False,
    check: bool = False, capture: bool = True,
    timeout: float = 60) -> subprocess.CompletedProcess:
        return subprocess.run(
    args,
    shell=shell,
    check=check,
    capture_output=capture,
    text=True,
    timeout=timeout,
)

    @staticmethod
    def _display_env() -> dict:
        """Ensure DISPLAY / WAYLAND_DISPLAY / XAUTHORITY are passed through."""
        env = os.environ.copy()
        if "DISPLAY" not in env and os.path.exists("/tmp/.X11-unix"):
            env.setdefault("DISPLAY", ":0")
            env.setdefault("XAUTHORITY", str(Path.home() / ".Xauthority"))
            return env

        # ------------------------------------------------------------------ #
        # Original methods (kept intact)
        # ------------------------------------------------------------------ #
    def open_app(self, name: str) -> dict:
        key = name.strip().lower()
        command = APP_MAP.get(key, key)
        try:
            subprocess.Popen(command, shell=True, env=self._display_env())
            return self.ok(f"Opened {name}")
        except Exception as exc:
            return self.error(f"Could not open {name}: {exc}")

    def web_search(self, app: str, query: str) -> dict:
        key = app.strip().lower()
        browser_cmd = APP_MAP.get(key, key)
        url = "https://www.google.com/search?q=" + urllib.parse.quote(query)
        try:
            subprocess.Popen([browser_cmd, url], env=self._display_env())
            return self.ok(f"Searched '{query}' in {app}")
        except Exception as exc:
            return self.error(f"Could not search in {app}: {exc}")

    def type_text(self, text: str) -> dict:
import pyautogui
try:
    pyautogui.write(text, interval=0.02)
        return self.ok("Text typed")
except Exception as exc:
    return self.error(f"Could not type text: {exc}")

    def open_file(self, path: str) -> dict:
        try:
            subprocess.Popen(["xdg-open", path], env=self._display_env())
            return self.ok(f"Opened {path}")
        except Exception as exc:
            return self.error(f"Could not open {path}: {exc}")

    def change_setting(self, key: str, value: str) -> dict:
        setting_key = key.strip().lower()
        if setting_key not in ALLOWED_SETTINGS:
            return self.error(f"'{key}' is not an allowed setting")
        try:
            subprocess.Popen(
                ["gnome-control-center", ALLOWED_SETTINGS[setting_key]],
                env=self._display_env(),
            )
            return self.ok(f"Opened {key} settings")
        except Exception as exc:
            return self.error(f"Could not open {key} settings: {exc}")

        # ------------------------------------------------------------------ #
        # Shell / process execution
        # ------------------------------------------------------------------ #
    def run_command(self, command: str, shell: str = "bash",
    admin: bool = False, password: Optional[str] = None,
    timeout: float = 60) -> dict:
        """Run a shell command.

        ``shell``: 'bash' | 'sh' | 'zsh'
        ``admin``: if True, runs via sudo.
        """
        if any(tok in command for tok in _DANGEROUS_TOKENS):
            return self.error("Command blocked by safety policy")

        try:
            if admin:
                proc = self._sudo([shell, "-c", command],
                password=password, timeout=timeout)
            else:
                proc = self._run([shell, "-c", command], timeout=timeout)

                return self.ok(
            f"Command exited with {proc.returncode}",
            stdout=proc.stdout.strip() if proc.stdout else "",
            stderr=proc.stderr.strip() if proc.stderr else "",
            returncode=proc.returncode,
        )
        except subprocess.TimeoutExpired:
            return self.error("Command timed out")
    except Exception as exc:
        return self.error(f"Command failed: {exc}")

    def kill_process(self, name_or_pid: Union[str, int],
    force: bool = True, admin: bool = False) -> dict:
        try:
            sig = "-9" if force else "-15"
            if isinstance(name_or_pid, int):
                args = ["kill", sig, str(name_or_pid)]
            else:
                args = ["pkill", sig, "-f", name_or_pid]
                if admin:
                    proc = self._sudo(args)
                else:
                    proc = self._run(args)
                    if proc.returncode == 0:
                        return self.ok(f"Killed {name_or_pid}")
                    return self.error(proc.stderr.strip() or "kill failed")
        except Exception as exc:
            return self.error(f"Could not kill process: {exc}")

    def list_processes(self, filter_name: Optional[str] = None) -> dict:
        try:
            proc = self._run(["ps", "-eo", "pid,comm,pcpu,pmem,user", "--no-headers"])
            rows = []
            for line in proc.stdout.splitlines():
                parts = line.split(None, 4)
                if len(parts) < 5:
                    continue
                if filter_name and filter_name.lower() not in parts[1].lower():
                    continue
                rows.append({
                    "pid": parts[0],
                    "name": parts[1],
                    "cpu": parts[2],
                    "mem": parts[3],
                    "user": parts[4],
                })
                return self.ok(f"{len(rows)} processes", processes=rows)
        except Exception as exc:
            return self.error(f"Could not list processes: {exc}")

        # ------------------------------------------------------------------ #
        # systemd services
        # ------------------------------------------------------------------ #
    def start_service(self, name: str, user: bool = False) -> dict:
        return self._service_action(name, "start", user)

    def stop_service(self, name: str, user: bool = False) -> dict:
        return self._service_action(name, "stop", user)

    def restart_service(self, name: str, user: bool = False) -> dict:
        return self._service_action(name, "restart", user)

    def _service_action(self, name: str, action: str,
    user: bool = False) -> dict:
        try:
            args = ["systemctl"]
            if user:
                args.append("--user")
                args += [action, name]
                if not user:
                    proc = self._sudo(args)
                else:
                    proc = self._run(args)
                    if proc.returncode == 0:
                        return self.ok(f"Service {name} {action}ed")
                    return self.error(proc.stderr.strip() or f"systemctl {action} failed")
        except Exception as exc:
            return self.error(f"Service {action} failed: {exc}")

        # ------------------------------------------------------------------ #
        # Filesystem
        # ------------------------------------------------------------------ #
    def read_file(self, path: str, encoding: str = "utf-8") -> dict:
        try:
            data = Path(path).read_text(encoding=encoding)
            return self.ok(f"Read {len(data)} chars", content=data)
        except Exception as exc:
            return self.error(f"Could not read {path}: {exc}")

    def write_file(self, path: str, content: str,
    encoding: str = "utf-8", append: bool = False,
    admin: bool = False) -> dict:
        try:
            p = Path(path)
            p.parent.mkdir(parents=True, exist_ok=True)
            if admin and not self.is_root():
                # Use sudo tee so we don't need to chown the file.
                cmd = ["sudo", "tee", "-a" if append else "", str(p)]
                # Remove empty string from list
                cmd = [c for c in cmd if c]
                proc = subprocess.run(
                    cmd, input=content, text=True, capture_output=True)
                    if proc.returncode != 0:
                        return self.error(proc.stderr.strip() or "sudo write failed")
                    else:
                        mode = "a" if append else "w"
                        with p.open(mode, encoding=encoding) as f:
                            f.write(content)
                            return self.ok(f"Wrote {path}")
        except Exception as exc:
            return self.error(f"Could not write {path}: {exc}")

    def delete_path(self, path: str, to_trash: bool = True) -> dict:
        """Delete a file/folder. Uses gio trash if available."""
        try:
            p = Path(path)
            if not p.exists():
                return self.error(f"Path does not exist: {path}")
            if to_trash and shutil.which("gio"):
                proc = self._run(["gio", "trash", str(p)])
                if proc.returncode == 0:
                    return self.ok(f"Trashed {path}")
                if p.is_dir():
                    shutil.rmtree(p)
                else:
                    p.unlink()
                    return self.ok(f"Deleted {path}")
        except Exception as exc:
            return self.error(f"Could not delete {path}: {exc}")

    def move_path(self, src: str, dst: str) -> dict:
        try:
            shutil.move(src, dst)
            return self.ok(f"Moved {src} -> {dst}")
        except Exception as exc:
            return self.error(f"Move failed: {exc}")

    def copy_path(self, src: str, dst: str) -> dict:
        try:
            if Path(src).is_dir():
                shutil.copytree(src, dst, dirs_exist_ok=True)
            else:
                shutil.copy2(src, dst)
                return self.ok(f"Copied {src} -> {dst}")
        except Exception as exc:
            return self.error(f"Copy failed: {exc}")

    def list_dir(self, path: str) -> dict:
        try:
            entries = []
            for e in Path(path).iterdir():
                entries.append({
                    "name": e.name,
                    "is_dir": e.is_dir(),
                    "size": e.stat().st_size if e.is_file() else None,
                })
                return self.ok(f"{len(entries)} entries", entries=entries)
        except Exception as exc:
            return self.error(f"List failed: {exc}")

    def chmod(self, path: str, mode: str, admin: bool = False) -> dict:
        try:
            args = ["chmod", mode, path]
            proc = self._sudo(args) if admin else self._run(args)
            if proc.returncode == 0:
                return self.ok(f"chmod {mode} {path}")
            return self.error(proc.stderr.strip() or "chmod failed")
        except Exception as exc:
            return self.error(f"chmod failed: {exc}")

    def chown(self, path: str, user: str, group: Optional[str] = None) -> dict:
        try:
            owner = f"{user}:{group}" if group else user
            proc = self._sudo(["chown", "-R", owner, path])
            if proc.returncode == 0:
                return self.ok(f"chown {owner} {path}")
            return self.error(proc.stderr.strip() or "chown failed")
        except Exception as exc:
            return self.error(f"chown failed: {exc}")

        # ------------------------------------------------------------------ #
        # Input simulation (keyboard / mouse)
        # ------------------------------------------------------------------ #
    def press_keys(self, *keys: str, interval: float = 0.05) -> dict:
import pyautogui
try:
    pyautogui.hotkey(*keys, interval=interval)
    return self.ok(f"Pressed {'+'.join(keys)}")
except Exception as exc:
    return self.error(f"Key press failed: {exc}")

    def mouse_click(self, x: Optional[int] = None,
    y: Optional[int] = None, button: str = "left",
    clicks: int = 1) -> dict:
import pyautogui
try:
    if x is not None and y is not None:
        pyautogui.click(x=x, y=y, button=button, clicks=clicks)
    else:
        pyautogui.click(button=button, clicks=clicks)
        return self.ok("Mouse click")
except Exception as exc:
    return self.error(f"Mouse click failed: {exc}")

    def mouse_move(self, x: int, y: int, duration: float = 0.0) -> dict:
import pyautogui
try:
    pyautogui.moveTo(x, y, duration=duration)
    return self.ok(f"Moved to ({x},{y})")
except Exception as exc:
    return self.error(f"Mouse move failed: {exc}")

    def scroll(self, amount: int) -> dict:
import pyautogui
try:
    pyautogui.scroll(amount)
    return self.ok(f"Scrolled {amount}")
except Exception as exc:
    return self.error(f"Scroll failed: {exc}")

# ------------------------------------------------------------------ #
# Screen
# ------------------------------------------------------------------ #
    def screenshot(self, path: Optional[str] = None) -> dict:
        """Screenshot via gnome-screenshot / scrot / import fallback."""
import base64
try:
    if path:
        for tool in (["gnome-screenshot", "-f", path],
        ["scrot", path],
        ["import", "-window", "root", path]):
            if shutil.which(tool[0]):
                proc = self._run(tool, capture=False)
                if proc.returncode == 0:
                    return self.ok(f"Screenshot saved to {path}")
                return self.error("No screenshot tool available")
                # Return PNG bytes as base64 without saving
import pyautogui
img = pyautogui.screenshot()
buf = io.BytesIO()
img.save(buf, format="PNG")
return self.ok("Screenshot captured",
                image_b64=base64.b64encode(buf.getvalue()).decode())
except Exception as exc:
    return self.error(f"Screenshot failed: {exc}")

    def screen_size(self) -> dict:
import pyautogui
try:
    w, h = pyautogui.size()
    return self.ok(f"{w}x{h}", width=w, height=h)
except Exception as exc:
    return self.error(f"Could not get screen size: {exc}")

# ------------------------------------------------------------------ #
# System / power / info
# ------------------------------------------------------------------ #
    def system_info(self) -> dict:
        try:
            info = {
                "os": platform.system(),
                "distro": platform.freedesktop_os_release().get("PRETTY_NAME", ""),
                "release": platform.release(),
                "version": platform.version(),
                "machine": platform.machine(),
                "processor": platform.processor(),
                "hostname": platform.node(),
                "python": platform.python_version(),
                "is_root": self.is_root(),
                "user": pwd.getpwuid(os.getuid()).pw_name,
                "display": os.environ.get("DISPLAY", ""),
                "wayland": os.environ.get("WAYLAND_DISPLAY", ""),
            }
            return self.ok("System info", info=info)
        except Exception as exc:
            return self.error(f"System info failed: {exc}")

    def lock_screen(self) -> dict:
        try:
            for cmd in (["loginctl", "lock-session"],
            ["gnome-screensaver-command", "-l"],
            ["xdg-screensaver", "lock"]):
                if shutil.which(cmd[0]):
                    self._run(cmd, capture=False)
                    return self.ok("Screen locked")
                return self.error("No lock command available")
        except Exception as exc:
            return self.error(f"Lock failed: {exc}")

    def shutdown(self, delay: int = 30, force: bool = True,
    restart: bool = False) -> dict:
        """Schedule shutdown/restart. Delay in minutes (systemd convention)."""
        try:
            delay_min = max(0, int(delay / 60)) if delay >= 60 else 0
            action = "reboot" if restart else "poweroff"
            args = ["shutdown", f"-{action}", f"+{delay_min}"]
            if force:
                args = ["shutdown", "-f", f"-{action}", f"+{delay_min}"]
                proc = self._sudo(args)
                if proc.returncode == 0:
                    return self.ok(f"{action} scheduled in {delay_min} min")
                return self.error(proc.stderr.strip() or "shutdown failed")
        except Exception as exc:
            return self.error(f"Shutdown failed: {exc}")

    def cancel_shutdown(self) -> dict:
        try:
            proc = self._sudo(["shutdown", "-c"])
            if proc.returncode == 0:
                return self.ok("Shutdown cancelled")
            return self.error(proc.stderr.strip() or "cancel failed")
        except Exception as exc:
            return self.error(f"Cancel failed: {exc}")

    def sleep(self) -> dict:
        try:
            proc = self._sudo(["systemctl", "suspend"])
            if proc.returncode == 0:
                return self.ok("Suspending")
            return self.error(proc.stderr.strip() or "suspend failed")
        except Exception as exc:
            return self.error(f"Sleep failed: {exc}")

    def set_volume(self, level: int) -> dict:
        """Set master volume 0-100 via pactl/amixer/wpctl."""
        level = max(0, min(100, int(level)))
        try:
            if shutil.which("pactl"):
                self._run(["pactl", "set-sink-volume", "@DEFAULT_SINK@", f"{level}%"])
                return self.ok(f"Volume set to {level}%")
            if shutil.which("wpctl"):
                self._run(["wpctl", "set-volume", "@DEFAULT_AUDIO_SINK@", f"{level/100:.2f}"])
                return self.ok(f"Volume set to {level}%")
            if shutil.which("amixer"):
                self._run(["amixer", "-q", "sset", "Master", f"{level}%"])
                return self.ok(f"Volume set to {level}%")
            return self.error("No volume control tool found")
        except Exception as exc:
            return self.error(f"Volume failed: {exc}")

    def mute(self, mute: bool = True) -> dict:
        try:
            state = "1" if mute else "0"
            if shutil.which("pactl"):
                self._run(["pactl", "set-sink-mute", "@DEFAULT_SINK@", state])
            elif shutil.which("wpctl"):
                self._run(["wpctl", "set-mute", "@DEFAULT_AUDIO_SINK@", state])
            elif shutil.which("amixer"):
                self._run(["amixer", "-q", "sset", "Master", "mute" if mute else "unmute"])
            else:
                return self.error("No mute tool found")
            return self.ok("Muted" if mute else "Unmuted")
        except Exception as exc:
            return self.error(f"Mute failed: {exc}")

    def set_brightness(self, level: int) -> dict:
        """Set screen brightness 0-100 via brightnessctl."""
        level = max(0, min(100, int(level)))
        try:
            if not shutil.which("brightnessctl"):
                return self.error("brightnessctl not installed")
            self._run(["brightnessctl", "set", f"{level}%"])
            return self.ok(f"Brightness set to {level}%")
        except Exception as exc:
            return self.error(f"Brightness failed: {exc}")

        # ------------------------------------------------------------------ #
        # Cron / startup / autostart
        # ------------------------------------------------------------------ #
    def add_cron(self, schedule: str, command: str,
    user: bool = True) -> dict:
        """Add a cron entry. ``schedule`` is a standard 5-field cron expr."""
        try:
            line = f"{schedule} {command}\n"
            if user:
                existing = self._run(["crontab", "-l"]).stdout or ""
                new = existing + line
                proc = subprocess.run(
                    ["crontab", "-"], input=new, text=True, capture_output=True)
            else:
                existing = self._sudo(["crontab", "-l", "-u", "root"]).stdout or ""
                new = existing + line
                proc = subprocess.run(
                    ["sudo", "crontab", "-u", "root", "-"],
                    input=new, text=True, capture_output=True)
                    if proc.returncode == 0:
                        return self.ok("Cron entry added")
                    return self.error(proc.stderr.strip() or "crontab failed")
        except Exception as exc:
            return self.error(f"Cron failed: {exc}")

    def list_cron(self, user: bool = True) -> dict:
        try:
            if user:
                proc = self._run(["crontab", "-l"])
            else:
                proc = self._sudo(["crontab", "-l", "-u", "root"])
                return self.ok("Cron entries", output=proc.stdout)
        except Exception as exc:
            return self.error(f"Cron list failed: {exc}")

    def add_autostart(self, name: str, command: str) -> dict:
        """Create a ~/.config/autostart .desktop entry."""
        try:
            autostart = Path.home() / ".config" / "autostart"
            autostart.mkdir(parents=True, exist_ok=True)
            desktop = autostart / f"{name}.desktop"
            desktop.write_text(
                "[Desktop Entry]\n"
                "Type=Application\n"
                f"Name={name}\n"
                f"Exec={command}\n"
                "X-GNOME-Autostart-enabled=true\n"
            )
            return self.ok(f"Autostart entry '{name}' created")
        except Exception as exc:
            return self.error(f"Autostart failed: {exc}")

    def remove_autostart(self, name: str) -> dict:
        try:
            desktop = Path.home() / ".config" / "autostart" / f"{name}.desktop"
            if desktop.exists():
                desktop.unlink()
                return self.ok(f"Autostart entry '{name}' removed")
            return self.error("Autostart entry not found")
        except Exception as exc:
            return self.error(f"Remove autostart failed: {exc}")

        # ------------------------------------------------------------------ #
        # Network
        # ------------------------------------------------------------------ #
    def ip_config(self) -> dict:
        try:
            if shutil.which("ip"):
                proc = self._run(["ip", "addr"])
            else:
                proc = self._run(["ifconfig", "-a"])
                return self.ok("ip output", output=proc.stdout)
        except Exception as exc:
            return self.error(f"ip failed: {exc}")

    def ping(self, host: str, count: int = 4) -> dict:
        try:
            proc = self._run(["ping", "-c", str(count), host], timeout=30)
            return self.ok(f"Pinged {host}", output=proc.stdout)
        except Exception as exc:
            return self.error(f"Ping failed: {exc}")

    def flush_dns(self) -> dict:
        try:
            if shutil.which("resolvectl"):
                proc = self._sudo(["resolvectl", "flush-caches"])
                return self.ok("DNS cache flushed", output=proc.stdout)
            if shutil.which("systemd-resolve"):
                proc = self._sudo(["systemd-resolve", "--flush-caches"])
                return self.ok("DNS cache flushed", output=proc.stdout)
            return self.error("No DNS flush tool found")
        except Exception as exc:
            return self.error(f"Flush DNS failed: {exc}")

        # ------------------------------------------------------------------ #
        # Clipboard
        # ------------------------------------------------------------------ #
    def clipboard_get(self) -> dict:
        try:
            if os.environ.get("WAYLAND_DISPLAY") and shutil.which("wl-paste"):
                proc = self._run(["wl-paste"])
            elif shutil.which("xclip"):
                proc = self._run(["xclip", "-selection", "clipboard", "-o"])
            elif shutil.which("xsel"):
                proc = self._run(["xsel", "--clipboard", "--output"])
            else:
                return self.error("No clipboard tool found")
            return self.ok("Clipboard read", content=proc.stdout)
        except Exception as exc:
            return self.error(f"Clipboard read failed: {exc}")

    def clipboard_set(self, text: str) -> dict:
        try:
            if os.environ.get("WAYLAND_DISPLAY") and shutil.which("wl-copy"):
                proc = subprocess.run(["wl-copy"], input=text, text=True,
                capture_output=True)
            elif shutil.which("xclip"):
                proc = subprocess.run(
                    ["xclip", "-selection", "clipboard"],
                    input=text, text=True, capture_output=True)
            elif shutil.which("xsel"):
                proc = subprocess.run(
                    ["xsel", "--clipboard", "--input"],
                    input=text, text=True, capture_output=True)
            else:
                return self.error("No clipboard tool found")
            if proc.returncode == 0:
                return self.ok("Clipboard set")
            return self.error(proc.stderr.strip() or "clipboard set failed")
        except Exception as exc:
            return self.error(f"Clipboard set failed: {exc}")

        # ------------------------------------------------------------------ #
        # Window management (X11 via wmctrl; Wayland fallback via gdbus)
        # ------------------------------------------------------------------ #
    def list_windows(self) -> dict:
        try:
            if shutil.which("wmctrl"):
                proc = self._run(["wmctrl", "-l"])
                windows = []
                for line in proc.stdout.splitlines():
                    parts = line.split(None, 3)
                    if len(parts) >= 4:
                        windows.append({
                            "id": parts[0], "desktop": parts[1],
                            "host": parts[2], "title": parts[3],
                        })
                        return self.ok(f"{len(windows)} windows", windows=windows)
                    return self.error("wmctrl not installed")
        except Exception as exc:
            return self.error(f"List windows failed: {exc}")

    def focus_window(self, title_substr: str) -> dict:
        try:
            if not shutil.which("wmctrl"):
                return self.error("wmctrl not installed")
            proc = self._run(["wmctrl", "-a", title_substr])
            if proc.returncode == 0:
                return self.ok(f"Focused window matching '{title_substr}'")
            return self.error(proc.stderr.strip() or "focus failed")
        except Exception as exc:
            return self.error(f"Focus failed: {exc}")

        # ------------------------------------------------------------------ #
        # Downloads
        # ------------------------------------------------------------------ #
    def download_file(self, url: str, dest: str) -> dict:
        try:
            Path(dest).parent.mkdir(parents=True, exist_ok=True)
            urllib.request.urlretrieve(url, dest)
            return self.ok(f"Downloaded to {dest}")
        except Exception as exc:
            return self.error(f"Download failed: {exc}")

        # ------------------------------------------------------------------ #
        # Package management (Fedora/GNOME default via dnf; falls back to apt)
        # ------------------------------------------------------------------ #
    def install_package(self, name: str, password: Optional[str] = None) -> dict:
        try:
            if shutil.which("dnf"):
                proc = self._sudo(["dnf", "install", "-y", name], password=password,
                timeout=600)
            elif shutil.which("apt"):
                proc = self._sudo(["apt-get", "install", "-y", name], password=password,
                timeout=600)
            elif shutil.which("pacman"):
                proc = self._sudo(["pacman", "-S", "--noconfirm", name],
                password=password, timeout=600)
            else:
                return self.error("No supported package manager found")
            if proc.returncode == 0:
                return self.ok(f"Installed {name}")
            return self.error(proc.stderr.strip() or "install failed")
        except Exception as exc:
            return self.error(f"Install failed: {exc}")

    def remove_package(self, name: str, password: Optional[str] = None) -> dict:
        try:
            if shutil.which("dnf"):
                proc = self._sudo(["dnf", "remove", "-y", name], password=password,
                timeout=600)
            elif shutil.which("apt"):
                proc = self._sudo(["apt-get", "remove", "-y", name], password=password,
                timeout=600)
            elif shutil.which("pacman"):
                proc = self._sudo(["pacman", "-R", "--noconfirm", name],
                password=password, timeout=600)
            else:
                return self.error("No supported package manager found")
            if proc.returncode == 0:
                return self.ok(f"Removed {name}")
            return self.error(proc.stderr.strip() or "remove failed")
        except Exception as exc:
            return self.error(f"Remove failed: {exc}")

    def update_system(self, password: Optional[str] = None) -> dict:
        try:
            if shutil.which("dnf"):
                proc = self._sudo(["dnf", "upgrade", "-y"], password=password,
                timeout=3600)
            elif shutil.which("apt"):
                self._sudo(["apt-get", "update"], password=password, timeout=600)
                proc = self._sudo(["apt-get", "upgrade", "-y"], password=password,
                timeout=3600)
            elif shutil.which("pacman"):
                proc = self._sudo(["pacman", "-Syu", "--noconfirm"],
                password=password, timeout=3600)
            else:
                return self.error("No supported package manager found")
            if proc.returncode == 0:
                return self.ok("System updated")
            return self.error(proc.stderr.strip() or "update failed")
        except Exception as exc:
            return self.error(f"Update failed: {exc}")

        # ------------------------------------------------------------------ #
        # Users / groups (admin)
        # ------------------------------------------------------------------ #
    def add_user(self, username: str, password: Optional[str] = None,
    sudo_password: Optional[str] = None) -> dict:
        try:
            proc = self._sudo(["useradd", "-m", username], password=sudo_password)
            if proc.returncode != 0 and "already exists" not in proc.stderr:
                return self.error(proc.stderr.strip() or "useradd failed")
            if password:
                chpass = subprocess.run(
                    ["sudo", "chpasswd"],
                    input=f"{username}:{password}\n", text=True,
                    capture_output=True)
                    if chpass.returncode != 0:
                        return self.error(chpass.stderr.strip() or "chpasswd failed")
                    return self.ok(f"User '{username}' created")
        except Exception as exc:
            return self.error(f"add_user failed: {exc}")

    def delete_user(self, username: str,
    remove_home: bool = True,
    sudo_password: Optional[str] = None) -> dict:
        try:
            args = ["userdel"]
            if remove_home:
                args.append("-r")
                args.append(username)
                proc = self._sudo(args, password=sudo_password)
                if proc.returncode == 0:
                    return self.ok(f"User '{username}' deleted")
                return self.error(proc.stderr.strip() or "userdel failed")
        except Exception as exc:
            return self.error(f"delete_user failed: {exc}")

    def add_to_group(self, username: str, group: str,
    sudo_password: Optional[str] = None) -> dict:
        try:
            proc = self._sudo(["usermod", "-aG", group, username],
            password=sudo_password)
            if proc.returncode == 0:
                return self.ok(f"Added {username} to {group}")
            return self.error(proc.stderr.strip() or "usermod failed")
        except Exception as exc:
            return self.error(f"add_to_group failed: {exc}")