"""Streamlit UI for Field Service Dispatch.

Communicates exclusively via the FastAPI HTTP API. Never imports from app/.
"""
from __future__ import annotations

import os

import httpx
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

# ── Config ────────────────────────────────────────────────────────────────────
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")

st.set_page_config(page_title="Field Service Dispatch", page_icon="🔧", layout="wide")


# ── HTTP helpers (DO NOT MODIFY) ─────────────────────────────────────────────
def _headers() -> dict[str, str]:
    """Build headers with API key from session state."""
    h: dict[str, str] = {}
    token = st.session_state.get("token")
    if token:
        h["X-API-Key"] = token
    return h


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


def _delete(path: str) -> httpx.Response:
    return httpx.delete(
        f"{API_BASE_URL}{path}",
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
            "Could not reach the API at " + API_BASE_URL + ".\n\n"
            "Start the API first:\n"
            "```\n"
            "cd target-apps/field-service-dispatch\n"
            ".venv\\Scripts\\Activate.ps1  # or source .venv/bin/activate\n"
            "uvicorn app.main:app --reload --port 8000\n"
            "```\n\n"
            "If the API crashed, check the terminal for errors."
        )
        st.stop()
    except Exception as exc:
        st.error(f"Unexpected error reaching API: {exc}")
        st.stop()


# ── Main ──────────────────────────────────────────────────────────────────────
_ensure_api_reachable()


def login_page():
    """Login form."""
    st.title("🔧 Field Service Dispatch - Login")
    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Login", type="primary")
        if submitted:
            resp = httpx.post(
                f"{API_BASE_URL}/api/v1/auth/token",
                json={"username": username, "password": password},
                timeout=30.0,
                follow_redirects=True,
            )
            if resp.status_code == 200:
                data = resp.json()
                st.session_state["token"] = data["access_token"]
                st.session_state["role"] = data["role"]
                st.session_state["technician_id"] = data.get("technician_id")
                st.session_state["username"] = username
                st.rerun()
            else:
                st.error("Invalid credentials. Please try again.")


