"""
icons.py
--------
Real vector icons (FontAwesome, via the `qtawesome` package) instead of
emoji glyphs. qtawesome bundles the icon fonts itself, so this works
offline with no extra asset files - just `pip install qtawesome`.

This is the Python equivalent of using react-icons / Bootstrap Icons /
Font Awesome in a web app: you reference an icon by name
("fa5s.microphone") and get back a real QIcon you can hand to any
QPushButton, QLabel, QAction, etc.

Usage:
    from .icons import icon
    button.setIcon(icon("fa5s.microphone", color="#2f7dff"))
    button.setIconSize(QSize(20, 20))

If qtawesome (or its icon font) somehow fails to load - e.g. a stripped-down
Python environment - `icon()` returns an empty QIcon instead of crashing the
whole app, so the GUI still runs; only the icon glyph would be missing.
"""

from PyQt6.QtGui import QIcon

try:
    import qtawesome as qta
    _QTA_OK = True
except Exception:
    _QTA_OK = False


def icon(name: str, color: str = "#000000") -> QIcon:
    """Return a QIcon for a FontAwesome 5 name, e.g. 'fa5s.microphone'.

    Browse available names at https://fontawesome.com (solid icons use the
    'fa5s.' prefix, regular 'fa5r.', brands 'fa5b.').
    """
    if not _QTA_OK:
        return QIcon()
    try:
        return qta.icon(name, color=color)
    except Exception:
        return QIcon()
