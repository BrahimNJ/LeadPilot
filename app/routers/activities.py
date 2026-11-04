from datetime import UTC, datetime

from fastapi import APIRouter, status
from sqlalchemy import func, select

from app.models import Activity, Contact, utcnow
from app.routers.deps import PaginationDep, SessionDep, get_or_404
from app.schemas import ActivityIn, ActivityOut, Page

router = APIRouter(prefix="/contacts/{contact_id}/activities", tags=["activities"])


def _as_utc(moment: datetime) -> datetime:
    # SQLite hands datetimes back without a timezone; everything we store is UTC.
    return moment.replace(tzinfo=UTC) if moment.tzinfo is None else moment.astimezone(UTC)


@router.post("", status_code=status.HTTP_201_CREATED)
def log_activity(contact_id: int, payload: ActivityIn, session: SessionDep) -> ActivityOut:
    contact = get_or_404(session, Contact, contact_id)
    occurred_at = _as_utc(payload.occurred_at or utcnow())

    activity = Activity(
        contact_id=contact.id,
        kind=payload.kind,
        subject=payload.subject,
        body=payload.body,
        occurred_at=occurred_at,
    )
    session.add(activity)
    # Logging an old call afterwards must not make the contact look recently touched.
    if contact.last_contacted_at is None or occurred_at > _as_utc(contact.last_contacted_at):
        contact.last_contacted_at = occurred_at
    session.commit()
    session.refresh(activity)
    return ActivityOut.model_validate(activity)


@router.get("")
def timeline(contact_id: int, session: SessionDep, page: PaginationDep) -> Page[ActivityOut]:
    get_or_404(session, Contact, contact_id)
    query = select(Activity).where(Activity.contact_id == contact_id)

    total = session.scalar(select(func.count()).select_from(query.subquery())) or 0
    rows = session.scalars(
        query.order_by(Activity.occurred_at.desc(), Activity.id.desc())
        .limit(page.limit)
        .offset(page.offset)
    )
    return Page(
        items=[ActivityOut.model_validate(a) for a in rows],
        total=total,
        limit=page.limit,
        offset=page.offset,
    )
