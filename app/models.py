import enum
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def enum_values(enum_cls: type[enum.Enum]) -> list[str]:
    return [item.value for item in enum_cls]


class EmailIngestStatus(str, enum.Enum):
    received = "received"
    stored = "stored"
    queued = "queued"
    extracting = "extracting"
    extracted = "extracted"
    thread_merged = "thread_merged"
    skipped_duplicate_thread = "skipped_duplicate_thread"
    failed = "failed"


class WorkItemStatus(str, enum.Enum):
    extracting = "extracting"
    ready_for_review = "ready_for_review"
    in_review = "in_review"
    assigned = "assigned"
    approved = "approved"
    submitted_to_guidewire = "submitted_to_guidewire"
    guidewire_failed = "guidewire_failed"
    closed_duplicate = "closed_duplicate"
    closed_thread_merge = "closed_thread_merge"
    rejected = "rejected"


CLOSED_WORK_ITEM_STATUSES = {
    WorkItemStatus.rejected,
    WorkItemStatus.closed_duplicate,
    WorkItemStatus.closed_thread_merge,
}


class ExtractionJobStatus(str, enum.Enum):
    pending = "pending"
    processing = "processing"
    succeeded = "succeeded"
    failed = "failed"
    dead_lettered = "dead_lettered"


class AttachmentKind(str, enum.Enum):
    pdf = "pdf"
    docx = "docx"
    xlsx = "xlsx"
    pptx = "pptx"
    txt = "txt"
    png = "png"
    jpeg = "jpeg"
    mp4 = "mp4"
    other = "other"


class GuidewireTarget(str, enum.Enum):
    none = "none"
    pc = "pc"
    cc = "cc"


class DuplicateMatchType(str, enum.Enum):
    none = "none"
    same_thread = "same_thread"
    rule = "rule"
    manual = "manual"


class Email(Base):
    __tablename__ = "emails"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conversation_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    internet_message_id: Mapped[str | None] = mapped_column(Text, unique=True)
    in_reply_to: Mapped[str | None] = mapped_column(Text)
    references_header: Mapped[str | None] = mapped_column(Text)
    mailbox_address: Mapped[str] = mapped_column(Text, nullable=False)
    subject: Mapped[str | None] = mapped_column(Text)
    body_text: Mapped[str | None] = mapped_column(Text)
    body_html: Mapped[str | None] = mapped_column(Text)
    sender_email: Mapped[str | None] = mapped_column(Text)
    sender_name: Mapped[str | None] = mapped_column(Text)
    to_addresses: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, server_default=text("'{}'"))
    cc_addresses: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, server_default=text("'{}'"))
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    raw_blob_url: Mapped[str | None] = mapped_column(Text)
    status: Mapped[EmailIngestStatus] = mapped_column(
        Enum(EmailIngestStatus, name="email_ingest_status", values_callable=enum_values),
        nullable=False,
        default=EmailIngestStatus.received,
    )
    merged_into_email_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("emails.id"))
    ingest_payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    attachments: Mapped[list["Attachment"]] = relationship(back_populates="email")


class Attachment(Base):
    __tablename__ = "attachments"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("emails.id", ondelete="CASCADE"), nullable=False)
    file_name: Mapped[str] = mapped_column(Text, nullable=False)
    content_type: Mapped[str | None] = mapped_column(Text)
    kind: Mapped[AttachmentKind] = mapped_column(
        Enum(AttachmentKind, name="attachment_kind", values_callable=enum_values),
        nullable=False,
        default=AttachmentKind.other,
    )
    size_bytes: Mapped[int | None] = mapped_column(Integer)
    blob_url: Mapped[str] = mapped_column(Text, nullable=False)
    checksum_sha256: Mapped[str | None] = mapped_column(Text)
    extracted_text: Mapped[str | None] = mapped_column(Text)
    extraction_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    di_operation_id: Mapped[str | None] = mapped_column(Text)
    status: Mapped[ExtractionJobStatus] = mapped_column(
        Enum(ExtractionJobStatus, name="extraction_job_status", values_callable=enum_values),
        nullable=False,
        default=ExtractionJobStatus.pending,
    )
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    email: Mapped[Email] = relationship(back_populates="attachments")


