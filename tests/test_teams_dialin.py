import asyncio

import pytest

from voice_interview.config import InterviewConfig
from voice_interview.connectors.base import JoinTarget
from voice_interview.connectors.teams_dialin import TeamsDialInConnector


def make_config() -> InterviewConfig:
    return InterviewConfig(
        daily_api_key="dk",
        dtmf_initial_delay_s=0.0,
        dtmf_confirm_delay_s=0.0,
    )


def make_target() -> JoinTarget:
    return JoinTarget(kind="teams_pstn", dial_number="+15551234567", conference_id="987654321")


class FakePoster:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    async def __call__(self, url, headers, payload):
        self.calls.append({"url": url, "headers": headers, "payload": payload})
        return self.responses.pop(0)


class StubTransport:
    def __init__(self):
        self.dialouts = []
        self.dtmf = []

    async def start_dialout(self, settings):
        self.dialouts.append(settings)

    async def send_dtmf(self, settings):
        self.dtmf.append(settings)


def test_requires_pstn_target() -> None:
    with pytest.raises(ValueError):
        TeamsDialInConnector(make_config(), JoinTarget(kind="console"))


def test_create_room_requests_dialout_and_owner_token() -> None:
    poster = FakePoster(
        [
            (200, {"url": "https://x.daily.co/room1", "name": "room1"}),
            (200, {"token": "tok-1"}),
        ]
    )
    connector = TeamsDialInConnector(make_config(), make_target(), http_post=poster)
    asyncio.run(connector._create_room())

    rooms_call, token_call = poster.calls
    assert rooms_call["url"].endswith("/rooms")
    assert rooms_call["headers"]["Authorization"] == "Bearer dk"
    assert rooms_call["payload"]["properties"]["enable_dialout"] is True
    assert rooms_call["payload"]["properties"]["exp"] > 0

    assert token_call["url"].endswith("/meeting-tokens")
    assert token_call["payload"]["properties"] == {"room_name": "room1", "is_owner": True}

    assert connector._room_url == "https://x.daily.co/room1"
    assert connector._token == "tok-1"


def test_daily_api_error_is_actionable() -> None:
    poster = FakePoster([(403, {"error": "dialout not enabled"})])
    connector = TeamsDialInConnector(make_config(), make_target(), http_post=poster)
    with pytest.raises(RuntimeError, match="PSTN dial-out"):
        asyncio.run(connector._create_room())


def test_joined_starts_dialout_to_target_number() -> None:
    connector = TeamsDialInConnector(make_config(), make_target())
    transport = StubTransport()
    asyncio.run(connector.handle_joined(transport, {}))
    assert transport.dialouts == [{"phoneNumber": "+15551234567"}]


def test_answer_sends_conference_id_then_confirm_hash() -> None:
    connector = TeamsDialInConnector(make_config(), make_target())
    transport = StubTransport()
    asyncio.run(connector.handle_dialout_answered(transport, {"sessionId": "sess-1"}))

    assert transport.dtmf == [
        {"sessionId": "sess-1", "tones": "987654321#"},
        {"sessionId": "sess-1", "tones": "#"},
    ]

    # A duplicate answer event must not re-send the conference ID.
    asyncio.run(connector.handle_dialout_answered(transport, {"sessionId": "sess-1"}))
    assert len(transport.dtmf) == 2


def test_dialout_loss_notifies_pipeline() -> None:
    connector = TeamsDialInConnector(make_config(), make_target())
    seen = []

    async def on_call_ended(reason):
        seen.append(reason)

    connector.on_call_ended = on_call_ended
    asyncio.run(connector.handle_dialout_lost("dialout-error", {"detail": "x"}))
    assert seen == ["dialout-error"]
