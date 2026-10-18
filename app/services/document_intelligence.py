from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any

import httpx

from app.config import Settings
from app.models import Attachment, AttachmentKind, ExtractionJobStatus
from app.services.blob_sas import build_read_sas

logger = logging.getLogger(__name__)

DI_KINDS = {
    AttachmentKind.pdf,
    AttachmentKind.png,
    AttachmentKind.jpeg,
    AttachmentKind.docx,
    AttachmentKind.xlsx,
    AttachmentKind.pptx,
}


@dataclass
class AttachmentExtract:
    text: str = ""
    payload: dict[str, Any] = field(default_factory=dict)
    status: ExtractionJobStatus = ExtractionJobStatus.succeeded
    error_message: str | None = None


def document_intelligence_configured(settings: Settings) -> bool:
    return bool(settings.document_intelligence_endpoint and settings.document_intelligence_key)


async def extract_attachment(attachment: Attachment, settings: Settings) -> AttachmentExtract:
    if attachment.kind == AttachmentKind.mp4:
        return AttachmentExtract(
            status=ExtractionJobStatus.failed,
            error_message="video_not_transcribed",
        )
    if attachment.kind == AttachmentKind.txt:
        try:
            text = await _download_text(attachment.blob_url, settings)
            return AttachmentExtract(text=text, payload={"source": "blob-text"})
        except Exception as exc:  # noqa: BLE001 — surface as attachment failure
            logger.warning("txt download failed file=%s err=%s", attachment.file_name, exc)
            return AttachmentExtract(
                status=ExtractionJobStatus.failed,
                error_message=f"txt_download_failed: {exc}",
            )
    if attachment.kind in DI_KINDS:
        if not document_intelligence_configured(settings):
            return AttachmentExtract(
                text=f"[pending-di] {attachment.file_name}",
                payload={"source": "stub"},
            )
        return await _analyze_with_document_intelligence(attachment, settings)
    return AttachmentExtract(
        status=ExtractionJobStatus.failed,
        error_message="unsupported_for_extraction",
    )


async def _download_text(blob_url: str, settings: Settings) -> str:
    url, _ = build_read_sas(blob_url, settings)
    async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
        response = await client.get(url)
        response.raise_for_status()
        return response.text


async def _analyze_with_document_intelligence(attachment: Attachment, settings: Settings) -> AttachmentExtract:
    url, _ = build_read_sas(attachment.blob_url, settings)
    try:
        content, payload = await asyncio.to_thread(
            _analyze_sync,
            settings.document_intelligence_endpoint,
            settings.document_intelligence_key,
            url,
        )
        return AttachmentExtract(text=content or "", payload=payload)
    except Exception as exc:  # noqa: BLE001
        logger.exception("document intelligence failed file=%s", attachment.file_name)
        return AttachmentExtract(
            status=ExtractionJobStatus.failed,
            error_message=f"document_intelligence_failed: {exc}",
        )


def _analyze_sync(endpoint: str, key: str, url: str) -> tuple[str, dict[str, Any]]:
    from azure.ai.documentintelligence import DocumentIntelligenceClient
    from azure.ai.documentintelligence.models import AnalyzeDocumentRequest
    from azure.core.credentials import AzureKeyCredential

    client = DocumentIntelligenceClient(endpoint, AzureKeyCredential(key))
    poller = client.begin_analyze_document(
        "prebuilt-layout",
        AnalyzeDocumentRequest(url_source=url),
    )
    result = poller.result()
    content = result.content or ""
    pages = len(result.pages or [])
    return content, {"source": "document-intelligence", "model": "prebuilt-layout", "pageCount": pages}
