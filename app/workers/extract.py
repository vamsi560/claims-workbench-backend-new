from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import Settings, get_settings
from app.models import (
    Email,
    ExtractionJobStatus,
    ProcessingJob,
    WorkItem,
    WorkItemStatus,
)
from app.services.audit import write_audit
from app.services.document_intelligence import extract_attachment
from app.services.duplicates import find_and_store_duplicates, weak_sender_subject_duplicates
from app.services.fnol import apply_fnol_fields
from app.services.foundry import map_fnol_fields


async def process_extract_job(db: AsyncSession, job_id: UUID, settings: Settings | None = None) -> None:
    settings = settings or get_settings()
    job = (
        await db.execute(select(ProcessingJob).where(ProcessingJob.id == job_id))
    ).scalar_one_or_none()
    if job is None:
        return

    job.status = ExtractionJobStatus.processing
    job.started_at = datetime.now(timezone.utc)

    work_item = (
        await db.execute(select(WorkItem).where(WorkItem.id == job.work_item_id))
    ).scalar_one()
    email = (
        await db.execute(
            select(Email).options(selectinload(Email.attachments)).where(Email.id == job.email_id)
        )
    ).scalar_one()

    texts: list[str] = []
    if email.body_text:
        texts.append(email.body_text)
    failures = 0
    for attachment in email.attachments:
        result = await extract_attachment(attachment, settings)
        attachment.status = result.status
        attachment.error_message = result.error_message
        attachment.extracted_text = result.text or None
        attachment.extraction_json = result.payload or None
        if result.status == ExtractionJobStatus.failed:
            failures += 1
            continue
        if result.text:
            texts.append(result.text)

    combined = "\n\n".join(texts)
    overwrite = job.job_type == "new_work_item"
    extraction, model_name = await map_fnol_fields(
        subject=email.subject,
        body=email.body_text,
        combined_text=combined,
        settings=settings,
    )
    if not extraction.reporter_email:
        extraction.reporter_email = email.sender_email
    if not extraction.reporter_name:
        extraction.reporter_name = email.sender_name
    apply_fnol_fields(work_item, extraction, overwrite=overwrite)
    work_item.extraction_model = model_name
    work_item.status = WorkItemStatus.ready_for_review

    await find_and_store_duplicates(db, work_item)
    if job.job_type == "new_work_item":
        await weak_sender_subject_duplicates(db, work_item, email)

    job.status = ExtractionJobStatus.succeeded
    job.completed_at = datetime.now(timezone.utc)
    job.result = {
        "attachmentCount": len(email.attachments),
        "attachmentFailures": failures,
        "model": model_name,
    }
    await write_audit(
        db,
        work_item.id,
        "extracted",
        None,
        {"jobType": job.job_type, "emailId": str(email.id), "model": model_name},
    )
    await db.commit()


async def process_latest_pending(db: AsyncSession, work_item_id: UUID) -> None:
    job = (
        await db.execute(
            select(ProcessingJob)
            .where(
                ProcessingJob.work_item_id == work_item_id,
                ProcessingJob.status == ExtractionJobStatus.pending,
            )
            .order_by(ProcessingJob.created_at.desc())
        )
    ).scalars().first()
    if job:
        await process_extract_job(db, job.id)
