import pytest

from voice_interview.connectors.invite_parser import InviteParseError, parse_join_target

INVITE_TEXT = """
Microsoft Teams meeting
Join on your computer, mobile app or room device
Click here to join the meeting
https://teams.microsoft.com/l/meetup-join/19%3ameeting_abc123%40thread.v2/0

Or call in (audio only)
+1 555-123-4567,,987654321#   United States, New York
Phone Conference ID: 987 654 321#
Find a local number | Reset PIN
"""


def test_parses_pasted_invite_text() -> None:
    target = parse_join_target(INVITE_TEXT)
    assert target.kind == "teams_pstn"
    assert target.dial_number == "+15551234567"
    assert target.conference_id == "987654321"


def test_parses_dial_string() -> None:
    target = parse_join_target("+15551234567,,123456789#")
    assert target.dial_number == "+15551234567"
    assert target.conference_id == "123456789"


def test_parses_dial_string_with_spaces() -> None:
    target = parse_join_target("+1 (555) 123-4567,, 123456789")
    assert target.dial_number == "+15551234567"
    assert target.conference_id == "123456789"


def test_explicit_flags_take_precedence() -> None:
    target = parse_join_target(
        "anything", dial_number="+44 20 7946 0958", conference_id="111 222 333"
    )
    assert target.dial_number == "+442079460958"
    assert target.conference_id == "111222333"


def test_bare_teams_url_rejected_with_guidance() -> None:
    with pytest.raises(InviteParseError, match="Dial in by phone"):
        parse_join_target("https://teams.microsoft.com/l/meetup-join/19%3ameeting_x/0")


def test_garbage_rejected() -> None:
    with pytest.raises(InviteParseError, match="dial-in number"):
        parse_join_target("let's meet tomorrow")


def test_conference_id_without_phone_rejected() -> None:
    with pytest.raises(InviteParseError):
        parse_join_target("Phone Conference ID: 123 456 789#")
