"""A copilot that runs without any API key.

It scores with a few transparent rules. It is what the tests use, and what a
fresh clone runs out of the box, so the whole app works offline.
"""

from datetime import UTC

from app.ai.context import ContactContext
from app.ai.schemas import LeadScore, ScoreResult
from app.domain.pipeline import CLOSED_STAGES, OPEN_STAGES, Stage

MODEL_NAME = "offline-rules"


class OfflineCopilot:
    def score_lead(self, ctx: ContactContext) -> ScoreResult:
        score = 10
        reasons: list[str] = []
        risks: list[str] = []

        open_deals = [d for d in ctx.deals if Stage(d.stage) not in CLOSED_STAGES]
        if open_deals:
            best = max(open_deals, key=lambda d: OPEN_STAGES.index(Stage(d.stage)))
            score += 15 * (OPEN_STAGES.index(Stage(best.stage)) + 1)
            reasons.append(f"Open deal '{best.title}' in {best.stage}")
        else:
            risks.append("No open deal")

        if ctx.activities:
            last = ctx.activities[0].occurred_at
            last = last.replace(tzinfo=UTC) if last.tzinfo is None else last
            days = (ctx.now - last).days
            if days <= 14:
                score += 20
                when = "today" if days == 0 else "yesterday" if days == 1 else f"{days} days ago"
                reasons.append(f"Contacted {when}")
            elif days > 45:
                score -= 10
                risks.append(f"No contact for {days} days")
            if len(ctx.activities) >= 3:
                score += 5
                reasons.append(f"{len(ctx.activities)} interactions logged")
        else:
            risks.append("No interaction logged yet")

        score = max(0, min(100, score))
        temperature = "hot" if score >= 70 else "warm" if score >= 40 else "cold"
        lead = LeadScore(score=score, temperature=temperature, reasons=reasons, risks=risks)
        return ScoreResult(lead=lead, model=MODEL_NAME)
