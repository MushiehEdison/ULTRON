"""
parser.py
---------
Turns raw transcribed text into a structured, whitelisted command:

    parse_command(text: str) -> {"function": <name>, "args": {...}}

Two paths, in order:

1. LLM path — if ANTHROPIC_API_KEY is configured (see app/utils/config.py),
   the text is sent to Claude with tool-calling forced onto the single
   `run_command` tool defined in app/intent/schema.py. The model can only
   pick a whitelisted function; it never returns free text.

2. Offline fallback — if no API key is set, the call fails, times out, or
   the model somehow returns something outside the whitelist, a small
   rule-based parser handles the common phrasings instead. This is what
   keeps the app from being a single point of failure on network/API
   availability, and it's also what makes app/intent/parser.py testable
   and CI-runnable with no secrets configured.

Either way, the result is validated against ALLOWED_COMMANDS before it's
ever returned — app/router/dispatcher.py re-validates again independently,
so an invalid command here is inconvenient, not unsafe.
"""

import json
import re

from app.intent.schema import ALLOWED_COMMANDS, required_args, INTENT_TOOL
from app.utils.config import config
from app.utils.logger import get_logger

log = get_logger(__name__)

_FALLBACK_FUNCTION = "open_app"  # least-surprising default if nothing matches


# --------------------------------------------------------------------------- #
# Public entry point
# --------------------------------------------------------------------------- #
def parse_command(text: str) -> dict:
    text = (text or "").strip()
    if not text:
        return {"function": _FALLBACK_FUNCTION, "args": {"name": ""}}

    if config.has_llm():
        try:
            result = _parse_with_llm(text)
            if _is_valid(result):
                return result
            log.warning("LLM returned an invalid/unwhitelisted command, falling back: %s", result)
        except Exception:
            log.exception("Intent LLM call failed, falling back to offline parser")

    return _parse_offline(text)


def _is_valid(result) -> bool:
    if not isinstance(result, dict):
        return False
    function = result.get("function")
    args = result.get("args")
    if function not in ALLOWED_COMMANDS or not isinstance(args, dict):
        return False
    return all(a in args for a in required_args(function))


# --------------------------------------------------------------------------- #
# LLM path
# --------------------------------------------------------------------------- #
def _parse_with_llm(text: str) -> dict:
    import anthropic

    client = anthropic.Anthropic(api_key=config.anthropic_api_key)
    response = client.messages.create(
        model=config.intent_model,
        max_tokens=config.intent_max_tokens,
        tools=[INTENT_TOOL],
        tool_choice={"type": "tool", "name": "run_command"},
        messages=[
            {
                "role": "user",
                "content": (
                    "Convert this spoken command into a run_command tool call. "
                    f'Spoken text: "{text}"'
                ),
            }
        ],
        timeout=config.intent_timeout_seconds,
    )

    for block in response.content:
        if block.type == "tool_use" and block.name == "run_command":
            payload = block.input
            if isinstance(payload, str):
                payload = json.loads(payload)
            return {
                "function": payload.get("function"),
                "args": payload.get("args", {}) or {},
            }

    raise ValueError("No run_command tool_use block in LLM response")


# --------------------------------------------------------------------------- #
# Offline fallback parser
# --------------------------------------------------------------------------- #
_SEARCH_RE = re.compile(
    r"^(?:search|google|look\s*up|find)\s+(?:for\s+)?(.+?)"
    r"(?:\s+(?:on|using|in|with)\s+(\w+))?$",
    re.IGNORECASE,
)
_TYPE_RE = re.compile(r"^(?:type|write|enter)\s+(.+)$", re.IGNORECASE)
_OPEN_FILE_RE = re.compile(
    r"^open\s+(?:the\s+)?file\s+(.+)$|^open\s+(\S+\.\w{1,5})$", re.IGNORECASE
)
_OPEN_APP_RE = re.compile(r"^(?:open|launch|start)\s+(.+)$", re.IGNORECASE)
_SETTING_RE = re.compile(
    r"^(?:turn\s+(on|off)|enable|disable|toggle|set)\s+(?:the\s+)?"
    r"(wifi|wi-fi|bluetooth|display|brightness|sound|volume|battery)"
    r"(?:\s+to\s+(.+))?$",
    re.IGNORECASE,
)


def _parse_offline(text: str) -> dict:
    stripped = text.strip().rstrip(".!")

    m = _SEARCH_RE.match(stripped)
    if m:
        query = m.group(1).strip()
        app = (m.group(2) or config.default_browser).strip().lower()
        return {"function": "web_search", "args": {"app": app, "query": query}}

    m = _OPEN_FILE_RE.match(stripped)
    if m:
        path = (m.group(1) or m.group(2) or "").strip()
        return {"function": "open_file", "args": {"path": path}}

    m = _SETTING_RE.match(stripped)
    if m:
        on_off, key, explicit_value = m.groups()
        key = "wifi" if key in ("wifi", "wi-fi") else key
        if key == "brightness":
            key = "display"
        if key == "volume":
            key = "sound"
        value = explicit_value.strip() if explicit_value else (on_off or "toggle")
        return {"function": "change_setting", "args": {"key": key, "value": value}}

    m = _TYPE_RE.match(stripped)
    if m:
        return {"function": "type_text", "args": {"text": m.group(1).strip()}}

    m = _OPEN_APP_RE.match(stripped)
    if m:
        return {"function": "open_app", "args": {"name": m.group(1).strip().lower()}}

    # Nothing matched — treat the whole utterance as an app name rather than
    # silently dropping it; the router/adapter will report a clean error if
    # no such app exists.
    return {"function": _FALLBACK_FUNCTION, "args": {"name": stripped.lower()}}
