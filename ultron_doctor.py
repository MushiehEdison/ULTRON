"""
ultron_doctor.py
-----------------
Drop this file in the ROOT of your ULTRON repo (same folder as README.md)
and run:

    python ultron_doctor.py

It checks every layer of the stack -- Python version, dependencies, config,
each app module, the automation adapter for your OS, and the existing
pytest suite -- and prints a clear PASS/FAIL report with the reason and a
suggested fix for anything broken. It does NOT open apps, use your mic, or
touch your screen; everything is either an import check or a mocked call.

Exit code is 0 if everything passed, 1 if anything failed.
"""

import importlib
import os
import platform
import subprocess
import sys

RESULTS = []  # (label, "ok" | "fail" | "warn", detail)


def check(label):
    """Decorator: runs fn, records ok/fail, never lets one failure kill the script."""
    def decorator(fn):
        try:
            detail = fn()
            RESULTS.append((label, "ok", detail or ""))
        except Exception as exc:
            RESULTS.append((label, "fail", f"{type(exc).__name__}: {exc}"))
        return fn
    return decorator


def warn(label, detail):
    RESULTS.append((label, "warn", detail))


# ---------------------------------------------------------------------------
# 1. Python version
# ---------------------------------------------------------------------------
@check("Python version")
def _():
    v = sys.version_info
    if v < (3, 10):
        raise RuntimeError(
            f"Python {v.major}.{v.minor} detected — faster-whisper/PyQt6 want 3.10+"
        )
    return f"{v.major}.{v.minor}.{v.micro}"


# ---------------------------------------------------------------------------
# 2. Are we even standing in the repo root?
# ---------------------------------------------------------------------------
@check("Repo root (app/ folder found)")
def _():
    if not os.path.isdir(os.path.join(os.getcwd(), "app")):
        raise RuntimeError(
            "No 'app' folder here — run this script from the ULTRON repo root "
            "(same folder as README.md, requirements.txt)"
        )
    return os.getcwd()


sys.path.insert(0, os.getcwd())


# ---------------------------------------------------------------------------
# 3. Third-party packages from requirements.txt
# ---------------------------------------------------------------------------
# (import name may differ from the pip package name — mapped below)
PACKAGES = {
    "faster_whisper": "faster-whisper",
    "sounddevice": "sounddevice",
    "numpy": "numpy",
    "anthropic": "anthropic",
    "dotenv": "python-dotenv",
    "pyautogui": "pyautogui",
    "PyQt6": "PyQt6",
    "qtawesome": "qtawesome",
    "pytest": "pytest",
}
if sys.platform == "win32":
    PACKAGES["pywinauto"] = "pywinauto"
elif sys.platform == "darwin":
    PACKAGES["objc"] = "pyobjc"
elif sys.platform.startswith("linux"):
    PACKAGES["Xlib"] = "python-xlib"

for import_name, pip_name in PACKAGES.items():
    def make_check(imp, pip):
        @check(f"Package: {pip}")
        def _():
            mod = importlib.import_module(imp)
            return getattr(mod, "__version__", "installed")
        return _
    make_check(import_name, pip_name)


# ---------------------------------------------------------------------------
# 4. Config / .env
# ---------------------------------------------------------------------------
@check("app.utils.config loads")
def _():
    from app.utils.config import config
    if not config.has_llm():
        warn(
            "ANTHROPIC_API_KEY",
            "Not set — intent parsing will fall back to the offline rule-based "
            "parser (limited command coverage). Add it to a .env file at the "
            "repo root if you want full LLM parsing: ANTHROPIC_API_KEY=sk-ant-...",
        )
    return f"stt_model_size={config.stt_model_size}, has_llm={config.has_llm()}"


# ---------------------------------------------------------------------------
# 5. Import every app module on its own, so one broken module doesn't hide
#    the status of the others
# ---------------------------------------------------------------------------
APP_MODULES = [
    "app.utils.logger",
    "app.utils.config",
    "app.intent.schema",
    "app.intent.parser",
    "app.router.dispatcher",
    "app.automation.base",
    "app.stt.recognizer",
    "app.gui.theme",
    "app.gui.humanize",
    "app.gui.main_window",
]
if sys.platform == "win32":
    APP_MODULES.append("app.automation.windows_adapter")
elif sys.platform == "darwin":
    APP_MODULES.append("app.automation.mac_adapter")
