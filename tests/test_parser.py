"""
Tests for app/intent/parser.py.

app/intent/parser.py is still empty as of this commit — pytest.importorskip
below means these tests SKIP (not fail) until it's implemented, so CI
doesn't break for the other modules in the meantime. Once parse_command()
exists, these run for real.

Expected contract (see docs/ARCHITECTURE.md):
    parse_command(text: str) -> dict
    returns {"function": <whitelisted name>, "args": {...}}
    """

import pytest

parser = pytest.importorskip(
    "app.intent.parser",
    reason="app/intent/parser.py not implemented yet",
)

if not hasattr(parser, "parse_command"):
    pytest.skip(
        "app.intent.parser.parse_command not implemented yet",
        allow_module_level=True,
    )


def test_parse_command_returns_expected_shape():
    result = parser.parse_command("open chrome")
    assert isinstance(result, dict)
    assert "function" in result
    assert "args" in result
    assert isinstance(result["args"], dict)


def test_parse_command_maps_open_app_correctly():
    result = parser.parse_command("open chrome")
    assert result["function"] == "open_app"
    assert result["args"].get("name", "").lower() == "chrome"


def test_parse_command_maps_web_search_correctly():
    result = parser.parse_command("search for cats on chrome")
    assert result["function"] == "web_search"
    assert "cats" in result["args"].get("query", "").lower()


def test_parse_command_only_returns_whitelisted_functions():
    from app.intent.schema import ALLOWED_COMMANDS
    result = parser.parse_command("open notepad")
    assert result["function"] in ALLOWED_COMMANDS