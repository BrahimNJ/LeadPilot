import pytest

from app.domain.pipeline import Stage, TransitionError, check_transition

ALLOWED = [
    (Stage.LEAD, Stage.QUALIFIED),
    (Stage.LEAD, Stage.PROPOSAL),
    (Stage.QUALIFIED, Stage.NEGOTIATION),
    (Stage.PROPOSAL, Stage.NEGOTIATION),
    (Stage.NEGOTIATION, Stage.WON),
    (Stage.LEAD, Stage.LOST),
    (Stage.NEGOTIATION, Stage.LOST),
]

REFUSED = [
    (Stage.PROPOSAL, Stage.QUALIFIED, "back"),
    (Stage.LEAD, Stage.WON, "only be won from negotiation"),
    (Stage.WON, Stage.LOST, "can no longer move"),
    (Stage.LOST, Stage.LEAD, "can no longer move"),
    (Stage.LEAD, Stage.LEAD, "already"),
]


@pytest.mark.parametrize(("current", "target"), ALLOWED)
def test_allowed_transitions(current, target):
    check_transition(current, target)


@pytest.mark.parametrize(("current", "target", "reason"), REFUSED)
def test_refused_transitions(current, target, reason):
    with pytest.raises(TransitionError, match=reason):
        check_transition(current, target)
