"""A copilot that runs without any API key.

It scores with a few transparent rules. It is what the tests use, and what a
fresh clone runs out of the box, so the whole app works offline.
"""

from datetime import UTC

from app.ai.context import ContactContext
from app.ai.schemas import FollowUpDraft, Insights, Language, LeadScore, ScoreResult
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

    def insights(self, ctx: ContactContext) -> Insights:
        c = ctx.contact
        if not ctx.activities:
            return Insights(
                summary=f"Nothing has been logged with {c.first_name} {c.last_name} yet.",
                open_questions=["What problem are they trying to solve?", "Who decides?"],
                next_action=f"Book a discovery call with {c.first_name}.",
            )
        last = ctx.activities[0]
        open_deals = [d for d in ctx.deals if Stage(d.stage) not in CLOSED_STAGES]
        deal_part = (
            f" {len(open_deals)} open deal(s), {sum(d.amount for d in open_deals)} EUR in total."
            if open_deals
            else " No open deal."
        )
        return Insights(
            summary=(
                f"{len(ctx.activities)} interaction(s) logged, the latest on "
                f"{last.occurred_at:%Y-%m-%d}: {last.subject}.{deal_part}"
            ),
            open_questions=[] if open_deals else ["Is there a project we can help with?"],
            next_action=f"Follow up with {c.first_name} on: {last.subject}.",
        )

    def draft_follow_up(
        self, ctx: ContactContext, language: Language, goal: str | None
    ) -> FollowUpDraft:
        name = ctx.contact.first_name
        topic = ctx.activities[0].subject if ctx.activities else None
        if language == "fr":
            about = f" suite à notre échange ({topic})" if topic else ""
            return FollowUpDraft(
                subject=f"Suivi{about}",
                body=f"Bonjour {name},\n\nJe reviens vers vous{about}. "
                "Avez-vous quelques minutes cette semaine pour en parler ?\n\nBien à vous",
            )
        about = f" after our last conversation ({topic})" if topic else ""
        return FollowUpDraft(
            subject=f"Following up{about}",
            body=f"Hi {name},\n\nI wanted to follow up{about}. "
            "Do you have a few minutes this week to talk it through?\n\nBest regards",
        )
