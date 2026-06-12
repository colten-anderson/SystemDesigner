"""Microsoft Teams connector: Daily room + PSTN dial-out + DTMF conference ID.

Join choreography:

1. Create a short-lived Daily room with dial-out enabled (Daily REST API).
2. Mint an owner meeting token (dial-out requires owner privileges).
3. The bot joins the room through Pipecat's DailyTransport.
4. On join, dial out to the Teams meeting's PSTN dial-in number.
5. When the call is answered, wait for the Teams IVR greeting, then send the
   conference ID as DTMF tones followed by '#', and a trailing '#' for the
   "record your name or press #" prompt on tenants that ask for it.

Requirements (documented in docs/voice-interview.md): a Daily account with
PSTN dial-out enabled and a purchased phone number, and a Teams meeting whose
organizer has Audio Conferencing (so the invite carries a dial-in number).
The organizer must admit the caller from the lobby unless callers bypass it.
"""

from __future__ import annotations

import asyncio

from ..config import InterviewConfig
from .base import JoinTarget, MeetingConnector

ROOM_EXPIRY_S = 2 * 60 * 60  # rooms self-destruct after two hours


class TeamsDialInConnector(MeetingConnector):
    def __init__(self, config: InterviewConfig, target: JoinTarget, *, http_post=None):
        if target.kind != "teams_pstn" or not target.dial_number:
            raise ValueError("TeamsDialInConnector needs a teams_pstn JoinTarget with a dial number")
        self.config = config
        self.target = target
        self.transport = None
        # Injectable for tests: async (url, headers, payload) -> (status, body).
        self._http_post = http_post or self._aiohttp_post
        self._room_url: str | None = None
        self._room_name: str | None = None
        self._token: str | None = None
        self._dialout_session_id: str | None = None
        self._dtmf_sent = False
        self.on_call_ended = None  # set by the pipeline; called on dial-out loss

    # -- Daily REST helpers ---------------------------------------------

    @staticmethod
    async def _aiohttp_post(url: str, headers: dict, payload: dict) -> tuple[int, dict]:
        import aiohttp

        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=payload) as response:
                return response.status, await response.json()

    async def _daily_post(self, path: str, payload: dict) -> dict:
        headers = {"Authorization": f"Bearer {self.config.daily_api_key}"}
        status, body = await self._http_post(
            f"{self.config.daily_api_url}{path}", headers, payload
        )
        if status >= 400:
            raise RuntimeError(
                f"Daily API {path} failed ({status}): {body}. "
                "PSTN dial-out must be enabled on your Daily domain and a "
                "phone number purchased — see docs/voice-interview.md."
            )
        return body

    async def _create_room(self) -> None:
        import time

        room = await self._daily_post(
            "/rooms",
            {
                "properties": {
                    "enable_dialout": True,
                    "exp": int(time.time()) + ROOM_EXPIRY_S,
                }
            },
        )
        self._room_url = room["url"]
        self._room_name = room["name"]
        token = await self._daily_post(
            "/meeting-tokens",
            {"properties": {"room_name": self._room_name, "is_owner": True}},
        )
        self._token = token["token"]

    # -- MeetingConnector ------------------------------------------------

    async def create_transport(self):
        try:
            from pipecat.transports.daily.transport import DailyParams, DailyTransport
        except ImportError:  # older pipecat layout
            from pipecat.transports.services.daily import DailyParams, DailyTransport
        from pipecat.audio.vad.silero import SileroVADAnalyzer

        await self._create_room()

        self.transport = DailyTransport(
            self._room_url,
            self._token,
            self.config.bot_name,
            DailyParams(
                audio_in_enabled=True,
                audio_out_enabled=True,
                vad_analyzer=SileroVADAnalyzer(),
            ),
        )
        self._register_dialout_handlers()
        return self.transport

    def _register_dialout_handlers(self) -> None:
        transport = self.transport

        @transport.event_handler("on_joined")
        async def on_joined(transport, data):
            await self.handle_joined(transport, data)

        @transport.event_handler("on_dialout_answered")
        async def on_dialout_answered(transport, data):
            await self.handle_dialout_answered(transport, data)

        @transport.event_handler("on_dialout_error")
        async def on_dialout_error(transport, data):
            await self.handle_dialout_lost("dialout-error", data)

        @transport.event_handler("on_dialout_stopped")
        async def on_dialout_stopped(transport, data):
            await self.handle_dialout_lost("dialout-stopped", data)

    # The handlers below hold the join choreography; they take the transport
    # as a parameter so tests can drive them with a stub.

    async def handle_joined(self, transport, data) -> None:
        print(f"[teams] joined Daily room, dialing {self.target.dial_number} ...")
        await transport.start_dialout({"phoneNumber": self.target.dial_number})

    async def handle_dialout_answered(self, transport, data) -> None:
        self._dialout_session_id = data.get("sessionId")
        print("[teams] call answered; entering conference ID via DTMF ...")
        if self.target.conference_id and not self._dtmf_sent:
            self._dtmf_sent = True
            await asyncio.sleep(self.config.dtmf_initial_delay_s)
            await transport.send_dtmf(
                {
                    "sessionId": self._dialout_session_id,
                    "tones": f"{self.target.conference_id}#",
                }
            )
            # Tenants that prompt unauthenticated callers to record a name
            # accept '#' to continue.
            await asyncio.sleep(self.config.dtmf_confirm_delay_s)
            await transport.send_dtmf(
                {"sessionId": self._dialout_session_id, "tones": "#"}
            )
            print(
                "[teams] conference ID sent. If the meeting has a lobby, "
                "ask the organizer to admit the caller."
            )

    async def handle_dialout_lost(self, reason: str, data) -> None:
        print(f"[teams] {reason}: {data}")
        if self.on_call_ended:
            await self.on_call_ended(reason)

    async def connect(self) -> None:
        # Dial-out is driven by the on_joined event once the pipeline runs.
        return None

    async def disconnect(self) -> None:
        if self.transport is not None:
            try:
                await self.transport.stop_dialout(self._dialout_session_id)
            except Exception:
                pass
