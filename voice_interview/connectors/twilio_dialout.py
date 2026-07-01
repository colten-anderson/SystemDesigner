"""Microsoft Teams connector via Twilio PSTN dial-out (self-serve alternative
to Daily).

Twilio is fully self-serve: buy a phone number with a credit card and place
outbound calls immediately — no account-gated feature to have enabled. The
trade-off is that Twilio delivers call audio by connecting a **Media Streams
websocket back to you**, so this connector runs a small in-process websocket
server and needs a publicly reachable URL (e.g. an ngrok tunnel) — see
docs/voice-interview.md for the two-line setup.

Join choreography:

1. Start an in-process FastAPI websocket server on ``TWILIO_WS_PORT``.
2. Create the outbound call via the Twilio REST API:
   - ``SendDigits`` types the Teams conference ID (with ``w`` = 0.5s pauses
     replacing the Daily connector's sleep-based DTMF timing), then ``#``,
     then a trailing ``#`` for tenants that prompt callers to record a name.
   - Inline TwiML ``<Connect><Stream>`` points the call's audio at our
     public websocket URL.
3. Twilio answers the media websocket with ``connected`` + ``start`` events;
   the ``start`` event carries the stream/call SIDs the frame serializer
   needs. The interview pipeline is then built on that transport.
4. When the pipeline ends (end_interview or pause), the serializer hangs up
   the call; a caller-side hang-up ends the pipeline and pauses the session.
"""

from __future__ import annotations

import json
from xml.sax.saxutils import quoteattr

from ..config import InterviewConfig
from .base import JoinTarget

TWILIO_API_BASE = "https://api.twilio.com/2010-04-01"


class TwilioSetupError(RuntimeError):
    pass


def send_digits_sequence(config: InterviewConfig, conference_id: str | None) -> str:
    """Twilio SendDigits string: 'w' is a 0.5s pause, so the configured IVR
    delays translate directly instead of needing media-path DTMF."""

    if not conference_id:
        return ""
    initial = "w" * max(1, round(config.dtmf_initial_delay_s * 2))
    confirm = "w" * max(1, round(config.dtmf_confirm_delay_s * 2))
    return f"{initial}{conference_id}#{confirm}#"


def stream_twiml(public_url: str) -> str:
    """Inline TwiML connecting the call's audio to our websocket endpoint."""

    ws_url = public_url.rstrip("/")
    for prefix, replacement in (("https://", "wss://"), ("http://", "ws://")):
        if ws_url.startswith(prefix):
            ws_url = replacement + ws_url[len(prefix) :]
            break
    if not ws_url.startswith(("ws://", "wss://")):
        ws_url = "wss://" + ws_url
    return (
        "<Response><Connect>"
        f"<Stream url={quoteattr(ws_url + '/ws')} />"
        "</Connect></Response>"
    )


def build_call_request(config: InterviewConfig, target: JoinTarget) -> tuple[str, dict]:
    """(url, form-encoded payload) for the Twilio create-call REST request."""

    if not config.twilio_account_sid or not config.twilio_auth_token:
        raise TwilioSetupError("TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN are required")
    if not config.twilio_from_number:
        raise TwilioSetupError(
            "TWILIO_FROM_NUMBER is required (a phone number purchased in your "
            "Twilio console)"
        )
    if not config.public_url:
        raise TwilioSetupError(
            "PUBLIC_URL is required for the Twilio provider: Twilio streams the "
            "call audio to a websocket it must be able to reach. Run e.g. "
            "`ngrok http 8765` and pass the https URL via --public-url or "
            "PUBLIC_URL. See docs/voice-interview.md."
        )
    url = f"{TWILIO_API_BASE}/Accounts/{config.twilio_account_sid}/Calls.json"
    payload = {
        "To": target.dial_number,
        "From": config.twilio_from_number,
        "Twiml": stream_twiml(config.public_url),
    }
    digits = send_digits_sequence(config, target.conference_id)
    if digits:
        payload["SendDigits"] = digits
    return url, payload


