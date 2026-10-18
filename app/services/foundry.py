from __future__ import annotations

import asyncio
import json
import logging
import re
from datetime import datetime

from app.config import Settings
from app.services.fnol import FnolExtraction

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You extract First Notice of Loss (FNOL) fields from insurance email text and attachment OCR.
Return a single JSON object with these keys (use null when unknown):
policy_number, claim_number, line_of_business, policy_holder_name, claimant_name,
reporter_name, reporter_email, reporter_phone, loss_datetime (ISO-8601), loss_timezone,
loss_location, loss_type, loss_cause, loss_description, injured (boolean or null),
police_report_number, vehicle_identifiers (array of {vin, plate, make, model, year}),
extra_fields (object), field_confidence (object mapping field name to 0-1).
Do not invent claim numbers. Prefer policy numbers and names as written in the source.
"""

_POLICY_RE = re.compile(r"\b(?:policy|pol)[#:\s-]*([A-Z0-9][A-Z0-9-]{4,})\b", re.I)
_PHONE_RE = re.compile(r"\b(?:\+?1[-.\s]?)?(?:\(?\d{3}\)?[-.\s]?)\d{3}[-.\s]?\d{4}\b")


def foundry_configured(settings: Settings) -> bool:
    return bool(settings.azure_ai_foundry_endpoint and settings.azure_ai_foundry_key)


async def map_fnol_fields(
    *,
    subject: str | None,
    body: str | None,
    combined_text: str,
    settings: Settings,
) -> tuple[FnolExtraction, str]:
    if foundry_configured(settings):
        try:
            extraction = await _map_with_foundry(subject, body, combined_text, settings)
            return extraction, settings.azure_ai_foundry_deployment or "azure-ai-foundry"
        except Exception:
            logger.exception("foundry mapping failed; using heuristic fallback")
    return heuristic_fnol(subject, body, combined_text), "heuristic"


def heuristic_fnol(subject: str | None, body: str | None, combined_text: str) -> FnolExtraction:
    text = "\n".join(part for part in (subject, body, combined_text) if part)
    policy = None
    match = _POLICY_RE.search(text)
    if match:
        policy = match.group(1).upper()
    phone = None
    phone_match = _PHONE_RE.search(text)
    if phone_match:
        phone = phone_match.group(0)
    confidence: dict[str, float] = {}
    if policy:
        confidence["policy_number"] = 0.55
    if body:
        confidence["loss_description"] = 0.4
    return FnolExtraction(
        policy_number=policy,
        reporter_phone=phone,
        loss_description=(body or combined_text)[:4000] or None,
        extra_fields={"mapper": "heuristic"},
        field_confidence=confidence,
    )


async def _map_with_foundry(
    subject: str | None,
    body: str | None,
    combined_text: str,
    settings: Settings,
) -> FnolExtraction:
    raw = await asyncio.to_thread(
        _complete_sync,
        settings.azure_ai_foundry_endpoint,
        settings.azure_ai_foundry_key,
        settings.azure_ai_foundry_deployment,
        subject or "",
        body or "",
        combined_text[:20000],
    )
    return parse_foundry_json(raw)


def parse_foundry_json(raw: str) -> FnolExtraction:
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    data = json.loads(cleaned)
    if "loss_datetime" in data and data["loss_datetime"]:
        try:
            data["loss_datetime"] = datetime.fromisoformat(str(data["loss_datetime"]).replace("Z", "+00:00"))
        except ValueError:
            data["loss_datetime"] = None
    return FnolExtraction.model_validate(data)


def _complete_sync(endpoint: str, key: str, deployment: str, subject: str, body: str, combined: str) -> str:
    from azure.ai.inference import ChatCompletionsClient
    from azure.ai.inference.models import SystemMessage, UserMessage
    from azure.core.credentials import AzureKeyCredential

    client = ChatCompletionsClient(endpoint=endpoint, credential=AzureKeyCredential(key))
    user = (
        f"Email subject:\n{subject}\n\nEmail body:\n{body}\n\n"
        f"Combined email + attachment text:\n{combined}"
    )
    kwargs: dict = {
        "messages": [
            SystemMessage(content=SYSTEM_PROMPT),
            UserMessage(content=user),
        ],
        "temperature": 0,
        "response_format": "json_object",
    }
    if deployment:
        kwargs["model"] = deployment
    response = client.complete(**kwargs)
    return response.choices[0].message.content or "{}"
