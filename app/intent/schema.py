"""
schema.py
---------
The whitelist. This is the single source of truth for every command the
system is allowed to execute — the LLM in parser.py is forced to choose
from it, and dispatcher.py re-validates against it before anything ever
reaches app/automation/. Add a command here first (and to
docs/COMMAND_SCHEMA.md), then implement it on every platform adapter.
"""

# function name -> list of required arg names.
# Must match the abstract methods on app.automation.base.AutomationAdapter.
ALLOWED_COMMANDS = {
    "open_app": ["name"],
    "web_search": ["app", "query"],
    "type_text": ["text"],
    "open_file": ["path"],
    "change_setting": ["key", "value"],
}

# Commands that require an explicit user confirmation before they run,
# per the non-negotiable safety layer in the spec (Section 5).
DESTRUCTIVE_COMMANDS = {"change_setting"}

# Settings every platform adapter is guaranteed to support (each adapter's
# own ALLOWED_SETTINGS may be a superset of this — see
# app/automation/{windows,linux,mac}_adapter.py). Used by the intent parser
# as a hint so the LLM/fallback don't invent settings no adapter honors.
COMMON_SETTINGS = ["wifi", "bluetooth", "display", "sound", "battery"]

# Anthropic tool-calling definition built from ALLOWED_COMMANDS. Forcing the
# model to call this exact tool (tool_choice) is what keeps its output to
# strict, whitelisted JSON instead of free text — see app/intent/parser.py.
INTENT_TOOL = {
    "name": "run_command",
    "description": (
        "Execute exactly one whitelisted PC-automation command based on what "
        "the user asked for. Never invent a command outside the enum below."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "function": {
                "type": "string",
                "enum": sorted(ALLOWED_COMMANDS.keys()),
                "description": "Which whitelisted command to run.",
            },
            "args": {
                "type": "object",
                "description": (
                    "Arguments for the chosen function. open_app: {name}. "
                    "web_search: {app, query}. type_text: {text}. "
                    "open_file: {path}. change_setting: {key, value} where "
                    f"key is one of {COMMON_SETTINGS}."
                ),
            },
        },
        "required": ["function", "args"],
    },
}


def required_args(function: str):
    """Convenience accessor used by parser.py's fallback and by tests."""
    return ALLOWED_COMMANDS.get(function, [])
