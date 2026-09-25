"""
parser.py
---------
Turns raw transcribed text into a structured, whitelisted command or plan.

Public API:
    parse_command(text, context=None) -> dict

Result dict is one of:
    - action   : {"kind": "action",   "function": str, "args": dict,
                  "confidence": float, "reasoning": str}
    - plan     : {"kind": "plan",     "steps": [ {function, args}, ... ],
                  "confidence": float, "reasoning": str}
    - clarify  : {"kind": "clarify",  "question": str, "confidence": float}
    - error    : {"kind": "error",    "message": str}

Three paths, in order:
    1. Cloud LLM (Anthropic) with forced tool-calling.
    2. Offline LLM (Ollama, default Qwen2.5-0.5B-Instruct) with a lean
       JSON-schema prompt tuned for small models.
    3. Regex fallback (no model required).

Every LLM result is validated against ALLOWED_COMMANDS before return.
The confidence floor + whitelist means a weak small model is a bonus,
never a liability: any misfire kicks down to the regex parser, same as
if no model were installed at all.
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field, asdict
from typing import Any

from app.intent.schema import (
    ALLOWED_COMMANDS,
    COMMON_SETTINGS,
    required_args,
    INTENT_TOOL,
)
from app.utils.config import config
from app.utils.logger import get_logger

log = get_logger(__name__)

_FALLBACK_FUNCTION = "open_app"

# Below this confidence, trust the regex parser over the (small) LLM.
_CONFIDENCE_FLOOR = 0.35


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------

@dataclass
class ParsedResult:
    kind: str                       # "action" | "plan" | "clarify" | "error"
    function: str | None = None
    args: dict[str, Any] = field(default_factory=dict)
    steps: list[dict] = field(default_factory=list)
    question: str | None = None
    message: str | None = None
    confidence: float = 1.0
    reasoning: str = ""

    def to_dict(self) -> dict:
        return {k: v for k, v in asdict(self).items() if v not in (None, {}, [])}


# ---------------------------------------------------------------------------
# Tiny in-process cache (identical utterance -> same result for N seconds)
# ---------------------------------------------------------------------------

_CACHE: dict[str, tuple[float, ParsedResult]] = {}
_CACHE_TTL = 30.0  # seconds


def _cache_get(key: str) -> ParsedResult | None:
    hit = _CACHE.get(key)
    if not hit:
        return None
    ts, value = hit
    if time.time() - ts > _CACHE_TTL:
        _CACHE.pop(key, None)
        return None
    return value


def _cache_put(key: str, value: ParsedResult) -> None:
    _CACHE[key] = (time.time(), value)
    if len(_CACHE) > 256:
        oldest = min(_CACHE.items(), key=lambda kv: kv[1][0])[0]
        _CACHE.pop(oldest, None)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def parse_command(text: str, context: dict | None = None) -> dict:
    """
    context (optional) may contain:
        history      : list[{"role": "user"|"assistant", "content": str}]
        last_app     : str   # e.g. "chrome"
        last_query   : str   # e.g. "weather in paris"
        platform     : str   # "windows" | "macos" | "linux"
    """
    text = (text or "").strip()
    context = context or {}

    if not text:
        return ParsedResult(
            kind="action", function=_FALLBACK_FUNCTION,
            args={"name": ""}, confidence=0.0,
            reasoning="empty utterance",
        ).to_dict()

    cache_key = text.lower()
    if cached := _cache_get(cache_key):
        log.debug("parser cache hit: %r", text)
        return cached.to_dict()

    # 1. Cloud LLM
    if config.has_llm():
        try:
            result = _parse_with_llm(text, context)
            if _is_usable(result):
                _cache_put(cache_key, result)
                return result.to_dict()
            log.warning("Cloud LLM invalid result, falling back: %s", result)
        except Exception:
            log.exception("Cloud intent LLM call failed, falling back")

    # 2. Offline LLM (Qwen2.5-0.5B-Instruct by default)
    if config.has_offline_llm():
        try:
            result = _parse_with_offline_llm(text, context)
            if _is_usable(result):
                _cache_put(cache_key, result)
                return result.to_dict()
            log.warning("Offline LLM invalid/low-confidence result, falling back: %s", result)
        except Exception:
            log.exception("Offline intent LLM call failed, falling back to regex")

    # 3. Regex fallback
    result = _parse_offline(text, context)
    _cache_put(cache_key, result)
    return result.to_dict()


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def _valid_step(step: dict) -> bool:
    if not isinstance(step, dict):
        return False
    fn = step.get("function")
    args = step.get("args", {}) or {}
    if fn not in ALLOWED_COMMANDS or not isinstance(args, dict):
        return False
    return all(a in args for a in required_args(fn))


def _is_usable(result: ParsedResult) -> bool:
    if not isinstance(result, ParsedResult):
        return False
    if result.kind == "clarify":
        return bool(result.question) and result.confidence >= 0.25
    if result.kind == "plan":
        return (
            bool(result.steps)
            and all(_valid_step(s) for s in result.steps)
            and result.confidence >= _CONFIDENCE_FLOOR
        )
    if result.kind == "action":
        return (
            _valid_step({"function": result.function, "args": result.args})
            and result.confidence >= _CONFIDENCE_FLOOR
        )
    return False


# ---------------------------------------------------------------------------
# Cloud LLM path (Anthropic)
# ---------------------------------------------------------------------------

_CLOUD_SYSTEM_PROMPT = (
    "You convert a spoken PC-automation command into ONE of:\n"
    "  (a) a single action  -> {function, args}\n"
    "  (b) a multi-step plan -> {steps:[{function,args}, ...]}\n"
    "  (c) a clarifying question -> {clarify: '...'}\n"
    "Always include a confidence (0..1) and a one-sentence reasoning.\n"
    "Use the conversation context when the user says 'it', 'that', "
    "'the same thing', or refers to a previous app/query.\n"
    "If the request is ambiguous or the target is missing, ASK instead of "
    "guessing. Prefer a plan over a chain of separate commands."
)


def _parse_with_llm(text: str, context: dict) -> ParsedResult:
    import anthropic

    client = anthropic.Anthropic(api_key=config.anthropic_api_key)

    ctx_lines = []
    if context.get("platform"):
        ctx_lines.append(f"Platform: {context['platform']}")
    if context.get("last_app"):
        ctx_lines.append(f"Last app opened: {context['last_app']}")
    if context.get("last_query"):
        ctx_lines.append(f"Last search query: {context['last_query']}")
    ctx_block = "\n".join(ctx_lines) or "(none)"

    messages = []
    for turn in context.get("history", [])[-6:]:
        messages.append({"role": turn["role"], "content": turn["content"]})
    messages.append({
        "role": "user",
        "content": (
            f"Context:\n{ctx_block}\n\n"
            f'Spoken text: "{text}"'
        ),
    })

    response = client.messages.create(
        model=config.intent_model,
        max_tokens=config.intent_max_tokens,
        system=_CLOUD_SYSTEM_PROMPT,
        tools=[INTENT_TOOL],
        tool_choice={"type": "tool", "name": "run_command"},
        messages=messages,
        timeout=config.intent_timeout_seconds,
    )

    for block in response.content:
        if block.type == "tool_use" and block.name == "run_command":
            payload = block.input
            if isinstance(payload, str):
                payload = json.loads(payload)
            return _payload_to_result(payload)

    raise ValueError("No run_command tool_use block in LLM response")


def _payload_to_result(payload: dict) -> ParsedResult:
    conf = float(payload.get("confidence", 0.7) or 0.7)
    reason = payload.get("reasoning", "") or ""

    if payload.get("clarify"):
        return ParsedResult(kind="clarify", question=str(payload["clarify"]),
                            confidence=conf, reasoning=reason)

    if payload.get("steps"):
        steps = []
        for s in payload["steps"]:
            fn = s.get("function")
            args = s.get("args", {}) or {}
            if fn in ALLOWED_COMMANDS:
                for a in required_args(fn):
                    args.setdefault(a, "")
            steps.append({"function": fn, "args": args})
        return ParsedResult(kind="plan", steps=steps,
                            confidence=conf, reasoning=reason)

    fn = payload.get("function")
    args = payload.get("args", {}) or {}
    if fn in ALLOWED_COMMANDS:
        for a in required_args(fn):
            args.setdefault(a, "")
    return ParsedResult(kind="action", function=fn, args=args,
                        confidence=conf, reasoning=reason)


# ---------------------------------------------------------------------------
# Offline LLM path (Ollama + Qwen2.5-0.5B-Instruct)
# ---------------------------------------------------------------------------

def _build_offline_prompt() -> str:
    """
    Prompt tuned for Qwen2.5-0.5B-Instruct:
      - schema first, task last (small models weight the tail heavily)
      - one example per shape, not five
      - explicit "no markdown, no prose" reinforcement near the end
    """
    fns = ", ".join(sorted(ALLOWED_COMMANDS.keys()))
    required = "; ".join(
        f"{fn}=>{sorted(required_args(fn))}" for fn in ALLOWED_COMMANDS
    )
    return (
        "You are a strict JSON generator for PC voice commands.\n"
        f"Allowed functions: {fns}\n"
        f"Required args: {required}\n"
        f"change_setting key must be one of: {COMMON_SETTINGS}\n"
        "\n"
        "Return ONE of these three JSON shapes, nothing else:\n"
        '  {"function":"<name>","args":{...},"confidence":0.0-1.0}\n'
        '  {"steps":[{"function":"<name>","args":{...}},...],"confidence":0.0-1.0}\n'
        '  {"clarify":"<question>","confidence":0.0-1.0}\n'
        "\n"
        "Rules:\n"
        "- Use steps only when the user asks for 2+ actions.\n"
        "- Use clarify when the target is ambiguous or missing.\n"
        "- If unsure, prefer clarify over guessing.\n"
        "- Output raw JSON only. No markdown. No commentary.\n"
        "\n"
        "Example 1: open chrome\n"
        '{"function":"open_app","args":{"name":"chrome"},"confidence":0.95}\n'
        "\n"
        "Example 2: open chrome and search for cats\n"
        '{"steps":[{"function":"open_app","args":{"name":"chrome"}},'
        '{"function":"web_search","args":{"app":"chrome","query":"cats"}}],'
        '"confidence":0.85}\n'
        "\n"
        "Example 3: open it\n"
        '{"clarify":"What would you like me to open?","confidence":0.3}\n'
    )


_OFFLINE_SYSTEM_PROMPT = _build_offline_prompt()


def _repair_json(raw: str) -> dict:
    """
    Small-model JSON fixups. Qwen2.5-0.5B occasionally emits:
      - trailing commas
      - single-quoted keys/strings
      - a leading/trailing code fence despite instructions
      - stray prose around the JSON
    """
    s = raw.strip()

    # Strip markdown fences if the model ignored instructions.
    if s.startswith("```"):
        s = s.strip("`")
        if "\n" in s:
            first, rest = s.split("\n", 1)
            if first.strip().lower() in ("json", "json5", ""):
                s = rest

    # Find the outermost {...} if there's stray prose.
    if not s.startswith("{"):
        start = s.find("{")
        end = s.rfind("}")
        if start != -1 and end != -1 and end > start:
            s = s[start:end + 1]

    try:
        return json.loads(s)
    except json.JSONDecodeError:
        pass

    fixed = s.replace("'", '"')
    fixed = re.sub(r",\s*([}\]])", r"\1", fixed)
    return json.loads(fixed)


def _parse_with_offline_llm(text: str, context: dict) -> ParsedResult:
    import ollama

    ctx_bits = []
    if context.get("last_app"):
        ctx_bits.append(f"last_app={context['last_app']}")
    if context.get("last_query"):
        ctx_bits.append(f"last_query={context['last_query']}")
    ctx_str = ("Context: " + ", ".join(ctx_bits) + "\n") if ctx_bits else ""

    messages = [{"role": "system", "content": _OFFLINE_SYSTEM_PROMPT}]

    # Truncate history hard — Qwen 0.5B has a small effective window.
    max_turns = getattr(config, "offline_intent_max_history", 2)
    for turn in context.get("history", [])[-max_turns:]:
        messages.append({"role": turn["role"], "content": turn["content"]})

    messages.append({
        "role": "user",
        "content": f'{ctx_str}Command: "{text}"',
    })

    response = ollama.chat(
        model=config.offline_intent_model,
        format="json",
        options={
            "temperature": getattr(config, "offline_intent_temperature", 0.1),
            "num_predict": getattr(config, "offline_intent_num_predict", 256),
            "num_ctx": 1024,
            "top_p": 0.9,
            "stop": ["\n\n", "```"],
        },
        messages=messages,
    )

    content = (response.get("message", {}) or {}).get("content", "") or ""
    if not content.strip():
        raise ValueError("Offline LLM returned empty content")

    payload = _repair_json(content)
    return _payload_to_result(payload)


# ---------------------------------------------------------------------------
# Rule-based fallback parser
# ---------------------------------------------------------------------------

_SEARCH_RE = re.compile(
    r"^(?:search|google|look\s*up|find)\s+(?:for\s+)?(.+?)"
    r"(?:\s+(?:on|using|in|with)\s+(\w+))?$",
    re.IGNORECASE,
)
_TYPE_RE = re.compile(r"^(?:type|write|enter)\s+(.+)$", re.IGNORECASE)
_OPEN_FILE_RE = re.compile(
    r"^open\s+(?:the\s+)?file\s+(.+)$|^open\s+(\S+\.\w{1,5})$", re.IGNORECASE
)
_OPEN_APP_RE = re.compile(r"^(?:open|launch|start|run)\s+(.+)$", re.IGNORECASE)
_SETTING_RE = re.compile(
    r"^(?:turn\s+(on|off)|enable|disable|toggle|set)\s+(?:the\s+)?"
    r"(wifi|wi-fi|bluetooth|display|brightness|sound|volume|battery)"
    r"(?:\s+to\s+(.+))?$",
    re.IGNORECASE,
)
_CLOSE_RE = re.compile(
    r"^(?:close|quit|exit|kill)\s+(?:the\s+)?(.+)$", re.IGNORECASE
)

_CONJUNCTION_RE = re.compile(
    r"\s*(?:,\s*)?(?:and\s+then|then|and)\s+", re.IGNORECASE
)

_PRONOUN_RE = re.compile(r"\b(it|that|this|the same|the same thing)\b", re.IGNORECASE)


def _resolve_pronouns(text: str, context: dict) -> str:
    if not _PRONOUN_RE.search(text):
        return text
    last_app = context.get("last_app")
    last_query = context.get("last_query")
    lower = text.lower()
    if "open" in lower and last_app:
        return _PRONOUN_RE.sub(last_app, text)
    if "search" in lower and last_query:
        return _PRONOUN_RE.sub(last_query, text)
    return text


def _parse_one(text: str, context: dict) -> ParsedResult:
    stripped = text.strip().rstrip(".!")

    m = _SEARCH_RE.match(stripped)
    if m:
        query = m.group(1).strip()
        app = (m.group(2) or config.default_browser).strip().lower()
        return ParsedResult(
            kind="action", function="web_search",
            args={"app": app, "query": query}, confidence=0.8,
            reasoning="matched search pattern",
        )

    m = _OPEN_FILE_RE.match(stripped)
    if m:
        path = (m.group(1) or m.group(2) or "").strip()
        return ParsedResult(
            kind="action", function="open_file",
            args={"path": path}, confidence=0.8,
            reasoning="matched open-file pattern",
        )

    m = _SETTING_RE.match(stripped)
    if m:
        on_off, key, explicit_value = m.groups()
        key = "wifi" if key in ("wifi", "wi-fi") else key
        if key == "brightness":
            key = "display"
        if key == "volume":
            key = "sound"
        value = explicit_value.strip() if explicit_value else (on_off or "toggle")
        return ParsedResult(
            kind="action", function="change_setting",
            args={"key": key, "value": value}, confidence=0.85,
            reasoning="matched setting pattern",
        )

    m = _TYPE_RE.match(stripped)
    if m:
        return ParsedResult(
            kind="action", function="type_text",
            args={"text": m.group(1).strip()}, confidence=0.85,
            reasoning="matched type pattern",
        )

    m = _CLOSE_RE.match(stripped)
    if m and "close_app" in ALLOWED_COMMANDS:
        return ParsedResult(
            kind="action", function="close_app",
            args={"name": m.group(1).strip().lower()}, confidence=0.75,
            reasoning="matched close pattern",
        )

    m = _OPEN_APP_RE.match(stripped)
    if m:
        return ParsedResult(
            kind="action", function="open_app",
            args={"name": m.group(1).strip().lower()}, confidence=0.8,
            reasoning="matched open pattern",
        )

    return ParsedResult(
        kind="action", function=_FALLBACK_FUNCTION,
        args={"name": stripped.lower()}, confidence=0.3,
        reasoning="no pattern matched; assumed app name",
    )


def _parse_offline(text: str, context: dict) -> ParsedResult:
    text = _resolve_pronouns(text, context)

    clauses = [c.strip() for c in _CONJUNCTION_RE.split(text) if c.strip()]
    if len(clauses) > 1:
        steps_results = [_parse_one(c, context) for c in clauses]
        if all(r.kind == "action" for r in steps_results):
            steps = [{"function": r.function, "args": r.args} for r in steps_results]
            return ParsedResult(
                kind="plan", steps=steps,
                confidence=min(r.confidence for r in steps_results),
                reasoning="split on conjunction",
            )

    return _parse_one(text, context)