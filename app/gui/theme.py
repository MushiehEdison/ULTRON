"""
theme.py
--------
All colors + stylesheet generation live here so the "look" of ULTRON can be
tweaked from a single file without touching layout/animation code.

Roland: this is the file to edit if you just want to change colors/fonts.

Two palettes are provided - LIGHT (default) and DARK - plus one set of
STATE_COLORS (accent colors) that stay the same in both, so the reactor
core / waveform / status pill always read the same "meaning" regardless of
theme: blue=idle, green=listening, amber=thinking, violet=speaking,
red=error/alert.
"""

# accent colors per assistant state - identical in both themes
STATE_COLORS = {
    "idle":       "#2f7dff",   # arc-reactor blue - waiting for the wake word
    "listening":  "#00d9a3",   # green - actively hearing the mic
    "thinking":   "#ffb020",   # amber - LLM parsing the command
    "speaking":   "#8a5bff",   # violet - TTS / response playing
    "error":      "#ff4757",   # red - something failed / needs confirmation
}

# the "brand" accent used for chrome/borders/HUD lines regardless of state
BRAND_ACCENT = "#2f7dff"

FONT_FAMILY = "Segoe UI, Inter, -apple-system, sans-serif"
MONO_FAMILY = "Consolas, 'JetBrains Mono', 'Courier New', monospace"

PALETTES = {
    "light": dict(
        bg="#eef1f8",
        panel="#ffffff",
        panel2="#f3f5fb",
        border="#d7deee",
        border_strong="#b9c4dd",
        text="#12151f",
        muted="#636d82",
        grid="#c9d3ea",
        shadow="rgba(47,125,255,60)",
        log_text="#3a4256",
    ),
    "dark": dict(
        bg="#0a0d14",
        panel="#11151f",
        panel2="#161b28",
        border="#232a3b",
        border_strong="#39435c",
        text="#e8ecf7",
        muted="#7a8399",
        grid="#1c2436",
        shadow="rgba(47,125,255,90)",
        log_text="#b9c2d8",
    ),
}


def palette(mode: str) -> dict:
    return PALETTES.get(mode, PALETTES["light"])


def build_stylesheet(mode: str) -> str:
    p = palette(mode)
    return f"""
QMainWindow {{
    background-color: {p['bg']};
}}

QWidget {{
    color: {p['text']};
    font-family: {FONT_FAMILY};
    font-size: 13px;
}}

#Panel, #HudPanel {{
    background-color: {p['panel']};
    border: 1px solid {p['border']};
    border-radius: 16px;
}}

#TitleLabel {{
    font-size: 21px;
    font-weight: 700;
    letter-spacing: 3px;
    color: {p['text']};
}}

#SubtitleLabel {{
    color: {p['muted']};
    font-size: 11px;
    letter-spacing: 1px;
}}

#StatusPill {{
    border-radius: 11px;
    padding: 4px 14px;
    font-weight: 700;
    font-size: 11px;
    letter-spacing: 1px;
}}

#SectionLabel {{
    color: {p['muted']};
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 1.5px;
}}

#TranscriptLabel {{
    color: {p['text']};
    font-size: 16px;
    font-weight: 500;
}}

QTextEdit#LogConsole, QPlainTextEdit#CommandView {{
    background-color: {p['panel2']};
    border: 1px solid {p['border']};
    border-radius: 10px;
    padding: 8px;
    color: {p['log_text']};
    font-family: {MONO_FAMILY};
    font-size: 12px;
}}

QPushButton#MicButton {{
    background-color: {p['panel2']};
    border: 2px solid {BRAND_ACCENT};
    border-radius: 36px;
}}
QPushButton#MicButton:hover {{
    border: 2px solid {STATE_COLORS['listening']};
}}
QPushButton#MicButton:pressed {{
    background-color: {p['border']};
}}

QPushButton#IconButton {{
    background-color: {p['panel2']};
    border: 1px solid {p['border']};
    border-radius: 18px;
    font-size: 15px;
    color: {p['text']};
}}
QPushButton#IconButton:hover {{
    border: 1px solid {BRAND_ACCENT};
    color: {BRAND_ACCENT};
}}
QPushButton#IconButton:pressed {{
    background-color: {p['border']};
}}

QPushButton#GhostButton {{
    background-color: transparent;
    border: 1px solid {p['border']};
    border-radius: 8px;
    padding: 6px 12px;
    color: {p['muted']};
}}
QPushButton#GhostButton:hover {{
    border: 1px solid {p['border_strong']};
    color: {p['text']};
}}

QScrollBar:vertical {{
    background: transparent;
    width: 8px;
}}
QScrollBar::handle:vertical {{
    background: {p['border_strong']};
    border-radius: 4px;
    min-height: 24px;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0px;
}}
"""
