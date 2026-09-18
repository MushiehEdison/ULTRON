"""
Validates a parsed command against the whitelist, then dispatches it to the
platform automation adapter. This is the safety boundary described in
docs/ARCHITECTURE.md — nothing reaches app/automation/ without passing
through here first.

Expects app/intent/schema.py to export:
    ALLOWED_COMMANDS: dict[str, list[str]]   # function name -> required arg names
    DESTRUCTIVE_COMMANDS: set[str]           # function names that need confirmation

    If schema.py isn't ready yet, a fallback matching the current adapters
    (app/automation/base.py) is used so this file still works standalone.
    """

from app.automation.base import get_adapter
from app.utils.logger import get_logger

log = get_logger(__name__)

try:
    from app.intent.schema import ALLOWED_COMMANDS, DESTRUCTIVE_COMMANDS
except ImportError:
    log.warning("app/intent/schema.py not found or incomplete — using fallback whitelist")
    ALLOWED_COMMANDS = {
        "open_app": ["name"],
        "web_search": ["app", "query"],
        "type_text": ["text"],
        "open_file": ["path"],
        "change_setting": ["key", "value"],
    }
    DESTRUCTIVE_COMMANDS = {"change_setting"}


class Dispatcher:

    def __init__(self):
        self.adapter = get_adapter()

    def dispatch(self, command: dict) -> dict:
        """Validate + run (or flag for confirmation) a parsed command."""
        validation_error = self._validate(command)
        if validation_error:
            log.warning("Rejected command: %s (%s)", command, validation_error)
            return {"status": "error", "message": validation_error}

        function = command["function"]

        if function in DESTRUCTIVE_COMMANDS:
            log.info("Command needs confirmation: %s", command)
            return {"status": "needs_confirmation", "message": f"Confirm: {function}?"}

        return self._execute(command)

    def confirm(self, command: dict) -> dict:
        """Run a command the user has just approved after a
        needs_confirmation response. Re-validates — never trust that the
        command wasn't tampered with between dispatch() and confirm()."""
        validation_error = self._validate(command)
        if validation_error:
            log.warning("Rejected command on confirm: %s (%s)", command, validation_error)
            return {"status": "error", "message": validation_error}

        return self._execute(command)

        # ---- internals ----

    def _validate(self, command: dict) -> str | None:
        if not isinstance(command, dict):
            return "Command must be a dict"

        function = command.get("function")
        args = command.get("args", {})

        if function is None:
            return "Missing 'function'"

        if function not in ALLOWED_COMMANDS:
            return f"'{function}' is not a whitelisted command"

        if not isinstance(args, dict):
            return "'args' must be a dict"

        required_args = ALLOWED_COMMANDS[function]
        missing = [a for a in required_args if a not in args]
        if missing:
            return f"Missing required args for '{function}': {missing}"

        return None

    def _execute(self, command: dict) -> dict:
        function = command["function"]
        args = command.get("args", {})

        method = getattr(self.adapter, function, None)
        if method is None:
            log.error("Whitelisted command '%s' has no matching adapter method", function)
            return {"status": "error", "message": f"'{function}' is not implemented on this platform"}

        try:
            result = method(**args)
            log.info("Executed %s(%s) -> %s", function, args, result)
            return result
        except Exception as exc:
            log.exception("Adapter raised while executing %s", function)
            return {"status": "error", "message": str(exc)}