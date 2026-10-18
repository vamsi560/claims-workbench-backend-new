"""Service Bus consumer for email-extract jobs.

Run from backend/: python -m app.workers.run_extract
"""

from __future__ import annotations

import asyncio
import json
import logging
from uuid import UUID

from sqlalchemy import select

from app.config import get_settings
from app.database import SessionLocal
from app.models import ExtractionJobStatus, ProcessingJob
from app.workers.extract import process_extract_job

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("extract-worker")


async def handle_payload(payload: dict) -> None:
    async with SessionLocal() as db:
        job = (
            await db.execute(
                select(ProcessingJob)
                .where(
                    ProcessingJob.work_item_id == UUID(payload["workItemId"]),
                    ProcessingJob.email_id == UUID(payload["emailId"]),
                )
                .order_by(ProcessingJob.created_at.desc())
            )
        ).scalars().first()
        if job is None:
            logger.warning("no processing job for payload=%s", payload)
            return
        if job.status == ExtractionJobStatus.succeeded:
            logger.info("job already succeeded id=%s", job.id)
            return
        await process_extract_job(db, job.id)


async def run() -> None:
    settings = get_settings()
    if not settings.service_bus_connection_string:
        raise SystemExit("SERVICE_BUS_CONNECTION_STRING is required for the extract worker")

    from azure.servicebus.aio import ServiceBusClient

    async with ServiceBusClient.from_connection_string(settings.service_bus_connection_string) as client:
        receiver = client.get_queue_receiver(settings.service_bus_extract_queue)
        async with receiver:
            logger.info("listening on queue=%s", settings.service_bus_extract_queue)
            async for message in receiver:
                try:
                    payload = json.loads(str(message))
                    await handle_payload(payload)
                    await receiver.complete_message(message)
                except Exception:
                    logger.exception("extract job failed")
                    await receiver.dead_letter_message(message, reason="extract_failed")


if __name__ == "__main__":
    asyncio.run(run())
