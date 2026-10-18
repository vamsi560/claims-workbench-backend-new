from datetime import datetime
from math import ceil
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import get_settings
from app.database import get_db
from app.models import (
    Attachment,
    DuplicateCandidate,
    DuplicateMatchType,
    Email,
    GuidewireSubmission,
    GuidewireTarget,
    ProcessingJob,
    WorkItem,
    WorkItemAudit,
    WorkItemEmail,
    WorkItemStatus,
)
from app.schemas.work_items import (
    AssignRequest,
    AttachmentOut,
    AuditOut,
    DuplicateCandidateOut,
    EmailOut,
    GuidewireSubmitRequest,
    JobOut,
    SasResponse,
    StatusRequest,
    WorkItemDetail,
    WorkItemListItem,
    WorkItemListResponse,
    WorkItemPatch,
)
from app.services.audit import snapshot_fields, utcnow, write_audit
from app.services.blob_sas import build_read_sas
from app.services.queue import get_queue_publisher

router = APIRouter(prefix="/work-items", tags=["work-items"])


async def _get_item(db: AsyncSession, work_item_id: UUID) -> WorkItem:
    item = (await db.execute(select(WorkItem).where(WorkItem.id == work_item_id))).scalar_one_or_none()
    if item is None:
        raise HTTPException(status_code=404, detail="Work item not found")
    return item


