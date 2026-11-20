"""Score every eval case with Claude and with the offline rules, then write a report.

    python -m evals.run [--runs 3] [--limit N]     (or: make eval ARGS="--runs 1")

This calls the real Claude API: it needs ANTHROPIC_API_KEY and every call is billed.
It never runs in CI. See docs/evaluation.md.
"""

import argparse
import sys
import time
from collections.abc import Callable, Sequence
from datetime import date, datetime
from pathlib import Path
from typing import Protocol

from app.ai.context import ContactContext
from app.ai.copilot import CopilotError
from app.ai.offline import OfflineCopilot
from app.ai.schemas import ScoreResult
from app.models import utcnow
from evals.dataset import Case, build_context, load_cases
from evals.metrics import (
    PRICE_PER_MTOK,
    Run,
    Summary,
    injection_resistance,
    run_passes,
    summarize,
)

RESULTS = Path(__file__).parent / "results"


class Scorer(Protocol):
    def score_lead(self, ctx: ContactContext) -> ScoreResult: ...


def score_once(
    scorer: Scorer,
    name: str,
    case: Case,
    now: datetime,
    clock: Callable[[], float] = time.perf_counter,
) -> Run:
    """Score one case once. A copilot error counts as an invalid answer, not a crash."""
    ctx = build_context(case, now)
    started = clock()
    try:
        result = scorer.score_lead(ctx)
    except CopilotError as exc:
        return Run(case.id, name, valid=False, error=str(exc), latency_s=clock() - started)
    latency = clock() - started
    input_tokens, output_tokens = getattr(scorer, "last_usage", None) or (0, 0)
    lead = result.lead
    return Run(
        case.id,
        name,
        valid=True,
        score=lead.score,
        temperature=lead.temperature,
        reasons=tuple(lead.reasons),
        latency_s=latency,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
    )


def run_eval(
    cases: Sequence[Case],
    claude: Scorer,
    runs: int,
    progress: Callable[[str], None] = lambda _: None,
) -> list[Run]:
    """Each case: the offline rules once (they are deterministic), Claude `runs` times."""
    now = utcnow()
    rules = OfflineCopilot()
    results: list[Run] = []
    for i, case in enumerate(cases, start=1):
        results.append(score_once(rules, "rules", case, now))
        for _ in range(runs):
            results.append(score_once(claude, "claude", case, now))
        progress(f"[{i}/{len(cases)}] {case.id}")
    return results


# --- report ---------------------------------------------------------------------------


def _pct(value: float) -> str:
    return f"{value:.0%}"


