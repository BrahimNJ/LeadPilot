from datetime import timedelta
from typing import Literal

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select

from app.models import Contact, Deal, Task, utcnow
from app.routers.deps import PaginationDep, SessionDep, get_or_404, paginate
from app.schemas import Page, TaskIn, TaskOut

# Tasks are created and listed under their contact, and handled on their own after that.
contact_router = APIRouter(prefix="/contacts/{contact_id}/tasks", tags=["tasks"])
router = APIRouter(prefix="/tasks", tags=["tasks"])


# Open tasks first, the soonest at the top; tasks without a date after dated ones.
SOONEST_FIRST = (Task.due_date.asc().nulls_last(), Task.id)


def _check_deal(session: SessionDep, deal_id: int | None, contact_id: int) -> None:
    if deal_id is None:
        return
    deal = session.get(Deal, deal_id)
    if deal is None or deal.contact_id != contact_id:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            f"deal {deal_id} not found for contact {contact_id}",
        )


def _save(session: SessionDep, task: Task) -> TaskOut:
    session.commit()
    session.refresh(task)
    return TaskOut.model_validate(task)


@contact_router.post("", status_code=status.HTTP_201_CREATED)
def create_task(contact_id: int, payload: TaskIn, session: SessionDep) -> TaskOut:
    contact = get_or_404(session, Contact, contact_id)
    _check_deal(session, payload.deal_id, contact.id)
    task = Task(contact_id=contact.id, **payload.model_dump())
    session.add(task)
    return _save(session, task)


@contact_router.get("")
def contact_tasks(
    contact_id: int,
    session: SessionDep,
    page: PaginationDep,
    done: bool | None = Query(
        default=None, description="true: done tasks only, false: open only, absent: both"
    ),
) -> Page[TaskOut]:
    get_or_404(session, Contact, contact_id)
    query = select(Task).where(Task.contact_id == contact_id)
    if done is not None:
        query = query.where(Task.done_at.is_not(None) if done else Task.done_at.is_(None))
    return paginate(session, query, page, TaskOut, Task.done_at.is_not(None), *SOONEST_FIRST)


@router.get("")
def agenda(
    session: SessionDep,
    page: PaginationDep,
    due: Literal["overdue", "today", "week"] | None = Query(
        default=None, description="`week`: due today or in the next 6 days"
    ),
    done: bool = Query(default=False, description="true: done tasks instead of open ones"),
) -> Page[TaskOut]:
    """Tasks across every contact, soonest first: what to do today, this week, or late."""
    today = utcnow().date()
    query = select(Task).where(Task.done_at.is_not(None) if done else Task.done_at.is_(None))
    if due == "overdue":
        query = query.where(Task.due_date < today)
    elif due == "today":
        query = query.where(Task.due_date == today)
    elif due == "week":
        query = query.where(Task.due_date >= today, Task.due_date <= today + timedelta(days=6))
    return paginate(session, query, page, TaskOut, *SOONEST_FIRST)


@router.post("/{task_id}/complete")
def complete_task(task_id: int, session: SessionDep) -> TaskOut:
    task = get_or_404(session, Task, task_id)
    # Completing twice keeps the first completion time.
    if task.done_at is None:
        task.done_at = utcnow()
    return _save(session, task)


@router.post("/{task_id}/reopen")
def reopen_task(task_id: int, session: SessionDep) -> TaskOut:
    task = get_or_404(session, Task, task_id)
    task.done_at = None
    return _save(session, task)


@router.get("/{task_id}")
def get_task(task_id: int, session: SessionDep) -> TaskOut:
    return TaskOut.model_validate(get_or_404(session, Task, task_id))


@router.put("/{task_id}")
def update_task(task_id: int, payload: TaskIn, session: SessionDep) -> TaskOut:
    """Change the title, due date or deal. Completion has its own endpoints."""
    task = get_or_404(session, Task, task_id)
    _check_deal(session, payload.deal_id, task.contact_id)
    for field, value in payload.model_dump().items():
        setattr(task, field, value)
    return _save(session, task)


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task(task_id: int, session: SessionDep) -> None:
    session.delete(get_or_404(session, Task, task_id))
    session.commit()
