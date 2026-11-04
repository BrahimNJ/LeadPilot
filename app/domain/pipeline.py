"""Sales pipeline rules, kept free of any web or database code."""

from enum import StrEnum


class Stage(StrEnum):
    LEAD = "lead"
    QUALIFIED = "qualified"
    PROPOSAL = "proposal"
    NEGOTIATION = "negotiation"
    WON = "won"
    LOST = "lost"


OPEN_STAGES: tuple[Stage, ...] = (
    Stage.LEAD,
    Stage.QUALIFIED,
    Stage.PROPOSAL,
    Stage.NEGOTIATION,
)
CLOSED_STAGES = frozenset({Stage.WON, Stage.LOST})


class TransitionError(ValueError):
    pass


def check_transition(current: Stage, target: Stage) -> None:
    """Raise `TransitionError` unless a deal may move from `current` to `target`.

    Deals only move forward. Skipping stages is fine (a warm referral can go
    straight to proposal), going back is not: it would hide how long a deal
    really took. Any open deal can be lost; only a deal in negotiation can be won.
    """
    if current == target:
        raise TransitionError(f"deal is already {current}")
    if current in CLOSED_STAGES:
        raise TransitionError(f"deal is {current} and can no longer move")
    if target == Stage.LOST:
        return
    if target == Stage.WON:
        if current != Stage.NEGOTIATION:
            raise TransitionError("a deal can only be won from negotiation")
        return
    if OPEN_STAGES.index(target) < OPEN_STAGES.index(current):
        raise TransitionError(f"cannot move a deal back from {current} to {target}")
