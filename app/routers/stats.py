from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import func, select

from app.domain.pipeline import CLOSED_STAGES, Stage
from app.models import Company, Contact, Deal
from app.routers.deps import SessionDep

router = APIRouter(prefix="/stats", tags=["stats"])


class Stats(BaseModel):
    companies: int
    contacts: int
    open_deals: int
    open_pipeline_amount: int
    won_deals: int
    lost_deals: int
    win_rate: float | None


@router.get("")
def overview(session: SessionDep) -> Stats:
    """Headline numbers. `win_rate` is won / (won + lost), null until a deal is closed."""
    deals = {
        stage: (count, amount)
        for stage, count, amount in session.execute(
            select(Deal.stage, func.count(), func.coalesce(func.sum(Deal.amount), 0)).group_by(
                Deal.stage
            )
        )
    }
    open_rows = [row for stage, row in deals.items() if Stage(stage) not in CLOSED_STAGES]
    won = deals.get(Stage.WON, (0, 0))[0]
    lost = deals.get(Stage.LOST, (0, 0))[0]
    return Stats(
        companies=session.scalar(select(func.count()).select_from(Company)) or 0,
        contacts=session.scalar(select(func.count()).select_from(Contact)) or 0,
        open_deals=sum(count for count, _ in open_rows),
        open_pipeline_amount=sum(amount for _, amount in open_rows),
        won_deals=won,
        lost_deals=lost,
        win_rate=round(won / (won + lost), 2) if won + lost else None,
    )
