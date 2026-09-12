"""Human approval queue (spec §22, §11/ADR-004). The backend — not this
router's presence or absence in any UI — is what enforces that a
high-risk run cannot proceed without a decision here: policy_node
(orchestration/nodes.py) is what actually created the Approval row and
left the Run at `awaiting_approval`; these endpoints only record a
decision and flip the Run's terminal status.
"""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas import ApprovalDecision, ApprovalOut
from app.db.repositories import ApprovalRepository, RunRepository
from app.db.session import get_session

router = APIRouter(prefix="/api/approvals", tags=["approvals"])


@router.get("", response_model=list[ApprovalOut])
async def list_approvals(
    status: str | None = None, session: AsyncSession = Depends(get_session)
) -> list[ApprovalOut]:
    approvals = await ApprovalRepository(session).list(status=status)
    return [ApprovalOut.model_validate(a) for a in approvals]


@router.get("/{approval_id}", response_model=ApprovalOut)
async def get_approval(
    approval_id: str, session: AsyncSession = Depends(get_session)
) -> ApprovalOut:
    approval = await ApprovalRepository(session).get(approval_id)
    if approval is None:
        raise HTTPException(status_code=404, detail=f"Approval {approval_id} not found")
    return ApprovalOut.model_validate(approval)


@router.post("/{approval_id}/approve", response_model=ApprovalOut)
async def approve(
    approval_id: str,
    payload: ApprovalDecision,
    session: AsyncSession = Depends(get_session),
) -> ApprovalOut:
    repo = ApprovalRepository(session)
    approval = await repo.get(approval_id)
    if approval is None:
        raise HTTPException(status_code=404, detail=f"Approval {approval_id} not found")
    if approval.status != "pending":
        raise HTTPException(
            status_code=409, detail=f"Approval {approval_id} is already {approval.status}"
        )

    updated = await repo.update(
        approval_id, status="approved", decided_by=payload.decided_by, decided_at=datetime.now(UTC)
    )
    await RunRepository(session).update(approval.run_id, status="completed")
    assert updated is not None
    return ApprovalOut.model_validate(updated)


@router.post("/{approval_id}/reject", response_model=ApprovalOut)
async def reject(
    approval_id: str,
    payload: ApprovalDecision,
    session: AsyncSession = Depends(get_session),
) -> ApprovalOut:
    repo = ApprovalRepository(session)
    approval = await repo.get(approval_id)
    if approval is None:
        raise HTTPException(status_code=404, detail=f"Approval {approval_id} not found")
    if approval.status != "pending":
        raise HTTPException(
            status_code=409, detail=f"Approval {approval_id} is already {approval.status}"
        )

    updated = await repo.update(
        approval_id, status="rejected", decided_by=payload.decided_by, decided_at=datetime.now(UTC)
    )
    await RunRepository(session).update(approval.run_id, status="rejected")
    assert updated is not None
    return ApprovalOut.model_validate(updated)
