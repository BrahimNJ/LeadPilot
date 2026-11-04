import json

import anthropic
import httpx2
import pytest

from app.ai.claude import ClaudeCopilot
from app.ai.context import ContactContext
from app.ai.copilot import CopilotRefused, CopilotUnavailable
from app.ai.offline import OfflineCopilot
from app.ai.schemas import LeadScore, ScoreResult
from app.models import Contact, utcnow
from app.routers.copilot import get_copilot


@pytest.fixture
def contact(client):
    return client.post(
        "/contacts",
        json={"first_name": "Ines", "last_name": "Moreau", "email": "ines@helio.fr"},
    ).json()


# --- endpoint, with the offline copilot (the default in tests) --------------------------


def test_offline_score_rewards_an_active_deal(client, contact):
    deal = client.post(
        "/deals", json={"title": "Helio pilot", "amount": 8000, "contact_id": contact["id"]}
    ).json()
    client.post(f"/deals/{deal['id']}/stage", json={"stage": "negotiation"})
    client.post(f"/contacts/{contact['id']}/activities", json={"kind": "call", "subject": "Demo"})

    result = client.post(f"/contacts/{contact['id']}/score").json()

    assert result["model"] == "offline-rules"
    assert result["lead"]["temperature"] == "hot"
    assert "Open deal 'Helio pilot' in negotiation" in result["lead"]["reasons"]
    assert client.get(f"/contacts/{contact['id']}").json()["score"] == result["lead"]["score"]


def test_offline_score_is_cold_without_history(client, contact):
    assert isinstance(client.app.dependency_overrides[get_copilot](), OfflineCopilot)

    result = client.post(f"/contacts/{contact['id']}/score").json()

    assert result["lead"]["temperature"] == "cold"
    assert "No interaction logged yet" in result["lead"]["risks"]


class BrokenCopilot:
    def __init__(self, error):
        self.error = error

    def score_lead(self, ctx):
        raise self.error


@pytest.mark.parametrize(
    ("error", "status"),
    [(CopilotUnavailable("down"), 503), (CopilotRefused("declined"), 422)],
)
def test_copilot_failures_become_clean_http_errors(client, contact, error, status):
    client.app.dependency_overrides[get_copilot] = lambda: BrokenCopilot(error)

    response = client.post(f"/contacts/{contact['id']}/score")

    assert response.status_code == status
    assert response.json()["detail"] == str(error)


# --- Claude copilot, with the real SDK and a fake HTTP transport ------------------------


def claude_with(handler) -> ClaudeCopilot:
    http = httpx2.Client(transport=httpx2.MockTransport(handler))
    client = anthropic.Anthropic(api_key="test-key", http_client=http, max_retries=0)
    return ClaudeCopilot(client, model="claude-opus-5-5", effort="low")


def message(content: str | None, stop_reason: str = "end_turn") -> dict:
    return {
        "id": "msg_test",
        "type": "message",
        "role": "assistant",
        "model": "claude-opus-5-5",
        "content": [] if content is None else [{"type": "text", "text": content}],
        "stop_reason": stop_reason,
        "stop_sequence": None,
        "usage": {"input_tokens": 120, "output_tokens": 40},
    }


def context() -> ContactContext:
    contact = Contact(id=1, first_name="Ines", last_name="Moreau", email="ines@helio.fr")
    return ContactContext(contact=contact, deals=[], activities=[], now=utcnow())


def test_claude_copilot_sends_the_record_and_parses_the_score():
    sent = {}
    answer = {"score": 35, "temperature": "cold", "reasons": ["No deal yet"], "risks": []}

    def handler(request: httpx2.Request) -> httpx2.Response:
        sent.update(json.loads(request.content))
        return httpx2.Response(200, json=message(json.dumps(answer)))

    result = claude_with(handler).score_lead(context())

    assert result == ScoreResult(lead=LeadScore(**answer), model="claude-opus-5-5")
    assert sent["model"] == "claude-opus-5-5"
    assert sent["output_config"]["effort"] == "low"
    assert sent["output_config"]["format"]["type"] == "json_schema"
    assert "<crm_record>" in sent["messages"][0]["content"]
    assert "Ines Moreau" in sent["messages"][0]["content"]


def test_claude_refusal_is_reported_as_refused():
    copilot = claude_with(lambda _: httpx2.Response(200, json=message(None, "refusal")))

    with pytest.raises(CopilotRefused):
        copilot.score_lead(context())


def test_claude_server_error_is_reported_as_unavailable():
    error = {"type": "error", "error": {"type": "api_error", "message": "boom"}}
    copilot = claude_with(lambda _: httpx2.Response(500, json=error))

    with pytest.raises(CopilotUnavailable):
        copilot.score_lead(context())


def test_claude_unparsable_answer_is_reported_as_unavailable():
    copilot = claude_with(lambda _: httpx2.Response(200, json=message('{"score": "high"')))

    with pytest.raises(CopilotUnavailable, match="could not be read"):
        copilot.score_lead(context())


# --- insights and follow-up drafts ------------------------------------------------------


def test_insights_for_a_new_contact_suggest_a_discovery_call(client, contact):
    insights = client.post(f"/contacts/{contact['id']}/insights").json()

    assert insights["next_action"] == "Book a discovery call with Ines."
    assert insights["open_questions"]


def test_insights_mention_the_latest_interaction(client, contact):
    client.post(
        f"/contacts/{contact['id']}/activities",
        json={
            "kind": "meeting",
            "subject": "Security review",
            "occurred_at": "2026-11-02T10:00:00Z",
        },
    )

    insights = client.post(f"/contacts/{contact['id']}/insights").json()

    assert "2026-11-02: Security review" in insights["summary"]


@pytest.mark.parametrize(("language", "greeting"), [("fr", "Bonjour Ines"), ("en", "Hi Ines")])
def test_follow_up_draft_in_the_requested_language(client, contact, language, greeting):
    draft = client.post(f"/contacts/{contact['id']}/follow-up", json={"language": language}).json()

    assert draft["body"].startswith(greeting)


def test_follow_up_draft_is_not_stored_as_an_activity(client, contact):
    client.post(f"/contacts/{contact['id']}/follow-up", json={})

    assert client.get(f"/contacts/{contact['id']}/activities").json()["total"] == 0


def test_claude_follow_up_prompt_carries_language_and_goal():
    sent = {}

    def handler(request: httpx2.Request) -> httpx2.Response:
        sent.update(json.loads(request.content))
        return httpx2.Response(200, json=message('{"subject": "Suivi", "body": "Bonjour"}'))

    draft = claude_with(handler).draft_follow_up(context(), "fr", "Fix a date for the demo")

    prompt = sent["messages"][0]["content"]
    assert draft.subject == "Suivi"
    assert "in French" in prompt
    assert "Fix a date for the demo" in prompt
