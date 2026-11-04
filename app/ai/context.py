"""Turn a contact and its history into the text the copilot reads.

The copilot only knows what is written here: no browsing, no other customers.
Keeping this in one function makes it easy to see (and test) exactly what
leaves the CRM.
"""

from dataclasses import dataclass
from datetime import datetime

from app.models import Activity, Contact, Deal

MAX_ACTIVITIES = 50


@dataclass(frozen=True)
class ContactContext:
    contact: Contact
    deals: list[Deal]
    activities: list[Activity]  # newest first
    now: datetime


def render(ctx: ContactContext) -> str:
    c = ctx.contact
    lines = [
        f"Today: {ctx.now:%Y-%m-%d}",
        f"Contact: {c.first_name} {c.last_name}, {c.role or 'role unknown'}",
    ]
    if c.company is not None:
        company = c.company
        details = ", ".join(
            x for x in (company.industry, company.size and f"{company.size} employees") if x
        )
        lines.append(f"Company: {company.name}" + (f" ({details})" if details else ""))

    lines.append("")
    lines.append("Deals:" if ctx.deals else "Deals: none yet")
    for deal in ctx.deals:
        close = f", expected close {deal.expected_close}" if deal.expected_close else ""
        lines.append(f"- {deal.title}: {deal.amount} EUR, stage {deal.stage}{close}")

    shown = ctx.activities[:MAX_ACTIVITIES]
    lines.append("")
    lines.append(f"Activities (newest first, {len(shown)} of {len(ctx.activities)}):")
    if not shown:
        lines.append("- none logged")
    for activity in shown:
        lines.append(f"- {activity.occurred_at:%Y-%m-%d} [{activity.kind}] {activity.subject}")
        if activity.body:
            lines.append(f"  {activity.body}")
    return "\n".join(lines)
