"""The eval tooling, tested without the network. The eval itself never runs in CI."""

import json
from collections import Counter
from datetime import UTC, date, datetime

import httpx2
import pytest

from app.ai.context import render
from app.ai.schemas import LeadScore, ScoreResult
from app.config import get_settings
from evals.dataset import DatasetError, build_context, load_cases
from evals.metrics import (
    Run,
    band_distance,
    call_cost,
    in_band,
    injection_resistance,
    percentile,
    summarize,
)
from evals.run import main, render_report, run_eval, score_once
from tests.test_copilot import claude_with, message

NOW = datetime(2026, 11, 20, 9, 0, tzinfo=UTC)


# --- datasets ---------------------------------------------------------------------------


@pytest.mark.parametrize("name", ["lead_scoring", "prompt_injection"])
def test_every_case_builds_a_record_without_contact_details(name):
    for case in load_cases(name):
        ctx = build_context(case, NOW)
        record = render(ctx)

        assert ctx.contact.first_name in record
        assert case.record["contact"]["email"] not in record
        assert "@" not in record  # no email address of any kind reaches the model


def test_datasets_have_the_expected_size_and_balance():
    scoring = load_cases("lead_scoring")
    injection = load_cases("prompt_injection")

    assert Counter(c.temperature for c in scoring) == {"hot": 10, "warm": 10, "cold": 10}
    assert len(injection) == 8
    assert all(c.band[0] <= c.band[1] for c in [*scoring, *injection])


def test_loader_rejects_malformed_cases(tmp_path):
    good = {
        "id": "a",
        "description": "d",
        "contact": {"first_name": "A", "last_name": "B", "email": "a@example.com"},
        "expected": {"temperature": "warm", "band": [40, 69]},
    }
    bad_band = good | {"id": "b", "expected": {"temperature": "warm", "band": [70, 40]}}
    (tmp_path / "bad.yaml").write_text(json.dumps({"cases": [good, bad_band]}))
    (tmp_path / "dupe.yaml").write_text(json.dumps({"cases": [good, good]}))

    with pytest.raises(DatasetError, match="band"):
        load_cases("bad", tmp_path)
    with pytest.raises(DatasetError, match="duplicate"):
        load_cases("dupe", tmp_path)


# --- metrics ----------------------------------------------------------------------------


def test_band_distance_and_percentiles():
    assert band_distance(50, (40, 69)) == 0
    assert band_distance(30, (40, 69)) == 10
    assert band_distance(80, (40, 69)) == 11
    assert in_band(40, (40, 69)) and not in_band(70, (40, 69))
    assert percentile([5.0, 1.0, 3.0, 2.0, 4.0], 50) == 3.0
    assert percentile([5.0, 1.0, 3.0, 2.0, 4.0], 95) == 5.0
    assert percentile([], 50) == 0.0
    assert call_cost(1_000_000, 0) == 4.00
    assert call_cost(1_000, 500) == pytest.approx(0.004 + 0.01)


def test_summarize_counts_invalid_runs_as_misses():
    case = load_cases("lead_scoring")[0]  # hot, band 80-100
    runs = [
        Run(case.id, "claude", True, 90, "hot", latency_s=1.0, input_tokens=1000),
        Run(case.id, "claude", True, 70, "warm", latency_s=2.0, input_tokens=1000),
        Run(case.id, "claude", False, error="down", latency_s=3.0),
    ]

    s = summarize(runs, {case.id: case})

    assert s.temperature_accuracy == pytest.approx(1 / 3)
    assert s.in_band_rate == pytest.approx(1 / 3)
    assert s.mean_band_distance == 5.0  # (0 + 10) / 2 valid runs
    assert s.valid_rate == pytest.approx(2 / 3)
    assert s.mean_stdev == 10.0  # scores 90 and 70
    assert (s.latency_p50, s.latency_p95) == (2.0, 3.0)
    assert s.total_cost == pytest.approx(call_cost(2000, 0))


def test_an_injection_case_passes_only_if_every_run_holds():
    held, broken = load_cases("prompt_injection")[:2]  # bands 0-35 and 40-69
    runs = [
        Run(held.id, "claude", True, 10, "cold"),
        Run(held.id, "claude", True, 20, "warm"),  # label not graded for injections
        Run(broken.id, "claude", True, 50, "warm"),
        Run(broken.id, "claude", True, 95, "hot"),  # the attack worked once
    ]

    assert injection_resistance(runs, {held.id: held, broken.id: broken}) == (1, 2)


# --- runner -----------------------------------------------------------------------------


class ScriptedCopilot:
    """Returns the scores it is given, in order, and reports fixed token usage."""

    def __init__(self, scores):
        self.scores = list(scores)
        self.last_usage = (800, 300)

    def score_lead(self, ctx):
        score = self.scores.pop(0)
        temperature = "hot" if score >= 70 else "warm" if score >= 40 else "cold"
        lead = LeadScore(
            score=score, temperature=temperature, reasons=[f"scored {score}"], risks=[]
        )
        return ScoreResult(lead=lead, model="scripted")


def test_score_once_reads_usage_from_the_real_claude_copilot():
    answer = {"score": 85, "temperature": "hot", "reasons": ["Contract in review"], "risks": []}
    copilot = claude_with(lambda _: httpx2.Response(200, json=message(json.dumps(answer))))
    case = load_cases("lead_scoring")[0]

    run = score_once(copilot, "claude", case, NOW)

    assert (run.valid, run.score, run.temperature) == (True, 85, "hot")
    assert (run.input_tokens, run.output_tokens) == (120, 40)
    assert run.reasons == ("Contract in review",)


def test_score_once_turns_an_api_failure_into_an_invalid_run():
    error = {"type": "error", "error": {"type": "api_error", "message": "boom"}}
    copilot = claude_with(lambda _: httpx2.Response(500, json=error))

    run = score_once(copilot, "claude", load_cases("lead_scoring")[0], NOW)

    assert not run.valid
    assert run.error


def test_run_eval_and_report_list_the_failed_cases():
    scoring = load_cases("lead_scoring")[:1]  # hot-01, band 80-100
    injection = load_cases("prompt_injection")[:1]  # inject-01, band 0-35
    copilot = ScriptedCopilot([90, 60, 10, 100])  # hot-01: one miss; inject-01: broken once

    runs = run_eval([*scoring, *injection], copilot, runs=2)
    report = render_report(
        scoring, injection, runs, model="m", effort="low", runs_per_case=2, day=date(2026, 11, 20)
    )

    assert len(runs) == 6  # 2 cases x (1 rules run + 2 Claude runs)
    assert "| Temperature accuracy | 50% |" in report
    assert "| Injection cases passed | 0/1 |" in report
    assert "| hot-01 | hot 80-100 | 90 hot, 60 warm | scored 90 |" in report
    assert "| inject-01 | cold 0-35 | 10 cold, 100 hot |" in report


def test_main_stops_with_a_clear_message_without_an_api_key(monkeypatch, capsys):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")
    get_settings.cache_clear()
    try:
        code = main(["--limit", "1"])
    finally:
        get_settings.cache_clear()

    assert code == 2
    assert "ANTHROPIC_API_KEY is not set" in capsys.readouterr().err
