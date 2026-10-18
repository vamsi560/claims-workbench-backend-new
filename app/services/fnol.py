from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.models import WorkItem

FNOL_FIELD_KEYS = (
    "policy_number",
    "claim_number",
    "line_of_business",
    "policy_holder_name",
    "claimant_name",
    "reporter_name",
    "reporter_email",
    "reporter_phone",
    "loss_datetime",
    "loss_timezone",
    "loss_location",
    "loss_type",
    "loss_cause",
    "loss_description",
    "injured",
    "police_report_number",
    "vehicle_identifiers",
    "extra_fields",
)


class VehicleIdentifier(BaseModel):
    vin: str | None = None
    plate: str | None = None
    make: str | None = None
    model: str | None = None
    year: int | str | None = None


class FnolExtraction(BaseModel):
    policy_number: str | None = None
    claim_number: str | None = None
    line_of_business: str | None = None
    policy_holder_name: str | None = None
    claimant_name: str | None = None
    reporter_name: str | None = None
    reporter_email: str | None = None
    reporter_phone: str | None = None
    loss_datetime: datetime | None = None
    loss_timezone: str | None = None
    loss_location: str | None = None
    loss_type: str | None = None
    loss_cause: str | None = None
    loss_description: str | None = None
    injured: bool | None = None
    police_report_number: str | None = None
    vehicle_identifiers: list[VehicleIdentifier] = Field(default_factory=list)
    extra_fields: dict[str, Any] = Field(default_factory=dict)
    field_confidence: dict[str, float] = Field(default_factory=dict)


def _empty(value: Any) -> bool:
    return value is None or value == "" or value == [] or value == {}


def apply_fnol_fields(item: WorkItem, extraction: FnolExtraction, *, overwrite: bool) -> None:
    dumped = extraction.model_dump(mode="json", exclude={"field_confidence"})
    item.extracted_fields = {**(item.extracted_fields or {}), **dumped}
    item.field_confidence = extraction.field_confidence or {}

    for key in FNOL_FIELD_KEYS:
        value = getattr(extraction, key)
        if key == "vehicle_identifiers":
            value = [row.model_dump(exclude_none=True) for row in extraction.vehicle_identifiers]
            if not value:
                continue
        elif key == "extra_fields":
            if not extraction.extra_fields:
                continue
            current = item.extra_fields or {}
            item.extra_fields = {**current, **extraction.extra_fields} if not overwrite else extraction.extra_fields
            continue
        if _empty(value):
            continue
        current = getattr(item, key)
        if overwrite or _empty(current):
            setattr(item, key, value)
