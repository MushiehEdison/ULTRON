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