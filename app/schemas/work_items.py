from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models import WorkItemStatus


class WorkItemListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: UUID
    work_item_number: str = Field(alias="workItemNumber")
    status: WorkItemStatus
    conversation_id: str = Field(alias="conversationId")
    assigned_to: str | None = Field(default=None, alias="assignedTo")
    policy_number: str | None = Field(default=None, alias="policyNumber")
    policy_holder_name: str | None = Field(default=None, alias="policyHolderName")
    loss_datetime: datetime | None = Field(default=None, alias="lossDatetime")
    duplicate_match_type: str = Field(alias="duplicateMatchType")
    created_at: datetime = Field(alias="createdAt")


class WorkItemListResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    items: list[WorkItemListItem]
    total: int
    page: int
    page_size: int = Field(alias="pageSize")
    total_pages: int = Field(alias="totalPages")


class AttachmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: UUID
    file_name: str = Field(alias="fileName")
    content_type: str | None = Field(default=None, alias="contentType")
    kind: str
    size_bytes: int | None = Field(default=None, alias="sizeBytes")
    blob_url: str = Field(alias="blobUrl")
    status: str
    error_message: str | None = Field(default=None, alias="errorMessage")


class EmailOut(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: UUID
    subject: str | None = None
    body_text: str | None = Field(default=None, alias="bodyText")
    sender_email: str | None = Field(default=None, alias="senderEmail")
    sender_name: str | None = Field(default=None, alias="senderName")
    received_at: datetime = Field(alias="receivedAt")
    status: str
    is_root: bool = Field(alias="isRoot")
    attachments: list[AttachmentOut] = Field(default_factory=list)


class DuplicateCandidateOut(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: UUID
    matched_item_id: UUID = Field(alias="matchedItemId")
    match_type: str = Field(alias="matchType")
    score: float | None = None
    reason: str | None = None


class JobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: UUID
    job_type: str = Field(alias="jobType")
    status: str
    queue_name: str = Field(alias="queueName")
    error_message: str | None = Field(default=None, alias="errorMessage")
    created_at: datetime = Field(alias="createdAt")


class AuditOut(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: UUID
    actor: str | None = None
    action: str
    before_json: dict[str, Any] | None = Field(default=None, alias="before")
    after_json: dict[str, Any] | None = Field(default=None, alias="after")
    created_at: datetime = Field(alias="createdAt")


class WorkItemDetail(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: UUID
    work_item_number: str = Field(alias="workItemNumber")
    status: WorkItemStatus
    conversation_id: str = Field(alias="conversationId")
    assigned_to: str | None = Field(default=None, alias="assignedTo")
    assigned_at: datetime | None = Field(default=None, alias="assignedAt")
    policy_number: str | None = Field(default=None, alias="policyNumber")
    claim_number: str | None = Field(default=None, alias="claimNumber")
    line_of_business: str | None = Field(default=None, alias="lineOfBusiness")
    policy_holder_name: str | None = Field(default=None, alias="policyHolderName")
    claimant_name: str | None = Field(default=None, alias="claimantName")
    reporter_name: str | None = Field(default=None, alias="reporterName")
    reporter_email: str | None = Field(default=None, alias="reporterEmail")
    reporter_phone: str | None = Field(default=None, alias="reporterPhone")
    loss_datetime: datetime | None = Field(default=None, alias="lossDatetime")
    loss_timezone: str | None = Field(default=None, alias="lossTimezone")
    loss_location: str | None = Field(default=None, alias="lossLocation")
    loss_type: str | None = Field(default=None, alias="lossType")
    loss_cause: str | None = Field(default=None, alias="lossCause")
    loss_description: str | None = Field(default=None, alias="lossDescription")
    injured: bool | None = None
    police_report_number: str | None = Field(default=None, alias="policeReportNumber")
    vehicle_identifiers: list[Any] = Field(default_factory=list, alias="vehicleIdentifiers")
    extra_fields: dict[str, Any] = Field(default_factory=dict, alias="extraFields")
    extracted_fields: dict[str, Any] = Field(default_factory=dict, alias="extractedFields")
    field_confidence: dict[str, Any] = Field(default_factory=dict, alias="fieldConfidence")
    duplicate_of_id: UUID | None = Field(default=None, alias="duplicateOfId")
    duplicate_match_type: str = Field(alias="duplicateMatchType")
    emails: list[EmailOut] = Field(default_factory=list)
    duplicates: list[DuplicateCandidateOut] = Field(default_factory=list)
    jobs: list[JobOut] = Field(default_factory=list)
    audit: list[AuditOut] = Field(default_factory=list)
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")


class WorkItemPatch(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    policy_number: str | None = Field(default=None, alias="policyNumber")
    claim_number: str | None = Field(default=None, alias="claimNumber")
    line_of_business: str | None = Field(default=None, alias="lineOfBusiness")
    policy_holder_name: str | None = Field(default=None, alias="policyHolderName")
    claimant_name: str | None = Field(default=None, alias="claimantName")
    reporter_name: str | None = Field(default=None, alias="reporterName")
    reporter_email: str | None = Field(default=None, alias="reporterEmail")
    reporter_phone: str | None = Field(default=None, alias="reporterPhone")
    loss_datetime: datetime | None = Field(default=None, alias="lossDatetime")
    loss_timezone: str | None = Field(default=None, alias="lossTimezone")
    loss_location: str | None = Field(default=None, alias="lossLocation")
    loss_type: str | None = Field(default=None, alias="lossType")
    loss_cause: str | None = Field(default=None, alias="lossCause")
    loss_description: str | None = Field(default=None, alias="lossDescription")
    injured: bool | None = None
    police_report_number: str | None = Field(default=None, alias="policeReportNumber")
    vehicle_identifiers: list[Any] | None = Field(default=None, alias="vehicleIdentifiers")
    extra_fields: dict[str, Any] | None = Field(default=None, alias="extraFields")


class AssignRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    assigned_to: str = Field(alias="assignedTo", min_length=1)


class StatusRequest(BaseModel):
    status: Literal["in_review", "approved", "rejected", "ready_for_review"]


class GuidewireSubmitRequest(BaseModel):
    target: Literal["pc", "cc"]


class SasResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    url: str
    expires_in_seconds: int = Field(alias="expiresInSeconds")