@router.get("", response_model=WorkItemListResponse)
async def list_work_items(
    db: AsyncSession = Depends(get_db),
    status: WorkItemStatus | None = Query(default=None),
    assigned_to: str | None = Query(default=None, alias="assignedTo"),
    q: str | None = Query(default=None),
    date_from: datetime | None = Query(default=None, alias="dateFrom"),
    date_to: datetime | None = Query(default=None, alias="dateTo"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100, alias="pageSize"),
):
    stmt = select(WorkItem)
    count_stmt = select(func.count()).select_from(WorkItem)
    if status:
        stmt = stmt.where(WorkItem.status == status)
        count_stmt = count_stmt.where(WorkItem.status == status)
    if assigned_to:
        stmt = stmt.where(WorkItem.assigned_to == assigned_to)
        count_stmt = count_stmt.where(WorkItem.assigned_to == assigned_to)
    if date_from:
        stmt = stmt.where(WorkItem.created_at >= date_from)
        count_stmt = count_stmt.where(WorkItem.created_at >= date_from)
    if date_to:
        stmt = stmt.where(WorkItem.created_at <= date_to)
        count_stmt = count_stmt.where(WorkItem.created_at <= date_to)
    if q:
        like = f"%{q}%"
        filt = or_(
            WorkItem.work_item_number.ilike(like),
            WorkItem.policy_number.ilike(like),
            WorkItem.policy_holder_name.ilike(like),
            WorkItem.claimant_name.ilike(like),
            WorkItem.claim_number.ilike(like),
        )
        stmt = stmt.where(filt)
        count_stmt = count_stmt.where(filt)

    total = (await db.execute(count_stmt)).scalar_one()
    rows = (
        await db.execute(
            stmt.order_by(WorkItem.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
        )
    ).scalars().all()
    return WorkItemListResponse(
        items=[WorkItemListItem.model_validate(row) for row in rows],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=ceil(total / page_size) if total else 0,
    )


@router.get("/{work_item_id}", response_model=WorkItemDetail)
async def get_work_item(work_item_id: UUID, db: AsyncSession = Depends(get_db)):
    item = await _get_item(db, work_item_id)
    links = (
        await db.execute(
            select(WorkItemEmail)
            .options(selectinload(WorkItemEmail.email).selectinload(Email.attachments))
            .where(WorkItemEmail.work_item_id == item.id)
        )
    ).scalars().all()
    emails: list[EmailOut] = []
    for link in sorted(links, key=lambda row: row.email.received_at):
        emails.append(
            EmailOut(
                id=link.email.id,
                subject=link.email.subject,
                body_text=link.email.body_text,
                sender_email=link.email.sender_email,
                sender_name=link.email.sender_name,
                received_at=link.email.received_at,
                status=link.email.status.value,
                is_root=link.is_root,
                attachments=[AttachmentOut.model_validate(att) for att in link.email.attachments],
            )
        )
    duplicates = (
        await db.execute(select(DuplicateCandidate).where(DuplicateCandidate.work_item_id == item.id))
    ).scalars().all()
    jobs = (
        await db.execute(
            select(ProcessingJob)
            .where(ProcessingJob.work_item_id == item.id)
            .order_by(ProcessingJob.created_at.desc())
        )
    ).scalars().all()
    audit = (
        await db.execute(
            select(WorkItemAudit)
            .where(WorkItemAudit.work_item_id == item.id)
            .order_by(WorkItemAudit.created_at.desc())
        )
    ).scalars().all()
    detail = WorkItemDetail.model_validate(item)
    return detail.model_copy(
        update={
            "emails": emails,
            "duplicates": [DuplicateCandidateOut.model_validate(row) for row in duplicates],
            "jobs": [JobOut.model_validate(row) for row in jobs],
            "audit": [AuditOut.model_validate(row) for row in audit],
        }
    )


@router.patch("/{work_item_id}", response_model=WorkItemDetail)
async def patch_work_item(
    work_item_id: UUID,
    body: WorkItemPatch,
    db: AsyncSession = Depends(get_db),
):
    item = await _get_item(db, work_item_id)
    before = snapshot_fields(item)
    data = body.model_dump(exclude_unset=True)
    for key, value in data.items():
        setattr(item, key, value)
    await write_audit(db, item.id, "fields_updated", before, snapshot_fields(item))
    await db.commit()
    return await get_work_item(work_item_id, db)


@router.post("/{work_item_id}/assign", response_model=WorkItemDetail)
async def assign_work_item(work_item_id: UUID, body: AssignRequest, db: AsyncSession = Depends(get_db)):
    item = await _get_item(db, work_item_id)
    before = snapshot_fields(item)
    item.assigned_to = body.assigned_to
    item.assigned_at = utcnow()
    item.status = WorkItemStatus.assigned
    await write_audit(db, item.id, "assigned", before, snapshot_fields(item))
    await db.commit()
    return await get_work_item(work_item_id, db)


@router.post("/{work_item_id}/status", response_model=WorkItemDetail)
async def set_status(work_item_id: UUID, body: StatusRequest, db: AsyncSession = Depends(get_db)):
    item = await _get_item(db, work_item_id)
    before = snapshot_fields(item)
    item.status = WorkItemStatus(body.status)
    await write_audit(db, item.id, "status_changed", before, snapshot_fields(item))
    await db.commit()
    return await get_work_item(work_item_id, db)


@router.post("/{work_item_id}/duplicates/{candidate_id}/accept", response_model=WorkItemDetail)
async def accept_duplicate(work_item_id: UUID, candidate_id: UUID, db: AsyncSession = Depends(get_db)):
    item = await _get_item(db, work_item_id)
    candidate = (
        await db.execute(
            select(DuplicateCandidate).where(
                DuplicateCandidate.id == candidate_id,
                DuplicateCandidate.work_item_id == work_item_id,
            )
        )
    ).scalar_one_or_none()
    if candidate is None:
        raise HTTPException(status_code=404, detail="Duplicate candidate not found")
    before = snapshot_fields(item)
    item.status = WorkItemStatus.closed_duplicate
    item.duplicate_of_id = candidate.matched_item_id
    item.duplicate_match_type = DuplicateMatchType.manual
    await write_audit(db, item.id, "duplicate_accepted", before, snapshot_fields(item))
    await db.commit()
    return await get_work_item(work_item_id, db)


@router.post("/{work_item_id}/duplicates/{candidate_id}/dismiss", response_model=WorkItemDetail)
async def dismiss_duplicate(work_item_id: UUID, candidate_id: UUID, db: AsyncSession = Depends(get_db)):
    item = await _get_item(db, work_item_id)
    candidate = (
        await db.execute(
            select(DuplicateCandidate).where(
                DuplicateCandidate.id == candidate_id,
                DuplicateCandidate.work_item_id == work_item_id,
            )
        )
    ).scalar_one_or_none()
    if candidate is None:
        raise HTTPException(status_code=404, detail="Duplicate candidate not found")
    await db.delete(candidate)
    await write_audit(db, item.id, "duplicate_dismissed", None, {"candidateId": str(candidate_id)})
    await db.commit()
    return await get_work_item(work_item_id, db)


@router.post("/{work_item_id}/submit-guidewire")
async def submit_guidewire(
    work_item_id: UUID,
    body: GuidewireSubmitRequest,
    db: AsyncSession = Depends(get_db),
):
    settings = get_settings()
    if not settings.guidewire_enabled:
        raise HTTPException(status_code=409, detail="Guidewire submit is disabled")
    item = await _get_item(db, work_item_id)
    if item.status not in {WorkItemStatus.approved, WorkItemStatus.assigned, WorkItemStatus.ready_for_review}:
        raise HTTPException(status_code=409, detail="Work item is not ready to submit")

    payload = {"workItemId": str(item.id), "target": body.target, "attempt": 1}
    submission = GuidewireSubmission(
        work_item_id=item.id,
        target=GuidewireTarget(body.target),
        request_json=payload,
        status="queued",
    )
    db.add(submission)
    message_id = await get_queue_publisher(settings).send(settings.service_bus_guidewire_queue, payload)
    job = ProcessingJob(
        work_item_id=item.id,
        queue_name=settings.service_bus_guidewire_queue,
        message_id=message_id,
        job_type="guidewire_submit",
        payload=payload,
    )
    db.add(job)
    item.guidewire_target = GuidewireTarget(body.target)
    item.status = WorkItemStatus.submitted_to_guidewire
    item.submitted_at = utcnow()
    await write_audit(db, item.id, "guidewire_queued", None, payload)
    await db.commit()
    return {"status": "queued", "target": body.target, "workItemId": str(item.id)}


@router.get("/{work_item_id}/attachments/{attachment_id}/sas", response_model=SasResponse)
async def attachment_sas(
    work_item_id: UUID,
    attachment_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    await _get_item(db, work_item_id)
    attachment = (
        await db.execute(
            select(Attachment)
            .join(Email, Email.id == Attachment.email_id)
            .join(WorkItemEmail, WorkItemEmail.email_id == Email.id)
            .where(
                Attachment.id == attachment_id,
                WorkItemEmail.work_item_id == work_item_id,
            )
        )
    ).scalar_one_or_none()
    if attachment is None:
        raise HTTPException(status_code=404, detail="Attachment not found")
    url, ttl = build_read_sas(attachment.blob_url, get_settings())
    return SasResponse(url=url, expires_in_seconds=ttl)
