from datetime import date, datetime
from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, EmailStr, Field

from app.domain.pipeline import Stage

ActivityKind = Literal["note", "call", "email", "meeting"]
CompanySize = Literal["1-10", "11-50", "51-200", "201-1000", "1000+"]


class Page[T](BaseModel):
    items: list[T]
    total: int
    limit: int
    offset: int


class CompanyIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    domain: str | None = Field(default=None, max_length=253, examples=["acme.fr"])
    industry: str | None = Field(default=None, max_length=100)
    size: CompanySize | None = None


class CompanyOut(CompanyIn):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime


class ContactIn(BaseModel):
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    email: EmailStr
    phone: str | None = Field(default=None, max_length=40)
    role: str | None = Field(default=None, max_length=120, examples=["Head of Sales"])
    company_id: int | None = None


class ContactOut(ContactIn):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    last_contacted_at: datetime | None


class DealIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    amount: int = Field(ge=0, description="Estimated value in euros")
    contact_id: int
    expected_close: date | None = None


class DealOut(DealIn):
    model_config = ConfigDict(from_attributes=True)

    id: int
    stage: Stage
    created_at: datetime
    closed_at: datetime | None


class StageChange(BaseModel):
    stage: Stage


class PipelineStage(BaseModel):
    stage: Stage
    deals: int
    amount: int


class ActivityIn(BaseModel):
    kind: ActivityKind
    subject: str = Field(min_length=1, max_length=200)
    body: str = Field(default="", max_length=10_000)
    occurred_at: AwareDatetime | None = Field(
        default=None, description="When it happened; defaults to now"
    )


class ActivityOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    contact_id: int
    kind: ActivityKind
    subject: str
    body: str
    occurred_at: datetime
