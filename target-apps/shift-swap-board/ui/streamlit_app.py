"""Shift Swap Board — Streamlit UI.

Communicates with FastAPI backend over HTTP only. Never imports from app/.
"""
from __future__ import annotations

import os

import httpx
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

# ── Config ────────────────────────────────────────────────────────────────────
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")

st.set_page_config(page_title="Shift Swap Board", page_icon="🔄", layout="wide")


# ── HTTP helpers (DO NOT MODIFY) ─────────────────────────────────────────────
def _headers() -> dict[str, str]:
    """Return auth headers from session state."""
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


def _post(path: str, json_body: dict | None = None) -> httpx.Response:
    return httpx.post(
        f"{API_BASE_URL}{path}",
        json=json_body or {},
        headers=_headers(),
        timeout=60.0,
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
            "Could not reach the API at " + API_BASE_URL + ".\n\n"
            "Start the API first:\n"
            "```\n"
            "cd target-apps/shift-swap-board\n"
            ".venv\\Scripts\\Activate.ps1  # or source .venv/bin/activate\n"
            "uvicorn app.main:app --reload --port 8000\n"
            "```\n\n"
            "If the API crashed, check the terminal for errors (common: DATABASE_URL not set in .env)."
        )
        st.stop()
    except Exception as exc:
        st.error(f"Unexpected error reaching API: {exc}")
        st.stop()


# ── Startup ───────────────────────────────────────────────────────────────────
_ensure_api_reachable()


# ── Login Page ────────────────────────────────────────────────────────────────
def login_page():
    st.title("🔄 Shift Swap Board — Login")
    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Login")
        if submitted:
            resp = _post("/auth/login", {"username": username, "password": password})
            if resp.status_code == 200:
                data = resp.json()
                st.session_state["token"] = data["access_token"]
                import json, base64
                parts = data["access_token"].split(".")
                payload = json.loads(base64.urlsafe_b64decode(parts[1] + "=="))
                st.session_state["role"] = payload.get("role", "staff")
                st.session_state["user_id"] = payload.get("sub", "")
                st.rerun()
            else:
                st.error(f"Login failed: {resp.json().get('detail', resp.text)}")


# ── My Shifts ─────────────────────────────────────────────────────────────────
def my_shifts_page():
    st.header("My Shifts")
    resp = _get("/roster/mine")
    if resp.status_code == 200:
        shifts = resp.json()
        if not shifts:
            st.info("You have no upcoming shifts.")
        else:
            for s in shifts:
                col1, col2, col3, col4 = st.columns([2, 2, 2, 2])
                col1.write(s["shift_date"])
                col2.write(s["shift_window"])
                col3.write(s["display_name"])
                if col4.button("Offer for Swap", key=f"offer_{s['id']}"):
                    r = _post("/swaps", {"offered_shift_id": s["id"]})
                    if r.status_code == 201:
                        st.success("Swap offer created!")
                        st.rerun()
                    else:
                        st.error(f"Error: {r.json().get('detail', r.text)}")
    else:
        st.error(f"Failed to load shifts: {resp.text}")


# ── Open Swaps ────────────────────────────────────────────────────────────────
def open_swaps_page():
    st.header("Open Swaps")
    resp = _get("/swaps", params={"status": "open"})
    if resp.status_code == 200:
        swaps = resp.json()
        if not swaps:
            st.info("No open swaps available.")
        else:
            for sw in swaps:
                with st.container():
                    st.write(f"**Swap ID:** {sw['id'][:8]}... | **Status:** {sw['status']} | **Offered by:** {sw['offered_by_user_id'][:8]}...")
                    if sw["offered_by_user_id"] != st.session_state.get("user_id"):
                        if st.button("Claim", key=f"claim_{sw['id']}"):
                            r = _post(f"/swaps/{sw['id']}/claim")
                            if r.status_code == 200:
                                st.success("Swap claimed!")
                                st.rerun()
                            else:
                                st.error(f"Error: {r.json().get('detail', r.text)}")
                    st.divider()
    else:
        st.error(f"Failed to load swaps: {resp.text}")


