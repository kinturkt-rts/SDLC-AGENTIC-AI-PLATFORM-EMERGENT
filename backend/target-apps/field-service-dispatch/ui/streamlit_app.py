"""Field Service Dispatch — Streamlit UI.

Communicates with the FastAPI backend over HTTP only.
Provides views for Dispatcher (board), Technician (my jobs), and Owner (read-only).
"""
from __future__ import annotations

import os
from datetime import date

import httpx
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

# ── Config ────────────────────────────────────────────────────────────────────
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")

st.set_page_config(page_title="Field Service Dispatch", page_icon="🔧", layout="wide")


# ── HTTP helpers (DO NOT MODIFY) ─────────────────────────────────────────────
def _headers() -> dict[str, str]:
    token = st.session_state.get("token")
    if token:
        return {"Authorization": f"Bearer {token}"}
    return {}


def _get(path: str, params: dict | None = None) -> httpx.Response:
    return httpx.get(
        f"{API_BASE_URL}{path}",
        params=params,
        headers=_headers(),
        timeout=30.0,
        follow_redirects=True,
    )


def _post(path: str, json_body: dict | None = None, data: dict | None = None) -> httpx.Response:
    kwargs: dict = {
        "headers": _headers(),
        "timeout": 60.0,
        "follow_redirects": True,
    }
    if json_body is not None:
        kwargs["json"] = json_body
    if data is not None:
        kwargs["data"] = data
    return httpx.post(f"{API_BASE_URL}{path}", **kwargs)


def _patch(path: str, json_body: dict) -> httpx.Response:
    return httpx.patch(
        f"{API_BASE_URL}{path}",
        json=json_body,
        headers=_headers(),
        timeout=30.0,
        follow_redirects=True,
    )


def _ensure_api_reachable() -> None:
    """Check API health on startup; stop with actionable error if unreachable."""
    try:
        resp = httpx.get(f"{API_BASE_URL}/health", timeout=10.0, follow_redirects=True)
        if resp.status_code == 503:
            data = resp.json()
            failed = [k for k, v in data.get("checks", {}).items() if v != "ok"]
            st.error(
                f"API is running but unhealthy — failing checks: {', '.join(failed)}.\n\n"
                "Troubleshooting:\n"
                "- Is DATABASE_URL set correctly in .env?\n"
                "- Is the RDS/Postgres instance reachable from your machine?\n"
                "- Run `curl http://localhost:8000/health` for details."
            )
            st.stop()
    except httpx.ConnectError:
        st.error(
            f"Could not reach the API at {API_BASE_URL}.\n\n"
            "Start the API first:\n"
            "```\n"
            "cd target-apps/field-service-dispatch\n"
            ".venv\\Scripts\\Activate.ps1  # or source .venv/bin/activate\n"
            "uvicorn app.main:app --reload --port 8000\n"
            "```\n\n"
            "If the API crashed, check the terminal for errors (common: DATABASE_URL not set in .env)."
        )
        st.stop()
    except Exception as exc:
        st.error(f"Unexpected error reaching API: {exc}")
        st.stop()


# ── Auth ──────────────────────────────────────────────────────────────────────
def login_form():
    st.title("🔧 Field Service Dispatch — Login")
    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Login")
        if submitted:
            resp = _post("/auth/token", data={"username": username, "password": password})
            if resp.status_code == 200:
                data = resp.json()
                st.session_state["token"] = data["access_token"]
                st.session_state["role"] = data["role"]
                st.rerun()
            else:
                st.error("Invalid credentials. Please try again.")


def logout():
    if st.sidebar.button("Logout"):
        st.session_state.clear()
        st.rerun()


