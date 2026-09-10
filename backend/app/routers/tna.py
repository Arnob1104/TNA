import uuid

from fastapi import APIRouter, Depends, Header, HTTPException

from app.auth import CurrentUser, get_current_user
from app.config import settings
from app.db import execute, fetch_all
from app.graphs.tna_watcher_graph import tna_watcher_app

router = APIRouter(prefix="/tna", tags=["tna"])


def _run_scan_for_tenant(tenant_id: str) -> dict:
    thread_id = f"tna-{tenant_id}-{uuid.uuid4()}"
    config = {"configurable": {"thread_id": thread_id}}
    result = tna_watcher_app.invoke({"tenant_id": tenant_id}, config=config)

    if result.get("__interrupt__"):
        execute(
            """
            INSERT INTO tna_threads (thread_id, tenant_id, status, created_at)
            VALUES (:thread_id, :tenant_id, 'pending', now())
            """,
            {"thread_id": thread_id, "tenant_id": tenant_id},
        )
        return {"tenant_id": tenant_id, "status": "pending_approval", "thread_id": thread_id}
    return {"tenant_id": tenant_id, "status": "no_risk_found"}


@router.post("/scan-all")
def trigger_scan_all(x_cron_secret: str = Header(default="")):
    """
    Runs the TNA Watcher for every tenant in one call. Meant to be hit by
    a scheduled job (e.g. a free GitHub Actions cron workflow) once a day
    - not by a logged-in user, so it's protected by a shared secret
    instead of a Supabase JWT.
    """
    if x_cron_secret != settings.cron_secret:
        raise HTTPException(status_code=401, detail="Invalid cron secret")

    tenants = fetch_all("SELECT id FROM tenants")
    return [_run_scan_for_tenant(str(t["id"])) for t in tenants]


@router.post("/scan")
def trigger_scan(user: CurrentUser = Depends(get_current_user)):
    """
    Kicks off one run of the TNA Deadline Watcher for the caller's tenant.
    In production this is called by a scheduled job (APScheduler/Celery
    Beat) once per tenant per day - exposed here too so it can be
    triggered manually or tested from the dashboard.
    """
    thread_id = f"tna-{user.tenant_id}-{uuid.uuid4()}"
    config = {"configurable": {"thread_id": thread_id}}

    result = tna_watcher_app.invoke({"tenant_id": user.tenant_id}, config=config)

    interrupt_payload = result.get("__interrupt__")
    if interrupt_payload:
        # Graph paused waiting for a human decision - record it so it
        # shows up in the approvals inbox.
        execute(
            """
            INSERT INTO tna_threads (thread_id, tenant_id, status, created_at)
            VALUES (:thread_id, :tenant_id, 'pending', now())
            """,
            {"thread_id": thread_id, "tenant_id": user.tenant_id},
        )
        return {"status": "pending_approval", "thread_id": thread_id}

    return {"status": "no_risk_found"}
