"""Preflight checks: catch a dead-on-arrival setup BEFORE the meeting starts.

``python scripts/run_interview.py --check`` runs every check and prints an
actionable report. Network is touched only when a Daily key is present (one
GET to the Daily API to confirm the key works and report the domain), and the
HTTP getter is injectable for tests.
"""

from __future__ import annotations

from dataclasses import dataclass
from importlib import util as importlib_util
from pathlib import Path
import json
import sys

from .config import InterviewConfig

OK = "ok"
WARN = "warn"
FAIL = "fail"

_MARKS = {OK: "[ok]  ", WARN: "[warn]", FAIL: "[FAIL]"}


@dataclass(frozen=True)
class CheckResult:
    name: str
    status: str  # ok | warn | fail
    detail: str


def _module_available(name: str) -> bool:
    return importlib_util.find_spec(name) is not None


def _default_http_get(url: str, headers: dict) -> tuple[int, dict]:
    import urllib.error
    import urllib.request

    request = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        try:
            body = json.loads(error.read().decode("utf-8"))
        except Exception:
            body = {}
        return error.code, body
    except Exception as error:  # network unreachable, DNS, timeout...
        return 0, {"error": str(error)}


def run_checks(
    config: InterviewConfig,
    repo_root: Path,
    *,
    check_network: bool = True,
    http_get=_default_http_get,
) -> list[CheckResult]:
    results: list[CheckResult] = []

    # 1. Python version.
    if sys.version_info >= (3, 11):
        results.append(CheckResult("python", OK, f"Python {sys.version.split()[0]}"))
    else:
        results.append(
            CheckResult("python", FAIL, f"Python 3.11+ required, found {sys.version.split()[0]}")
        )

    # 2. Protocol files (the interview's single source of truth).
    try:
        from .protocol import load_plan

        plan = load_plan(repo_root)
        total_fields = sum(len(s.output_fields) for s in plan.sections)
        results.append(
            CheckResult(
                "protocol",
                OK,
                f"{len(plan.sections)} templates, {total_fields} fields, "
                f"{len(plan.mode_emphasis)} interview modes parsed",
            )
        )
    except Exception as error:
        results.append(CheckResult("protocol", FAIL, f"cannot load protocol files: {error}"))

    # 3. Provider keys, per mode.
    def key_check(name: str, env_var: str, value: str | None, needed_for: str) -> None:
        if value:
            results.append(CheckResult(name, OK, f"{env_var} is set"))
        else:
            results.append(
                CheckResult(
                    name,
                    WARN,
                    f"{env_var} not set — required for {needed_for} "
                    "(copy .env.example to .env)",
                )
            )

    key_check("anthropic", "ANTHROPIC_API_KEY", config.anthropic_api_key, "all modes")
    key_check("deepgram", "DEEPGRAM_API_KEY", config.deepgram_api_key, "voice modes")
    key_check("cartesia", "CARTESIA_API_KEY", config.cartesia_api_key, "voice modes")
    key_check("daily", "DAILY_API_KEY", config.daily_api_key, "--join (Teams dial-out)")

    # 4. Optional dependencies, per mode.
    if _module_available("anthropic"):
        results.append(CheckResult("text deps", OK, "anthropic SDK installed (--text ready)"))
    else:
        results.append(
            CheckResult("text deps", WARN, "anthropic SDK missing — pip install -e '.[text]'")
        )
    if _module_available("pipecat"):
        voice_missing = [
            name
            for name, module in [
                ("daily", "daily"),
                ("deepgram", "deepgram"),
                ("anthropic", "anthropic"),
                ("aiohttp", "aiohttp"),
            ]
            if not _module_available(module)
        ]
        if voice_missing:
            results.append(
                CheckResult(
                    "voice deps",
                    WARN,
                    "pipecat installed but missing: "
                    + ", ".join(voice_missing)
                    + " — pip install -e '.[voice]'",
                )
            )
        else:
            results.append(CheckResult("voice deps", OK, "full voice stack installed"))
    else:
        results.append(
            CheckResult("voice deps", WARN, "pipecat not installed — pip install -e '.[voice]'")
        )

    # 5. Daily API reachability + dial-out capability (the #1 first-run trap:
    #    PSTN dial-out is a paid, account-gated Daily feature).
    if config.daily_api_key and check_network:
        status, body = http_get(
            f"{config.daily_api_url}/",
            {"Authorization": f"Bearer {config.daily_api_key}"},
        )
        if status == 200:
            domain = body.get("domain_name", "unknown")
            dialout = (body.get("config") or {}).get("enable_dialout")
            if dialout:
                results.append(
                    CheckResult(
                        "daily api", OK, f"domain '{domain}' reachable, dial-out ENABLED"
                    )
                )
            else:
                results.append(
                    CheckResult(
                        "daily api",
                        WARN,
                        f"domain '{domain}' reachable, but dial-out does not appear "
                        "enabled — contact Daily to enable PSTN dial-out and buy a "
                        "phone number, or the Teams dial attempt will fail",
                    )
                )
        elif status == 401:
            results.append(CheckResult("daily api", FAIL, "DAILY_API_KEY was rejected (401)"))
        elif status == 0:
            results.append(
                CheckResult("daily api", WARN, f"could not reach Daily: {body.get('error')}")
            )
        else:
            results.append(CheckResult("daily api", WARN, f"unexpected response ({status})"))

    return results


def mode_readiness(results: list[CheckResult]) -> dict[str, bool]:
    """Which run modes are ready, based on the check results."""

    by_name = {r.name: r for r in results}

    def good(*names: str) -> bool:
        return all(
            name in by_name and by_name[name].status == OK for name in names
        )

    return {
        "--text": good("python", "protocol", "anthropic", "text deps"),
        "--local-audio": good(
            "python", "protocol", "anthropic", "deepgram", "cartesia", "voice deps"
        ),
        "--join (Teams)": good(
            "python", "protocol", "anthropic", "deepgram", "cartesia", "daily", "voice deps"
        ),
    }


def print_report(results: list[CheckResult]) -> int:
    """Print the doctor report; exit code 1 only on hard failures."""

    print("SystemDesigner voice interviewer — preflight check\n")
    for result in results:
        print(f"  {_MARKS[result.status]} {result.name:<11} {result.detail}")

    print("\nRun modes:")
    for mode, ready in mode_readiness(results).items():
        print(f"  {'[ready]' if ready else '[not ready]':<12} {mode}")

    print(
        "\nDetails and account setup: docs/voice-interview.md "
        "(keys go in .env — see .env.example)"
    )
    return 1 if any(r.status == FAIL for r in results) else 0