def dispatcher_view():
    """Dispatcher board + management."""
    st.title("🔧 Dispatcher Board")

    tab_board, tab_customers, tab_technicians, tab_work_orders = st.tabs([
        "📋 Board", "👤 Customers", "🔧 Technicians", "📝 Work Orders"
    ])

    with tab_board:
        import datetime
        board_date = st.date_input("Board Date", value=datetime.date.today())
        if st.button("🔄 Refresh Board"):
            st.rerun()

        resp = _get("/api/v1/board", params={"date": str(board_date)})
        if resp.status_code == 200:
            board = resp.json()

            # SLA Breaches
            if board["sla_breaches"]:
                st.error(f"⚠️ SLA BREACHES: {len(board['sla_breaches'])} orders")
                for o in board["sla_breaches"]:
                    st.markdown(f"- 🔴 **{o['description']}** (Priority: {o['priority']}, Status: {o['status']})")

            # Unassigned queue
            st.subheader("Unassigned Queue")
            if board["unassigned"]:
                for o in board["unassigned"]:
                    marker = "🔴" if o.get("sla_breached") else "⚪"
                    st.markdown(f"{marker} **{o['description']}** | {o['priority']} | {o['time_window']} | ID: `{o['id'][:8]}...`")
            else:
                st.info("No unassigned orders.")

            # Technician columns
            st.subheader("Technician Assignments")
            cols = st.columns(max(len(board["technicians"]), 1))
            for i, tech in enumerate(board["technicians"]):
                with cols[i % len(cols)]:
                    st.markdown(f"**{tech['technician_name']}**")
                    if tech["orders"]:
                        for o in tech["orders"]:
                            marker = "🔴" if o.get("sla_breached") else "🟢"
                            st.markdown(f"{marker} {o['description']} [{o['status']}]")
                    else:
                        st.caption("No assignments")
        else:
            st.error(f"Failed to load board: {resp.status_code}")

    with tab_customers:
        st.subheader("Create Customer")
        with st.form("create_customer"):
            full_name = st.text_input("Full Name")
            phone = st.text_input("Phone")
            email = st.text_input("Email (optional)")
            street = st.text_input("Street")
            city = st.text_input("City")
            state = st.text_input("State")
            zip_code = st.text_input("ZIP")
            if st.form_submit_button("Create Customer"):
                payload = {
                    "full_name": full_name, "phone": phone, "street": street,
                    "city": city, "state": state, "zip": zip_code
                }
                if email:
                    payload["email"] = email
                resp = _post("/api/v1/customers", payload)
                if resp.status_code == 201:
                    st.success("Customer created!")
                    st.rerun()
                else:
                    st.error(f"Error: {resp.text}")

        st.subheader("Customer List")
        resp = _get("/api/v1/customers")
        if resp.status_code == 200:
            customers = resp.json()
            if customers:
                import pandas as pd
                df = pd.DataFrame(customers)[["id", "full_name", "phone", "city", "state"]]
                st.dataframe(df, width=900)

    with tab_technicians:
        st.subheader("Create Technician")
        with st.form("create_tech"):
            tech_name = st.text_input("Name")
            tech_skills = st.multiselect("Skills", ["residential", "commercial", "install"])
            if st.form_submit_button("Create Technician"):
                resp = _post("/api/v1/technicians", {"name": tech_name, "skills": tech_skills, "active": True})
                if resp.status_code == 201:
                    st.success("Technician created!")
                    st.rerun()
                else:
                    st.error(f"Error: {resp.text}")

        st.subheader("Technician List")
        resp = _get("/api/v1/technicians")
        if resp.status_code == 200:
            techs = resp.json()
            if techs:
                import pandas as pd
                df = pd.DataFrame(techs)[["id", "name", "skills", "active"]]
                st.dataframe(df, width=900)

    with tab_work_orders:
        st.subheader("Create Work Order")
        # Fetch customers for dropdown
        cust_resp = _get("/api/v1/customers")
        customers_list = cust_resp.json() if cust_resp.status_code == 200 else []
        cust_options = {c["full_name"]: c["id"] for c in customers_list}

        with st.form("create_wo"):
            import datetime
            selected_cust = st.selectbox("Customer", list(cust_options.keys()) if cust_options else ["No customers"])
            desc = st.text_area("Description")
            priority = st.selectbox("Priority", ["routine", "urgent"])
            sched_date = st.date_input("Scheduled Date", value=datetime.date.today())
            time_win = st.selectbox("Time Window", ["morning", "afternoon", "all_day"])
            if st.form_submit_button("Create Work Order"):
                if selected_cust in cust_options:
                    resp = _post("/api/v1/work-orders", {
                        "customer_id": cust_options[selected_cust],
                        "description": desc,
                        "priority": priority,
                        "scheduled_date": str(sched_date),
                        "time_window": time_win,
                    })
                    if resp.status_code == 201:
                        st.success("Work order created!")
                        st.rerun()
                    else:
                        st.error(f"Error: {resp.text}")

        st.subheader("Assign Technician")
        # Fetch work orders and technicians for assignment
        wo_resp = _get("/api/v1/work-orders")
        work_orders_list = wo_resp.json() if wo_resp.status_code == 200 else []
        assignable = [wo for wo in work_orders_list if wo["status"] in ("new", "assigned")]
        wo_options = {f"{wo['description'][:40]} [{wo['status']}]": wo["id"] for wo in assignable}

        tech_resp = _get("/api/v1/technicians")
        techs_list = tech_resp.json() if tech_resp.status_code == 200 else []
        active_techs = [t for t in techs_list if t["active"]]
        tech_options = {t["name"]: t["id"] for t in active_techs}

        with st.form("assign_form"):
            sel_wo = st.selectbox("Work Order", list(wo_options.keys()) if wo_options else ["No assignable orders"])
            sel_tech = st.selectbox("Technician", list(tech_options.keys()) if tech_options else ["No active technicians"])
            if st.form_submit_button("Assign"):
                if sel_wo in wo_options and sel_tech in tech_options:
                    resp = _post("/api/v1/assignments", {
                        "work_order_id": wo_options[sel_wo],
                        "technician_id": tech_options[sel_tech],
                    })
                    if resp.status_code == 201:
                        st.success("Assigned!")
                        st.rerun()
                    else:
                        st.error(f"Error: {resp.json().get('detail', resp.text)}")


