"""Windows implementation of AutomationAdapter with extended PC control."""

import ctypes
import io
import os
import shutil
import subprocess
import sys
import time
import urllib.parse
from pathlib import Path
from typing import Optional, Union

from app.automation.base import AutomationAdapter

APP_MAP = {
    "chrome": "chrome", "firefox": "firefox", "edge": "msedge",
    "notepad": "notepad", "calculator": "calc", "explorer": "explorer",
    "file explorer": "explorer", "paint": "mspaint", "word": "winword",
    "excel": "excel", "settings": "ms-settings:", "cmd": "cmd",
    "command prompt": "cmd", "powershell": "powershell",
    "terminal": "wt", "task manager": "taskmgr", "regedit": "regedit",
    "control panel": "control", "device manager": "devmgmt.msc",
    "services": "services.msc", "event viewer": "eventvwr.msc",
    "snipping tool": "snippingtool", "vlc": "vlc", "spotify": "spotify",
    "vscode": "code", "vs code": "code",
}

ALLOWED_SETTINGS = {
    "wifi": "ms-settings:network-wifi", "bluetooth": "ms-settings:bluetooth",
    "display": "ms-settings:display", "sound": "ms-settings:sound",
    "battery": "ms-settings:batterysaver", "network": "ms-settings:network",
    "privacy": "ms-settings:privacy", "update": "ms-settings:windowsupdate",
    "apps": "ms-settings:appsfeatures", "accounts": "ms-settings:yourinfo",
    "time": "ms-settings:dateandtime",
    "language": "ms-settings:regionlanguage",
    "keyboard": "ms-settings:easeofaccess-keyboard",
    "mouse": "ms-settings:mousetouchpad",
    "storage": "ms-settings:storagesense",
    "multitasking": "ms-settings:multitasking",
    "default apps": "ms-settings:defaultapps",
}

_DANGEROUS_TOKENS = (
    "format ", "diskpart", "rm -rf /", "del /f /s /q c:\\",
    "rd /s /q c:\\", ":(){:|:&};:", "mkfs", "shutdown /r /t 0",
)