# ── Floor Lead Inbox ──────────────────────────────────────────────────────────
def floor_lead_inbox():
    st.header("Floor Lead Inbox")
    resp = _get("/swaps", params={"status": "claimed"})
    if resp.status_code == 200:
        swaps = resp.json()
        if not swaps:
            st.info("No claimed swaps pending decision.")
        else:
            for sw in swaps:
                with st.container():
                    st.write(f"**Swap ID:** {sw['id'][:8]}... | **Claimed by:** {sw.get('claimed_by_user_id', 'N/A')}")
                    note = st.text_input("Decision note (optional)", key=f"note_{sw['id']}")
                    col1, col2 = st.columns(2)
                    if col1.button("Approve", key=f"approve_{sw['id']}"):
                        r = _post(f"/swaps/{sw['id']}/approve", {"decision_note": note or None})
                        if r.status_code == 200:
                            st.success("Swap approved!")
                            st.rerun()
                        else:
                            st.error(f"Error: {r.json().get('detail', r.text)}")
                    if col2.button("Deny", key=f"deny_{sw['id']}"):
                        r = _post(f"/swaps/{sw['id']}/deny", {"decision_note": note or None})
                        if r.status_code == 200:
                            st.success("Swap denied.")
                            st.rerun()
                        else:
                            st.error(f"Error: {r.json().get('detail', r.text)}")
                    st.divider()
    else:
        st.error(f"Failed to load claimed swaps: {resp.text}")


# ── Roster View ───────────────────────────────────────────────────────────────
def roster_view_page():
    st.header("Roster View")
    resp = _get("/roster")
    if resp.status_code == 200:
        rows = resp.json()
        if not rows:
            st.info("No roster data.")
        else:
            import pandas as pd
            df = pd.DataFrame(rows)
            st.dataframe(df[["shift_date", "shift_window", "display_name"]], use_container_width=True)
    else:
        st.error(f"Failed to load roster: {resp.text}")


# ── Audit Log (Admin) ─────────────────────────────────────────────────────────
def audit_log_page():
    st.header("Audit Log")
    resp = _get("/audit", params={"limit": 50})
    if resp.status_code == 200:
        rows = resp.json()
        if not rows:
            st.info("No audit entries.")
        else:
            import pandas as pd
            df = pd.DataFrame(rows)
            st.dataframe(df, use_container_width=True)
    else:
        st.error(f"Failed to load audit log: {resp.text}")


# ── Floor Lead Management (Admin) ─────────────────────────────────────────────
def floor_lead_management_page():
    st.header("Floor Lead Assignments")
    # Fetch current assignments
    resp = _get("/floor-leads")
    assignments = []
    if resp.status_code == 200:
        assignments = resp.json()
        if assignments:
            import pandas as pd
            df = pd.DataFrame(assignments)
            st.dataframe(df, use_container_width=True)
        else:
            st.info("No floor lead assignments yet.")
    else:
        st.error(f"Failed to load floor leads: {resp.text}")

    st.subheader("Assign Floor Lead to Week")
    # Build lead options from existing assignments
    lead_options: list[str] = []
    lead_ids_seen: set[str] = set()
    for item in assignments:
        uid = item.get("floor_lead_user_id", "")
        if uid and uid not in lead_ids_seen:
            lead_ids_seen.add(uid)
            lead_options.append(uid)

    if not lead_options:
        st.warning("No floor lead users found. Seed the database with floor_lead role users first.")
    else:
        with st.form("assign_lead_form"):
            week_start = st.text_input("Week Start (Monday, YYYY-MM-DD)")
            selected_lead = st.selectbox("Floor Lead User", options=lead_options)
            submitted = st.form_submit_button("Assign")
            if submitted and selected_lead:
                r = _post("/floor-leads", {"week_start": week_start, "floor_lead_user_id": selected_lead})
                if r.status_code == 201:
                    st.success("Floor lead assigned!")
                    st.rerun()
                else:
                    st.error(f"Error: {r.json().get('detail', r.text)}")


# ── Main App ──────────────────────────────────────────────────────────────────
if "token" not in st.session_state or not st.session_state["token"]:
    login_page()
else:
    st.sidebar.title("🔄 Shift Swap Board")
    role = st.session_state.get("role", "staff")
    st.sidebar.write(f"Role: **{role}**")
    if st.sidebar.button("Logout"):
        st.session_state.clear()
        st.rerun()

    tabs = ["My Shifts", "Open Swaps", "Roster View"]
    if role in ("floor_lead", "admin"):
        tabs.append("Floor Lead Inbox")
    if role == "admin":
        tabs.append("Audit Log")
        tabs.append("Floor Lead Mgmt")

    selected = st.sidebar.radio("Navigation", tabs)

    if selected == "My Shifts":
        my_shifts_page()
    elif selected == "Open Swaps":
        open_swaps_page()
    elif selected == "Roster View":
        roster_view_page()
    elif selected == "Floor Lead Inbox":
        floor_lead_inbox()
    elif selected == "Audit Log":
        audit_log_page()
    elif selected == "Floor Lead Mgmt":
        floor_lead_management_page()
