from pathlib import Path

from voice_interview.config import InterviewConfig
from voice_interview.doctor import (
    FAIL,
    OK,
    WARN,
    CheckResult,
    mode_readiness,
    print_report,
    run_checks,
)

REPO_ROOT = Path(__file__).resolve().parents[1]


def by_name(results):
    return {r.name: r for r in results}


def test_checks_with_no_keys_warn_but_do_not_fail() -> None:
    results = run_checks(InterviewConfig(), REPO_ROOT, check_network=False)
    named = by_name(results)
    assert named["python"].status == OK
    assert named["protocol"].status == OK
    assert "10 templates" in named["protocol"].detail
    for key in ["anthropic", "deepgram", "cartesia", "daily"]:
        assert named[key].status == WARN
        assert ".env" in named[key].detail
    # No hard failures means exit code 0: warnings guide, they don't block.
    assert print_report(results) == 0


def test_daily_api_dialout_enabled(capsys) -> None:
    def fake_get(url, headers):
        assert headers["Authorization"] == "Bearer dk"
        return 200, {"domain_name": "acme", "config": {"enable_dialout": True}}

    results = run_checks(
        InterviewConfig(daily_api_key="dk"), REPO_ROOT, http_get=fake_get
    )
    daily = by_name(results)["daily api"]
    assert daily.status == OK
    assert "dial-out ENABLED" in daily.detail


def test_daily_api_dialout_missing_warns_with_guidance() -> None:
    def fake_get(url, headers):
        return 200, {"domain_name": "acme", "config": {}}

    results = run_checks(
        InterviewConfig(daily_api_key="dk"), REPO_ROOT, http_get=fake_get
    )
    daily = by_name(results)["daily api"]
    assert daily.status == WARN
    assert "PSTN dial-out" in daily.detail


def test_daily_api_bad_key_fails_and_sets_exit_code() -> None:
    def fake_get(url, headers):
        return 401, {"error": "invalid token"}

    results = run_checks(
        InterviewConfig(daily_api_key="bad"), REPO_ROOT, http_get=fake_get
    )
    daily = by_name(results)["daily api"]
    assert daily.status == FAIL
    assert print_report(results) == 1


def test_daily_api_unreachable_warns_not_fails() -> None:
    def fake_get(url, headers):
        return 0, {"error": "DNS failure"}

    results = run_checks(
        InterviewConfig(daily_api_key="dk"), REPO_ROOT, http_get=fake_get
    )
    assert by_name(results)["daily api"].status == WARN


def test_network_check_skipped_without_key() -> None:
    def explode(url, headers):  # must never be called
        raise AssertionError("network touched without a Daily key")

    results = run_checks(InterviewConfig(), REPO_ROOT, http_get=explode)
    assert "daily api" not in by_name(results)


def test_mode_readiness_logic() -> None:
    def result_set(ready_names):
        all_names = [
            "python", "protocol", "anthropic", "deepgram",
            "cartesia", "daily", "text deps", "voice deps",
        ]
        return [
            CheckResult(name, OK if name in ready_names else WARN, "")
            for name in all_names
        ]

    text_only = mode_readiness(result_set(["python", "protocol", "anthropic", "text deps"]))
    assert text_only["--text"] is True
    assert text_only["--local-audio"] is False
    assert text_only["--join (Teams)"] is False

    everything = mode_readiness(
        result_set(
            ["python", "protocol", "anthropic", "deepgram", "cartesia",
             "daily", "text deps", "voice deps"]
        )
    )
    assert all(everything.values())


def test_report_lists_run_modes(capsys) -> None:
    print_report(run_checks(InterviewConfig(), REPO_ROOT, check_network=False))
    out = capsys.readouterr().out
    assert "Run modes:" in out
    assert "--text" in out
    assert "--join (Teams)" in out
    assert ".env.example" in out
