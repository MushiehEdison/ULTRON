"""
Tests for app/router/dispatcher.py.

Uses a FakeAdapter instead of a real platform adapter, so these run
identically on any OS/CI runner without touching pyautogui/subprocess.
"""

import pytest

from app.router.dispatcher import Dispatcher


class FakeAdapter:
    """Records calls instead of touching the real OS."""

    def __init__(self):
        self.calls = []

    def open_app(self, name):
        self.calls.append(("open_app", name))
        return {"status": "ok", "message": f"opened {name}"}

    def change_setting(self, key, value):
        self.calls.append(("change_setting", key, value))
        return {"status": "ok", "message": f"changed {key} to {value}"}


@pytest.fixture
def dispatcher():
    d = Dispatcher.__new__(Dispatcher)   # skip __init__'s get_adapter() call
    d.adapter = FakeAdapter()
    return d


def test_unknown_command_is_rejected(dispatcher):
    result = dispatcher.dispatch({"function": "delete_everything", "args": {}})
    assert result["status"] == "error"
    assert "not a whitelisted command" in result["message"]


def test_missing_required_args_is_rejected(dispatcher):
    result = dispatcher.dispatch({"function": "open_app", "args": {}})
    assert result["status"] == "error"
    assert "Missing required args" in result["message"]


def test_valid_non_destructive_command_executes_immediately(dispatcher):
    result = dispatcher.dispatch({"function": "open_app", "args": {"name": "chrome"}})
    assert result["status"] == "ok"
    assert ("open_app", "chrome") in dispatcher.adapter.calls


def test_destructive_command_requires_confirmation(dispatcher):
    result = dispatcher.dispatch({
        "function": "change_setting",
        "args": {"key": "wifi", "value": "off"},
    })
    assert result["status"] == "needs_confirmation"
    # must NOT have executed yet
    assert dispatcher.adapter.calls == []


def test_confirm_executes_a_previously_flagged_command(dispatcher):
    command = {"function": "change_setting", "args": {"key": "wifi", "value": "off"}}
    dispatcher.dispatch(command)              # flags it
    result = dispatcher.confirm(command)       # user said yes
    assert result["status"] == "ok"
    assert ("change_setting", "wifi", "off") in dispatcher.adapter.calls


def test_malformed_command_is_rejected(dispatcher):
    result = dispatcher.dispatch("not a dict")
    assert result["status"] == "error"