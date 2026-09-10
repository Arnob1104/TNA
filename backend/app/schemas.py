from datetime import datetime
from pydantic import BaseModel


class OrderOut(BaseModel):
    order_ref: str
    style: str | None = None
    ship_date: datetime | None = None
    status: str | None = None
    last_assessment: str | None = None
    last_risk_flag: bool | None = None


class AssessRequest(BaseModel):
    order_ref: str


class AssessJobOut(BaseModel):
    job_id: str
    status: str  # "queued" | "running" | "done" | "error"


class AssessResultOut(BaseModel):
    order_ref: str
    is_at_risk: bool
    summary: str
    assessed_at: datetime


class PendingApprovalOut(BaseModel):
    thread_id: str
    draft: str
    at_risk_tasks: list[str]
    created_at: datetime


class ApprovalDecision(BaseModel):
    decision: str  # "approve" | "reject"