class WorkItem(Base):
    __tablename__ = "work_items"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    work_item_number: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    root_email_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("emails.id"), nullable=False)
    conversation_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    status: Mapped[WorkItemStatus] = mapped_column(
        Enum(WorkItemStatus, name="work_item_status", values_callable=enum_values),
        nullable=False,
        default=WorkItemStatus.extracting,
    )
    duplicate_of_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("work_items.id"))
    duplicate_match_type: Mapped[DuplicateMatchType] = mapped_column(
        Enum(DuplicateMatchType, name="duplicate_match_type", values_callable=enum_values),
        nullable=False,
        default=DuplicateMatchType.none,
    )
    duplicate_score: Mapped[float | None] = mapped_column(Numeric(5, 4))
    assigned_to: Mapped[str | None] = mapped_column(Text)
    assigned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    policy_number: Mapped[str | None] = mapped_column(Text)
    claim_number: Mapped[str | None] = mapped_column(Text)
    line_of_business: Mapped[str | None] = mapped_column(Text)
    policy_holder_name: Mapped[str | None] = mapped_column(Text)
    claimant_name: Mapped[str | None] = mapped_column(Text)
    reporter_name: Mapped[str | None] = mapped_column(Text)
    reporter_email: Mapped[str | None] = mapped_column(Text)
    reporter_phone: Mapped[str | None] = mapped_column(Text)
    loss_datetime: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    loss_timezone: Mapped[str | None] = mapped_column(Text)
    loss_location: Mapped[str | None] = mapped_column(Text)
    loss_type: Mapped[str | None] = mapped_column(Text)
    loss_cause: Mapped[str | None] = mapped_column(Text)
    loss_description: Mapped[str | None] = mapped_column(Text)
    injured: Mapped[bool | None] = mapped_column(Boolean)
    police_report_number: Mapped[str | None] = mapped_column(Text)
    vehicle_identifiers: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    extra_fields: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    extracted_fields: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    field_confidence: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    extraction_model: Mapped[str | None] = mapped_column(Text)
    guidewire_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    guidewire_target: Mapped[GuidewireTarget] = mapped_column(
        Enum(GuidewireTarget, name="guidewire_target", values_callable=enum_values),
        nullable=False,
        default=GuidewireTarget.none,
    )
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    email_links: Mapped[list["WorkItemEmail"]] = relationship(back_populates="work_item")
    duplicate_candidates: Mapped[list["DuplicateCandidate"]] = relationship(
        back_populates="work_item",
        foreign_keys="DuplicateCandidate.work_item_id",
    )


class WorkItemEmail(Base):
    __tablename__ = "work_item_emails"

    work_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("work_items.id", ondelete="CASCADE"), primary_key=True
    )
    email_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("emails.id", ondelete="CASCADE"), primary_key=True
    )
    is_root: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    linked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    work_item: Mapped[WorkItem] = relationship(back_populates="email_links")
    email: Mapped[Email] = relationship()


class ProcessingJob(Base):
    __tablename__ = "processing_jobs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("emails.id"))
    work_item_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("work_items.id"))
    queue_name: Mapped[str] = mapped_column(Text, nullable=False)
    message_id: Mapped[str | None] = mapped_column(Text)
    job_type: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[ExtractionJobStatus] = mapped_column(
        Enum(ExtractionJobStatus, name="extraction_job_status", values_callable=enum_values, create_type=False),
        nullable=False,
        default=ExtractionJobStatus.pending,
    )
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    result: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    error_message: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class DuplicateCandidate(Base):
    __tablename__ = "duplicate_candidates"
    __table_args__ = (CheckConstraint("work_item_id <> matched_item_id", name="chk_dup_not_self"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    work_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("work_items.id", ondelete="CASCADE"), nullable=False
    )
    matched_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("work_items.id", ondelete="CASCADE"), nullable=False
    )
    match_type: Mapped[DuplicateMatchType] = mapped_column(
        Enum(DuplicateMatchType, name="duplicate_match_type", values_callable=enum_values, create_type=False),
        nullable=False,
    )
    score: Mapped[float | None] = mapped_column(Numeric(5, 4))
    reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    work_item: Mapped[WorkItem] = relationship(foreign_keys=[work_item_id], back_populates="duplicate_candidates")
    matched_item: Mapped[WorkItem] = relationship(foreign_keys=[matched_item_id])


class WorkItemAudit(Base):
    __tablename__ = "work_item_audit"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    work_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("work_items.id", ondelete="CASCADE"), nullable=False
    )
    actor: Mapped[str | None] = mapped_column(Text)
    action: Mapped[str] = mapped_column(Text, nullable=False)
    before_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    after_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class GuidewireSubmission(Base):
    __tablename__ = "guidewire_submissions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    work_item_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("work_items.id"), nullable=False)
    target: Mapped[GuidewireTarget] = mapped_column(
        Enum(GuidewireTarget, name="guidewire_target", values_callable=enum_values, create_type=False),
        nullable=False,
    )
    request_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    response_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    external_id: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
