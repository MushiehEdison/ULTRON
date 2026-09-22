"""
config.py
---------
Single place every other module pulls settings from. Nothing here is
hard-coded into the codebase that shouldn't be -- secrets come from the
environment (optionally via a local .env file) and never from source.

Usage:
    from app.utils.config import config
    config.anthropic_api_key
    config.stt_model_size

Create a `.env` file at the repo root (already in .gitignore) to override
any of these, e.g.:

    ANTHROPIC_API_KEY=sk-ant-...
    ULTRON_INTENT_MODEL=claude-haiku-4-5-20251001
    ULTRON_STT_MODEL_SIZE=small
"""

import os
from dataclasses import dataclass, field

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    # python-dotenv is optional -- env vars set another way still work.
    pass


def _env_str(key: str, default: str) -> str:
    val = os.environ.get(key)
    return val if val not in (None, "") else default


def _env_int(key: str, default: int) -> int:
    val = os.environ.get(key)
    try:
        return int(val) if val not in (None, "") else default
    except ValueError:
        return default


def _env_float(key: str, default: float) -> float:
    val = os.environ.get(key)
    try:
        return float(val) if val not in (None, "") else default
    except ValueError:
        return default


def _env_bool(key: str, default: bool) -> bool:
    val = os.environ.get(key)
    if val is None or val == "":
        return default
    return val.strip().lower() in ("1", "true", "yes", "on")


@dataclass(frozen=True)
class Config:
    # ---- Intent parsing (LLM) --------------------------------------------
    anthropic_api_key: str = field(default_factory=lambda: os.environ.get("ANTHROPIC_API_KEY", ""))
    intent_model: str = field(default_factory=lambda: _env_str("ULTRON_INTENT_MODEL", "claude-haiku-4-5-20251001"))
    intent_max_tokens: int = field(default_factory=lambda: _env_int("ULTRON_INTENT_MAX_TOKENS", 300))
    intent_timeout_seconds: float = field(default_factory=lambda: _env_float("ULTRON_INTENT_TIMEOUT", 8.0))

    # ---- Speech-to-text ----------------------------------------------------
    stt_model_size: str = field(default_factory=lambda: _env_str("ULTRON_STT_MODEL_SIZE", "base"))
    stt_device: str = field(default_factory=lambda: _env_str("ULTRON_STT_DEVICE", "cpu"))
    stt_compute_type: str = field(default_factory=lambda: _env_str("ULTRON_STT_COMPUTE_TYPE", "int8"))
    stt_language: str = field(default_factory=lambda: _env_str("ULTRON_STT_LANGUAGE", "en"))
    sample_rate: int = field(default_factory=lambda: _env_int("ULTRON_SAMPLE_RATE", 16000))

    # Voice-activity detection (simple energy-based silence trimming)
    vad_silence_rms: float = field(default_factory=lambda: _env_float("ULTRON_VAD_SILENCE_RMS", 0.010))
    vad_silence_duration: float = field(default_factory=lambda: _env_float("ULTRON_VAD_SILENCE_DURATION", 0.9))
    vad_max_phrase_seconds: float = field(default_factory=lambda: _env_float("ULTRON_VAD_MAX_PHRASE", 12.0))
    vad_min_phrase_seconds: float = field(default_factory=lambda: _env_float("ULTRON_VAD_MIN_PHRASE", 0.35))

    # ---- Automation defaults ------------------------------------------------
    default_browser: str = field(default_factory=lambda: _env_str("ULTRON_DEFAULT_BROWSER", "chrome"))

    # ---- Misc ---------------------------------------------------------------
    log_level: str = field(default_factory=lambda: _env_str("ULTRON_LOG_LEVEL", "INFO"))

    def has_llm(self) -> bool:
        """Whether a real Anthropic API key is configured. When False,
        app/intent/parser.py falls back to its offline rule-based parser
        instead of failing the whole pipeline."""
        return bool(self.anthropic_api_key)


config = Config()
