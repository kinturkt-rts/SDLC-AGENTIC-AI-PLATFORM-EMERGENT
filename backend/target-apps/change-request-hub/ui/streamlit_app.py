"""Change Request Hub — Streamlit UI.

Runs as Terminal 2: streamlit run ui/streamlit_app.py --server.port 8501
Connects to the FastAPI backend over HTTP (never imports app/).
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

import requests
import streamlit as st

# Config
API_BASE_URL = os.environ.get("API_BASE_URL", "http://localhost:8000")
_REQUEST_TIMEOUT = 30


class _ErrorResponse:
    """Stand-in when requests fails so views can show errors without crashing."""

    status_code = 0

    def __init__(self, detail: str) -> None:
        self._detail = detail

    def json(self) -> dict:
        return {"detail": self._detail}


# ---- HTTP helpers ----
def _headers() -> dict:
    token = st.session_state.get("access_token")
    if token:
        return {"Authorization": f"Bearer {token}"}
    return {}


def _get(path: str, params: dict | None = None):
    try:
        return requests.get(
            f"{API_BASE_URL}{path}",
            headers=_headers(),
            params=params,
            timeout=_REQUEST_TIMEOUT,
        )
    except requests.Timeout:
        return _ErrorResponse(
            "API read timed out. Ensure Terminal 1 is running and use "
            "`uvicorn ... --reload-dir app --reload-dir schemas` (not bare `--reload`)."
        )
    except requests.ConnectionError:
        return _ErrorResponse(f"Cannot connect to API at {API_BASE_URL}")


def _post(path: str, json: dict | None = None):
    try:
        return requests.post(
            f"{API_BASE_URL}{path}",
            headers=_headers(),
            json=json,
            timeout=_REQUEST_TIMEOUT,
        )
    except requests.Timeout:
        return _ErrorResponse("API timed out on POST")
    except requests.ConnectionError:
        return _ErrorResponse(f"Cannot connect to API at {API_BASE_URL}")


def _patch(path: str, json: dict | None = None):
    try:
        return requests.patch(
            f"{API_BASE_URL}{path}",
            headers=_headers(),
            json=json,
            timeout=_REQUEST_TIMEOUT,
        )
    except requests.Timeout:
        return _ErrorResponse("API timed out on PATCH")
    except requests.ConnectionError:
        return _ErrorResponse(f"Cannot connect to API at {API_BASE_URL}")


def _implementer_options() -> dict[str, str]:
    """Load implementers once per render (never inside a per-row loop)."""
    users_resp = _get("/api/v1/users", params={"role": "implementer", "page_size": 50})
    if users_resp.status_code == 200:
        return {u["display_name"]: u["id"] for u in users_resp.json()["items"]}
    return {}


def _ensure_api_reachable():
    try:
        r = requests.get(f"{API_BASE_URL}/health", timeout=5)
        if r.status_code != 200:
            st.error(f"API health check returned {r.status_code}. Ensure the API is running.")
            st.stop()
    except (requests.ConnectionError, requests.Timeout):
        st.error(f"Cannot connect to API at {API_BASE_URL}. Start the API first (Terminal 1).")
        st.stop()


# ---- Login ----
def login_page():
    st.title("🔐 Change Request Hub — Login")
    with st.form("login_form"):
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Login")
    if submitted:
        resp = _post("/api/v1/auth/token", json={"email": email, "password": password})
        if resp.status_code == 200:
            data = resp.json()
            st.session_state["access_token"] = data["access_token"]
            # Decode role from token (simple base64 decode of payload)
            import json, base64
            payload = data["access_token"].split(".")[1]
            # Add padding
            payload += "=" * (4 - len(payload) % 4)
            claims = json.loads(base64.urlsafe_b64decode(payload))
            st.session_state["user_id"] = claims.get("sub")
            st.session_state["role"] = claims.get("role")
            st.rerun()
        else:
            st.error("Invalid credentials")


# ---- Requester View ----
def requester_view():
    st.header("📝 My Change Requests")
    tab1, tab2 = st.tabs(["My Changes", "Create Change Request"])

    with tab1:
        resp = _get("/api/v1/change-requests")
        if resp.status_code == 200:
            data = resp.json()
            if data["items"]:
                for cr in data["items"]:
                    with st.expander(f"{cr['title']} [{cr['status']}]"):
                        st.write(f"**Type:** {cr['change_type']} | **Risk:** {cr['risk']}")
                        st.write(f"**Created:** {cr['created_at']}")
                        st.write(f"**Description:** {cr['description']}")
                        # Submit button for drafts
                        if cr["status"] == "draft":
                            if st.button("Submit for Approval", key=f"submit_{cr['id']}"):
                                r = _patch(f"/api/v1/change-requests/{cr['id']}/status", json={"to_status": "submitted"})
                                if r.status_code == 200:
                                    st.success("Submitted!")
                                    st.rerun()
                                else:
                                    st.error(r.json().get("detail", "Error"))
            else:
                st.info("No change requests yet.")
        else:
            st.error("Failed to load changes")

    with tab2:
        # Load services and environments for dropdowns
        svcs = _get("/api/v1/services", params={"page_size": 100})
        envs = _get("/api/v1/environments", params={"page_size": 100})
        svc_list = svcs.json()["items"] if svcs.status_code == 200 else []
        env_list = envs.json()["items"] if envs.status_code == 200 else []

        with st.form("create_cr"):
            title = st.text_input("Title*")
            description = st.text_area("Description*")
            svc_names = {s["name"]: s["id"] for s in svc_list}
            env_names = {e["name"]: e["id"] for e in env_list}
            service_name = st.selectbox("Service*", list(svc_names.keys()) if svc_names else [""])
            env_name = st.selectbox("Target Environment*", list(env_names.keys()) if env_names else [""])
            change_type = st.selectbox("Change Type*", ["standard", "normal", "emergency"])
            risk = st.selectbox("Risk*", ["low", "medium", "high", "critical"])
            planned_start = st.date_input("Planned Start*")
            planned_end = st.date_input("Planned End*")
            rollback_plan = st.text_area("Rollback Plan*")
            submitted = st.form_submit_button("Create")

        if submitted:
            if not all([title, description, service_name, env_name, rollback_plan]):
                st.error("All fields are required")
            else:
                body = {
                    "title": title,
                    "description": description,
                    "service_id": svc_names.get(service_name, ""),
                    "target_environment_id": env_names.get(env_name, ""),
                    "change_type": change_type,
                    "risk": risk,
                    "planned_start": datetime.combine(planned_start, datetime.min.time(), tzinfo=timezone.utc).isoformat(),
                    "planned_end": datetime.combine(planned_end, datetime.min.time(), tzinfo=timezone.utc).isoformat(),
                    "rollback_plan": rollback_plan,
                }
                r = _post("/api/v1/change-requests", json=body)
                if r.status_code == 201:
                    st.success("Change request created!")
                    st.rerun()
                else:
                    st.error(r.json().get("detail", "Error creating change request"))


# ---- Manager View ----
def manager_view():
    st.header("📋 Change Manager")
    tab1, tab2, tab3, tab4 = st.tabs(["Triage Queue", "Service Catalog", "Environments", "Blackout Windows"])

    with tab1:
        resp = _get("/api/v1/change-requests", params={"page_size": 50})
        impl_map = _implementer_options()
        if resp.status_code == 200:
            items = resp.json()["items"]
            if items:
                for cr in items:
                    with st.expander(f"{cr['title']} [{cr['status']}] - {cr['change_type']}/{cr['risk']}"):
                        st.write(f"**ID:** {cr['id']}")
                        st.write(f"**Description:** {cr['description']}")
                        st.write(f"**Planned:** {cr.get('planned_start', 'N/A')} → {cr.get('planned_end', 'N/A')}")

                        col1, col2, col3 = st.columns(3)
                        if cr["status"] == "submitted":
                            with col1:
                                if st.button("✅ Approve", key=f"appr_{cr['id']}"):
                                    r = _patch(f"/api/v1/change-requests/{cr['id']}/status", json={"to_status": "approved"})
                                    if r.status_code == 200:
                                        st.success("Approved")
                                        st.rerun()
                                    else:
                                        st.error(r.json().get("detail", "Error"))
                            with col2:
                                reason = st.text_input("Reason", key=f"rej_reason_{cr['id']}")
                                if st.button("❌ Reject", key=f"rej_{cr['id']}"):
                                    r = _patch(f"/api/v1/change-requests/{cr['id']}/status", json={"to_status": "rejected", "reason": reason})
                                    if r.status_code == 200:
                                        st.success("Rejected")
                                        st.rerun()
                                    else:
                                        st.error(r.json().get("detail", "Error"))
                        if cr["status"] == "approved":
                            with col1:
                                if st.button("📅 Schedule", key=f"sched_{cr['id']}"):
                                    r = _patch(f"/api/v1/change-requests/{cr['id']}/status", json={"to_status": "scheduled"})
                                    if r.status_code == 200:
                                        st.success("Scheduled")
                                        st.rerun()
                                    else:
                                        st.error(r.json().get("detail", "Error"))
                        if cr["status"] == "completed":
                            with col1:
                                if st.button("🔒 Close", key=f"close_{cr['id']}"):
                                    r = _patch(f"/api/v1/change-requests/{cr['id']}/status", json={"to_status": "closed"})
                                    if r.status_code == 200:
                                        st.success("Closed")
                                        st.rerun()
                                    else:
                                        st.error(r.json().get("detail", "Error"))

                        # Assign implementer
                        with col3:
                            if impl_map:
                                sel = st.selectbox(
                                    "Assign",
                                    [""] + list(impl_map.keys()),
                                    key=f"assign_sel_{cr['id']}",
                                )
                                if sel and st.button("Assign", key=f"assign_{cr['id']}"):
                                    r = _patch(
                                        f"/api/v1/change-requests/{cr['id']}/assign",
                                        json={"implementer_id": impl_map[sel]},
                                    )
                                    if r.status_code == 200:
                                        st.success("Assigned")
                                        st.rerun()
                                    else:
                                        st.error(r.json().get("detail", "Error"))
                            else:
                                st.caption("No implementers loaded")
            else:
                st.info("No change requests.")
        else:
            st.error(resp.json().get("detail", "Failed to load change requests"))

    with tab2:
        st.subheader("Services")
        svc_resp = _get("/api/v1/services", params={"page_size": 100})
        if svc_resp.status_code == 200:
            for s in svc_resp.json()["items"]:
                st.write(f"- **{s['name']}** ({s['tier']}) — {s['owner_team']}")
        with st.form("create_service"):
            sname = st.text_input("Name")
            steam = st.text_input("Owner Team")
            stier = st.selectbox("Tier", ["tier1", "tier2", "tier3"])
            if st.form_submit_button("Create Service"):
                r = _post("/api/v1/services", json={"name": sname, "owner_team": steam, "tier": stier})
                if r.status_code == 201:
                    st.success("Created")
                    st.rerun()
                else:
                    st.error(r.json().get("detail", "Error"))

    with tab3:
        st.subheader("Environments")
        env_resp = _get("/api/v1/environments", params={"page_size": 100})
        if env_resp.status_code == 200:
            for e in env_resp.json()["items"]:
                st.write(f"- **{e['name']}** (order: {e['sort_order']})")
        with st.form("create_env"):
            ename = st.text_input("Environment Name")
            eorder = st.number_input("Sort Order", min_value=1, value=1)
            if st.form_submit_button("Create Environment"):
                r = _post("/api/v1/environments", json={"name": ename, "sort_order": int(eorder)})
                if r.status_code == 201:
                    st.success("Created")
                    st.rerun()
                else:
                    st.error(r.json().get("detail", "Error"))

    with tab4:
        st.subheader("Blackout Windows")
        bw_resp = _get("/api/v1/blackout-windows", params={"page_size": 100})
        if bw_resp.status_code == 200:
            for b in bw_resp.json()["items"]:
                st.write(f"- {b['start_at']} → {b['end_at']} — {b['reason']}")
        env_resp2 = _get("/api/v1/environments", params={"page_size": 100})
        env_list2 = env_resp2.json()["items"] if env_resp2.status_code == 200 else []
        with st.form("create_bw"):
            bw_env_map = {e["name"]: e["id"] for e in env_list2}
            bw_env = st.selectbox("Environment", list(bw_env_map.keys()) if bw_env_map else [""])
            bw_start = st.date_input("Start")
            bw_end = st.date_input("End")
            bw_reason = st.text_input("Reason")
            if st.form_submit_button("Create Blackout Window"):
                body = {
                    "environment_id": bw_env_map.get(bw_env, ""),
                    "start_at": datetime.combine(bw_start, datetime.min.time(), tzinfo=timezone.utc).isoformat(),
                    "end_at": datetime.combine(bw_end, datetime.min.time(), tzinfo=timezone.utc).isoformat(),
                    "reason": bw_reason,
                }
                r = _post("/api/v1/blackout-windows", json=body)
                if r.status_code == 201:
                    st.success("Created")
                    st.rerun()
                else:
                    st.error(r.json().get("detail", "Error"))


# ---- Implementer View ----
def implementer_view():
    st.header("🔧 My Queue")
    resp = _get("/api/v1/change-requests")
    if resp.status_code == 200:
        items = resp.json()["items"]
        if items:
            for cr in items:
                with st.expander(f"{cr['title']} [{cr['status']}]"):
                    st.write(f"**Type:** {cr['change_type']} | **Risk:** {cr['risk']}")
                    st.write(f"**Description:** {cr['description']}")
                    if cr["status"] == "scheduled":
                        if st.button("▶️ Start", key=f"start_{cr['id']}"):
                            r = _patch(f"/api/v1/change-requests/{cr['id']}/status", json={"to_status": "implementing"})
                            if r.status_code == 200:
                                st.success("Started")
                                st.rerun()
                            else:
                                st.error(r.json().get("detail", "Error"))
                    elif cr["status"] == "implementing":
                        if st.button("✅ Complete", key=f"complete_{cr['id']}"):
                            r = _patch(f"/api/v1/change-requests/{cr['id']}/status", json={"to_status": "completed"})
                            if r.status_code == 200:
                                st.success("Completed")
                                st.rerun()
                            else:
                                st.error(r.json().get("detail", "Error"))
                    # Comment box
                    comment_text = st.text_input("Add comment", key=f"comment_{cr['id']}")
                    if st.button("Post Comment", key=f"post_comment_{cr['id']}"):
                        if comment_text:
                            r = _post(f"/api/v1/change-requests/{cr['id']}/comments", json={"body": comment_text})
                            if r.status_code == 201:
                                st.success("Comment posted")
                                st.rerun()
                            else:
                                st.error(r.json().get("detail", "Error"))
        else:
            st.info("No assigned changes.")
    else:
        st.error("Failed to load queue")


# ---- Leadership View ----
def leadership_view():
    st.header("📊 Leadership Dashboard")
    resp = _get("/api/v1/dashboard/summary")
    if resp.status_code == 200:
        data = resp.json()
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Overdue Scheduled", data["overdue_scheduled_count"])
        with col2:
            st.metric("Active Emergencies", data["active_emergency_count"])
        with col3:
            total_changes = sum(data["counts_by_status"].values())
            st.metric("Total Changes", total_changes)

        st.subheader("Counts by Status")
        for status_val, count in data["counts_by_status"].items():
            st.write(f"- **{status_val}**: {count}")

        st.subheader("Counts by Risk")
        for risk_val, count in data["counts_by_risk"].items():
            st.write(f"- **{risk_val}**: {count}")

        st.subheader("Top Services")
        for svc in data["top_services"]:
            st.write(f"- Service {svc['service_id']}: {svc['count']} changes")

        st.subheader("Monthly by Environment")
        for env in data["monthly_by_env"]:
            st.write(f"- Env {env['environment_id']}: {env['count']} changes this month")
    else:
        st.error("Failed to load dashboard")


# ---- Main ----
def main():
    st.set_page_config(page_title="Change Request Hub", layout="wide")
    _ensure_api_reachable()

    if "access_token" not in st.session_state:
        login_page()
        return

    role = st.session_state.get("role", "")
    st.sidebar.title(f"Role: {role.title()}")
    if st.sidebar.button("Logout"):
        for k in ["access_token", "user_id", "role"]:
            st.session_state.pop(k, None)
        st.rerun()

    if role == "requester":
        requester_view()
    elif role == "manager":
        manager_view()
    elif role == "implementer":
        implementer_view()
    elif role == "leadership":
        leadership_view()
    else:
        st.error(f"Unknown role: {role}")


if __name__ == "__main__":
    main()
else:
    main()
