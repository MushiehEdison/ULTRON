<<<<<<< HEAD
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
=======
import pytest


from app.intent.schema import (
    is_valid_command,
    validate_command,
)


def test_valid_command():
    assert is_valid_command("open_app") is True


def test_invalid_command():
    assert is_valid_command("delete_files") is False


def test_valid_structured_command():
    command = {
        "function": "open_app",
        "args": {
            "name": "Chrome"
        }
    }

    assert validate_command(command) is True


def test_missing_argument():
    command = {
        "function": "open_app",
        "args": {}
    }

    with pytest.raises(ValueError):
        validate_command(command)


def test_unknown_command():
    command = {
        "function": "delete_files",
        "args": {}
    }

    with pytest.raises(ValueError):
        validate_command(command)


def test_all_allowed_commands_are_valid():
    commands = [
        {
            "function": "open_app",
            "args": {
                "name": "Chrome"
            }
        },
        {
            "function": "web_search",
            "args": {
                "app": "Chrome",
                "query": "cats"
            }
        },
        {
            "function": "type_text",
            "args": {
                "text": "hello world"
            }
        },
        {
            "function": "open_file",
            "args": {
                "path": "report.pdf"
            }
        },
        {
            "function": "change_setting",
            "args": {
                "key": "brightness",
                "value": "50 percent"
            }
        },
    ]

    for command in commands:
        assert validate_command(command) is True
>>>>>>> feature/intent-schema-parser
