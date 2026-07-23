"""Streamlit UI for Student Management API.

Calls the FastAPI backend over HTTP. Requires the API to be running on port 8000.

Coverage: GET /api/v1/students, GET /api/v1/students/{id}, GET /api/v1/students/seed
"""
from __future__ import annotations

import os

import httpx
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

# ── Config ────────────────────────────────────────────────────────────────────
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")

st.set_page_config(page_title="Student Management", page_icon="\ud83c\udf93", layout="wide")


# ── HTTP helpers (DO NOT MODIFY) ─────────────────────────────────────────────
def _headers() -> dict[str, str]:
    """Build headers from session state API key."""
    key = st.session_state.get("api_key", "")
    if key:
        return {"X-API-Key": key}
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
        json=json_body,
        headers=_headers(),
        timeout=60.0,
        follow_redirects=True,
    )


def _put(path: str, json_body: dict) -> httpx.Response:
    return httpx.put(
        f"{API_BASE_URL}{path}",
        json=json_body,
        headers=_headers(),
        timeout=30.0,
        follow_redirects=True,
    )


def _patch(path: str, json_body: dict | None = None) -> httpx.Response:
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
        resp = httpx.get(
            f"{API_BASE_URL}/health",
            timeout=10.0,
            follow_redirects=True,
        )
        if resp.status_code == 503:
            data = resp.json()
            failed = [k for k, v in data.get("checks", {}).items() if v != "ok"]
            st.error(
                f"API is running but unhealthy \u2014 failing checks: {', '.join(failed)}.\n\n"
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
            "cd target-apps/student-management\n"
            ".venv\\Scripts\\Activate.ps1  # or source .venv/bin/activate\n"
            "uvicorn app.main:app --reload --port 8000 --reload-dir app --reload-dir schemas\n"
            "```"
        )
        st.stop()
    except Exception as exc:
        st.error(f"Unexpected error reaching API: {exc}")
        st.stop()


# ── Startup check ─────────────────────────────────────────────────────────────
_ensure_api_reachable()

# ── Sidebar — API key ─────────────────────────────────────────────────────────
st.sidebar.title("\ud83d\udd11 Authentication")
api_key_input = st.sidebar.text_input(
    "API Key",
    value=st.session_state.get("api_key", ""),
    type="password",
    help="Enter WRITE_API_KEY (full access) or READ_API_KEY (read-only).",
)
if api_key_input:
    st.session_state["api_key"] = api_key_input

if not st.session_state.get("api_key"):
    st.warning("Enter your API key in the sidebar to access data.")
    st.stop()

# ── Main UI ───────────────────────────────────────────────────────────────────
st.title("\ud83c\udf93 Student Management")

tab_browse, tab_create, tab_update, tab_deactivate, tab_seed = st.tabs(
    ["Browse Students", "Create Student", "Update Student", "Deactivate", "Seed Data"]
)

# ── Tab: Browse (calls GET /api/v1/students) ──────────────────────────────────
with tab_browse:
    st.subheader("Student List")
    col1, col2 = st.columns(2)
    with col1:
        filter_course = st.text_input("Filter by course", key="browse_course")
    with col2:
        filter_status = st.selectbox(
            "Filter by status",
            options=["", "active", "inactive"],
            key="browse_status",
        )
    params: dict[str, str] = {}
    if filter_course:
        params["course"] = filter_course
    if filter_status:
        params["status"] = filter_status

    resp = _get("/api/v1/students", params=params if params else None)
    if resp.status_code == 200:
        students = resp.json()
        if students:
            import pandas as pd
            df = pd.DataFrame(students)
            display_cols = ["student_id", "full_name", "email", "course", "enrollment_date", "status"]
            existing_cols = [c for c in display_cols if c in df.columns]
            st.dataframe(df[existing_cols], width="stretch")
        else:
            st.info("No students found.")
    elif resp.status_code == 401:
        st.error("Invalid API key. Check your key in the sidebar.")
    else:
        st.error(f"Error {resp.status_code}: {resp.text}")

