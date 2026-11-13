from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import func, select

from app.models import Activity, Contact, utcnow
from app.routers.deps import PaginationDep, SessionDep, get_or_404, paginate
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

    order = (Activity.occurred_at.desc(), Activity.id.desc())
    return paginate(session, query, page, ActivityOut, *order)


@router.delete("/{activity_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_activity(contact_id: int, activity_id: int, session: SessionDep) -> None:
    contact = get_or_404(session, Contact, contact_id)
    activity = session.get(Activity, activity_id)
    # An activity of another contact is reported as missing, not deleted through this URL.
    if activity is None or activity.contact_id != contact.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"activity {activity_id} not found")

    session.delete(activity)
    session.flush()
    # Last contact = the most recent activity left, or none.
    contact.last_contacted_at = session.scalar(
        select(func.max(Activity.occurred_at)).where(Activity.contact_id == contact.id)
    )
    session.commit()
