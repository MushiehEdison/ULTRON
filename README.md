# Project Ultron

Voice-controlled PC automation. Say it, it happens — open apps, search the web, type, open files, change settings. Built in Python, packaged native for Windows, Fedora, and macOS.

## What it does

Speak a command → speech-to-text transcribes it → an LLM converts it into a structured action → a router validates it against a whitelist → a platform adapter executes it on your OS.

```
"open chrome and search cats"
→ { "function": "web_search", "args": { "app": "chrome", "query": "cats" } }
→ Chrome opens, search runs
```

No free-text execution. The LLM only ever picks from a fixed, whitelisted set of commands — every action is validated before it touches your machine, and destructive actions require confirmation.

## Architecture

```
Mic → STT (faster-whisper) → LLM Intent Parser → Command Router → Platform Adapter → OS Action
                                                        ↓
                                                   Command Schema
                                                    (whitelist)
```

Full system design, diagrams, and tool breakdown: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)

## Tech stack

| Layer | Tools |
|---|---|
| STT | faster-whisper, sounddevice |
| Intent parsing | LLM API (tool-calling / structured output) |
| Automation | pyautogui, subprocess, pywinauto (Win), pyobjc/AppleScript (Mac), wmctrl/xlib (Linux) |
| GUI | PyQt6 / PySide6 |
| Packaging | PyInstaller → .exe / .rpm / .dmg |
| CI | GitHub Actions (build matrix) |

## Project structure

```
voice-pc-assistant/
├── app/
│   ├── main.py            # entry point
│   ├── stt/                # speech-to-text
│   ├── intent/              # schema.py (whitelist) + parser.py (LLM calls)
│   ├── router/              # validates + dispatches commands
│   ├── automation/          # base.py + windows/linux/mac adapters
│   └── gui/                 # PyQt app
├── tests/
├── build/                  # per-OS packaging configs
└── docs/
```

## Status

3-week build: Week 1 ramp-up on the stack, Weeks 2–3 development + integration + packaging. Currently: `in progress`.

## Setup

```bash
git clone https://github.com/<org>/voice-pc-assistant.git
cd voice-pc-assistant
pip install -r requirements.txt
cp .env.example .env   # add your ANTHROPIC_API_KEY (optional — falls back to an offline parser without it)
python -m app.main
```

## Contributing

Each module (STT, intent parser, router, per-OS adapters, GUI) is owned by one contributor and built against the shared interface in `app/automation/base.py`. See [`docs/CONTRIBUTING.md`](docs/CONTRIBUTING.md) for branch naming and PR process.

## Safety

- LLM output is restricted to a fixed command whitelist — it cannot invent actions.
- Destructive actions (delete, system setting changes) require confirmation.
- Every executed command is logged.

## License

TBD
