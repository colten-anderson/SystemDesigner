"""Configuration: every provider key, model, and join knob lives here.

Values come from the environment, optionally seeded from a ``.env`` file
(parsed with a tiny stdlib reader; ``python-dotenv`` is used instead when
installed). Nothing provider-specific is hardcoded elsewhere.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import os


def load_env_file(path: Path) -> dict[str, str]:
    """Minimal .env parser (KEY=VALUE lines, # comments, optional quotes)."""

    values: dict[str, str] = {}
    if not path.is_file():
        return values
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        value = value.strip().strip("'\"")
        values[key.strip()] = value
    return values


def apply_env_file(path: Path) -> None:
    try:  # Prefer python-dotenv when available (handles more edge cases).
        from dotenv import load_dotenv

        load_dotenv(path, override=False)
        return
    except ImportError:
        pass
    for key, value in load_env_file(path).items():
        os.environ.setdefault(key, value)


@dataclass
class InterviewConfig:
    # LLM (Anthropic). claude-opus-4-8 is the current recommended default;
    # set LLM_MODEL=claude-sonnet-4-6 for lower latency and ~40% lower cost.
    anthropic_api_key: str | None = None
    llm_model: str = "claude-opus-4-8"
    # Spoken turns are one or two sentences; capping output tokens bounds the
    # cost of any runaway turn without affecting normal operation.
    llm_max_tokens: int = 1024

    # Voice providers.
    deepgram_api_key: str | None = None
    cartesia_api_key: str | None = None
    cartesia_voice_id: str = "71a7ad14-091c-4e8e-a314-022ece01c121"  # Cartesia default

    # Daily (transport + PSTN dial-out for Teams).
    daily_api_key: str | None = None
    daily_api_url: str = "https://api.daily.co/v1"

    # Teams dial-out behavior.
    dtmf_initial_delay_s: float = 3.0  # wait for the Teams IVR greeting
    dtmf_confirm_delay_s: float = 3.0  # wait before the trailing '#'
    bot_name: str = "SystemDesigner Interviewer"

    extras: dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_env(cls, env_file: Path | None = None) -> "InterviewConfig":
        if env_file is not None:
            apply_env_file(env_file)
        else:
            apply_env_file(Path.cwd() / ".env")

        def _float(name: str, default: float) -> float:
            raw = os.environ.get(name)
            try:
                return float(raw) if raw else default
            except ValueError:
                return default

        def _int(name: str, default: int) -> int:
            raw = os.environ.get(name)
            try:
                return int(raw) if raw else default
            except ValueError:
                return default

        return cls(
            anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY"),
            llm_model=os.environ.get("LLM_MODEL", cls.llm_model),
            llm_max_tokens=_int("LLM_MAX_TOKENS", cls.llm_max_tokens),
            deepgram_api_key=os.environ.get("DEEPGRAM_API_KEY"),
            cartesia_api_key=os.environ.get("CARTESIA_API_KEY"),
            cartesia_voice_id=os.environ.get("CARTESIA_VOICE_ID", cls.cartesia_voice_id),
            daily_api_key=os.environ.get("DAILY_API_KEY"),
            daily_api_url=os.environ.get("DAILY_API_URL", cls.daily_api_url),
            dtmf_initial_delay_s=_float("DTMF_INITIAL_DELAY_S", cls.dtmf_initial_delay_s),
            dtmf_confirm_delay_s=_float("DTMF_CONFIRM_DELAY_S", cls.dtmf_confirm_delay_s),
            bot_name=os.environ.get("INTERVIEW_BOT_NAME", cls.bot_name),
        )

    def snapshot(self) -> dict:
        """Non-secret view stored in the interview state for provenance."""

        return {
            "llm_model": self.llm_model,
            "stt": "deepgram",
            "tts": "cartesia",
            "transport": "daily",
        }

    def missing_for_voice(self) -> list[str]:
        required = {
            "ANTHROPIC_API_KEY": self.anthropic_api_key,
            "DEEPGRAM_API_KEY": self.deepgram_api_key,
            "CARTESIA_API_KEY": self.cartesia_api_key,
            "DAILY_API_KEY": self.daily_api_key,
        }
        return [name for name, value in required.items() if not value]

    def missing_for_local_audio(self) -> list[str]:
        # Local mic/speaker needs the voice providers but no Daily telephony.
        return [name for name in self.missing_for_voice() if name != "DAILY_API_KEY"]

    def missing_for_text(self) -> list[str]:
        return [] if self.anthropic_api_key else ["ANTHROPIC_API_KEY"]
