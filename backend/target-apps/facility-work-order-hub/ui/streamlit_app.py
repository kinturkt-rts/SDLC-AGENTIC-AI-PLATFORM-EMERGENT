"""Streamlit UI for Facility Work Order Hub.

Calls the FastAPI backend over HTTP. Never imports from app/.
Role-gated views based on JWT claims stored in session state.
"""
from __future__ import annotations

import os

import httpx
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

# ── Config ──
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")

st.set_page_config(page_title="Facility Work Order Hub", page_icon="\U0001f527", layout="wide")


# ── HTTP helpers ──

def _headers() -> dict:
    token = st.session_state.get("token", "")
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


def _post(path: str, json_body: dict) -> httpx.Response:
    return httpx.post(
        f"{API_BASE_URL}{path}",
        json=json_body,
        headers=_headers(),
        timeout=60.0,
        follow_redirects=True,
    )


def _patch(path: str, json_body: dict) -> httpx.Response:
    return httpx.patch(
        f"{API_BASE_URL}{path}",
        json=json_body,
        headers=_headers(),
        timeout=30.0,
        follow_redirects=True,
    )


def _ensure_api_reachable() -> None:
    try:
        resp = _get("/health")
        if resp.status_code == 503:
            data = resp.json()
            failed = [k for k, v in data.get("checks", {}).items() if v != "ok"]
            st.error(
                f"API unhealthy \u2014 failing checks: {', '.join(failed)}.\n\n"
                "Check DATABASE_URL in .env and that RDS is reachable."
            )
            st.stop()
    except httpx.ConnectError:
        st.error(
            f"Cannot reach API at {API_BASE_URL}.\n\n"
            "Start the API first:\n"
            "```\n"
            "cd target-apps/facility-work-order-hub\n"
            "uvicorn app.main:app --reload --port 8000\n"
            "```"
        )
        st.stop()
    except Exception as exc:
        st.error(f"Unexpected error: {exc}")
        st.stop()


# ── Login page ──

def login_page():
    st.title("\U0001f512 Login")
    with st.form("login_form"):
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Login")
        if submitted:
            resp = _post("/api/v1/auth/token", {"email": email, "password": password})
            if resp.status_code == 200:
                data = resp.json()
                st.session_state["token"] = data["access_token"]
                # Decode role from JWT payload (base64)
                import json, base64
                payload_b64 = data["access_token"].split(".")[1]
                payload_b64 += "=" * (4 - len(payload_b64) % 4)
                claims = json.loads(base64.urlsafe_b64decode(payload_b64))
                st.session_state["role"] = claims.get("role", "")
                st.session_state["user_id"] = claims.get("sub", "")
                st.session_state["email"] = claims.get("email", "")
                st.rerun()
            else:
                st.error("Invalid credentials")


# ── Role views ──

def requester_view():
    st.header("\U0001f4cb My Work Orders")
    tab1, tab2 = st.tabs(["Submit New", "My Orders"])
    with tab1:
        with st.form("create_wo"):
            title = st.text_input("Title")
            description = st.text_area("Description")
            category = st.selectbox("Category", ["HVAC", "plumbing", "electrical", "access", "general"])
            priority = st.selectbox("Priority", ["low", "normal", "urgent"])
            site_id = st.text_input("Site ID")
            location_id = st.text_input("Location ID (optional)", value="")
            submitted = st.form_submit_button("Create")
            if submitted:
                body = {
                    "title": title,
                    "description": description,
                    "category": category,
                    "priority": priority,
                    "site_id": site_id,
                }
                if location_id:
                    body["location_id"] = location_id
                resp = _post("/api/v1/work-orders", body)
                if resp.status_code == 201:
                    st.success("Work order created!")
                    data = resp.json()
                    if data.get("warnings"):
                        st.warning("\n".join(data["warnings"]))
                else:
                    st.error(f"Error: {resp.text}")
    with tab2:
        resp = _get("/api/v1/work-orders")
        if resp.status_code == 200:
            data = resp.json()
            if data["items"]:
                st.dataframe(data["items"])
            else:
                st.info("No work orders yet.")


def technician_view():
    st.header("\U0001f6e0\ufe0f My Assigned Queue")
    resp = _get("/api/v1/work-orders")
    if resp.status_code == 200:
        data = resp.json()
        if not data["items"]:
            st.info("No assigned work orders.")
        else:
            for wo in data["items"]:
                with st.expander(f"{wo['title']} [{wo['status']}]"):
                    st.write(wo["description"])
                    st.write(f"Priority: {wo['priority']} | Category: {wo['category']}")
                    if wo["status"] == "assigned":
                        if st.button("Start", key=f"start_{wo['id']}"):
                            _patch(f"/api/v1/work-orders/{wo['id']}/status", {"status": "in_progress"})
                            st.rerun()
                    elif wo["status"] == "in_progress":
                        if st.button("Complete", key=f"complete_{wo['id']}"):
                            _patch(f"/api/v1/work-orders/{wo['id']}/status", {"status": "completed"})
                            st.rerun()


def admin_view():
    st.header("\U0001f3e2 Facilities Admin")
    tab1, tab2, tab3, tab4 = st.tabs(["All Work Orders", "Assign", "Sites", "Workload"])
    with tab1:
        resp = _get("/api/v1/work-orders")
        if resp.status_code == 200:
            st.dataframe(resp.json()["items"])
    with tab2:
        wo_id = st.text_input("Work Order ID to assign")
        assignee_id = st.text_input("Technician User ID")
        if st.button("Assign"):
            resp = _patch(f"/api/v1/work-orders/{wo_id}/assign", {"assignee_id": assignee_id})
            if resp.status_code == 200:
                st.success("Assigned!")
            else:
                st.error(resp.text)
    with tab3:
        with st.form("create_site"):
            code = st.text_input("Site Code")
            name = st.text_input("Name")
            address = st.text_input("Address")
            if st.form_submit_button("Create Site"):
                resp = _post("/api/v1/sites", {"site_code": code, "name": name, "address_line": address})
                if resp.status_code == 201:
                    st.success("Site created!")
                else:
                    st.error(resp.text)
    with tab4:
        resp = _get("/api/v1/dashboard/workload")
        if resp.status_code == 200:
            st.dataframe(resp.json())


def leadership_view():
    st.header("\U0001f4ca Leadership Dashboard")
    resp = _get("/api/v1/dashboard/sla")
    if resp.status_code == 200:
        data = resp.json()
        col1, col2, col3 = st.columns(3)
        col1.metric("Open", data["open_count"])
        col2.metric("Closed (this month)", data["closed_count"])
        col3.metric("Overdue", data["overdue_count"])
        st.subheader("Avg Days to Close by Category")
        st.json(data["avg_days_to_close_by_category"])
        st.subheader("Top Sites by Volume")
        st.dataframe(data["top_sites"])
    else:
        st.error(f"Error loading dashboard: {resp.text}")


# ── Main ──
_ensure_api_reachable()

if "token" not in st.session_state:
    login_page()
else:
    role = st.session_state.get("role", "")
    st.sidebar.write(f"Logged in as: **{st.session_state.get('email', '')}** ({role})")
    if st.sidebar.button("Logout"):
        for k in ["token", "role", "user_id", "email"]:
            st.session_state.pop(k, None)
        st.rerun()

    if role == "requester":
        requester_view()
    elif role == "technician":
        technician_view()
    elif role == "facilities_admin":
        admin_view()
    elif role == "leadership":
        leadership_view()
    else:
        st.warning(f"Unknown role: {role}")
