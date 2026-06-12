"""Parse a Teams meeting invite (or a plain dial string) into a JoinTarget.

A bare ``https://teams.microsoft.com/l/meetup-join/...`` link does NOT contain
the dial-in number — that lives in the invite's "Dial in by phone" block (and
requires the tenant's Audio Conferencing license). We therefore accept pasted
invite text or an explicit dial string, and reject bare URLs with guidance.
"""

from __future__ import annotations

import re

from .base import JoinTarget

# +1 555-123-4567 / +44 20 7946 0958 / (555) 123-4567 — at least 7 digits.
_PHONE_REGEX = re.compile(r"(\+?\d[\d\s().-]{6,}\d)")
# "Phone Conference ID: 123 456 789#" and similar invite phrasings.
_CONFERENCE_ID_REGEX = re.compile(
    r"(?:phone\s+)?conference\s+id[:\s]+([\d\s]{4,})#?", re.IGNORECASE
)
# Dial-string form: "+15551234567,,123456789#" (commas = pause, like a phone).
_DIAL_STRING_REGEX = re.compile(r"^\s*(\+?\d[\d().\s-]*\d)\s*,,?\s*(\d{4,})#?\s*$")

_TEAMS_URL_REGEX = re.compile(r"https://teams\.(?:microsoft|live)\.com/\S+", re.IGNORECASE)


class InviteParseError(ValueError):
    pass


def _normalize_phone(raw: str) -> str:
    digits = re.sub(r"[^\d+]", "", raw)
    if not digits.startswith("+") and len(digits) >= 10:
        digits = "+" + digits
    return digits


def _normalize_conference_id(raw: str) -> str:
    return re.sub(r"\D", "", raw)


def parse_join_target(
    raw: str,
    *,
    dial_number: str | None = None,
    conference_id: str | None = None,
) -> JoinTarget:
    """Build a Teams PSTN join target from invite text / dial string / flags."""

    raw = (raw or "").strip()

    if dial_number and conference_id:
        return JoinTarget(
            kind="teams_pstn",
            dial_number=_normalize_phone(dial_number),
            conference_id=_normalize_conference_id(conference_id),
            raw=raw,
        )

    dial_match = _DIAL_STRING_REGEX.match(raw)
    if dial_match:
        return JoinTarget(
            kind="teams_pstn",
            dial_number=_normalize_phone(dial_match.group(1)),
            conference_id=_normalize_conference_id(dial_match.group(2)),
            raw=raw,
        )

    conference_match = _CONFERENCE_ID_REGEX.search(raw)
    if conference_match:
        # Search for the phone number outside any URLs and outside the
        # conference-ID text itself (its digits would match the phone regex).
        without_urls = _TEAMS_URL_REGEX.sub(" ", raw)
        without_conference = _CONFERENCE_ID_REGEX.sub(" ", without_urls)
        phone_match = _PHONE_REGEX.search(without_conference)
        if phone_match:
            return JoinTarget(
                kind="teams_pstn",
                dial_number=_normalize_phone(dial_number or phone_match.group(1)),
                conference_id=_normalize_conference_id(conference_match.group(1)),
                raw=raw,
            )

    if _TEAMS_URL_REGEX.search(raw):
        raise InviteParseError(
            "A bare Teams meeting link does not contain the dial-in number. "
            "Paste the invite's 'Dial in by phone' block (number + conference "
            "ID), or pass --dial-number and --conference-id explicitly. The "
            "meeting organizer's tenant needs Audio Conferencing enabled for a "
            "dial-in number to exist."
        )

    raise InviteParseError(
        "Could not find a dial-in number and conference ID. Provide either the "
        "pasted Teams invite text, a dial string like '+15551234567,,123456789#', "
        "or --dial-number and --conference-id flags."
    )
