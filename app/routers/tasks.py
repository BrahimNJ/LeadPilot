from fastapi import APIRouter, HTTPException, status

from app.models import Contact, Deal, Task
from app.routers.deps import SessionDep, get_or_404
from app.schemas import TaskIn, TaskOut

# Tasks are created and listed under their contact, and handled on their own after that.
contact_router = APIRouter(prefix="/contacts/{contact_id}/tasks", tags=["tasks"])
router = APIRouter(prefix="/tasks", tags=["tasks"])


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
