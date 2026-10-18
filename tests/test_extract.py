from datetime import datetime, timezone
from uuid import uuid4

from app.config import Settings
from app.models import Attachment, AttachmentKind, ExtractionJobStatus, WorkItem
from app.services.document_intelligence import extract_attachment
from app.services.fnol import FnolExtraction, apply_fnol_fields
from app.services.foundry import heuristic_fnol, parse_foundry_json


def _settings(**kwargs) -> Settings:
    return Settings(**kwargs)


def _item(**kwargs) -> WorkItem:
    defaults = dict(
        id=uuid4(),
        work_item_number="WI-TEST",
        root_email_id=uuid4(),
        conversation_id="c1",
        vehicle_identifiers=[],
        extra_fields={},
        extracted_fields={},
        field_confidence={},
    )
    defaults.update(kwargs)
    return WorkItem(**defaults)


async def test_mp4_is_not_transcribed():
    attachment = Attachment(
        id=uuid4(),
        email_id=uuid4(),
        file_name="dashcam.mp4",
        kind=AttachmentKind.mp4,
        blob_url="https://example/dashcam.mp4",
    )
    result = await extract_attachment(attachment, _settings())
    assert result.status is ExtractionJobStatus.failed
    assert result.error_message == "video_not_transcribed"


async def test_pdf_without_di_is_placeholder():
    attachment = Attachment(
        id=uuid4(),
        email_id=uuid4(),
        file_name="police-report.pdf",
        kind=AttachmentKind.pdf,
        blob_url="https://example/police-report.pdf",
    )
    result = await extract_attachment(attachment, _settings())
    assert result.status is ExtractionJobStatus.succeeded
    assert result.text.startswith("[pending-di]")


async def test_zip_is_unsupported():
    attachment = Attachment(
        id=uuid4(),
        email_id=uuid4(),
        file_name="photos.zip",
        kind=AttachmentKind.other,
        blob_url="https://example/photos.zip",
    )
    result = await extract_attachment(attachment, _settings())
    assert result.status is ExtractionJobStatus.failed
    assert result.error_message == "unsupported_for_extraction"


def test_heuristic_picks_policy_from_body():
    extraction = heuristic_fnol(
        "FNOL - rear end collision",
        "Please log a claim. Policy POL-88912. Insured Jane Doe.",
        "",
    )
    assert extraction.policy_number == "POL-88912"
    assert extraction.loss_description is not None


def test_parse_foundry_json_strips_fences():
    raw = """```json
    {"policy_number": "POL-1", "injured": false, "field_confidence": {"policy_number": 0.9}}
    ```"""
    extraction = parse_foundry_json(raw)
    assert extraction.policy_number == "POL-1"
    assert extraction.injured is False
    assert extraction.field_confidence["policy_number"] == 0.9


def test_apply_fnol_does_not_overwrite_on_append():
    item = _item(policy_number="EXISTING", reporter_email="a@b.c")
    extraction = FnolExtraction(
        policy_number="NEW",
        claimant_name="Sam",
        loss_datetime=datetime(2026, 9, 11, 16, 30, tzinfo=timezone.utc),
        field_confidence={"policy_number": 0.8},
    )
    apply_fnol_fields(item, extraction, overwrite=False)
    assert item.policy_number == "EXISTING"
    assert item.claimant_name == "Sam"
    assert item.extracted_fields["policy_number"] == "NEW"


def test_apply_fnol_overwrites_on_new_item():
    item = _item(policy_number="EXISTING")
    extraction = FnolExtraction(policy_number="NEW")
    apply_fnol_fields(item, extraction, overwrite=True)
    assert item.policy_number == "NEW"