def parse_stream_start(messages: list[str]) -> tuple[str, str | None]:
    """Extract (stream_sid, call_sid) from the first Media Streams messages.

    Twilio sends a ``connected`` event followed by a ``start`` event; the
    order-tolerant scan below only requires that a ``start`` event is present.
    """

    for raw in messages:
        try:
            data = json.loads(raw)
        except (TypeError, json.JSONDecodeError):
            continue
        if data.get("event") == "start":
            start = data.get("start", {})
            stream_sid = start.get("streamSid")
            if stream_sid:
                return stream_sid, start.get("callSid")
    raise TwilioSetupError(
        "Twilio websocket did not deliver a 'start' event; the media stream "
        "never attached (check that PUBLIC_URL is reachable from the internet)."
    )


class TwilioDialOutConnector:
    """Server-driven connector: owns the REST dial-out and the websocket
    handshake; the pipeline layer supplies a callback that builds and runs the
    interview once a transport exists."""

    def __init__(self, config: InterviewConfig, target: JoinTarget, *, http_post_form=None):
        if target.kind != "teams_pstn" or not target.dial_number:
            raise ValueError("TwilioDialOutConnector needs a teams_pstn JoinTarget")
        self.config = config
        self.target = target
        self._http_post_form = http_post_form or self._aiohttp_post_form
        self.call_sid: str | None = None

    @staticmethod
    async def _aiohttp_post_form(url, auth, payload) -> tuple[int, dict]:
        import aiohttp

        basic = aiohttp.BasicAuth(auth[0], auth[1])
        async with aiohttp.ClientSession() as session:
            async with session.post(url, auth=basic, data=payload) as response:
                try:
                    body = await response.json()
                except Exception:
                    body = {}
                return response.status, body

    async def place_call(self) -> str:
        """Create the outbound call; returns the Twilio call SID."""

        url, payload = build_call_request(self.config, self.target)
        status, body = await self._http_post_form(
            url,
            (self.config.twilio_account_sid, self.config.twilio_auth_token),
            payload,
        )
        if status >= 400:
            raise TwilioSetupError(
                f"Twilio create-call failed ({status}): "
                f"{body.get('message', body)}. Check the from-number, account "
                "credentials, and that the destination number is dialable from "
                "your Twilio account (geo permissions)."
            )
        self.call_sid = body.get("sid")
        print(
            f"[twilio] dialing {self.target.dial_number} from "
            f"{self.config.twilio_from_number} (call {self.call_sid}); conference "
            "ID will be entered automatically."
        )
        return self.call_sid or ""

    async def serve(self, run_with_transport) -> None:
        """Start the websocket server, place the call, and hand the connected
        transport to ``run_with_transport(transport)``. Returns when the
        interview pipeline finishes."""

        import asyncio

        import uvicorn
        from fastapi import FastAPI, WebSocket

        from pipecat.audio.vad.silero import SileroVADAnalyzer
        from pipecat.serializers.twilio import TwilioFrameSerializer
        from pipecat.transports.websocket.fastapi import (
            FastAPIWebsocketParams,
            FastAPIWebsocketTransport,
        )

        app = FastAPI()
        done = asyncio.Event()

        @app.websocket("/ws")
        async def websocket_endpoint(websocket: WebSocket):
            await websocket.accept()
            iterator = websocket.iter_text()
            first = await iterator.__anext__()
            second = await iterator.__anext__()
            stream_sid, call_sid = parse_stream_start([first, second])
            print("[twilio] media stream attached; joining the meeting audio")

            serializer = TwilioFrameSerializer(
                stream_sid=stream_sid,
                call_sid=call_sid or self.call_sid,
                # With credentials, the serializer hangs the call up when the
                # pipeline ends.
                account_sid=self.config.twilio_account_sid,
                auth_token=self.config.twilio_auth_token,
            )
            transport = FastAPIWebsocketTransport(
                websocket=websocket,
                params=FastAPIWebsocketParams(
                    audio_in_enabled=True,
                    audio_out_enabled=True,
                    add_wav_header=False,
                    vad_analyzer=SileroVADAnalyzer(),
                    serializer=serializer,
                ),
            )
            try:
                await run_with_transport(transport)
            finally:
                done.set()

        server = uvicorn.Server(
            uvicorn.Config(
                app,
                host="0.0.0.0",
                port=self.config.twilio_ws_port,
                log_level="warning",
            )
        )
        server_task = asyncio.create_task(server.serve())
        try:
            await asyncio.sleep(0.5)  # let the socket bind before Twilio calls in
            await self.place_call()
            await done.wait()
        finally:
            server.should_exit = True
            await server_task
