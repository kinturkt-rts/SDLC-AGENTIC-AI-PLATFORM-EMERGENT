"""IT Asset Lifecycle — Streamlit UI.

Role-gated views: Asset Catalog, Assign/Return, Alerts Dashboard, Finance Valuation.
Communicates with FastAPI backend over HTTP. Never imports from app/ directly.
"""
from __future__ import annotations

import os

import httpx
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

# ── Config ────────────────────────────────────────────────────────────────────
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")

st.set_page_config(page_title="IT Asset Lifecycle", page_icon="💻", layout="wide")


# ── HTTP helpers ─────────────────────────────────────────────────────────────
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


def _post(path: str, json_body: dict | None = None) -> httpx.Response:
    return httpx.post(
        f"{API_BASE_URL}{path}",
        json=json_body or {},
        headers=_headers(),
        timeout=60.0,
        follow_redirects=True,
    )


def _patch(path: str, json_body: dict | None = None) -> httpx.Response:
    return httpx.patch(
        f"{API_BASE_URL}{path}",
        json=json_body or {},
        headers=_headers(),
        timeout=30.0,
        follow_redirects=True,
    )


def _ensure_api_reachable() -> None:
    """Check API health on startup."""
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
            "cd target-apps/it-asset-lifecycle\n"
            ".venv\\Scripts\\Activate.ps1  # or source .venv/bin/activate\n"
            "uvicorn app.main:app --reload --port 8000\n"
            "```"
        )
        st.stop()
    except Exception as exc:
        st.error(f"Unexpected error reaching API: {exc}")
        st.stop()


# ── Login ─────────────────────────────────────────────────────────────────────
def login_form():
    st.title("🔐 Login")
    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Login")
        if submitted:
            resp = httpx.post(
                f"{API_BASE_URL}/auth/login",
                json={"username": username, "password": password},
                timeout=30.0,
                follow_redirects=True,
            )
            if resp.status_code == 200:
                data = resp.json()
                st.session_state["token"] = data["access_token"]
                st.session_state["role"] = data["role"]
                st.session_state["username"] = username
                st.rerun()
            else:
                st.error("Invalid credentials")


def logout():
    for key in ["token", "role", "username"]:
        st.session_state.pop(key, None)
    st.rerun()


# ── Views ─────────────────────────────────────────────────────────────────────
def asset_catalog_view():
    st.header("📦 Asset Catalog")
    col1, col2, col3 = st.columns(3)
    with col1:
        type_filter = st.selectbox("Asset Type", ["All", "laptop", "monitor", "phone", "license", "misc"])
    with col2:
        status_filter = st.selectbox("Status", ["All", "in_stock", "assigned", "repair", "retired"])
    with col3:
        warranty_days = st.number_input("Warranty expiring within (days)", min_value=0, value=0, step=1)

    params = {}
    if type_filter != "All":
        params["type"] = type_filter
    if status_filter != "All":
        params["status"] = status_filter
    if warranty_days > 0:
        params["warranty_expiring_within_days"] = warranty_days

    resp = _get("/assets", params=params)
    if resp.status_code == 200:
        assets = resp.json()
        if assets:
            st.dataframe(assets, use_container_width=True)
        else:
            st.info("No assets found.")
    else:
        st.error(f"Error: {resp.status_code} — {resp.text}")


def assign_return_view():
    st.header("🔄 Assign / Return")
    tab1, tab2 = st.tabs(["Assign Asset", "Return Asset"])

    with tab1:
        with st.form("assign_form"):
            asset_id = st.text_input("Asset ID")
            employee_id = st.text_input("Employee ID")
            submitted = st.form_submit_button("Assign")
            if submitted and asset_id and employee_id:
                resp = _post(f"/assets/{asset_id}/assign", {"employee_id": employee_id})
                if resp.status_code == 201:
                    st.success("Asset assigned successfully!")
                    st.json(resp.json())
                else:
                    st.error(f"Error {resp.status_code}: {resp.json().get('detail', resp.text)}")

    with tab2:
        with st.form("return_form"):
            ret_asset_id = st.text_input("Asset ID to Return")
            condition = st.selectbox("Condition", ["in_stock", "repair"])
            note = st.text_area("Note (optional)")
            submitted = st.form_submit_button("Return")
            if submitted and ret_asset_id:
                body = {"condition": condition}
                if note:
                    body["note"] = note
                resp = _post(f"/assets/{ret_asset_id}/return", body)
                if resp.status_code == 200:
                    st.success("Asset returned successfully!")
                    st.json(resp.json())
                else:
                    st.error(f"Error {resp.status_code}: {resp.json().get('detail', resp.text)}")


def alerts_view():
    st.header("🚨 Alerts Dashboard")
    tab1, tab2, tab3 = st.tabs(["Offboarding", "Warranty", "License Overages"])

    with tab1:
        resp = _get("/alerts/offboarding")
        if resp.status_code == 200:
            data = resp.json()
            if data:
                for alert in data:
                    with st.expander(f"{alert['full_name']} — {alert['department']}"):
                        st.write(f"**Email:** {alert['email']}")
                        st.write(f"**Deactivated:** {alert.get('deactivated_at', 'N/A')}")
                        st.write("**Active Assets:**")
                        st.json(alert["active_assets"])
            else:
                st.success("No offboarding alerts!")
        else:
            st.error(f"Error: {resp.status_code}")

    with tab2:
        days = st.number_input("Days ahead", min_value=1, value=30, key="warranty_days")
        resp = _get("/alerts/warranty", params={"days": days})
        if resp.status_code == 200:
            data = resp.json()
            if data:
                st.dataframe(data, use_container_width=True)
            else:
                st.success("No warranty alerts!")
        else:
            st.error(f"Error: {resp.status_code}")

    with tab3:
        resp = _get("/alerts/license-overages")
        if resp.status_code == 200:
            data = resp.json()
            if data:
                st.dataframe(data, use_container_width=True)
            else:
                st.success("No license overages!")
        else:
            st.error(f"Error: {resp.status_code}")


def valuation_view():
    st.header("💰 Valuation by Department")
    resp = _get("/reports/valuation-by-department")
    if resp.status_code == 200:
        data = resp.json()
        if data:
            st.dataframe(data, use_container_width=True)
        else:
            st.info("No valuation data available.")
    else:
        st.error(f"Error: {resp.status_code}")


# ── Main ──────────────────────────────────────────────────────────────────────
_ensure_api_reachable()

if "token" not in st.session_state:
    login_form()
else:
    role = st.session_state.get("role", "")
    username = st.session_state.get("username", "")

    # Sidebar navigation
    st.sidebar.title(f"👤 {username} ({role})")
    if st.sidebar.button("Logout"):
        logout()

    pages = ["Asset Catalog"]
    if role in ("it_admin", "it_staff"):
        pages.append("Assign / Return")
        pages.append("Alerts")
    if role in ("it_admin", "finance_readonly"):
        pages.append("Valuation Report")

    selection = st.sidebar.radio("Navigation", pages)

    if selection == "Asset Catalog":
        asset_catalog_view()
    elif selection == "Assign / Return":
        assign_return_view()
    elif selection == "Alerts":
        alerts_view()
    elif selection == "Valuation Report":
        valuation_view()