elif sys.platform.startswith("linux"):
    APP_MODULES.append("app.automation.linux_adapter")

for mod_name in APP_MODULES:
    def make_import_check(name):
        @check(f"Import: {name}")
        def _():
            importlib.import_module(name)
            return "imported ok"
        return _
    make_import_check(mod_name)


# ---------------------------------------------------------------------------
# 6. Platform automation adapter actually resolves for this OS
# ---------------------------------------------------------------------------
@check("get_adapter() resolves for this OS")
def _():
    from app.automation.base import get_adapter
    adapter = get_adapter()
    return type(adapter).__name__


# ---------------------------------------------------------------------------
# 7. Audio input device visible to sounddevice (mic)
# ---------------------------------------------------------------------------
@check("Microphone / audio input device")
def _():
    import sounddevice as sd
    devices = sd.query_devices()
    inputs = [d["name"] for d in devices if d["max_input_channels"] > 0]
    if not inputs:
        raise RuntimeError("No input (microphone) devices found by sounddevice")
    return f"{len(inputs)} input device(s), default: {inputs[0]}"


# ---------------------------------------------------------------------------
# 8. Dispatcher + schema smoke test (mocked adapter, no real OS action)
# ---------------------------------------------------------------------------
@check("Router/dispatcher logic (mocked adapter)")
def _():
    from app.router.dispatcher import Dispatcher

    class FakeAdapter:
        def open_app(self, name):
            return {"status": "ok", "message": f"opened {name}"}

    d = Dispatcher.__new__(Dispatcher)
    d.adapter = FakeAdapter()

    ok_result = d.dispatch({"function": "open_app", "args": {"name": "chrome"}})
    assert ok_result["status"] == "ok", f"expected ok, got {ok_result}"

    bad_result = d.dispatch({"function": "delete_everything", "args": {}})
    assert bad_result["status"] == "error", f"whitelist did not block unknown command: {bad_result}"

    confirm_result = d.dispatch({"function": "change_setting", "args": {"key": "wifi", "value": "off"}})
    assert confirm_result["status"] == "needs_confirmation", f"destructive command not gated: {confirm_result}"

    return "whitelist + confirmation gate both behave as expected"


# ---------------------------------------------------------------------------
# 9. Intent parser smoke test (uses offline fallback if no API key)
# ---------------------------------------------------------------------------
@check("Intent parser (app.intent.parser.parse_command)")
def _():
    from app.intent import parser as parser_mod
    if not hasattr(parser_mod, "parse_command"):
        raise RuntimeError("parse_command() not implemented yet in app/intent/parser.py")
    result = parser_mod.parse_command("open chrome")
    if not (isinstance(result, dict) and "function" in result and "args" in result):
        raise RuntimeError(f"parse_command returned unexpected shape: {result!r}")
    return f"parse_command('open chrome') -> {result}"


# ---------------------------------------------------------------------------
# 10. Run the repo's own pytest suite
# ---------------------------------------------------------------------------
@check("pytest suite (tests/)")
def _():
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/", "-q", "--no-header"],
        capture_output=True, text=True, cwd=os.getcwd(),
    )
    output = (proc.stdout + proc.stderr).strip()
    if proc.returncode not in (0, 5):  # 5 = no tests collected
        raise RuntimeError(f"pytest exited {proc.returncode}\n{output[-1500:]}")
    return output.splitlines()[-1] if output else "no output"


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------
def main():
    print(f"\nULTRON diagnostic — {platform.system()} {platform.release()}, Python {sys.version.split()[0]}")
    print("=" * 78)

    fails = []
    warns = []
    for label, status, detail in RESULTS:
        icon = {"ok": "[PASS]", "fail": "[FAIL]", "warn": "[WARN]"}[status]
        print(f"{icon:8} {label:45} {detail}")
        if status == "fail":
            fails.append((label, detail))
        elif status == "warn":
            warns.append((label, detail))

    print("=" * 78)
    print(f"{len(RESULTS) - len(fails) - len(warns)} passed, {len(fails)} failed, {len(warns)} warnings\n")

    if fails:
        print("Problems to fix, in order:\n")
        for i, (label, detail) in enumerate(fails, 1):
            print(f"{i}. {label}")
            print(f"   {detail}\n")

    if warns:
        print("Non-blocking warnings:\n")
        for label, detail in warns:
            print(f"- {label}: {detail}\n")

    if not fails:
        print("Everything checks out. Run the app with: python -m app.main")

    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
