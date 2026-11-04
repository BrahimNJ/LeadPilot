from typing import Protocol

from app.ai.context import ContactContext
from app.ai.schemas import ScoreResult


class CopilotError(Exception):
    """Base class for failures the API turns into clean HTTP errors."""


class CopilotUnavailable(CopilotError):
    """The model could not be reached or did not return a usable answer."""


class CopilotRefused(CopilotError):
    """The model declined the request."""


class Copilot(Protocol):
    """What the rest of the app needs from an AI copilot.

    Routers depend on this protocol, never on an SDK, so the provider can be
    swapped (or faked in tests) without touching the domain.
    """

    def score_lead(self, ctx: ContactContext) -> ScoreResult: ...
