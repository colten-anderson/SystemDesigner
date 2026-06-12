# Voice Interview Guide

The voice interviewer joins a live meeting, **leads** the full SystemDesigner
interview (mode picker first, then all 10 portfolio files), asks follow-ups
when answers are thin, records explicit unknowns with an owner, and writes the
validated portfolio when the call ends.

One command runs everything — a single Python process, no extra services:

```bash
python scripts/run_interview.py --join "<pasted Teams invite dial-in block>"
```

## Architecture

Three layers behind narrow interfaces — swap any one without touching the others:

| Layer | Module | Role |
|---|---|---|
| Interview orchestrator | `voice_interview/orchestrator.py` | Deterministic authority: walks the schema, gates progress, tracks completion, persists state, writes markdown |
| Voice I/O | `voice_interview/pipeline.py` | Pipecat pipeline: Deepgram STT → Claude (Anthropic) → Cartesia TTS, with interruption handling (VAD) |
| Meeting connector | `voice_interview/connectors/` | Gets audio into a call: Teams via Daily PSTN dial-out, local mic, or text console |

The interview **content** is parsed at runtime from `templates/*.md`
("Interview Prompts" + "Output Structure") and
`interview-protocol/agent-system-prompt.md` (mode picker + mode emphasis).
Questions are never duplicated in code; editing those files changes what the
voice agent asks.

The LLM leads the conversation but can only make progress through tools
(`record_answer`, `mark_unknown`, `next_section`, ...). `next_section` is
gated: the model cannot advance until every field of the current file is
answered or explicitly recorded as `TBD (owner: ...; next: ...)` — which the
validator counts as a filled field while keeping the unknown honest.

## Platform support matrix

| Platform | Status | How |
|---|---|---|
| **Microsoft Teams** | ✅ Supported | PSTN dial-out to the meeting's dial-in number + DTMF conference ID (via Daily). Requires the organizer's tenant to have **Audio Conferencing** (so the invite has a dial-in number). |
| **Any phone-reachable bridge** | ✅ Works incidentally | Anything with a dial-in number + DTMF conference ID (e.g. Zoom dial-in) can be joined the same way: `--dial-number` + `--conference-id`. |
| **Slack Huddles** | ❌ Not supported | Slack exposes **no audio API and no dial-in** for Huddles — a bot cannot join one with audio in any supported way. We document this rather than fake it. Adding Slack later (if Slack ships an API) is one new `MeetingConnector` subclass. |
| **Local microphone** | ✅ Dev mode | `--local-audio` (no telephony, no meeting). |
| **Text console** | ✅ Dev mode | `--text` (no audio stack at all). |

## Accounts and keys

