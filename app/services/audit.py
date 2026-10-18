from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import WorkItem, WorkItemAudit, WorkItemStatus


def snapshot_fields(item: WorkItem) -> dict[str, Any]:
    return {
        "status": item.status.value,
        "assigned_to": item.assigned_to,
        "policy_number": item.policy_number,
        "claim_number": item.claim_number,
        "line_of_business": item.line_of_business,
        "policy_holder_name": item.policy_holder_name,
        "claimant_name": item.claimant_name,
        "reporter_name": item.reporter_name,
        "reporter_email": item.reporter_email,
        "reporter_phone": item.reporter_phone,
        "loss_datetime": item.loss_datetime.isoformat() if item.loss_datetime else None,
        "loss_timezone": item.loss_timezone,
        "loss_location": item.loss_location,
        "loss_type": item.loss_type,
        "loss_cause": item.loss_cause,
        "loss_description": item.loss_description,
        "injured": item.injured,
        "police_report_number": item.police_report_number,
        "vehicle_identifiers": item.vehicle_identifiers,
        "extra_fields": item.extra_fields,
        "duplicate_of_id": str(item.duplicate_of_id) if item.duplicate_of_id else None,
    }


async def write_audit(
    db: AsyncSession,
    work_item_id: UUID,
    action: str,
    before: dict[str, Any] | None,
    after: dict[str, Any] | None,
    actor: str | None = None,
) -> None:
    db.add(
        WorkItemAudit(
            work_item_id=work_item_id,
            actor=actor,
            action=action,
            before_json=before,
            after_json=after,
        )
    )


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def apply_status(item: WorkItem, status: WorkItemStatus) -> None:
    item.status = status
    if status == WorkItemStatus.assigned and item.assigned_to is None:
        raise ValueError("Cannot mark assigned without assigned_to")
