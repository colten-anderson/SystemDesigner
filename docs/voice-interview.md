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
| **Microsoft Teams** | ✅ Supported | PSTN dial-out to the meeting's dial-in number + automatic conference-ID entry, via **Daily or Twilio** (pick one — see "Choosing a telephony provider"). Requires the organizer's tenant to have **Audio Conferencing** (so the invite has a dial-in number). |
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
| Telephony (pick ONE) | The phone call into Teams | `--join` | **Daily** or **Twilio** — see the comparison below. |

Copy `.env.example` to `.env` and fill in the keys. All knobs are env/config
driven — nothing provider-specific is hardcoded.

```bash
pip install -e ".[voice]"          # voice stack with Daily telephony
pip install -e ".[voice-twilio]"   # voice stack with Twilio telephony
pip install -e ".[text]"           # text mode only (anthropic SDK)
```

### Choosing a telephony provider

The agent reaches Teams by placing an ordinary phone call to the meeting's
dial-in number. Two interchangeable providers can place that call
(`TELEPHONY_PROVIDER=daily|twilio` or `--provider`):

| | **Daily** (default) | **Twilio** |
|---|---|---|
| Procurement | **Account-gated**: PSTN dial-out must be enabled by Daily on your domain, plus a purchased number | **Fully self-serve**: sign up, buy a number with a card, dial immediately |
| Network setup | None — Daily hosts the media | Needs a **publicly reachable URL** for the call audio (Twilio streams it to you): run `ngrok http 8765` and set `PUBLIC_URL` to the https URL |
| Config | `DAILY_API_KEY` | `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_FROM_NUMBER`, `PUBLIC_URL` |
| Conference-ID entry | DTMF tones sent on the live call | Typed automatically via the call's `SendDigits` (the IVR delays map to `DTMF_*_DELAY_S` the same way) |
| Cost shape | Per-minute room + PSTN usage | Per-minute PSTN + ~$1/month for the number |

**If getting a Daily account is a blocker, use Twilio:**

```bash
pip install -e ".[voice-twilio]"
ngrok http 8765          # note the https URL it prints
python scripts/run_interview.py --provider twilio \
    --public-url https://<your-tunnel>.ngrok.app \
    --join "+15551234567,,123456789#" --out portfolios/my-system
```

Everything else (interview behavior, resume, summaries, validation) is
identical — the provider only changes who places the phone call.

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

Every run also writes **`interview-summary.md`** next to the portfolio: a
per-file coverage table, every TBD as a follow-up row (field, owner, next
step), the open questions raised during the call, and — for paused runs — the
exact resume command. Send it to the team as the post-meeting action list.

When you don't pass `--out`, the run starts in a timestamped folder and is
renamed to the captured system name at the end (e.g.
`portfolios/customer-billing-api`); the state file moves with it, so the
printed resume command always points at the right place.

## Quality gate and TBD warnings

The interview output is scored by the existing validator
(`scripts/validate_portfolio.py`) — the agreed gate is **80, without
`--strict`**. Files that contain `TBD (owner: ...)` entries trigger the
validator's *placeholder warning*; this is intentional and consistent with the
protocol's "capture unknowns explicitly" rule. `--strict` runs will flag them
until the owners fill the gaps — that's the point.

## Cost controls

An hour-long interview is dozens of LLM turns over a growing transcript. The
defaults are tuned to keep that cheap:

- **Prompt caching is ON** in the voice pipeline (and the text mode). The
  system prompt, tool definitions, and conversation prefix are re-sent every
  turn; caching cuts that repeated input to ~10% of full price after the
  first turn — the dominant saving on long calls.
- **Output tokens are capped** (`LLM_MAX_TOKENS`, default 1024). Spoken turns
  are one or two sentences; the cap bounds the cost of any runaway turn.
- **Model choice** is one flag (`--model`) or env var (`LLM_MODEL`):

  | Model | Input/Output per MTok | When |
  |---|---|---|
  | `claude-opus-4-8` (default) | $5 / $25 | Best interview quality — probing follow-ups, mode-aware judgment |
  | `claude-sonnet-4-6` | $3 / $15 | ~40% cheaper and lower latency; very good for routine interviews |
  | `claude-haiku-4-5` | $1 / $5 | Cheapest; fine for dry runs and demos, weaker follow-up judgment |

- The other meters are usage-based and independent of this repo's code:
  Deepgram STT and Cartesia TTS per audio minute, and Daily per PSTN
  dial-out minute. `--text` mode costs only LLM tokens; `--local-audio`
  skips telephony entirely. Use those for rehearsals, and save the dialed
  call for the real interview.

```bash
# Cheapest realistic rehearsal: text mode + small model
python scripts/run_interview.py --text --model claude-haiku-4-5
```

## Preflight check

Run this before the meeting — it verifies keys, installed dependencies, and
(when a Daily key is present) that your Daily domain actually has PSTN
dial-out enabled, which is the most common first-run failure:

```bash
python scripts/run_interview.py --check
```

It prints a per-check report and which run modes (`--text`, `--local-audio`,
`--join`) are ready.

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
