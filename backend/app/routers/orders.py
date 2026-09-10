import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException

from app.auth import CurrentUser, get_current_user
from app.db import execute, fetch_all, fetch_one
from app.graphs.order_status_graph import order_status_app
from app.schemas import AssessJobOut, AssessRequest, AssessResultOut, OrderOut

router = APIRouter(prefix="/orders", tags=["orders"])


@router.get("", response_model=list[OrderOut])
def list_orders(user: CurrentUser = Depends(get_current_user)):
    rows = fetch_all(
        """
        SELECT o.order_ref, o.style, o.ship_date, o.status,
               a.summary AS last_assessment, a.is_at_risk AS last_risk_flag
        FROM orders o
        LEFT JOIN LATERAL (
            SELECT summary, is_at_risk FROM assessments
            WHERE assessments.order_ref = o.order_ref AND assessments.tenant_id = o.tenant_id
            ORDER BY assessed_at DESC LIMIT 1
        ) a ON true
        WHERE o.tenant_id = :tenant_id
        ORDER BY o.ship_date NULLS LAST
        """,
        {"tenant_id": user.tenant_id},
    )
    return rows


def _run_assessment(job_id: str, tenant_id: str, order_ref: str):
    """Runs in the background so the API responds immediately."""
    try:
        result = order_status_app.invoke(
            {"tenant_id": tenant_id, "order_ref": order_ref}
        )
        execute(
            """
            INSERT INTO assessments (job_id, tenant_id, order_ref, is_at_risk, summary, status, assessed_at)
            VALUES (:job_id, :tenant_id, :order_ref, :is_at_risk, :summary, 'done', now())
            """,
            {
                "job_id": job_id,
                "tenant_id": tenant_id,
                "order_ref": order_ref,
                "is_at_risk": result.get("is_at_risk", False),
                "summary": result.get("final_answer", ""),
            },
        )
    except Exception as exc:  # noqa: BLE001
        execute(
            """
            INSERT INTO assessments (job_id, tenant_id, order_ref, status, summary, assessed_at)
            VALUES (:job_id, :tenant_id, :order_ref, 'error', :summary, now())
            """,
            {"job_id": job_id, "tenant_id": tenant_id, "order_ref": order_ref, "summary": str(exc)},
        )


@router.post("/{order_ref}/assess", response_model=AssessJobOut)
def assess_order(
    order_ref: str,
    background_tasks: BackgroundTasks,
    user: CurrentUser = Depends(get_current_user),
):
    job_id = str(uuid.uuid4())
    execute(
        """
        INSERT INTO assessments (job_id, tenant_id, order_ref, status, assessed_at)
        VALUES (:job_id, :tenant_id, :order_ref, 'queued', now())
        """,
        {"job_id": job_id, "tenant_id": user.tenant_id, "order_ref": order_ref},
    )
    background_tasks.add_task(_run_assessment, job_id, user.tenant_id, order_ref)
    return {"job_id": job_id, "status": "queued"}


@router.get("/assess/{job_id}", response_model=AssessResultOut)
def get_assessment(job_id: str, user: CurrentUser = Depends(get_current_user)):
    row = fetch_one(
        "SELECT * FROM assessments WHERE job_id = :job_id AND tenant_id = :tenant_id",
        {"job_id": job_id, "tenant_id": user.tenant_id},
    )
    if not row:
        raise HTTPException(status_code=404, detail="Job not found")
    if row["status"] == "queued":
        raise HTTPException(status_code=202, detail="Assessment still running")
    return {
        "order_ref": row["order_ref"],
        "is_at_risk": row["is_at_risk"],
        "summary": row["summary"],
        "assessed_at": row["assessed_at"],
    }
