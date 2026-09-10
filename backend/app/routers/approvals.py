from fastapi import APIRouter, Depends, HTTPException

from app.auth import CurrentUser, get_current_user
from app.db import execute, fetch_all, fetch_one
from app.graphs.tna_watcher_graph import tna_watcher_app
from app.schemas import ApprovalDecision, PendingApprovalOut

router = APIRouter(prefix="/approvals", tags=["approvals"])


@router.get("", response_model=list[PendingApprovalOut])
def list_pending_approvals(user: CurrentUser = Depends(get_current_user)):
    threads = fetch_all(
        """
        SELECT thread_id, created_at FROM tna_threads
        WHERE tenant_id = :tenant_id AND status = 'pending'
        ORDER BY created_at DESC
        """,
        {"tenant_id": user.tenant_id},
    )

    out = []
    for t in threads:
        config = {"configurable": {"thread_id": t["thread_id"]}}
        state = tna_watcher_app.get_state(config)
        # The interrupt payload is attached to the paused state's tasks.
        if state.tasks and state.tasks[0].interrupts:
            payload = state.tasks[0].interrupts[0].value
            out.append(
                {
                    "thread_id": t["thread_id"],
                    "draft": payload.get("draft", ""),
                    "at_risk_tasks": payload.get("at_risk_tasks", []),
                    "created_at": t["created_at"],
                }
            )
    return out


@router.post("/{thread_id}/decide")
def decide_approval(
    thread_id: str,
    body: ApprovalDecision,
    user: CurrentUser = Depends(get_current_user),
):
    thread = fetch_one(
        "SELECT * FROM tna_threads WHERE thread_id = :thread_id AND tenant_id = :tenant_id",
        {"thread_id": thread_id, "tenant_id": user.tenant_id},
    )
    if not thread:
        raise HTTPException(status_code=404, detail="Approval thread not found")
    if body.decision not in ("approve", "reject"):
        raise HTTPException(status_code=400, detail="decision must be 'approve' or 'reject'")

    from langgraph.types import Command

    config = {"configurable": {"thread_id": thread_id}}
    tna_watcher_app.invoke(Command(resume="approve" if body.decision == "approve" else "reject"), config=config)

    execute(
        "UPDATE tna_threads SET status = :status WHERE thread_id = :thread_id",
        {"status": "approved" if body.decision == "approve" else "rejected", "thread_id": thread_id},
    )
    return {"thread_id": thread_id, "status": body.decision}
