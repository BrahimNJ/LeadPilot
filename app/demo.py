"""Sample data for the public demo, so the API has something to show on first visit."""

from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.pipeline import CLOSED_STAGES, Stage
from app.models import Activity, Company, Contact, Deal, utcnow

COMPANIES = [
    ("Kibo Logistics", "kibo.example.com", "Logistics", "201-1000"),
    ("Brightwave Studio", "brightwave.example.org", "Media", "11-50"),
    ("Nordlicht Energie", "nordlicht.example.net", "Energy", "1000+"),
]

# first name, last name, email, role, company index
CONTACTS = [
    ("Sarah", "Klein", "sarah.klein@kibo.example.com", "CTO", 0),
    ("Yanis", "Morel", "yanis.morel@kibo.example.com", "Head of Operations", 0),
    ("Ines", "Garcia", "ines@brightwave.example.org", "Founder", 1),
    ("Lukas", "Weber", "l.weber@nordlicht.example.net", "Procurement Manager", 2),
    ("Amara", "Diallo", "amara.diallo@example.com", "Freelance consultant", None),
]

# title, amount, stage, contact index
DEALS = [
    ("Route planning pilot", 15000, Stage.NEGOTIATION, 0),
    ("Warehouse dashboard", 8000, Stage.QUALIFIED, 1),
    ("Studio CRM setup", 3500, Stage.WON, 2),
    ("Energy sales team rollout", 42000, Stage.PROPOSAL, 3),
    ("Consulting partnership", 6000, Stage.LOST, 4),
]

# contact index, kind, subject, body, days ago
ACTIVITIES = [
    (0, "meeting", "Demo with the tech team", "They want an API to plug into their TMS.", 2),
    (0, "email", "Security questionnaire sent", "Waiting for their answers.", 9),
    (1, "call", "Discovery call", "Pain point: weekly reporting done by hand.", 15),
    (2, "note", "Contract signed", "Kick-off planned next month.", 20),
    (3, "email", "Proposal sent", "Three options, from 30k to 50k.", 6),
    (3, "call", "Follow-up on the proposal", "Budget approval expected next quarter.", 1),
    (4, "call", "Intro call", "No budget this year.", 45),
]


def seed_demo(session: Session) -> bool:
    """Add the demo records to an empty database. Returns False if data was already there."""
    if session.scalar(select(Company.id).limit(1)) is not None:
        return False

    now = utcnow()
    companies = [Company(name=n, domain=d, industry=i, size=s) for n, d, i, s in COMPANIES]
    contacts = [
        Contact(
            first_name=first,
            last_name=last,
            email=email,
            role=role,
            company=companies[c] if c is not None else None,
        )
        for first, last, email, role, c in CONTACTS
    ]
    deals = [
        Deal(
            title=title,
            amount=amount,
            stage=stage,
            contact=contacts[c],
            expected_close=(now + timedelta(days=45)).date(),
            closed_at=now - timedelta(days=20) if stage in CLOSED_STAGES else None,
        )
        for title, amount, stage, c in DEALS
    ]
    activities = [
        Activity(
            contact=contacts[c],
            kind=kind,
            subject=subject,
            body=body,
            occurred_at=now - timedelta(days=days),
        )
        for c, kind, subject, body, days in ACTIVITIES
    ]
    # Same rule as the API: last contact = most recent activity.
    for contact in contacts:
        times = [a.occurred_at for a in activities if a.contact is contact]
        contact.last_contacted_at = max(times, default=None)

    session.add_all([*companies, *contacts, *deals, *activities])
    session.commit()
    return True
