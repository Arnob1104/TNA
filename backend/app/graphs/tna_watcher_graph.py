"""
TNA Deadline Watcher (scheduled, human-in-the-loop).

Same safety pattern as the prototype: scan -> draft -> INTERRUPT for a
human decision -> send or discard. Production changes:
  - Reads tna_calendar from Postgres, scoped by tenant_id.
  - Uses PostgresSaver instead of MemorySaver, so a paused
    "awaiting approval" thread survives a server restart - critical,
    since these threads can sit paused for hours until someone approves.
  - send_reminder writes to a `notifications` table the frontend/Slack
    integration can pick up, instead of print().
"""

from datetime import datetime, timedelta
from typing import Literal, TypedDict

from langgraph.graph import StateGraph, START, END
from langgraph.types import interrupt, Command
from langgraph.checkpoint.postgres import PostgresSaver
from langchain_groq import ChatGroq

from app.config import settings
from app.db import fetch_all, execute

llm = ChatGroq(model="llama-3.3-70b-versatile", temperature=0.1)


class TNAState(TypedDict):
    tenant_id: str
    at_risk_tasks: list[str]
    reminder_draft: str


def scan_tna_calendar(state: TNAState) -> dict:
    cutoff = datetime.now() + timedelta(days=3)
    rows = fetch_all(
        """
        SELECT task_name FROM tna_calendar
        WHERE tenant_id = :tenant_id
          AND deadline <= :cutoff
          AND status != 'Complete'
        """,
        {"tenant_id": state["tenant_id"], "cutoff": cutoff},
    )
    return {"at_risk_tasks": [r["task_name"] for r in rows]}


def draft_reminder(state: TNAState) -> dict:
    if not state["at_risk_tasks"]:
        return {"reminder_draft": "No tasks at risk - nothing to send."}

    task_list = "\n".join(f"- {t}" for t in state["at_risk_tasks"])
    prompt = f"Write a brief internal reminder message listing these at-risk TNA tasks:\n{task_list}"
    return {"reminder_draft": llm.invoke(prompt).content}


def human_approval(state: TNAState) -> Command[Literal["send_reminder", "discard"]]:
    if not state["at_risk_tasks"]:
        return Command(goto="discard")

    decision = interrupt(
        {
            "question": "Send this TNA reminder?",
            "draft": state["reminder_draft"],
            "at_risk_tasks": state["at_risk_tasks"],
        }
    )
    return Command(goto="send_reminder" if decision == "approve" else "discard")


def send_reminder(state: TNAState) -> dict:
    execute(
        """
        INSERT INTO notifications (tenant_id, message, kind, created_at)
        VALUES (:tenant_id, :message, 'tna_reminder', now())
        """,
        {"tenant_id": state["tenant_id"], "message": state["reminder_draft"]},
    )
    return {}


def discard(state: TNAState) -> dict:
    return {}


def build_tna_watcher_graph(checkpointer):
    graph = StateGraph(TNAState)
    graph.add_node("scan_tna_calendar", scan_tna_calendar)
    graph.add_node("draft_reminder", draft_reminder)
    graph.add_node("human_approval", human_approval)
    graph.add_node("send_reminder", send_reminder)
    graph.add_node("discard", discard)

    graph.add_edge(START, "scan_tna_calendar")
    graph.add_edge("scan_tna_calendar", "draft_reminder")
    graph.add_edge("draft_reminder", "human_approval")
    graph.add_edge("send_reminder", END)
    graph.add_edge("discard", END)

    return graph.compile(checkpointer=checkpointer)


# --- Postgres-backed checkpointer setup ---
# PostgresSaver needs its own connection and a one-time `.setup()` call
# to create its checkpoint tables. We do that lazily on first import.
_checkpointer_cm = PostgresSaver.from_conn_string(settings.database_url)
checkpointer = _checkpointer_cm.__enter__()
checkpointer.setup()

tna_watcher_app = build_tna_watcher_graph(checkpointer)