# ── Board View (Dispatcher/Owner) ────────────────────────────────────────────
def board_view():
    st.header("📋 Today's Dispatch Board")
    target_date = st.date_input("Board date", value=date.today())
    resp = _get("/board", params={"date": str(target_date)})
    if resp.status_code != 200:
        st.error(f"Error loading board: {resp.text}")
        return
    data = resp.json()

    # SLA Breaches
    if data["sla_breaches"]:
        st.subheader("🚨 SLA Breaches")
        for wo in data["sla_breaches"]:
            st.error(f"**{wo['description']}** — Priority: {wo['priority']} | Status: {wo['status']} | Scheduled: {wo['scheduled_date']}")

    # Unassigned
    st.subheader("📥 Unassigned Queue")
    if data["unassigned"]:
        for wo in data["unassigned"]:
            with st.expander(f"[{wo['priority'].upper()}] {wo['description']} ({wo['time_window']})"):
                st.write(f"**ID:** {wo['id']}")
                st.write(f"**Customer:** {wo['customer_id']}")
                st.write(f"**Scheduled:** {wo['scheduled_date']} | **Window:** {wo['time_window']}")
                if st.session_state.get("role") == "dispatcher":
                    # Assignment form
                    techs_resp = _get("/technicians", params={"active_only": "true"})
                    if techs_resp.status_code == 200:
                        techs = techs_resp.json()
                        tech_options = {t["display_name"]: t["id"] for t in techs}
                        selected = st.selectbox(
                            "Assign to", list(tech_options.keys()), key=f"assign_{wo['id']}"
                        )
                        if st.button("Assign", key=f"btn_assign_{wo['id']}"):
                            assign_resp = _patch(
                                f"/work-orders/{wo['id']}",
                                {"assigned_technician_id": tech_options[selected]},
                            )
                            if assign_resp.status_code == 200:
                                st.success("Assigned!")
                                st.rerun()
                            else:
                                st.error(f"Error: {assign_resp.text}")
    else:
        st.info("No unassigned orders.")

    # Technician Columns
    st.subheader("👷 Technician Assignments")
    if data["technician_columns"]:
        cols = st.columns(min(len(data["technician_columns"]), 3))
        for idx, (tech_id, orders) in enumerate(data["technician_columns"].items()):
            col = cols[idx % len(cols)]
            with col:
                st.markdown(f"**Tech: {tech_id[:8]}...**")
                for wo in orders:
                    status_emoji = {"assigned": "🟡", "in_progress": "🟠", "completed": "✅", "cancelled": "⛔"}.get(wo["status"], "⚪")
                    st.write(f"{status_emoji} {wo['description'][:40]} ({wo['status']})")
    else:
        st.info("No assigned orders for this date.")


