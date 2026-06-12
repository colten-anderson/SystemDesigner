"""Local microphone/speaker connector for development without telephony."""

from __future__ import annotations

from ..config import InterviewConfig
from .base import MeetingConnector


class LocalAudioConnector(MeetingConnector):
    def __init__(self, config: InterviewConfig):
        self.config = config
        self.transport = None

    async def create_transport(self):
        from pipecat.audio.vad.silero import SileroVADAnalyzer

        try:
            from pipecat.transports.local.audio import (
                LocalAudioTransport,
                LocalAudioTransportParams,
            )
        except ImportError:  # older pipecat layout
            from pipecat.transports.base_transport import TransportParams

            from pipecat.transports.local.audio import LocalAudioTransport

            LocalAudioTransportParams = TransportParams

        self.transport = LocalAudioTransport(
            LocalAudioTransportParams(
                audio_in_enabled=True,
                audio_out_enabled=True,
                vad_analyzer=SileroVADAnalyzer(),
            )
        )
        return self.transport

    async def connect(self) -> None:
        return None

    async def disconnect(self) -> None:
        return None
