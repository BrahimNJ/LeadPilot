from typing import Literal

from pydantic import BaseModel, Field


class LeadScore(BaseModel):
    """What the copilot returns when asked how promising a contact is."""

    score: int = Field(ge=0, le=100, description="0 = not a lead, 100 = ready to sign")
    temperature: Literal["hot", "warm", "cold"]
    reasons: list[str] = Field(description="Short facts from the record that support the score")
    risks: list[str] = Field(description="What could make this deal slip or fail")


class ScoreResult(BaseModel):
    """A score plus where it came from, so it can be audited later."""

    lead: LeadScore
    model: str


class Insights(BaseModel):
    """A ten-second read of where the relationship stands."""

    summary: str = Field(description="Three sentences at most")
    open_questions: list[str] = Field(description="What we still do not know and need to ask")
    next_action: str = Field(description="One concrete next step for the salesperson")


Language = Literal["fr", "en"]


class FollowUpDraft(BaseModel):
    """An email the salesperson reviews and sends themselves."""

    subject: str
    body: str
