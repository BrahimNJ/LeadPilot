from functools import lru_cache
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.ai.context import ContactContext
from app.ai.copilot import Copilot, CopilotError, CopilotRefused
from app.ai.offline import OfflineCopilot
from app.ai.schemas import FollowUpDraft, Insights, Language, ScoreResult
from app.config import get_settings
from app.models import Activity, Contact, Deal, utcnow
from app.routers.deps import SessionDep, get_or_404

router = APIRouter(prefix="/contacts/{contact_id}", tags=["copilot"])


@lru_cache
def get_copilot() -> Copilot:
    settings = get_settings()
    if not settings.anthropic_api_key:
        return OfflineCopilot()
    # Imported here: the SDK takes seconds to load, which a keyless instance never needs.
    import anthropic

    from app.ai.claude import ClaudeCopilot

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    return ClaudeCopilot(client, model=settings.llm_model, effort=settings.llm_effort)


CopilotDep = Annotated[Copilot, Depends(get_copilot)]


def load_context(session: SessionDep, contact_id: int) -> ContactContext:
    contact = get_or_404(session, Contact, contact_id)
    deals = list(session.scalars(select(Deal).where(Deal.contact_id == contact_id)))
    activities = list(
        session.scalars(
            select(Activity)
            .where(Activity.contact_id == contact_id)
            .order_by(Activity.occurred_at.desc(), Activity.id.desc())
        )
    )
    return ContactContext(contact=contact, deals=deals, activities=activities, now=utcnow())


def copilot_http_error(exc: CopilotError) -> HTTPException:
    code = status.HTTP_422_UNPROCESSABLE_CONTENT if isinstance(exc, CopilotRefused) else 503
    return HTTPException(code, str(exc))


@router.post("/score")
def score_contact(contact_id: int, session: SessionDep, copilot: CopilotDep) -> ScoreResult:
    ctx = load_context(session, contact_id)
    try:
        result = copilot.score_lead(ctx)
    except CopilotError as exc:
        raise copilot_http_error(exc) from exc

    contact = ctx.contact
    contact.score = result.lead.score
    contact.score_details = result.lead.model_dump()
    contact.score_model = result.model
    contact.scored_at = ctx.now
    session.commit()
    return result


@router.post("/insights")
def contact_insights(contact_id: int, session: SessionDep, copilot: CopilotDep) -> Insights:
    ctx = load_context(session, contact_id)
    try:
        return copilot.insights(ctx)
    except CopilotError as exc:
        raise copilot_http_error(exc) from exc


class FollowUpRequest(BaseModel):
    language: Language = "fr"
    goal: str | None = Field(
        default=None, max_length=300, examples=["Get a date for the security review"]
    )


@router.post("/follow-up")
def draft_follow_up(
    contact_id: int, payload: FollowUpRequest, session: SessionDep, copilot: CopilotDep
) -> FollowUpDraft:
    """Return a draft. Nothing is sent or stored: the salesperson stays in control."""
    ctx = load_context(session, contact_id)
    try:
        return copilot.draft_follow_up(ctx, payload.language, payload.goal)
    except CopilotError as exc:
        raise copilot_http_error(exc) from exc
