from datetime import UTC, date, datetime

import pytest

from app.domain.tasks import DueStatus, due_status

TODAY = date(2026, 11, 15)
DONE_AT = datetime(2026, 11, 10, 9, 0, tzinfo=UTC)


@pytest.mark.parametrize(
    ("due", "done_at", "expected"),
    [
        (date(2026, 11, 14), None, DueStatus.OVERDUE),
        (TODAY, None, DueStatus.TODAY),
        (date(2026, 11, 16), None, DueStatus.UPCOMING),
        (None, None, DueStatus.SOMEDAY),
        (date(2026, 11, 1), DONE_AT, DueStatus.DONE),
        (None, DONE_AT, DueStatus.DONE),
    ],
)
def test_due_status(due, done_at, expected):
    assert due_status(due, done_at, TODAY) == expected
