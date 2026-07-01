from pathlib import Path

from voice_interview.config import InterviewConfig, load_env_file


def test_load_env_file_parses_values_comments_and_quotes(tmp_path: Path) -> None:
    env = tmp_path / ".env"
    env.write_text(
        "# comment\n"
        "PLAIN=value\n"
        'QUOTED="with spaces"\n'
        "SINGLE='single'\n"
        "EMPTY=\n"
        "NOEQUALS\n"
        "  SPACED = padded \n",
        encoding="utf-8",
    )
    values = load_env_file(env)
    assert values["PLAIN"] == "value"
    assert values["QUOTED"] == "with spaces"
    assert values["SINGLE"] == "single"
    assert values["EMPTY"] == ""
    assert "NOEQUALS" not in values
    assert values["SPACED"] == "padded"


def test_load_env_file_missing_returns_empty(tmp_path: Path) -> None:
    assert load_env_file(tmp_path / "nope.env") == {}


def test_from_env_reads_keys_and_floats(tmp_path: Path, monkeypatch) -> None:
    for key in [
        "ANTHROPIC_API_KEY", "DEEPGRAM_API_KEY", "CARTESIA_API_KEY",
        "DAILY_API_KEY", "LLM_MODEL", "DTMF_INITIAL_DELAY_S",
    ]:
        monkeypatch.delenv(key, raising=False)
    env = tmp_path / ".env"
    env.write_text(
        "ANTHROPIC_API_KEY=ak\nDEEPGRAM_API_KEY=dk\nLLM_MODEL=claude-sonnet-4-6\n"
        "DTMF_INITIAL_DELAY_S=5.5\n",
        encoding="utf-8",
    )
    config = InterviewConfig.from_env(env)
    assert config.anthropic_api_key == "ak"
    assert config.deepgram_api_key == "dk"
    assert config.llm_model == "claude-sonnet-4-6"
    assert config.dtmf_initial_delay_s == 5.5


def test_env_vars_take_precedence_over_env_file(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "from-env")
    env = tmp_path / ".env"
    env.write_text("ANTHROPIC_API_KEY=from-file\n", encoding="utf-8")
    config = InterviewConfig.from_env(env)
    assert config.anthropic_api_key == "from-env"


def test_invalid_float_falls_back_to_default(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("DTMF_INITIAL_DELAY_S", "not-a-number")
    config = InterviewConfig.from_env(tmp_path / "absent.env")
    assert config.dtmf_initial_delay_s == InterviewConfig.dtmf_initial_delay_s


def test_missing_key_reports() -> None:
    config = InterviewConfig(anthropic_api_key="x", deepgram_api_key="y")
    missing_voice = config.missing_for_voice()
    assert "CARTESIA_API_KEY" in missing_voice
    assert "DAILY_API_KEY" in missing_voice
    assert "ANTHROPIC_API_KEY" not in missing_voice
    # Local audio doesn't need Daily telephony.
    assert "DAILY_API_KEY" not in config.missing_for_local_audio()
    assert "CARTESIA_API_KEY" in config.missing_for_local_audio()
    assert config.missing_for_text() == []
    assert InterviewConfig().missing_for_text() == ["ANTHROPIC_API_KEY"]


def test_missing_keys_for_twilio_provider() -> None:
    config = InterviewConfig(
        telephony_provider="twilio",
        anthropic_api_key="a",
        deepgram_api_key="d",
        cartesia_api_key="c",
        twilio_account_sid="AC1",
    )
    missing = config.missing_for_voice()
    assert "DAILY_API_KEY" not in missing
    assert "TWILIO_AUTH_TOKEN" in missing
    assert "TWILIO_FROM_NUMBER" in missing
    assert "PUBLIC_URL" in missing
    # Local audio needs no telephony keys regardless of provider.
    assert config.missing_for_local_audio() == []


def test_snapshot_contains_no_secrets() -> None:
    config = InterviewConfig(anthropic_api_key="sk-secret", daily_api_key="dk-secret")
    snapshot = config.snapshot()
    assert "sk-secret" not in str(snapshot)
    assert "dk-secret" not in str(snapshot)
    assert snapshot["llm_model"] == config.llm_model
