"""When a follow-up task is due, kept free of any web or database code."""

from datetime import date, datetime
from enum import StrEnum


class DueStatus(StrEnum):
    DONE = "done"
    OVERDUE = "overdue"
    TODAY = "today"
    UPCOMING = "upcoming"
    SOMEDAY = "someday"


def due_status(due: date | None, done_at: datetime | None, today: date) -> DueStatus:
    """Where a task stands. A done task is done whatever its date; no date means someday."""
    if done_at is not None:
        return DueStatus.DONE
    if due is None:
        return DueStatus.SOMEDAY
    if due < today:
        return DueStatus.OVERDUE
    if due == today:
        return DueStatus.TODAY
    return DueStatus.UPCOMING
