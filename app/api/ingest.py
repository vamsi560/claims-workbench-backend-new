from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from starlette.responses import JSONResponse

from app.api.deps import require_ingest_key
from app.config import get_settings
from app.database import get_db
from app.models import Email, WorkItem, WorkItemEmail
from app.schemas.ingest import EmailIngestRequest, EmailIngestResponse, EmailIngestStatusResponse
from app.services.ingest import ingest_email
from app.services.queue import get_queue_publisher

router = APIRouter(prefix="/ingest", tags=["ingest"])


@router.post("/emails", response_model=EmailIngestResponse)
async def post_email(
    payload: EmailIngestRequest,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_ingest_key),
):
    body, status_code = await ingest_email(db, payload, get_queue_publisher(get_settings()), get_settings())
    return JSONResponse(status_code=status_code, content=body.model_dump(mode="json", by_alias=True))


@router.get("/emails/{email_id}", response_model=EmailIngestStatusResponse)
async def get_email(
    email_id: UUID,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_ingest_key),
):
    email = (
        await db.execute(select(Email).options(selectinload(Email.attachments)).where(Email.id == email_id))
    ).scalar_one_or_none()
    if email is None:
        raise HTTPException(status_code=404, detail="Email not found")

    link = (
        await db.execute(
            select(WorkItemEmail, WorkItem)
            .join(WorkItem, WorkItem.id == WorkItemEmail.work_item_id)
            .where(WorkItemEmail.email_id == email.id)
        )
    ).first()
    work_item = link[1] if link else None
    return EmailIngestStatusResponse(
        email_id=email.id,
        status=email.status.value,
        conversation_id=email.conversation_id,
        internet_message_id=email.internet_message_id,
        subject=email.subject,
        received_at=email.received_at,
        work_item_id=work_item.id if work_item else None,
        work_item_number=work_item.work_item_number if work_item else None,
        attachment_count=len(email.attachments),
    )
