from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field

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
