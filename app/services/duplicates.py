from datetime import date, timedelta

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    CLOSED_WORK_ITEM_STATUSES,
    DuplicateCandidate,
    DuplicateMatchType,
    Email,
    WorkItem,
    WorkItemEmail,
)
from app.services.audit import write_audit


def _norm(value: str | None) -> str | None:
    if not value:
        return None
    return " ".join(value.lower().split())


def _loss_day(item: WorkItem) -> date | None:
    if item.loss_datetime is None:
        return None
    return item.loss_datetime.date()


async def find_and_store_duplicates(db: AsyncSession, work_item: WorkItem) -> None:
    result = await db.execute(
        select(WorkItem).where(
            WorkItem.id != work_item.id,
            WorkItem.conversation_id != work_item.conversation_id,
            WorkItem.status.notin_(list(CLOSED_WORK_ITEM_STATUSES)),
        )
    )
    others = result.scalars().all()
    strong: DuplicateCandidate | None = None

    for other in others:
        candidate = _compare(work_item, other)
        if candidate is None:
            continue
        db.add(candidate)
        if candidate.match_type == DuplicateMatchType.rule and strong is None:
            strong = candidate

    if strong:
        work_item.duplicate_match_type = DuplicateMatchType.rule
        work_item.duplicate_of_id = strong.matched_item_id
        work_item.duplicate_score = strong.score
        await write_audit(
            db,
            work_item.id,
            "duplicate_flagged",
            None,
            {"matchedItemId": str(strong.matched_item_id), "reason": strong.reason},
        )


def _compare(current: WorkItem, other: WorkItem) -> DuplicateCandidate | None:
    current_day = _loss_day(current)
    other_day = _loss_day(other)
    policy_match = (
        _norm(current.policy_number)
        and _norm(current.policy_number) == _norm(other.policy_number)
    )
    claim_match = (
        _norm(current.claim_number)
        and _norm(current.claim_number) == _norm(other.claim_number)
    )
    name_match = _norm(current.policy_holder_name) and (
        _norm(current.policy_holder_name) == _norm(other.policy_holder_name)
        or _norm(current.claimant_name) == _norm(other.claimant_name)
        or _norm(current.claimant_name) == _norm(other.policy_holder_name)
    )

    if claim_match:
        return DuplicateCandidate(
            work_item_id=current.id,
            matched_item_id=other.id,
            match_type=DuplicateMatchType.rule,
            score=0.99,
            reason="claim_number",
        )
    if policy_match and current_day and current_day == other_day:
        return DuplicateCandidate(
            work_item_id=current.id,
            matched_item_id=other.id,
            match_type=DuplicateMatchType.rule,
            score=0.95,
            reason="policy_number+loss_date",
        )
    if policy_match and name_match and current_day and other_day:
        if abs((current_day - other_day).days) <= 3:
            return DuplicateCandidate(
                work_item_id=current.id,
                matched_item_id=other.id,
                match_type=DuplicateMatchType.rule,
                score=0.9,
                reason="policy_number+name±3d",
            )
    return None


async def weak_sender_subject_duplicates(
    db: AsyncSession, work_item: WorkItem, root_email: Email
) -> None:
    if work_item.policy_number:
        return
    window_start = root_email.received_at - timedelta(days=1)
    window_end = root_email.received_at + timedelta(days=1)
    stmt: Select = (
        select(WorkItem, Email)
        .join(WorkItemEmail, WorkItemEmail.work_item_id == WorkItem.id)
        .join(Email, Email.id == WorkItemEmail.email_id)
        .where(
            WorkItem.id != work_item.id,
            WorkItemEmail.is_root.is_(True),
            Email.sender_email == root_email.sender_email,
            Email.received_at >= window_start,
            Email.received_at <= window_end,
        )
    )
    rows = (await db.execute(stmt)).all()
    subject = _norm(root_email.subject) or ""
    for other, email in rows:
        other_subject = _norm(email.subject) or ""
        if subject and other_subject and (subject in other_subject or other_subject in subject):
            db.add(
                DuplicateCandidate(
                    work_item_id=work_item.id,
                    matched_item_id=other.id,
                    match_type=DuplicateMatchType.rule,
                    score=0.4,
                    reason="sender+similar_subject±1d",
                )
            )