def technician_view():
    """Technician - My Jobs Today."""
    st.title("🔧 My Jobs Today")
    if st.button("🔄 Refresh"):
        st.rerun()

    import datetime
    resp = _get("/api/v1/work-orders", params={"date": str(datetime.date.today())})
    if resp.status_code == 200:
        orders = resp.json()
        if not orders:
            st.info("No jobs assigned for today.")
        for wo in orders:
            with st.expander(f"{'🔴' if wo['priority'] == 'urgent' else '⚪'} {wo['description']} [{wo['status']}]"):
                st.write(f"**Priority:** {wo['priority']}")
                st.write(f"**Time Window:** {wo['time_window']}")
                st.write(f"**Scheduled:** {wo['scheduled_date']}")
                if wo.get("completion_notes"):
                    st.write(f"**Notes:** {wo['completion_notes']}")

                # Action buttons based on status
                if wo["status"] == "assigned":
                    if st.button("▶️ Start (In Progress)", key=f"start_{wo['id']}"):
                        resp2 = _patch(f"/api/v1/work-orders/{wo['id']}/status", {"status": "in_progress"})
                        if resp2.status_code == 200:
                            st.success("Status updated!")
                            st.rerun()
                        else:
                            st.error(f"Error: {resp2.text}")

                elif wo["status"] == "in_progress":
                    with st.form(f"complete_{wo['id']}"):
                        notes = st.text_area("Completion Notes", key=f"notes_{wo['id']}")
                        parts_text = st.text_area("Parts (one per line: name,qty,cost)", key=f"parts_{wo['id']}")
                        if st.form_submit_button("✅ Complete"):
                            parts = []
                            if parts_text.strip():
                                for line in parts_text.strip().split("\n"):
                                    fields = line.split(",")
                                    if len(fields) >= 2:
                                        part = {"name": fields[0].strip(), "quantity": int(fields[1].strip())}
                                        if len(fields) >= 3:
                                            part["unit_cost"] = float(fields[2].strip())
                                        parts.append(part)
                            payload = {"status": "completed", "completion_notes": notes, "parts": parts}
                            resp2 = _patch(f"/api/v1/work-orders/{wo['id']}/status", payload)
                            if resp2.status_code == 200:
                                st.success("Job completed!")
                                st.rerun()
                            else:
                                st.error(f"Error: {resp2.json().get('detail', resp2.text)}")
    else:
        st.error(f"Error loading jobs: {resp.status_code}")


def owner_view():
    """Owner - Read-only board."""
    st.title("🔧 Owner Dashboard (Read-Only)")

    import datetime
    board_date = st.date_input("Board Date", value=datetime.date.today())
    if st.button("🔄 Refresh"):
        st.rerun()

    resp = _get("/api/v1/board", params={"date": str(board_date)})
    if resp.status_code == 200:
        board = resp.json()

        # SLA Breaches
        col1, col2, col3 = st.columns(3)
        col1.metric("Unassigned", len(board["unassigned"]))
        col2.metric("SLA Breaches", len(board["sla_breaches"]))
        total_assigned = sum(len(t["orders"]) for t in board["technicians"])
        col3.metric("Assigned Today", total_assigned)

        if board["sla_breaches"]:
            st.error(f"⚠️ {len(board['sla_breaches'])} SLA breach(es)")
            for o in board["sla_breaches"]:
                st.markdown(f"- 🔴 {o['description']} ({o['status']})")

        st.subheader("Technician Workload")
        for tech in board["technicians"]:
            with st.expander(f"{tech['technician_name']} ({len(tech['orders'])} orders)"):
                for o in tech["orders"]:
                    st.markdown(f"- {o['description']} [{o['status']}] {'🔴' if o.get('sla_breached') else ''}")
    else:
        st.error(f"Error: {resp.status_code}")


# ── Routing ───────────────────────────────────────────────────────────────────
if "token" not in st.session_state:
    login_page()
else:
    # Sidebar
    st.sidebar.write(f"**Logged in as:** {st.session_state.get('username', 'Unknown')}")
    st.sidebar.write(f"**Role:** {st.session_state.get('role', 'Unknown')}")
    if st.sidebar.button("Logout"):
        for key in ["token", "role", "technician_id", "username"]:
            st.session_state.pop(key, None)
        st.rerun()

    role = st.session_state.get("role")
    if role == "dispatcher":
        dispatcher_view()
    elif role == "technician":
        technician_view()
    elif role == "owner":
        owner_view()
    else:
        st.error(f"Unknown role: {role}")