# ── Tab: Create ───────────────────────────────────────────────────────────────
with tab_create:
    st.subheader("Create New Student")
    with st.form("create_form"):
        sid = st.text_input("Code (e.g. STU-010)", key="create_sid")
        fname = st.text_input("Full Name", key="create_fname")
        email = st.text_input("Email", key="create_email")
        course = st.text_input("Course", key="create_course")
        enroll = st.date_input("Enrollment Date", key="create_enroll")
        submitted = st.form_submit_button("Create")
        if submitted:
            payload = {
                "student_id": sid,
                "full_name": fname,
                "email": email,
                "course": course,
                "enrollment_date": str(enroll),
            }
            r = _post("/api/v1/students", payload)
            if r.status_code == 201:
                st.success(f"Student {sid} created!")
                st.json(r.json())
            elif r.status_code == 409:
                st.error("Conflict: student_id or email already exists.")
            elif r.status_code == 401:
                st.error("Unauthorized \u2014 write key required.")
            else:
                st.error(f"Error {r.status_code}: {r.text}")

# ── Tab: Update ───────────────────────────────────────────────────────────────
with tab_update:
    st.subheader("Update Student")
    resp_all = _get("/api/v1/students")
    if resp_all.status_code == 200:
        all_students = resp_all.json()
        if all_students:
            options = {s["student_id"]: s["full_name"] for s in all_students}
            selected_sid = st.selectbox(
                "Select student to update",
                options=list(options.keys()),
                format_func=lambda x: f"{x} \u2014 {options[x]}",
                key="update_select",
            )
            current = next((s for s in all_students if s["student_id"] == selected_sid), None)
            if current:
                with st.form("update_form"):
                    new_name = st.text_input("Full Name", value=current["full_name"])
                    new_email = st.text_input("Email", value=current["email"])
                    new_course = st.text_input("Course", value=current["course"])
                    new_status = st.selectbox(
                        "Status",
                        options=["active", "inactive"],
                        index=0 if current["status"] == "active" else 1,
                    )
                    update_submitted = st.form_submit_button("Update")
                    if update_submitted:
                        update_payload: dict = {}
                        if new_name != current["full_name"]:
                            update_payload["full_name"] = new_name
                        if new_email != current["email"]:
                            update_payload["email"] = new_email
                        if new_course != current["course"]:
                            update_payload["course"] = new_course
                        if new_status != current["status"]:
                            update_payload["status"] = new_status
                        if update_payload:
                            r = _put(f"/api/v1/students/{selected_sid}", update_payload)
                            if r.status_code == 200:
                                st.success("Updated!")
                                st.json(r.json())
                                st.rerun()
                            else:
                                st.error(f"Error {r.status_code}: {r.text}")
                        else:
                            st.info("No changes detected.")
        else:
            st.info("No students to update.")
    else:
        st.error("Could not load student list.")

# ── Tab: Deactivate ───────────────────────────────────────────────────────────
with tab_deactivate:
    st.subheader("Deactivate Student")
    resp_active = _get("/api/v1/students", params={"status": "active"})
    if resp_active.status_code == 200:
        active_students = resp_active.json()
        if active_students:
            options_d = {s["student_id"]: s["full_name"] for s in active_students}
            deact_sid = st.selectbox(
                "Select active student to deactivate",
                options=list(options_d.keys()),
                format_func=lambda x: f"{x} \u2014 {options_d[x]}",
                key="deact_select",
            )
            if st.button("Deactivate", key="deact_btn"):
                r = _patch(f"/api/v1/students/{deact_sid}/deactivate")
                if r.status_code == 200:
                    st.success(f"{deact_sid} deactivated!")
                    st.rerun()
                elif r.status_code == 401:
                    st.error("Unauthorized \u2014 write key required.")
                else:
                    st.error(f"Error {r.status_code}: {r.text}")
        else:
            st.info("No active students to deactivate.")
    else:
        st.error("Could not load active students.")

# ── Tab: Seed (calls GET /api/v1/students/seed) ──────────────────────────────
with tab_seed:
    st.subheader("Seed Demo Data")
    st.markdown(
        "Insert 3 predefined demo students (STU-001, STU-002, STU-003). "
        "Idempotent \u2014 safe to run multiple times."
    )
    # Show seed status via GET /api/v1/students/seed
    seed_status = _get("/api/v1/students/seed")
    if seed_status.status_code == 200:
        seed_info = seed_status.json()
        st.info(f"Currently {seed_info['seeded']} of 3 seed records exist.")

    if st.button("Seed Now", key="seed_btn"):
        r = _post("/api/v1/students/seed")
        if r.status_code == 200:
            data = r.json()
            st.success(f"Seeded {data['seeded']} new student(s).")
            st.rerun()
        elif r.status_code == 401:
            st.error("Unauthorized \u2014 write key required.")
        else:
            st.error(f"Error {r.status_code}: {r.text}")