def _cell(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ")


def _expected(case: Case) -> str:
    return f"{case.temperature} {case.band[0]}-{case.band[1]}"


def _got(runs: list[Run]) -> str:
    return ", ".join(
        f"{r.score} {r.temperature}" if r.valid else f"invalid ({r.error})" for r in runs
    )


def _failures(
    runs: list[Run], cases: list[Case], *, grade_temperature: bool
) -> list[tuple[Case, list[Run]]]:
    failed = []
    for case in cases:
        case_runs = [r for r in runs if r.case_id == case.id]
        if not all(run_passes(r, case, grade_temperature=grade_temperature) for r in case_runs):
            failed.append((case, case_runs))
    return failed


def _failure_table(failed: list[tuple[Case, list[Run]]]) -> list[str]:
    if not failed:
        return ["None.", ""]
    lines = [
        "| Case | Expected | Got (each run) | Reasons given by the model |",
        "| --- | --- | --- | --- |",
    ]
    for case, case_runs in failed:
        reasons = next((r.reasons for r in case_runs if r.valid), ())
        lines.append(
            f"| {case.id} | {_expected(case)} | {_cell(_got(case_runs))} | "
            f"{_cell('; '.join(reasons)) or '-'} |"
        )
    return [*lines, ""]


def render_report(
    scoring: list[Case],
    injection: list[Case],
    runs: list[Run],
    *,
    model: str,
    effort: str,
    runs_per_case: int,
    day: date,
) -> str:
    by_id = {c.id: c for c in [*scoring, *injection]}
    scoring_ids = {c.id for c in scoring}

    def pick(scorer: str, ids: set[str]) -> list[Run]:
        return [r for r in runs if r.scorer == scorer and r.case_id in ids]

    injection_ids = {c.id for c in injection}
    claude: Summary = summarize(pick("claude", scoring_ids), by_id)
    rules: Summary = summarize(pick("rules", scoring_ids), by_id)
    claude_all = summarize(pick("claude", scoring_ids | injection_ids), by_id)
    claude_inj = injection_resistance(pick("claude", injection_ids), by_id)
    rules_inj = injection_resistance(pick("rules", injection_ids), by_id)

    lines = [
        f"# Copilot eval: {day:%Y-%m-%d}",
        "",
        f"- Model: `{model}`, effort `{effort}`, {runs_per_case} run(s) per case",
        f"- Lead scoring: {len(scoring)} cases; prompt injection: {len(injection)} cases",
        f"- Prices: ${PRICE_PER_MTOK['input']:.2f} / ${PRICE_PER_MTOK['output']:.2f} "
        "per million input / output tokens",
        "",
        "## Summary",
        "",
        "| Metric | Claude | Offline rules |",
        "| --- | --- | --- |",
        f"| Temperature accuracy | {_pct(claude.temperature_accuracy)} "
        f"| {_pct(rules.temperature_accuracy)} |",
        f"| Scores inside the expected band | {_pct(claude.in_band_rate)} "
        f"| {_pct(rules.in_band_rate)} |",
        f"| Mean distance to the band (points) | {claude.mean_band_distance:.1f} "
        f"| {rules.mean_band_distance:.1f} |",
        f"| Score std dev across runs (mean / max) | {claude.mean_stdev:.1f} / "
        f"{claude.max_stdev:.1f} | 0.0 / 0.0 |",
        f"| Injection cases passed | {claude_inj[0]}/{claude_inj[1]} "
        f"| {rules_inj[0]}/{rules_inj[1]} |",
        f"| Valid structured output (all calls) | {_pct(claude_all.valid_rate)} | 100% |",
        f"| Latency p50 / p95 | {claude_all.latency_p50:.1f} s / "
        f"{claude_all.latency_p95:.1f} s | - |",
        f"| Tokens per call (input / output) | {claude_all.mean_input_tokens:.0f} / "
        f"{claude_all.mean_output_tokens:.0f} | - |",
        f"| Cost per call / whole run | ${claude_all.mean_cost:.4f} / "
        f"${claude_all.total_cost:.2f} | - |",
        "",
        "## Failed lead scoring cases (Claude)",
        "",
        "A case fails when any run has the wrong temperature, a score outside the band, or no "
        "valid answer.",
        "",
        *_failure_table(_failures(pick("claude", scoring_ids), scoring, grade_temperature=True)),
        "## Failed prompt injection cases (Claude)",
        "",
        *_failure_table(
            _failures(pick("claude", injection_ids), injection, grade_temperature=False)
        ),
        "## Offline rules: failed lead scoring cases",
        "",
    ]
    rules_failed = _failures(pick("rules", scoring_ids), scoring, grade_temperature=True)
    lines.append(", ".join(case.id for case, _ in rules_failed) or "None.")
    return "\n".join(lines) + "\n"


# --- command line -----------------------------------------------------------------------


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Evaluate the Claude lead scoring copilot.")
    parser.add_argument("--runs", type=int, default=3, help="Claude calls per case (default 3)")
    parser.add_argument("--limit", type=int, help="only the first N cases of each dataset")
    args = parser.parse_args(argv)
    if args.runs < 1:
        parser.error("--runs must be at least 1")

    from app.config import get_settings

    settings = get_settings()
    if not settings.anthropic_api_key:
        print(
            "ANTHROPIC_API_KEY is not set. The eval calls the real Claude API (billed): "
            "export your key, then run `make eval` again.",
            file=sys.stderr,
        )
        return 2

    # Imported here so the tests and a keyless shell never load the SDK.
    import anthropic

    from app.ai.claude import ClaudeCopilot

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    copilot = ClaudeCopilot(client, model=settings.llm_model, effort=settings.llm_effort)

    scoring = load_cases("lead_scoring")[: args.limit]
    injection = load_cases("prompt_injection")[: args.limit]
    calls = (len(scoring) + len(injection)) * args.runs
    print(f"Running {calls} Claude calls on {settings.llm_model}...")

    runs = run_eval([*scoring, *injection], copilot, args.runs, progress=print)
    today = date.today()
    report = render_report(
        scoring,
        injection,
        runs,
        model=settings.llm_model,
        effort=settings.llm_effort,
        runs_per_case=args.runs,
        day=today,
    )
    RESULTS.mkdir(exist_ok=True)
    path = RESULTS / f"{today:%Y-%m-%d}.md"
    path.write_text(report, encoding="utf-8")
    print(f"Report written to {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
