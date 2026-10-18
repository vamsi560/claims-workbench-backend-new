import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import Settings, get_settings
from app.models import (
    CLOSED_WORK_ITEM_STATUSES,
    Attachment,
    Email,
    EmailIngestStatus,
    ExtractionJobStatus,
    ProcessingJob,
    WorkItem,
    WorkItemEmail,
    WorkItemStatus,
)
from app.schemas.ingest import EmailIngestRequest, EmailIngestResponse
from app.services.attachments import classify_attachment_kind
from app.services.queue import QueuePublisher
from app.workers.extract import process_latest_pending


def new_work_item_number() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d")
    return f"WI-{stamp}-{uuid.uuid4().hex[:4].upper()}"


async def _open_work_item(db: AsyncSession, conversation_id: str) -> WorkItem | None:
    result = await db.execute(
        select(WorkItem).where(WorkItem.conversation_id == conversation_id)
    )
    items = result.scalars().all()
    return next((item for item in items if item.status not in CLOSED_WORK_ITEM_STATUSES), None)


async def _work_item_for_email(db: AsyncSession, email_id: uuid.UUID) -> WorkItem | None:
    result = await db.execute(
        select(WorkItem)
        .join(WorkItemEmail, WorkItemEmail.work_item_id == WorkItem.id)
        .where(WorkItemEmail.email_id == email_id)
    )
    return result.scalars().first()


async def _enqueue_extract(
    db: AsyncSession,
    publisher: QueuePublisher,
    settings: Settings,
    email: Email,
    work_item: WorkItem,
    job_type: str,
) -> ProcessingJob:
    payload = {
        "jobType": job_type,
        "emailId": str(email.id),
        "workItemId": str(work_item.id),
        "attempt": 1,
    }
    job = ProcessingJob(
        email_id=email.id,
        work_item_id=work_item.id,
        queue_name=settings.service_bus_extract_queue,
        job_type=job_type,
        status=ExtractionJobStatus.pending,
        attempt_count=1,
        payload=payload,
    )
    db.add(job)
    await db.flush()
    message_id = await publisher.send(settings.service_bus_extract_queue, payload)
    job.message_id = message_id
    email.status = EmailIngestStatus.queued
    return job


async def ingest_email(
    db: AsyncSession,
    payload: EmailIngestRequest,
    publisher: QueuePublisher,
    settings: Settings | None = None,
) -> tuple[EmailIngestResponse, int]:
    settings = settings or get_settings()

    if payload.internet_message_id:
        existing = (
            await db.execute(
                select(Email)
                .options(selectinload(Email.attachments))
                .where(Email.internet_message_id == payload.internet_message_id)
            )
        ).scalar_one_or_none()
        if existing:
            work_item = await _work_item_for_email(db, existing.id)
            return (
                EmailIngestResponse(
                    outcome="already_ingested",
                    email_id=existing.id,
                    work_item_id=work_item.id if work_item else None,
                    work_item_number=work_item.work_item_number if work_item else None,
                    thread_merged=False,
                ),
                200,
            )

    email = Email(
        conversation_id=payload.conversation_id,
        internet_message_id=payload.internet_message_id,
        in_reply_to=payload.in_reply_to,
        references_header=payload.references,
        mailbox_address=str(payload.mailbox_address),
        subject=payload.subject,
        body_text=payload.body_text,
        body_html=payload.body_html,
        sender_email=str(payload.sender.email),
        sender_name=payload.sender.name,
        to_addresses=[a.email for a in payload.to],
        cc_addresses=[a.email for a in payload.cc],
        received_at=payload.received_at,
        raw_blob_url=str(payload.raw_email.blob_url) if payload.raw_email else None,
        status=EmailIngestStatus.stored,
        ingest_payload=payload.model_dump(by_alias=True, mode="json"),
    )
    db.add(email)
    await db.flush()

    for att in payload.attachments:
        db.add(
            Attachment(
                email_id=email.id,
                file_name=att.file_name,
                content_type=att.content_type,
                kind=classify_attachment_kind(att.file_name, att.content_type),
                size_bytes=att.size_bytes,
                blob_url=str(att.blob_url),
                checksum_sha256=att.checksum_sha256,
            )
        )

    open_item = await _open_work_item(db, payload.conversation_id)
    if open_item:
        email.status = EmailIngestStatus.thread_merged
        email.merged_into_email_id = open_item.root_email_id
        db.add(
            WorkItemEmail(
                work_item_id=open_item.id,
                email_id=email.id,
                is_root=False,
            )
        )
        open_item.status = WorkItemStatus.extracting
        await _enqueue_extract(db, publisher, settings, email, open_item, "append_to_work_item")
        await db.commit()
        if settings.extract_inline:
            await process_latest_pending(db, open_item.id)
        return (
            EmailIngestResponse(
                outcome="thread_merged",
                email_id=email.id,
                work_item_id=open_item.id,
                work_item_number=open_item.work_item_number,
                thread_merged=True,
            ),
            202,
        )

    work_item = WorkItem(
        work_item_number=new_work_item_number(),
        root_email_id=email.id,
        conversation_id=payload.conversation_id,
        status=WorkItemStatus.extracting,
        reporter_email=str(payload.sender.email),
        reporter_name=payload.sender.name,
        guidewire_enabled=settings.guidewire_enabled,
    )
    db.add(work_item)
    await db.flush()
    db.add(WorkItemEmail(work_item_id=work_item.id, email_id=email.id, is_root=True))
    await _enqueue_extract(db, publisher, settings, email, work_item, "new_work_item")
    await db.commit()
    if settings.extract_inline:
        await process_latest_pending(db, work_item.id)
    return (
        EmailIngestResponse(
            outcome="created",
            email_id=email.id,
            work_item_id=work_item.id,
            work_item_number=work_item.work_item_number,
            thread_merged=False,
        ),
        202,
    )