# ── Technician My Jobs View ──────────────────────────────────────────────────
def my_jobs_view():
    st.header("🔨 My Jobs")
    resp = _get("/board", params={"date": str(date.today())})
    if resp.status_code != 200:
        st.error(f"Error loading jobs: {resp.text}")
        return
    data = resp.json()

    # Technician board returns only their orders in tech_columns
    all_orders = []
    for orders in data["technician_columns"].values():
        all_orders.extend(orders)

    if not all_orders:
        st.info("No jobs assigned to you today.")
        return

    for wo in all_orders:
        status_emoji = {"assigned": "🟡", "in_progress": "🟠", "completed": "✅"}.get(wo["status"], "⚪")
        with st.expander(f"{status_emoji} {wo['description']} — {wo['status']}"):
            st.write(f"**Priority:** {wo['priority']} | **Window:** {wo['time_window']}")

            if wo["status"] == "assigned":
                if st.button("▶️ Start Job", key=f"start_{wo['id']}"):
                    r = _patch(f"/work-orders/{wo['id']}", {"status": "in_progress"})
                    if r.status_code == 200:
                        st.success("Job started!")
                        st.rerun()
                    else:
                        st.error(f"Error: {r.text}")

            elif wo["status"] == "in_progress":
                st.markdown("**Complete this job:**")
                notes = st.text_area("Completion notes", key=f"notes_{wo['id']}")
                parts_count = st.number_input("Number of parts used", min_value=0, max_value=20, value=0, key=f"parts_n_{wo['id']}")
                parts = []
                for i in range(int(parts_count)):
                    c1, c2, c3 = st.columns(3)
                    pname = c1.text_input("Part name", key=f"pname_{wo['id']}_{i}")
                    pqty = c2.number_input("Qty", min_value=1, value=1, key=f"pqty_{wo['id']}_{i}")
                    pcost = c3.number_input("Unit cost ($)", min_value=0.0, value=0.0, key=f"pcost_{wo['id']}_{i}")
                    if pname:
                        part_item: dict = {"part_name": pname, "quantity": int(pqty)}
                        if pcost > 0:
                            part_item["unit_cost"] = pcost
                        parts.append(part_item)

                if st.button("✅ Complete Job", key=f"complete_{wo['id']}"):
                    if not notes or not notes.strip():
                        st.warning("Completion notes are required.")
                    else:
                        payload: dict = {"status": "completed", "completion_notes": notes}
                        if parts:
                            payload["parts"] = parts
                        r = _patch(f"/work-orders/{wo['id']}", payload)
                        if r.status_code == 200:
                            st.success("Job completed!")
                            st.rerun()
                        else:
                            st.error(f"Error: {r.text}")

            elif wo["status"] == "completed":
                st.write(f"**Notes:** {wo.get('completion_notes', 'N/A')}")


# ── Work Order Creation (Dispatcher) ─────────────────────────────────────────
def create_work_order_form():
    st.header("📝 Create Work Order")
    with st.form("create_wo"):
        customer_id = st.text_input("Customer ID (UUID)")
        description = st.text_area("Description")
        priority = st.selectbox("Priority", ["routine", "urgent"])
        scheduled_date = st.date_input("Scheduled Date", value=date.today())
        time_window = st.selectbox("Time Window", ["morning", "afternoon", "all_day"])
        submitted = st.form_submit_button("Create")
        if submitted:
            resp = _post("/work-orders", json_body={
                "customer_id": customer_id,
                "description": description,
                "priority": priority,
                "scheduled_date": str(scheduled_date),
                "time_window": time_window,
            })
            if resp.status_code == 201:
                st.success(f"Work order created: {resp.json()['id']}")
            else:
                st.error(f"Error {resp.status_code}: {resp.text}")


# ── Workload View (Owner/Dispatcher) ─────────────────────────────────────────
def workload_view():
    st.header("📊 Workload Summary")
    target_date = st.date_input("Date", value=date.today(), key="workload_date")
    resp = _get("/workload", params={"date": str(target_date)})
    if resp.status_code != 200:
        st.error(f"Error: {resp.text}")
        return
    data = resp.json()
    if data["workload"]:
        import pandas as pd
        df = pd.DataFrame(data["workload"])
        st.dataframe(df, use_container_width=True)
    else:
        st.info("No workload data for this date.")


# ── Main ──────────────────────────────────────────────────────────────────────
_ensure_api_reachable()

if "token" not in st.session_state:
    login_form()
else:
    logout()
    role = st.session_state.get("role", "")
    st.sidebar.markdown(f"**Role:** {role.capitalize()}")

    if role == "dispatcher":
        tab1, tab2, tab3, tab4 = st.tabs(["Board", "Create Work Order", "Workload", "Customers"])
        with tab1:
            board_view()
        with tab2:
            create_work_order_form()
        with tab3:
            workload_view()
        with tab4:
            st.header("Customers")
            st.info("Use the API at /docs to manage customers or extend this tab.")

    elif role == "technician":
        my_jobs_view()

    elif role == "owner":
        tab1, tab2 = st.tabs(["Board", "Workload"])
        with tab1:
            board_view()
        with tab2:
            workload_view()
    else:
        st.warning("Unknown role. Please log out and log in again.")
