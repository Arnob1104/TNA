"""
Order Status Agent (multi-step, on-demand).

Same shape as the original prototype: fetch order -> fetch TNA -> assess
risk -> compose a human-readable answer. The only real changes for
production are:
  - Excel reads become tenant-scoped Postgres reads.
  - Every node takes/returns state that includes tenant_id, so a query
    for one company can never see another company's rows.
"""

from typing import TypedDict
from langgraph.graph import StateGraph, START, END
from langchain_groq import ChatGroq

from app.db import fetch_all

llm = ChatGroq(model="llama-3.3-70b-versatile", temperature=0.1)


class OrderState(TypedDict):
    tenant_id: str
    order_ref: str
    order_data: str
    tna_data: str
    is_at_risk: bool
    final_answer: str


def fetch_order_data(state: OrderState) -> dict:
    rows = fetch_all(
        """
        SELECT order_ref, style, ship_date, status, quantity
        FROM orders
        WHERE tenant_id = :tenant_id AND order_ref = :order_ref
        """,
        {"tenant_id": state["tenant_id"], "order_ref": state["order_ref"]},
    )
    return {"order_data": str(rows[0]) if rows else "Order not found"}


def fetch_tna_data(state: OrderState) -> dict:
    rows = fetch_all(
        """
        SELECT task_name, deadline, status
        FROM tna_calendar
        WHERE tenant_id = :tenant_id AND order_ref = :order_ref
        ORDER BY deadline
        """,
        {"tenant_id": state["tenant_id"], "order_ref": state["order_ref"]},
    )
    return {"tna_data": str(rows) if rows else "No TNA entries for this order"}


def assess_risk(state: OrderState) -> dict:
    if state["order_data"] == "Order not found":
        return {"is_at_risk": False}

    prompt = f"""Order data: {state['order_data']}
TNA data: {state['tna_data']}

Today's date context assumed current. Is this order AT RISK of missing
its ship date? Answer with just YES or NO first, then a one-sentence reason."""
    response = llm.invoke(prompt).content
    return {"is_at_risk": response.strip().upper().startswith("YES")}


def compose_answer(state: OrderState) -> dict:
    if state["order_data"] == "Order not found":
        return {"final_answer": f"No order found matching '{state['order_ref']}' for your account."}

    status_flag = "AT RISK" if state["is_at_risk"] else "ON TRACK"
    prompt = f"""Write a one-paragraph status update for a merchandiser about
order {state['order_ref']}. Status flag: {status_flag}
Order data: {state['order_data']}
TNA data: {state['tna_data']}"""
    return {"final_answer": llm.invoke(prompt).content}


def build_order_status_graph():
    graph = StateGraph(OrderState)
    graph.add_node("fetch_order_data", fetch_order_data)
    graph.add_node("fetch_tna_data", fetch_tna_data)
    graph.add_node("assess_risk", assess_risk)
    graph.add_node("compose_answer", compose_answer)

    graph.add_edge(START, "fetch_order_data")
    graph.add_edge("fetch_order_data", "fetch_tna_data")
    graph.add_edge("fetch_tna_data", "assess_risk")
    graph.add_edge("assess_risk", "compose_answer")
    graph.add_edge("compose_answer", END)

    return graph.compile()


order_status_app = build_order_status_graph()
