"""Narrow interface between the voice pipeline and meeting platforms."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class JoinTarget:
    """Where the interview should happen."""

    kind: str  # "teams_pstn" | "local_audio" | "console"
    dial_number: str | None = None
    conference_id: str | None = None
    raw: str = ""

    def to_dict(self) -> dict:
        return {
            "kind": self.kind,
            "dial_number": self.dial_number,
            "conference_id": self.conference_id,
        }


class MeetingConnector(ABC):
    """Gets the agent's audio in and out of a meeting.

    Implementations create a Pipecat transport and perform any platform-side
    join choreography (for Teams: PSTN dial-out followed by DTMF conference-ID
    entry). The orchestrator and pipeline are connector-agnostic.
    """

    @abstractmethod
    async def create_transport(self):  # -> pipecat BaseTransport
        """Build the Pipecat transport this connector's audio flows through."""

    @abstractmethod
    async def connect(self) -> None:
        """Perform the platform join (dial-out, DTMF, ...). No-op locally."""

    @abstractmethod
    async def disconnect(self) -> None:
        """Leave the meeting and release platform resources."""
