"""Load the eval datasets and turn each case into the record the copilot reads."""

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Literal, cast

import yaml

from app.ai.context import ContactContext
from app.domain.pipeline import Stage
from app.models import Activity, Company, Contact, Deal

DATASETS = Path(__file__).parent / "datasets"

Temperature = Literal["hot", "warm", "cold"]
TEMPERATURES: tuple[Temperature, ...] = ("hot", "warm", "cold")
ACTIVITY_KINDS = ("note", "call", "email", "meeting")


class DatasetError(ValueError):
    """A dataset file or one of its cases is malformed."""


@dataclass(frozen=True)
class Case:
    id: str
    description: str
    temperature: Temperature
    band: tuple[int, int]
    record: dict[str, Any]  # contact, company, deals and activities as written in the file


def load_cases(name: str, directory: Path = DATASETS) -> list[Case]:
    """Read `<directory>/<name>.yaml`, check every case, and return them in file order."""
    raw = yaml.safe_load((directory / f"{name}.yaml").read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or not isinstance(raw.get("cases"), list):
        raise DatasetError(f"{name}: expected a top-level 'cases' list")

    cases = [_parse_case(item, name) for item in raw["cases"]]
    seen: set[str] = set()
    for case in cases:
        if case.id in seen:
            raise DatasetError(f"{name}: duplicate case id {case.id!r}")
        seen.add(case.id)
    return cases


def _parse_case(item: object, name: str) -> Case:
    if not isinstance(item, dict):
        raise DatasetError(f"{name}: every case must be a mapping")
    case_id = item.get("id")
    where = f"{name}/{case_id}"
    if not isinstance(case_id, str) or not isinstance(item.get("description"), str):
        raise DatasetError(f"{where}: 'id' and 'description' are required strings")

    contact = item.get("contact")
    if not isinstance(contact, dict) or not all(
        isinstance(contact.get(k), str) for k in ("first_name", "last_name", "email")
    ):
        raise DatasetError(f"{where}: contact needs first_name, last_name and email")

    expected = item.get("expected")
    if not isinstance(expected, dict) or expected.get("temperature") not in TEMPERATURES:
        raise DatasetError(f"{where}: expected.temperature must be one of {TEMPERATURES}")
    band = expected.get("band")
    if not (
        isinstance(band, list)
        and len(band) == 2
        and all(isinstance(b, int) for b in band)
        and 0 <= band[0] <= band[1] <= 100
    ):
        raise DatasetError(f"{where}: expected.band must be [min, max] within 0-100")

    return Case(
        id=case_id,
        description=item["description"],
        temperature=cast(Temperature, expected["temperature"]),
        band=(band[0], band[1]),
        record=item,
    )


def build_context(case: Case, now: datetime) -> ContactContext:
    """Build the same ContactContext the API builds from the database, without a database.

    The copilot reads it through `app.ai.context.render`, so the eval sends the model exactly
    what production sends: no email address, no phone number.
    """
    rec = case.record
    c = rec["contact"]
    contact = Contact(id=1, first_name=c["first_name"], last_name=c["last_name"], email=c["email"])
    contact.role = c.get("role")
    if company := rec.get("company"):
        contact.company = Company(
            name=company["name"], industry=company.get("industry"), size=company.get("size")
        )

    deals = [
        Deal(
            title=d["title"],
            amount=int(d["amount"]),
            stage=Stage(d["stage"]),
            expected_close=_in_days(now, d.get("close_in_days")),
        )
        for d in rec.get("deals") or []
    ]

    activities = []
    for a in rec.get("activities") or []:
        if a["kind"] not in ACTIVITY_KINDS:
            raise DatasetError(f"{case.id}: unknown activity kind {a['kind']!r}")
        activities.append(
            Activity(
                kind=a["kind"],
                subject=a["subject"],
                body=a.get("body", ""),
                occurred_at=now - timedelta(days=int(a["days_ago"])),
            )
        )
    activities.sort(key=lambda a: a.occurred_at, reverse=True)  # newest first, as in the API

    return ContactContext(contact=contact, deals=deals, activities=activities, now=now)


def _in_days(now: datetime, days: int | None) -> date | None:
    return None if days is None else (now + timedelta(days=days)).date()
