"""
humanize.py
-----------
Turns a whitelisted {function, args} command dict (see app/intent/schema.py)
into one plain-English sentence for on-screen display.

This exists purely so the *user-facing* GUI never has to show raw JSON.
Developers who want the raw command can still find it in the app log file
(see app/utils/logger.py) - it just isn't shown in the window anymore.
"""


def humanize_command(command: dict) -> str:
    if not isinstance(command, dict):
        return "Do something"

    function = command.get("function", "")
    args = command.get("args", {}) or {}

    if function == "open_app":
        return f"Open {args.get('name', 'an app')}"

    if function == "web_search":
        app = args.get("app", "your browser")
        query = args.get("query", "")
        return f'Search {app} for \u201c{query}\u201d' if query else f"Search with {app}"

    if function == "type_text":
        text = args.get("text", "")
        preview = text if len(text) <= 40 else text[:37] + "..."
        return f'Type \u201c{preview}\u201d'

    if function == "open_file":
        return f"Open {args.get('path', 'a file')}"

    if function == "change_setting":
        key = args.get("key", "a setting")
        value = args.get("value", "")
        return f"Change {key} to {value}" if value else f"Change {key}"

    return function.replace("_", " ").capitalize() or "Run a command"
