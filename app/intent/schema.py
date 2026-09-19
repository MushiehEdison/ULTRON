ALLOWED_COMMANDS = {
    "open_app",
    "web_search",
    "type_text",
    "open_file",
    "change_setting",
}

COMMAND_ARGUMENTS = {
    "open_app": ["name"],
    "web_search": ["app", "query"],
    "type_text": ["text"],
    "open_file": ["path"],
    "change_setting": ["key", "value"],
}


def is_valid_command(command):
    return command in ALLOWED_COMMANDS


def validate_command(command_data):
    """
    Validate a structured command produced by the LLM.

    Expected format:
    {
        "function": "open_app",
        "args": {
            "name": "Chrome"
        }
    }
    """

    if not isinstance(command_data, dict):
        raise ValueError("Command must be a dictionary.")

    if "function" not in command_data:
        raise ValueError("Command is missing 'function'.")

    if "args" not in command_data:
        raise ValueError("Command is missing 'args'.")

    function = command_data["function"]
    args = command_data["args"]

    if not is_valid_command(function):
        raise ValueError(f"Unknown command: {function}")

    if not isinstance(args, dict):
        raise ValueError("'args' must be a dictionary.")

    required_arguments = COMMAND_ARGUMENTS[function]

    for argument in required_arguments:
        if argument not in args:
            raise ValueError(
                f"Missing required argument '{argument}' "
                f"for '{function}'."
            )

    return True