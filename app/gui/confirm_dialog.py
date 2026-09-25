"""
confirm_dialog.py
------------------
A themed confirmation popup for actions that need explicit user approval
(see app.intent.schema.DESTRUCTIVE_COMMANDS) - e.g. "change_setting".

Replaces the plain OS QMessageBox with a frameless, rounded, theme-matched
card so the safety-confirmation step doesn't feel like a jarring system
dialog dropped on top of the app.

Usage:
    from .confirm_dialog import ask_confirmation
    approved = ask_confirmation(self, "Change wifi to off?")
"""

from PyQt6.QtCore import Qt, QPropertyAnimation, QEasingCurve
from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QGraphicsDropShadowEffect,
)
from PyQt6.QtGui import QColor

from .theme import palette, BRAND_ACCENT, FONT_FAMILY
from .icons import icon


class ConfirmDialog(QDialog):
    def __init__(self, parent, message: str, mode: str, title: str = "Confirm action"):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setModal(True)
        self._approved = False

        p = palette(mode)

        self.setStyleSheet("QDialog { background-color: rgba(10, 13, 20, 130); }")

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        card = QLabel()  # plain container widget (QLabel used only for easy styling)
        card.setObjectName("ConfirmCard")
        card.setFixedWidth(360)
        card.setStyleSheet(
            f"""
            #ConfirmCard {{
                background-color: {p['panel']};
                border: 1px solid {p['border_strong']};
                border-radius: 18px;
            }}
            """
        )
        shadow = QGraphicsDropShadowEffect(card)
        shadow.setBlurRadius(40)
        shadow.setOffset(0, 12)
        shadow.setColor(QColor(0, 0, 0, 90))
        card.setGraphicsEffect(shadow)

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(28, 26, 28, 22)
        card_layout.setSpacing(6)

        icon_label = QLabel()
        icon_label.setPixmap(icon("fa5s.shield-alt", color=BRAND_ACCENT).pixmap(34, 34))
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(icon_label)
        card_layout.addSpacing(10)

        title_label = QLabel(title)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setStyleSheet(
            f"color: {p['text']}; font-size: 16px; font-weight: 700; "
            f"font-family: {FONT_FAMILY}; background: transparent; border: none;"
        )
        card_layout.addWidget(title_label)

        message_label = QLabel(message)
        message_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        message_label.setWordWrap(True)
        message_label.setStyleSheet(
            f"color: {p['muted']}; font-size: 13px; font-family: {FONT_FAMILY}; "
            f"background: transparent; border: none;"
        )
        card_layout.addSpacing(4)
        card_layout.addWidget(message_label)
        card_layout.addSpacing(20)

        buttons = QHBoxLayout()
        buttons.setSpacing(12)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel_btn.setFixedHeight(40)
        cancel_btn.setStyleSheet(
            f"""
            QPushButton {{
                background-color: {p['panel2']};
                color: {p['text']};
                border: 1px solid {p['border_strong']};
                border-radius: 10px;
                font-weight: 600;
                font-family: {FONT_FAMILY};
            }}
            QPushButton:hover {{ border: 1px solid {p['muted']}; }}
            """
        )
        cancel_btn.clicked.connect(self._on_cancel)

        confirm_btn = QPushButton("Confirm")
        confirm_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        confirm_btn.setFixedHeight(40)
        confirm_btn.setStyleSheet(
            f"""
            QPushButton {{
                background-color: {BRAND_ACCENT};
                color: white;
                border: none;
                border-radius: 10px;
                font-weight: 700;
                font-family: {FONT_FAMILY};
            }}
            QPushButton:hover {{ background-color: {BRAND_ACCENT}; }}
            QPushButton:pressed {{ background-color: {p['border_strong']}; }}
            """
        )
        confirm_btn.clicked.connect(self._on_confirm)

        buttons.addWidget(cancel_btn)
        buttons.addWidget(confirm_btn)
        card_layout.addLayout(buttons)

        outer.addWidget(card, alignment=Qt.AlignmentFlag.AlignCenter)

        if parent is not None:
            self.resize(parent.width(), parent.height())

    def _on_confirm(self):
        self._approved = True
        self.accept()

    def _on_cancel(self):
        self._approved = False
        self.reject()

    def showEvent(self, event):
        super().showEvent(event)
        self.setWindowOpacity(0.0)
        anim = QPropertyAnimation(self, b"windowOpacity", self)
        anim.setDuration(180)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        anim.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)
        self._show_anim = anim


def ask_confirmation(parent, message: str, mode: str = "light", title: str = "Confirm action") -> bool:
    """Show the themed confirmation card, centered over `parent`, and block
    until the user picks Confirm or Cancel. Returns True if confirmed."""
    dialog = ConfirmDialog(parent, message, mode, title)
    dialog.exec()
    return dialog._approved