| Provider | Used for | Required when | Notes |
|---|---|---|---|
| [Anthropic](https://console.anthropic.com/) | LLM (the interviewer's brain) | always | `ANTHROPIC_API_KEY`. Default model `claude-opus-4-8`; set `LLM_MODEL=claude-sonnet-4-6` for lower latency. |
| [Deepgram](https://console.deepgram.com/) | Speech-to-text | voice modes | `DEEPGRAM_API_KEY` |
| [Cartesia](https://play.cartesia.ai/) | Text-to-speech | voice modes | `CARTESIA_API_KEY`, optional `CARTESIA_VOICE_ID` |
| [Daily](https://dashboard.daily.co/) | WebRTC transport + PSTN dial-out | `--join` | `DAILY_API_KEY`. **PSTN dial-out is a paid, account-gated Daily feature**: your Daily domain needs dial-out enabled and a purchased phone number. Without it the first dial attempt fails with a clear error. |

Copy `.env.example` to `.env` and fill in the keys. All knobs are env/config
driven — nothing provider-specific is hardcoded.

```bash
pip install -e ".[voice]"     # full voice stack (Pipecat + providers)
pip install -e ".[text]"      # text mode only (anthropic SDK)
```

## Running a real Teams interview

1. Schedule a Teams meeting whose invite shows a **"Dial in by phone"** block
   (this exists when the organizer has Audio Conferencing). A bare
   `teams.microsoft.com/l/meetup-join/...` link does **not** contain the
   dial-in number, so the CLI rejects it with guidance.
2. Start the interviewer with the pasted dial-in block, a dial string, or flags:

   ```bash
   python scripts/run_interview.py --join "+1 555-123-4567,,123456789#"
   # or
   python scripts/run_interview.py --join meeting \
       --dial-number "+15551234567" --conference-id 123456789 \
       --out portfolios/customer-billing-api
   ```

3. The agent creates a Daily room, dials the Teams number, enters the
   conference ID via DTMF, and greets the room. **Lobby caveat:** unless the
   meeting allows callers to bypass the lobby, the organizer must admit the
   caller ("SystemDesigner Interviewer").
4. The agent runs the interview: mode picker (A/B/C/D/Other), core facts, then
   all 10 files with mode-aware emphasis. People can talk over it ("barge-in"
   is supported), ask it to repeat, skip a section, or pause.
5. On completion (or early hang-up) it writes the 10 portfolio files and runs
   `scripts/validate_portfolio.py --quality-gate 80` on them automatically.

If the Teams IVR timing on your tenant differs (conference ID rejected),
tune `DTMF_INITIAL_DELAY_S` / `DTMF_CONFIRM_DELAY_S` in `.env`.

## State, resume, and early endings

Progress is saved to `<out-dir>/.interview-state.json` **after every recorded
answer** (atomic writes), so a dropped call loses at most the sentence in
flight.

There are two distinct ways an interview stops:

- **Pause** — the call drops, someone hangs up, Ctrl-D in text mode, or the
  team asks the agent to pause. The partial portfolio is written immediately
  (unanswered fields render as `TBD (owner: ...; next: ...)`), but the saved
  state is **not** finalized: every answer so far is preserved and the session
  resumes exactly where it left off. The CLI prints the resume command.
- **End** — the agent (with the team) explicitly ends the interview. Remaining
  unknowns are recorded as owned TBDs in the state itself and the session is
  finalized.

```bash
python scripts/run_interview.py --resume portfolios/my-system/.interview-state.json
```

Resume re-joins in the original mode (the saved dial-in details are reused;
pass `--join` to override), greets the room with a "welcome back — we were
working through <section>" opening, and re-anchors the model with a digest of
mode, facts, per-file completion, and the last transcript turns.

Either way the output directory always contains **all 10 files** that pass the
quality gate — partial portfolios carry explicit, actionable unknowns rather
than silence.

## Quality gate and TBD warnings

The interview output is scored by the existing validator
(`scripts/validate_portfolio.py`) — the agreed gate is **80, without
`--strict`**. Files that contain `TBD (owner: ...)` entries trigger the
validator's *placeholder warning*; this is intentional and consistent with the
protocol's "capture unknowns explicitly" rule. `--strict` runs will flag them
until the owners fill the gaps — that's the point.

## Deployment

The same code runs as a container (see `Dockerfile`):

```bash
docker build -t systemdesigner-interviewer .
docker run --rm --env-file .env -v "$PWD/portfolios:/app/portfolios" \
    systemdesigner-interviewer --join "+15551234567,,123456789#" \
    --out portfolios/my-system
```

No queues, databases, or side services: one process plus a state file.

## Development without a meeting

```bash
# Text console (only needs ANTHROPIC_API_KEY):
python scripts/run_interview.py --text --out portfolios/dev-run

# Local mic/speaker (needs Anthropic+Deepgram+Cartesia, no Daily):
pip install -e ".[voice,local-audio]"
python scripts/run_interview.py --local-audio --out portfolios/dev-run
```

The test suite never touches the network: the voice and meeting layers are
mocked behind their interfaces, and a scripted LLM drives full end-to-end
interviews whose output is checked against the real validator
(`tests/test_validator_gate.py`).

## Known limits

- **Bare Teams URLs can't be dialed.** Resolving a meeting link to its dial-in
  number would require a Microsoft Graph integration; today you paste the
  invite's dial-in block or pass flags. A Graph-based connector would slot in
  as another `MeetingConnector` without touching the rest.
- **Teams lobby:** phone callers may wait in the lobby until admitted.
- **Tenant IVR variance:** DTMF prompt timing differs across tenants; tune the
  delays in `.env`.
- **Slack:** see the support matrix above — no audio API exists to build on.
