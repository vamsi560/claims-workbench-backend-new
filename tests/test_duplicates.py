from datetime import datetime, timezone
from uuid import uuid4

from app.models import DuplicateMatchType, WorkItem
from app.services.duplicates import _compare


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


def test_policy_and_same_loss_day_is_strong():
    day = datetime(2026, 9, 11, 16, 30, tzinfo=timezone.utc)
    current = _item(policy_number="POL-88912", loss_datetime=day, conversation_id="a")
    other = _item(policy_number="pol-88912", loss_datetime=day, conversation_id="b")
    hit = _compare(current, other)
    assert hit is not None
    assert hit.match_type is DuplicateMatchType.rule
    assert hit.reason == "policy_number+loss_date"


def test_no_match_without_shared_keys():
    current = _item(policy_number="A", conversation_id="a")
    other = _item(policy_number="B", conversation_id="b")
    assert _compare(current, other) is None