class WindowsAdapter(AutomationAdapter):

    @staticmethod
    def is_admin() -> bool:
        try:
            return bool(ctypes.windll.shell32.IsUserAnAdmin())
        except Exception:
            return False

    def _run(self, args, shell=False, check=False, capture=True, timeout=60):
        return subprocess.run(args, shell=shell, check=check,
                              capture_output=capture, text=True, timeout=timeout,
                              creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))

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
        import pyautogui
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

    def run_command(self, command: str, shell: str = "cmd",
                    admin: bool = False, timeout: float = 60) -> dict:
        if any(tok in command.lower() for tok in _DANGEROUS_TOKENS):
            return self.error("Command blocked by safety policy")
        try:
            binary = "cmd.exe" if shell == "cmd" else "powershell.exe"
            args = [binary, "/c", command] if shell == "cmd" else [binary, "-Command", command]
            if admin and not self.is_admin():
                ctypes.windll.shell32.ShellExecuteW(None, "runas", binary,
                    " ".join(args[1:]), None, 0)
                return self.ok("Elevated command dispatched (UAC prompt shown)")
            proc = self._run(args, timeout=timeout)
            return self.ok(f"Command exited with {proc.returncode}",
                           stdout=proc.stdout.strip() if proc.stdout else "",
                           stderr=proc.stderr.strip() if proc.stderr else "",
                           returncode=proc.returncode)
        except subprocess.TimeoutExpired:
            return self.error("Command timed out")
        except Exception as exc:
            return self.error(f"Command failed: {exc}")

    def kill_process(self, name_or_pid, force: bool = True) -> dict:
        try:
            cmd = ["taskkill", "/IM" if isinstance(name_or_pid, str) else "/PID", str(name_or_pid)]
            if force:
                cmd.insert(1, "/F")
            proc = self._run(cmd)
            return self.ok(f"Killed {name_or_pid}") if proc.returncode == 0 \
                else self.error(proc.stderr.strip() or "taskkill failed")
        except Exception as exc:
            return self.error(f"Could not kill process: {exc}")

    def list_processes(self, filter_name: Optional[str] = None) -> dict:
        try:
            proc = self._run(["tasklist", "/FO", "CSV", "/NH"], timeout=30)
            rows = []
            for line in proc.stdout.splitlines():
                if not line.strip():
                    continue
                parts = [p.strip('"') for p in line.split('","')]
                if len(parts) < 5:
                    continue
                if filter_name and filter_name.lower() not in parts[0].lower():
                    continue
                rows.append({"name": parts[0], "pid": parts[1],
                             "session": parts[2], "mem": parts[4]})
            return self.ok(f"{len(rows)} processes", processes=rows)
        except Exception as exc:
            return self.error(f"Could not list processes: {exc}")

    def start_service(self, name: str) -> dict:
        return self._service_action(name, "start")

    def stop_service(self, name: str) -> dict:
        return self._service_action(name, "stop")

    def restart_service(self, name: str) -> dict:
        return self._service_action(name, "restart")

    def _service_action(self, name: str, action: str) -> dict:
        try:
            proc = self._run(["sc", action, name])
            return self.ok(f"Service {name} {action}ed") if proc.returncode == 0 \
                else self.error(proc.stderr.strip() or f"sc {action} failed")
        except Exception as exc:
            return self.error(f"Service {action} failed: {exc}")

    def read_file(self, path: str, encoding: str = "utf-8") -> dict:
        try:
            data = Path(path).read_text(encoding=encoding)
            return self.ok(f"Read {len(data)} chars", content=data)
        except Exception as exc:
            return self.error(f"Could not read {path}: {exc}")

    def write_file(self, path: str, content: str, encoding: str = "utf-8",
                   append: bool = False) -> dict:
        try:
            p = Path(path); p.parent.mkdir(parents=True, exist_ok=True)
            with p.open("a" if append else "w", encoding=encoding) as f:
                f.write(content)
            return self.ok(f"Wrote {path}")
        except Exception as exc:
            return self.error(f"Could not write {path}: {exc}")

    def delete_path(self, path: str, to_recycle: bool = True) -> dict:
        try:
            p = Path(path)
            if not p.exists():
                return self.error(f"Path does not exist: {path}")
            if to_recycle:
                import ctypes.wintypes
                class SHFILEOPSTRUCTW(ctypes.Structure):
                    _fields_ = [("hwnd", ctypes.wintypes.HWND),
                                ("wFunc", ctypes.wintypes.UINT),
                                ("pFrom", ctypes.wintypes.LPCWSTR),
                                ("pTo", ctypes.wintypes.LPCWSTR),
                                ("fFlags", ctypes.wintypes.USHORT),
                                ("fAnyOperationsAborted", ctypes.wintypes.BOOL),
                                ("hNameMappings", ctypes.wintypes.LPVOID),
                                ("lpszProgressTitle", ctypes.wintypes.LPCWSTR)]
                op = SHFILEOPSTRUCTW()
                op.wFunc = 3
                op.pFrom = str(p.absolute()) + "\0\0"
                op.fFlags = 0x40 | 0x10
                res = ctypes.windll.shell32.SHFileOperationW(ctypes.byref(op))
                if res != 0:
                    return self.error(f"Recycle failed (code {res})")
            elif p.is_dir():
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
            entries = [{"name": e.name, "is_dir": e.is_dir(),
                        "size": e.stat().st_size if e.is_file() else None}
                       for e in Path(path).iterdir()]
            return self.ok(f"{len(entries)} entries", entries=entries)
        except Exception as exc:
            return self.error(f"List failed: {exc}")

    def registry_read(self, hive: str, key: str, value: Optional[str] = None) -> dict:
        try:
            import winreg
            hives = {"HKCU": winreg.HKEY_CURRENT_USER, "HKLM": winreg.HKEY_LOCAL_MACHINE,
                     "HKCR": winreg.HKEY_CLASSES_ROOT, "HKU": winreg.HKEY_USERS,
                     "HKCC": winreg.HKEY_CURRENT_CONFIG}
            with winreg.OpenKey(hives[hive.upper()], key) as k:
                if value:
                    data, _ = winreg.QueryValueEx(k, value)
                else:
                    data, i = {}, 0
                    while True:
                        try:
                            n, d, _ = winreg.EnumValue(k, i); data[n] = d; i += 1
                        except OSError:
                            break
            return self.ok("Registry read", data=data)
        except Exception as exc:
            return self.error(f"Registry read failed: {exc}")

    def registry_write(self, hive: str, key: str, value: str, data,
                       dtype: str = "REG_SZ") -> dict:
        try:
            import winreg
            hives = {"HKCU": winreg.HKEY_CURRENT_USER, "HKLM": winreg.HKEY_LOCAL_MACHINE,
                     "HKCR": winreg.HKEY_CLASSES_ROOT, "HKU": winreg.HKEY_USERS,
                     "HKCC": winreg.HKEY_CURRENT_CONFIG}
            types = {"REG_SZ": winreg.REG_SZ, "REG_DWORD": winreg.REG_DWORD,
                     "REG_QWORD": winreg.REG_QWORD, "REG_BINARY": winreg.REG_BINARY,
                     "REG_EXPAND_SZ": winreg.REG_EXPAND_SZ}
            with winreg.CreateKeyEx(hives[hive.upper()], key, 0, winreg.KEY_WRITE) as k:
                winreg.SetValueEx(k, value, 0, types[dtype], data)
            return self.ok(f"Wrote {hive}\\{key}\\{value}")
        except PermissionError:
            return self.error("Access denied - run as Administrator")
        except Exception as exc:
            return self.error(f"Registry write failed: {exc}")

    def registry_delete(self, hive: str, key: str, value: Optional[str] = None) -> dict:
        try:
            import winreg
            hives = {"HKCU": winreg.HKEY_CURRENT_USER, "HKLM": winreg.HKEY_LOCAL_MACHINE}
            root = hives[hive.upper()]
            if value:
                with winreg.OpenKey(root, key, 0, winreg.KEY_WRITE) as k:
                    winreg.DeleteValue(k, value)
            else:
                winreg.DeleteKey(root, key)
            return self.ok("Registry deleted")
        except Exception as exc:
            return self.error(f"Registry delete failed: {exc}")

    def press_keys(self, *keys: str, interval: float = 0.05) -> dict:
        import pyautogui
        try:
            pyautogui.hotkey(*keys, interval=interval)
            return self.ok(f"Pressed {'+'.join(keys)}")
        except Exception as exc:
            return self.error(f"Key press failed: {exc}")

    def mouse_click(self, x=None, y=None, button="left", clicks=1) -> dict:
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

    def screenshot(self, path: Optional[str] = None) -> dict:
        import base64, pyautogui
        try:
            img = pyautogui.screenshot()
            if path:
                img.save(path); return self.ok(f"Screenshot saved to {path}")
            buf = io.BytesIO(); img.save(buf, format="PNG")
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

    def system_info(self) -> dict:
        try:
            import platform
            info = {"os": platform.system(), "release": platform.release(),
                    "version": platform.version(), "machine": platform.machine(),
                    "processor": platform.processor(), "hostname": platform.node(),
                    "python": platform.python_version(), "is_admin": self.is_admin(),
                    "user": os.environ.get("USERNAME", "")}
            return self.ok("System info", info=info)
        except Exception as exc:
            return self.error(f"System info failed: {exc}")

    def lock_screen(self) -> dict:
        try:
            ctypes.windll.user32.LockWorkStation()
            return self.ok("Workstation locked")
        except Exception as exc:
            return self.error(f"Lock failed: {exc}")

    def shutdown(self, delay: int = 30, force: bool = True, restart: bool = False) -> dict:
        try:
            args = ["shutdown", "/r" if restart else "/s", "/t", str(delay)]
            if force:
                args.append("/f")
            self._run(args)
            return self.ok(f"{'Restart' if restart else 'Shutdown'} scheduled in {delay}s")
        except Exception as exc:
            return self.error(f"Shutdown failed: {exc}")

    def cancel_shutdown(self) -> dict:
        try:
            self._run(["shutdown", "/a"]); return self.ok("Shutdown cancelled")
        except Exception as exc:
            return self.error(f"Cancel failed: {exc}")

    def sleep(self) -> dict:
        try:
            ctypes.windll.powrprof.SetSuspendState(0, 1, 0)
            return self.ok("Sleeping")
        except Exception as exc:
            return self.error(f"Sleep failed: {exc}")

    def set_volume(self, level: int) -> dict:
        level = max(0, min(100, int(level)))
        try:
            ps = (f"$o=New-Object -ComObject WScript.Shell;"
                  f"1..50|%{{$o.SendKeys([char]174)}};"
                  f"1..{int(level/2)}|%{{$o.SendKeys([char]175)}}")
            self._run(["powershell", "-Command", ps])
            return self.ok(f"Volume set to ~{level}%")
        except Exception as exc:
            return self.error(f"Volume failed: {exc}")

    def mute(self, mute: bool = True) -> dict:
        try:
            self._run(["powershell", "-Command",
                       "$o=New-Object -ComObject WScript.Shell;$o.SendKeys([char]173)"])
            return self.ok("Toggled mute")
        except Exception as exc:
            return self.error(f"Mute failed: {exc}")

    def schedule_task(self, name: str, command: str, schedule: str = "ONLOGON") -> dict:
        try:
            proc = self._run(["schtasks", "/Create", "/TN", name, "/TR", command,
                              "/SC", schedule, "/F"])
            return self.ok(f"Task '{name}' created") if proc.returncode == 0 \
                else self.error(proc.stderr.strip() or "schtasks failed")
        except Exception as exc:
            return self.error(f"Schedule failed: {exc}")

    def delete_task(self, name: str) -> dict:
        try:
            proc = self._run(["schtasks", "/Delete", "/TN", name, "/F"])
            return self.ok(f"Task '{name}' deleted") if proc.returncode == 0 \
                else self.error(proc.stderr.strip() or "schtasks failed")
        except Exception as exc:
            return self.error(f"Delete task failed: {exc}")

    def add_startup(self, name: str, command: str) -> dict:
        return self.registry_write("HKCU",
            r"Software\Microsoft\Windows\CurrentVersion\Run", name, command)

    def remove_startup(self, name: str) -> dict:
        return self.registry_delete("HKCU",
            r"Software\Microsoft\Windows\CurrentVersion\Run", name)

    def ip_config(self) -> dict:
        try:
            proc = self._run(["ipconfig", "/all"])
            return self.ok("ipconfig output", output=proc.stdout)
        except Exception as exc:
            return self.error(f"ipconfig failed: {exc}")

    def ping(self, host: str, count: int = 4) -> dict:
        try:
            proc = self._run(["ping", "-n", str(count), host], timeout=30)
            return self.ok(f"Pinged {host}", output=proc.stdout)
        except Exception as exc:
            return self.error(f"Ping failed: {exc}")

    def flush_dns(self) -> dict:
        try:
            proc = self._run(["ipconfig", "/flushdns"])
            return self.ok("DNS cache flushed", output=proc.stdout)
        except Exception as exc:
            return self.error(f"Flush DNS failed: {exc}")

    def clipboard_get(self) -> dict:
        try:
            import tkinter as tk
            r = tk.Tk(); r.withdraw()
            data = r.clipboard_get(); r.destroy()
            return self.ok("Clipboard read", content=data)
        except Exception as exc:
            return self.error(f"Clipboard read failed: {exc}")

    def clipboard_set(self, text: str) -> dict:
        try:
            import tkinter as tk
            r = tk.Tk(); r.withdraw()
            r.clipboard_clear(); r.clipboard_append(text); r.update(); r.destroy()
            return self.ok("Clipboard set")
        except Exception as exc:
            return self.error(f"Clipboard set failed: {exc}")

    def list_windows(self) -> dict:
        try:
            import ctypes.wintypes
            user32 = ctypes.windll.user32
            EnumWindowsProc = ctypes.WINFUNCTYPE(
                ctypes.wintypes.BOOL, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM)
            results = []
            def cb(hwnd, lparam):
                if user32.IsWindowVisible(hwnd):
                    n = user32.GetWindowTextLengthW(hwnd)
                    if n:
                        buf = ctypes.create_unicode_buffer(n + 1)
                        user32.GetWindowTextW(hwnd, buf, n + 1)
                        results.append({"hwnd": hwnd, "title": buf.value})
                return True
            user32.EnumWindows(EnumWindowsProc(cb), 0)
            return self.ok(f"{len(results)} windows", windows=results)
        except Exception as exc:
            return self.error(f"List windows failed: {exc}")

    def focus_window(self, title_substr: str) -> dict:
        try:
            result = self.list_windows()
            if not result.get("ok"):
                return result
            for w in result["windows"]:
                if title_substr.lower() in w["title"].lower():
                    ctypes.windll.user32.SetForegroundWindow(w["hwnd"])
                    return self.ok(f"Focused '{w['title']}'")
            return self.error(f"No window matching '{title_substr}'")
        except Exception as exc:
            return self.error(f"Focus failed: {exc}")

    def download_file(self, url: str, dest: str) -> dict:
        try:
            import urllib.request
            Path(dest).parent.mkdir(parents=True, exist_ok=True)
            urllib.request.urlretrieve(url, dest)
            return self.ok(f"Downloaded to {dest}")
        except Exception as exc:
            return self.error(f"Download failed: {exc}")
