from fastapi import APIRouter, Query, status
from sqlalchemy import func, or_, select

from app.models import Company, Contact
from app.routers.deps import PaginationDep, SessionDep, commit_or_409, contains, get_or_404
from app.schemas import CompanyIn, CompanyOut, ContactOut, Page

router = APIRouter(prefix="/companies", tags=["companies"])


def _save(session: SessionDep, company: Company) -> CompanyOut:
    commit_or_409(session, f"a company with domain {company.domain!r} already exists")
    session.refresh(company)
    return CompanyOut.model_validate(company)


@router.post("", status_code=status.HTTP_201_CREATED)
def create_company(payload: CompanyIn, session: SessionDep) -> CompanyOut:
    company = Company(**payload.model_dump())
    session.add(company)
    return _save(session, company)


@router.get("")
def list_companies(
    session: SessionDep,
    page: PaginationDep,
    q: str | None = Query(default=None, max_length=100, description="Search in names and domains"),
) -> Page[CompanyOut]:
    query = select(Company)
    if q:
        query = query.where(or_(contains(Company.name, q), contains(Company.domain, q)))

    total = session.scalar(select(func.count()).select_from(query.subquery())) or 0
    rows = session.scalars(
        query.order_by(Company.name, Company.id).limit(page.limit).offset(page.offset)
    )
    return Page(
        items=[CompanyOut.model_validate(c) for c in rows],
        total=total,
        limit=page.limit,
        offset=page.offset,
    )


@router.get("/{company_id}")
def get_company(company_id: int, session: SessionDep) -> CompanyOut:
    return CompanyOut.model_validate(get_or_404(session, Company, company_id))


@router.get("/{company_id}/contacts")
def company_contacts(company_id: int, session: SessionDep, page: PaginationDep) -> Page[ContactOut]:
    get_or_404(session, Company, company_id)
    query = select(Contact).where(Contact.company_id == company_id)

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


@router.put("/{company_id}")
def update_company(company_id: int, payload: CompanyIn, session: SessionDep) -> CompanyOut:
    company = get_or_404(session, Company, company_id)
    for field, value in payload.model_dump().items():
        setattr(company, field, value)
    return _save(session, company)


@router.delete("/{company_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_company(company_id: int, session: SessionDep) -> None:
    session.delete(get_or_404(session, Company, company_id))
    session.commit()
