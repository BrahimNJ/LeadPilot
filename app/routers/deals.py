from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, select

from app.domain.pipeline import CLOSED_STAGES, Stage, TransitionError, check_transition
from app.models import Contact, Deal, utcnow
from app.routers.deps import PaginationDep, SessionDep, get_or_404, paginate
from app.schemas import DealIn, DealOut, Page, PipelineStage, StageChange

router = APIRouter(prefix="/deals", tags=["deals"])


def _check_contact(session: SessionDep, contact_id: int) -> None:
    if session.get(Contact, contact_id) is None:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, f"contact {contact_id} not found"
        )


@router.post("", status_code=status.HTTP_201_CREATED)
def create_deal(payload: DealIn, session: SessionDep) -> DealOut:
    _check_contact(session, payload.contact_id)
    deal = Deal(**payload.model_dump())
    session.add(deal)
    session.commit()
    session.refresh(deal)
    return DealOut.model_validate(deal)


@router.get("")
def list_deals(
    session: SessionDep,
    page: PaginationDep,
    stage: Stage | None = None,
    contact_id: int | None = None,
    overdue: bool = Query(
        default=False, description="Only open deals whose expected close date has passed"
    ),
) -> Page[DealOut]:
    query = select(Deal)
    if overdue:
        query = query.where(
            Deal.stage.not_in(list(CLOSED_STAGES)), Deal.expected_close < utcnow().date()
        )
    if stage is not None:
        query = query.where(Deal.stage == stage)
    if contact_id is not None:
        query = query.where(Deal.contact_id == contact_id)

    return paginate(session, query, page, DealOut, Deal.created_at.desc(), Deal.id.desc())


@router.get("/pipeline")
def pipeline_summary(session: SessionDep) -> list[PipelineStage]:
    totals = select(Deal.stage, func.count(), func.coalesce(func.sum(Deal.amount), 0))
    found = {
        stage: (count, amount)
        for stage, count, amount in session.execute(totals.group_by(Deal.stage))
    }
    # Empty stages are listed too, so a board can render every column.
    summary = []
    for stage in Stage:
        count, amount = found.get(stage, (0, 0))
        summary.append(PipelineStage(stage=stage, deals=count, amount=amount))
    return summary


@router.get("/{deal_id}")
def get_deal(deal_id: int, session: SessionDep) -> DealOut:
    return DealOut.model_validate(get_or_404(session, Deal, deal_id))


@router.put("/{deal_id}")
def update_deal(deal_id: int, payload: DealIn, session: SessionDep) -> DealOut:
    """Edit the deal's details. The stage only changes through `POST /deals/{id}/stage`."""
    deal = get_or_404(session, Deal, deal_id)
    _check_contact(session, payload.contact_id)
    for field, value in payload.model_dump().items():
        setattr(deal, field, value)
    session.commit()
    session.refresh(deal)
    return DealOut.model_validate(deal)


@router.delete("/{deal_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_deal(deal_id: int, session: SessionDep) -> None:
    session.delete(get_or_404(session, Deal, deal_id))
    session.commit()


@router.post("/{deal_id}/stage")
def move_deal(deal_id: int, payload: StageChange, session: SessionDep) -> DealOut:
    deal = get_or_404(session, Deal, deal_id)
    try:
        check_transition(Stage(deal.stage), payload.stage)
    except TransitionError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from None

    deal.stage = payload.stage
    if payload.stage in (Stage.WON, Stage.LOST):
        deal.closed_at = utcnow()
    session.commit()
    session.refresh(deal)
    return DealOut.model_validate(deal)
