"""Training Compliance — Streamlit UI.

Role-gated screens:
  - HR Admin: Catalog, Roster, Record Completion
  - Manager: Team Compliance Board
  - Employee: My Trainings
  - Compliance Officer: Org Dashboard & Alerts

Communicates with FastAPI exclusively over HTTP. Never imports app/ modules.
"""
from __future__ import annotations

import os

import httpx
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

# ── Config
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")

st.set_page_config(page_title="Training Compliance", page_icon="📋", layout="wide")


# ── HTTP helpers (DO NOT MODIFY)
def _headers() -> dict[str, str]:
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
                "- Is the RDS/Postgres instance reachable?\n"
                "- Run `curl http://localhost:8000/health` for details."
            )
            st.stop()
    except httpx.ConnectError:
        st.error(
            f"Could not reach the API at {API_BASE_URL}.\n\n"
            "Start the API first:\n"
            "```\n"
            "cd target-apps/training-compliance\n"
            ".venv\\Scripts\\Activate.ps1  # or source .venv/bin/activate\n"
            "uvicorn app.main:app --reload --port 8000\n"
            "```"
        )
        st.stop()
    except Exception as exc:
        st.error(f"Unexpected error reaching API: {exc}")
        st.stop()


# ── Startup check
_ensure_api_reachable()


# ── Login screen
def show_login():
    st.title("🔐 Login")
    with st.form("login_form"):
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Login")
        if submitted:
            resp = httpx.post(
                f"{API_BASE_URL}/auth/token",
                json={"email": email, "password": password},
                timeout=30.0,
                follow_redirects=True,
            )
            if resp.status_code == 200:
                data = resp.json()
                st.session_state["token"] = data["access_token"]
                # Decode role from token (simple base64)
                import json
                import base64
                payload_b64 = data["access_token"].split(".")[1]
                # Add padding
                payload_b64 += "=" * (4 - len(payload_b64) % 4)
                claims = json.loads(base64.urlsafe_b64decode(payload_b64))
                st.session_state["role"] = claims.get("role", "")
                st.session_state["employee_id"] = claims.get("employee_id", "")
                st.session_state["user_id"] = claims.get("sub", "")
                st.rerun()
            else:
                st.error("Invalid credentials. Please try again.")


def show_logout():
    if st.sidebar.button("Logout"):
        for key in ["token", "role", "employee_id", "user_id"]:
            st.session_state.pop(key, None)
        st.rerun()


# ── HR Admin screens
def hr_catalog():
    st.subheader("📚 Course Catalog")
    resp = _get("/courses")
    if resp.status_code == 200:
        courses = resp.json()
        if courses:
            st.dataframe(courses, use_container_width=True)
        else:
            st.info("No courses found.")

    st.divider()
    st.subheader("Add Course")
    with st.form("add_course"):
        name = st.text_input("Course Name")
        category = st.selectbox("Category", ["safety", "security", "role_specific"])
        validity = st.number_input("Validity (months, 0 = no expiry)", min_value=0, value=12)
        all_staff = st.checkbox("Required for all staff")
        cert_ref = st.text_input("Certificate Reference (optional)")
        submitted = st.form_submit_button("Create Course")
        if submitted and name:
            payload = {
                "name": name,
                "category": category,
                "validity_period_months": validity if validity > 0 else None,
                "required_for_all_staff": all_staff,
                "certificate_ref": cert_ref or None,
            }
            r = _post("/courses", payload)
            if r.status_code == 201:
                st.success(f"Course '{name}' created!")
                st.rerun()
            else:
                st.error(f"Error {r.status_code}: {r.text}")


def hr_roster():
    st.subheader("👥 Employee Roster")
    resp = _get("/employees")
    if resp.status_code == 200:
        employees = resp.json()
        if employees:
            st.dataframe(employees, use_container_width=True)
        else:
            st.info("No employees found.")


def hr_record_completion():
    st.subheader("✅ Record Completion")
    with st.form("record_completion"):
        emp_id = st.text_input("Employee ID")
        course_id = st.text_input("Course ID")
        comp_date = st.date_input("Completion Date")
        submitted = st.form_submit_button("Record")
        if submitted and emp_id and course_id:
            r = _post("/completions", {
                "employee_id": emp_id,
                "course_id": course_id,
                "completion_date": str(comp_date),
            })
            if r.status_code == 201:
                st.success("Completion recorded!")
                st.json(r.json())
            else:
                st.error(f"Error {r.status_code}: {r.text}")


# ── Manager screen
def manager_team_board():
    st.subheader("👥 My Team Compliance")
    resp = _get("/compliance/team")
    if resp.status_code == 200:
        data = resp.json()
        if data:
            for emp in data:
                with st.expander(f"{emp['full_name']} ({emp['email']})"):
                    if emp["statuses"]:
                        st.dataframe(emp["statuses"])
                    else:
                        st.info("No required courses.")
        else:
            st.info("No direct reports found.")
    else:
        st.error(f"Error: {resp.text}")


# ── Employee screen
def employee_my_trainings():
    st.subheader("📋 My Trainings")
    emp_id = st.session_state.get("employee_id", "")
    if not emp_id:
        st.warning("No employee record linked to your account.")
        return
    resp = _get(f"/compliance/employee/{emp_id}")
    if resp.status_code == 200:
        data = resp.json()
        if data:
            st.dataframe(data, use_container_width=True)
        else:
            st.info("No required courses assigned to you.")
    else:
        st.error(f"Error: {resp.text}")


# ── Compliance Officer screen
def co_dashboard():
    st.subheader("📊 Org-Wide Dashboard")
    resp = _get("/reports/dashboard")
    if resp.status_code == 200:
        data = resp.json()
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Overdue Employees", len(data.get("overdue", [])))
        with col2:
            st.metric("Expiring Soon", len(data.get("expiring_soon", [])))

        st.divider()
        st.subheader("Compliance Rate by Department")
        if data.get("rate_by_dept"):
            st.dataframe(data["rate_by_dept"], use_container_width=True)

        st.divider()
        st.subheader("Course Gaps")
        if data.get("course_gaps"):
            st.dataframe(data["course_gaps"], use_container_width=True)
    else:
        st.error(f"Error: {resp.text}")


def co_alerts():
    st.subheader("🚨 Alerts")
    resp = _get("/alerts")
    if resp.status_code == 200:
        alerts = resp.json()
        if alerts:
            st.dataframe(alerts, use_container_width=True)
        else:
            st.success("No alerts!")
    else:
        st.error(f"Error: {resp.text}")


# ── Main routing
if "token" not in st.session_state:
    show_login()
else:
    show_logout()
    role = st.session_state.get("role", "")
    st.sidebar.write(f"**Role:** {role}")
    st.title("📋 Training Compliance")

    if role == "hr_admin":
        tab1, tab2, tab3 = st.tabs(["Catalog", "Roster", "Record Completion"])
        with tab1:
            hr_catalog()
        with tab2:
            hr_roster()
        with tab3:
            hr_record_completion()
    elif role == "manager":
        manager_team_board()
    elif role == "employee":
        employee_my_trainings()
    elif role == "compliance_officer":
        tab1, tab2 = st.tabs(["Dashboard", "Alerts"])
        with tab1:
            co_dashboard()
        with tab2:
            co_alerts()
    else:
        st.warning(f"Unknown role: {role}")
