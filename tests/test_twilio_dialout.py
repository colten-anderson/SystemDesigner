import asyncio
import json

import pytest

from voice_interview.config import InterviewConfig
from voice_interview.connectors.base import JoinTarget
from voice_interview.connectors.twilio_dialout import (
    TwilioDialOutConnector,
    TwilioSetupError,
    build_call_request,
    parse_stream_start,
    send_digits_sequence,
    stream_twiml,
)


def make_config(**overrides) -> InterviewConfig:
    defaults = dict(
        telephony_provider="twilio",
        twilio_account_sid="AC123",
        twilio_auth_token="tok",
        twilio_from_number="+19995550000",
        public_url="https://abc.ngrok.app",
        dtmf_initial_delay_s=2.0,
        dtmf_confirm_delay_s=1.0,
    )
    defaults.update(overrides)
    return InterviewConfig(**defaults)


def make_target() -> JoinTarget:
    return JoinTarget(kind="teams_pstn", dial_number="+15551234567", conference_id="987654321")


def test_send_digits_translates_delays_to_pauses() -> None:
    digits = send_digits_sequence(make_config(), "12345")
    # 2.0s initial -> 4 w's; 1.0s confirm -> 2 w's; then trailing '#'.
    assert digits == "wwww12345#ww#"


def test_send_digits_empty_without_conference_id() -> None:
    assert send_digits_sequence(make_config(), None) == ""
    assert send_digits_sequence(make_config(), "") == ""


def test_stream_twiml_converts_scheme_and_appends_ws_path() -> None:
    assert 'url="wss://abc.ngrok.app/ws"' in stream_twiml("https://abc.ngrok.app")
    assert 'url="ws://local.test/ws"' in stream_twiml("http://local.test/")
    # Bare host defaults to wss.
    assert 'url="wss://abc.ngrok.app/ws"' in stream_twiml("abc.ngrok.app")
    assert stream_twiml("https://x.io").startswith("<Response><Connect><Stream")


def test_build_call_request_payload() -> None:
    url, payload = build_call_request(make_config(), make_target())
    assert url == "https://api.twilio.com/2010-04-01/Accounts/AC123/Calls.json"
    assert payload["To"] == "+15551234567"
    assert payload["From"] == "+19995550000"
    assert payload["SendDigits"] == "wwww987654321#ww#"
    assert "wss://abc.ngrok.app/ws" in payload["Twiml"]


def test_build_call_request_requires_public_url() -> None:
    with pytest.raises(TwilioSetupError, match="PUBLIC_URL"):
        build_call_request(make_config(public_url=None), make_target())


def test_build_call_request_requires_credentials_and_number() -> None:
    with pytest.raises(TwilioSetupError, match="TWILIO_ACCOUNT_SID"):
        build_call_request(make_config(twilio_account_sid=None), make_target())
    with pytest.raises(TwilioSetupError, match="TWILIO_FROM_NUMBER"):
        build_call_request(make_config(twilio_from_number=None), make_target())


def test_parse_stream_start_extracts_sids() -> None:
    messages = [
        json.dumps({"event": "connected", "protocol": "Call"}),
        json.dumps(
            {"event": "start", "start": {"streamSid": "MZ1", "callSid": "CA9"}}
        ),
    ]
    assert parse_stream_start(messages) == ("MZ1", "CA9")


def test_parse_stream_start_rejects_missing_start() -> None:
    with pytest.raises(TwilioSetupError, match="PUBLIC_URL is reachable"):
        parse_stream_start([json.dumps({"event": "connected"}), "not-json"])


def test_place_call_posts_with_basic_auth_and_returns_sid() -> None:
    calls = []

    async def fake_post(url, auth, payload):
        calls.append({"url": url, "auth": auth, "payload": payload})
        return 201, {"sid": "CA42"}

    connector = TwilioDialOutConnector(make_config(), make_target(), http_post_form=fake_post)
    sid = asyncio.run(connector.place_call())
    assert sid == "CA42"
    assert connector.call_sid == "CA42"
    assert calls[0]["auth"] == ("AC123", "tok")
    assert calls[0]["payload"]["To"] == "+15551234567"


def test_place_call_error_is_actionable() -> None:
    async def fake_post(url, auth, payload):
        return 400, {"message": "geo permissions not enabled"}

    connector = TwilioDialOutConnector(make_config(), make_target(), http_post_form=fake_post)
    with pytest.raises(TwilioSetupError, match="geo permissions"):
        asyncio.run(connector.place_call())


def test_connector_requires_pstn_target() -> None:
    with pytest.raises(ValueError):
        TwilioDialOutConnector(make_config(), JoinTarget(kind="console"))
