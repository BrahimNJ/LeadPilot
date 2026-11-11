import csv
import io
from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, Query, Response, status
from sqlalchemy import Select, func, or_, select
from sqlalchemy.orm import selectinload

from app.models import Company, Contact
from app.routers.deps import PaginationDep, SessionDep, commit_or_409, contains, get_or_404
from app.schemas import ContactIn, ContactOut, Page

router = APIRouter(prefix="/contacts", tags=["contacts"])

SearchQ = Annotated[str | None, Query(max_length=100, description="Search in names and email")]
MinScore = Annotated[
    int | None, Query(ge=0, le=100, description="Only contacts the copilot scored at least this")
]
BY_NAME = (Contact.last_name, Contact.first_name, Contact.id)


def _filtered(q: str | None, company_id: int | None, min_score: int | None) -> Select[Contact]:
    """The contacts matching the filters shared by the list and the export."""
    query = select(Contact)
    if q:
        query = query.where(
            or_(
                contains(Contact.first_name, q),
                contains(Contact.last_name, q),
                contains(Contact.email, q),
            )
        )
    if company_id is not None:
        query = query.where(Contact.company_id == company_id)
    if min_score is not None:
        query = query.where(Contact.score >= min_score)
    return query


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
    q: SearchQ = None,
    company_id: int | None = None,
    sort: Literal["name", "score"] = Query(
        default="name", description="`score`: best leads first, unscored contacts last"
    ),
    min_score: MinScore = None,
) -> Page[ContactOut]:
    query = _filtered(q, company_id, min_score)

    total = session.scalar(select(func.count()).select_from(query.subquery())) or 0
    order = (Contact.score.desc().nulls_last(), *BY_NAME) if sort == "score" else BY_NAME
    rows = session.scalars(query.order_by(*order).limit(page.limit).offset(page.offset))
    return Page(
        items=[ContactOut.model_validate(c) for c in rows],
        total=total,
        limit=page.limit,
        offset=page.offset,
    )


MAX_EXPORT_ROWS = 10_000
# A cell starting with one of these runs as a formula when the file is opened in a spreadsheet.
_FORMULA_STARTS = ("=", "+", "-", "@", "\t", "\r")


def _safe_cell(value: object) -> object:
    """Make text that a spreadsheet would run as a formula display as plain text instead."""
    if isinstance(value, str) and value.startswith(_FORMULA_STARTS):
        return "'" + value
    return value


EXPORT_COLUMNS = [
    "id",
    "first_name",
    "last_name",
    "email",
    "phone",
    "role",
    "company",
    "score",
    "last_contacted_at",
]


# Declared before /{contact_id}, which would otherwise try to read "export" as an ID.
@router.get(
    "/export",
    response_class=Response,
    responses={200: {"content": {"text/csv": {}}, "description": "The contacts as CSV"}},
)
def export_contacts(
    session: SessionDep,
    q: SearchQ = None,
    company_id: int | None = None,
    min_score: MinScore = None,
) -> Response:
    """Download the matching contacts as a CSV file (10,000 rows at most), sorted by name."""
    query = _filtered(q, company_id, min_score).options(selectinload(Contact.company))
    rows = session.scalars(query.order_by(*BY_NAME).limit(MAX_EXPORT_ROWS))

    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(EXPORT_COLUMNS)
    for c in rows:
        last = c.last_contacted_at.isoformat() if c.last_contacted_at else ""
        company = c.company.name if c.company else ""
        cells = [c.id, c.first_name, c.last_name, c.email, c.phone, c.role, company, c.score, last]
        writer.writerow(["" if cell is None else _safe_cell(cell) for cell in cells])
    return Response(
        out.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="leadpilot-contacts.csv"'},
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
