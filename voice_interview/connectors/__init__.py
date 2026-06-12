"""Meeting connectors: thin adapters that get the agent into a conversation.

Adding a platform means adding one connector here — the orchestrator and voice
pipeline never change. Current support:

- ``teams_dialin``  — Microsoft Teams via Daily PSTN dial-out + DTMF.
- ``local_audio``   — local microphone/speaker (development).
- ``console_text``  — text console (development/tests; no audio stack at all).

Slack Huddles expose no third-party audio API or dial-in, so Slack is
documented as unsupported rather than faked. See docs/voice-interview.md.
"""
