"""
Tests for app/automation/base.py.

Doesn't touch a real OS adapter — just checks the abstract contract:
    you can't instantiate AutomationAdapter directly, get_adapter() picks the
    right subclass per platform, and the ok()/error() helpers return the shape
    dispatcher.py expects.
    """

from unittest.mock import patch

import pytest

from app.automation.base import AutomationAdapter, get_adapter


class FakeAdapter(AutomationAdapter):
    """Minimal concrete subclass, just to exercise the base helpers."""

    def open_app(self, name):
        return self.ok(f"opened {name}")

    def web_search(self, app, query):
        return self.ok(f"searched {query} in {app}")

    def type_text(self, text):
        return self.ok("typed")

    def open_file(self, path):
        return self.ok(f"opened {path}")

    def change_setting(self, key, value):
        return self.error(f"'{key}' not allowed")


def test_cannot_instantiate_abstract_adapter_directly():
    with pytest.raises(TypeError):
        AutomationAdapter()


def test_ok_helper_returns_expected_shape():
    adapter = FakeAdapter()
    result = adapter.ok("done")
    assert result == {"status": "ok", "message": "done"}


def test_error_helper_returns_expected_shape():
    adapter = FakeAdapter()
    result = adapter.error("nope")
    assert result == {"status": "error", "message": "nope"}


@patch("platform.system", return_value="Windows")
def test_get_adapter_picks_windows(mock_system):
    from app.automation.windows_adapter import WindowsAdapter
    assert isinstance(get_adapter(), WindowsAdapter)


@patch("platform.system", return_value="Linux")
def test_get_adapter_picks_linux(mock_system):
    from app.automation.linux_adapter import LinuxAdapter
    assert isinstance(get_adapter(), LinuxAdapter)


@patch("platform.system", return_value="Darwin")
def test_get_adapter_picks_mac(mock_system):
    from app.automation.mac_adapter import MacAdapter
    assert isinstance(get_adapter(), MacAdapter)


@patch("platform.system", return_value="SomeOtherOS")
def test_get_adapter_raises_on_unsupported_platform(mock_system):
    with pytest.raises(RuntimeError):
        get_adapter()