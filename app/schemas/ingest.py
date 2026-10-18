from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, HttpUrl


class Address(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    email: str
    name: str | None = None


class Sender(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    email: EmailStr
    name: str | None = None


class RawEmail(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    blob_url: HttpUrl = Field(alias="blobUrl")
    content_type: str | None = Field(default="message/rfc822", alias="contentType")


class IngestAttachment(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    file_name: str = Field(alias="fileName")
    content_type: str | None = Field(default=None, alias="contentType")
    size_bytes: int | None = Field(default=None, alias="sizeBytes", ge=0)
    blob_url: HttpUrl = Field(alias="blobUrl")
    checksum_sha256: str | None = Field(default=None, alias="checksumSha256")


class EmailIngestRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    schema_version: Literal["1.0"] = Field(alias="schemaVersion")
    logic_app_run_id: str | None = Field(default=None, alias="logicAppRunId")
    mailbox_address: EmailStr = Field(alias="mailboxAddress")
    conversation_id: str = Field(alias="conversationId", min_length=1)
    internet_message_id: str | None = Field(default=None, alias="internetMessageId")
    in_reply_to: str | None = Field(default=None, alias="inReplyTo")
    references: str | None = None
    subject: str | None = None
    body_text: str | None = Field(default=None, alias="bodyText")
    body_html: str | None = Field(default=None, alias="bodyHtml")
    received_at: datetime = Field(alias="receivedAt")
    sender: Sender
    to: list[Address] = Field(default_factory=list)
    cc: list[Address] = Field(default_factory=list)
    importance: str | None = None
    has_attachments: bool | None = Field(default=None, alias="hasAttachments")
    raw_email: RawEmail | None = Field(default=None, alias="rawEmail")
    attachments: list[IngestAttachment] = Field(default_factory=list)


class EmailIngestResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    outcome: Literal["created", "thread_merged", "already_ingested"]
    email_id: UUID = Field(alias="emailId")
    work_item_id: UUID | None = Field(default=None, alias="workItemId")
    work_item_number: str | None = Field(default=None, alias="workItemNumber")
    thread_merged: bool = Field(alias="threadMerged")


class EmailIngestStatusResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    email_id: UUID = Field(alias="emailId")
    status: str
    conversation_id: str = Field(alias="conversationId")
    internet_message_id: str | None = Field(default=None, alias="internetMessageId")
    subject: str | None = None
    received_at: datetime = Field(alias="receivedAt")
    work_item_id: UUID | None = Field(default=None, alias="workItemId")
    work_item_number: str | None = Field(default=None, alias="workItemNumber")
    attachment_count: int = Field(alias="attachmentCount")
