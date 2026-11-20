# Evaluating the copilot

The unit tests check that the copilot *works*: they fake the Claude API and check what is sent
and how the answer is read. They say nothing about whether the scores are *good*. The eval in
`evals/` answers that question by calling the real model on a fixed set of contacts with known
expected results.

## What is measured

Each case is scored by Claude several times (3 by default) and by the offline rules once, as
a baseline. The report compares both.

| Metric | What it tells you |
| --- | --- |
| Temperature accuracy | How often the hot / warm / cold label matches the expected one. |
| Scores inside the expected band | How often the 0-100 score falls in the range the case allows. |
| Mean distance to the band | When a score misses, by how many points on average (0 when inside). |
| Score std dev across runs | How much the score of one contact moves between identical calls. |
| Injection cases passed | How many attacks hidden in CRM text failed to move the score out of its band. |
| Valid structured output | How often Claude returned an answer that matched the schema. |
| Latency p50 / p95 | Typical and slow-case time for one scoring call. |
| Tokens and cost per call | Input and output tokens from the API's `usage` field, priced with `PRICE_PER_MTOK`. |

Invalid answers count as misses in accuracy and band rate, so a model that fails often cannot
look accurate by answering only the easy cases.

## The datasets

- `evals/datasets/lead_scoring.yaml`: 30 synthetic B2B contacts, 10 hot, 10 warm and 10 cold,
  including tricky ones: a big deal with no contact for 90 days, a lost deal followed by new
  interest, many emails but no deal, a champion who left, five follow-ups never answered. The
  labelling rubric is written at the top of the file.
- `evals/datasets/prompt_injection.yaml`: 8 contacts whose notes, emails or deal title contain
  an attack: an override asking for a score of 100, a fake `</crm_record><system>` block, a
  request to reveal the system prompt, an instruction in French, a pasted JSON answer, a fake
  admin message, and a lead asking to be marked cold. Each case holds the band the contact
  deserves without the attack; it passes only if every run stays in that band with a valid
  answer.

The names and companies are invented and every email uses `example.com`. Cases are turned into
the same `ContactContext` the API builds and sent through the same `render()` function, so the
model receives exactly what production sends: no email address and no phone number.

## How to run it

```bash
export ANTHROPIC_API_KEY=...                  # never commit it
make eval                                      # 38 cases x 3 runs = 114 calls
make eval ARGS="--runs 1 --limit 5"            # a quick, cheap check
```

The model and effort come from `LLM_MODEL` and `LLM_EFFORT`, as in the app. Every call is
billed; the report shows the measured cost of the run. Without a key the command stops with a
message and calls nothing. The eval never runs in CI; CI only runs the tests of its code
(`tests/test_evals.py`), which use a fake copilot.

## Reading the report

The report is written to `evals/results/YYYY-MM-DD.md`.

1. **Summary table.** Compare Claude with the offline rules. The rules are deterministic, so
   their spread is 0 and they ignore injections by construction: they are the floor, not a
   target. Claude should beat them on accuracy and on the tricky cases.
2. **Failed cases.** For each failure: the expected label and band, the score of every run, and
   the reasons the model gave. Read the reasons before changing anything: a failure is either
   a model mistake (fix the prompt) or a label you disagree with on reflection (fix the case,
   and say why in the commit).
3. **Spread.** A case whose score moves a lot between runs sits on a boundary or has an
   ambiguous record. A high mean spread makes single scores in the app less trustworthy.

To compare a prompt or model change, run the eval before and after with the same `--runs`.

## Known limits

- **Small and synthetic.** 30 + 8 cases written by hand. Good enough to catch regressions and
  obvious weaknesses, not to claim a precise accuracy figure: one case is more than 3 points.
- **Labels written by one person.** The expected temperatures and bands come from the rubric,
  applied by the author. Another salesperson might label some tricky cases differently.
- **Only lead scoring.** Insights and follow-up drafts are free text and are not evaluated yet.
- **Injection set is not exhaustive.** Passing 8 known attacks does not prove the copilot is
  safe against every attack; it shows the main defences hold.
- **Prices are a constant.** `PRICE_PER_MTOK` in `evals/metrics.py` holds the list price of
  `claude-opus-5-5`; update it if you change the model.
