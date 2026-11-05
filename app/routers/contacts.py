from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, or_, select

from app.models import Company, Contact
from app.routers.deps import PaginationDep, SessionDep, commit_or_409, get_or_404
from app.schemas import ContactIn, ContactOut, Page

router = APIRouter(prefix="/contacts", tags=["contacts"])


def _check_company(session: SessionDep, company_id: int | None) -> None:
    if company_id is not None and session.get(Company, company_id) is None:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, f"company {company_id} not found"
        )


def _save(session: SessionDep, contact: Contact) -> ContactOut:
    commit_or_409(session, f"a contact with email {contact.email!r} already exists")
    session.refresh(contact)
    return ContactOut.model_validate(contact)


@router.post("", status_code=status.HTTP_201_CREATED)
def create_contact(payload: ContactIn, session: SessionDep) -> ContactOut:
    _check_company(session, payload.company_id)
    contact = Contact(**payload.model_dump())
    session.add(contact)
    return _save(session, contact)


@router.get("")
def list_contacts(
    session: SessionDep,
    page: PaginationDep,
    q: str | None = Query(default=None, description="Search in names and email"),
    company_id: int | None = None,
    min_score: int | None = Query(
        default=None, ge=0, le=100, description="Only contacts the copilot scored at least this"
    ),
) -> Page[ContactOut]:
    query = select(Contact)
    if q:
        pattern = f"%{q.lower()}%"
        query = query.where(
            or_(
                func.lower(Contact.first_name).like(pattern),
                func.lower(Contact.last_name).like(pattern),
                func.lower(Contact.email).like(pattern),
            )
        )
    if company_id is not None:
        query = query.where(Contact.company_id == company_id)
    if min_score is not None:
        query = query.where(Contact.score >= min_score)

    total = session.scalar(select(func.count()).select_from(query.subquery())) or 0
    rows = session.scalars(
        query.order_by(Contact.last_name, Contact.first_name).limit(page.limit).offset(page.offset)
    )
    return Page(
        items=[ContactOut.model_validate(c) for c in rows],
        total=total,
        limit=page.limit,
        offset=page.offset,
    )


@router.get("/{contact_id}")
def get_contact(contact_id: int, session: SessionDep) -> ContactOut:
    return ContactOut.model_validate(get_or_404(session, Contact, contact_id))


@router.put("/{contact_id}")
def update_contact(contact_id: int, payload: ContactIn, session: SessionDep) -> ContactOut:
    contact = get_or_404(session, Contact, contact_id)
    _check_company(session, payload.company_id)
    for field, value in payload.model_dump().items():
        setattr(contact, field, value)
    return _save(session, contact)


@router.delete("/{contact_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_contact(contact_id: int, session: SessionDep) -> None:
    session.delete(get_or_404(session, Contact, contact_id))
    session.commit()
