from __future__ import annotations

import json
import logging
from typing import Any, Protocol

from app.config import Settings, get_settings

logger = logging.getLogger(__name__)


class QueuePublisher(Protocol):
    async def send(self, queue_name: str, payload: dict[str, Any]) -> str | None: ...


class LoggingQueuePublisher:
    """Used when Service Bus is not configured (local / tests)."""

    async def send(self, queue_name: str, payload: dict[str, Any]) -> str | None:
        logger.info("queue_publish queue=%s payload=%s", queue_name, json.dumps(payload, default=str))
        return None


class ServiceBusPublisher:
    def __init__(self, connection_string: str) -> None:
        self._connection_string = connection_string

    async def send(self, queue_name: str, payload: dict[str, Any]) -> str | None:
        from azure.servicebus import ServiceBusMessage
        from azure.servicebus.aio import ServiceBusClient

        async with ServiceBusClient.from_connection_string(self._connection_string) as client:
            sender = client.get_queue_sender(queue_name)
            async with sender:
                message = ServiceBusMessage(json.dumps(payload, default=str))
                await sender.send_messages(message)
                return str(message.message_id) if message.message_id else None


def get_queue_publisher(settings: Settings | None = None) -> QueuePublisher:
    settings = settings or get_settings()
    if settings.service_bus_connection_string:
        return ServiceBusPublisher(settings.service_bus_connection_string)
    return LoggingQueuePublisher()
