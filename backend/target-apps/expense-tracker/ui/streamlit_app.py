"""Streamlit UI for Expense Tracker — calls FastAPI over HTTP."""
from __future__ import annotations

import os
from decimal import Decimal

import httpx
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

# ── Config ──
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")
API_KEY = os.getenv("API_KEY", "")

HEADERS: dict[str, str] = {}
if API_KEY:
    HEADERS["X-API-Key"] = API_KEY

st.set_page_config(page_title="Expense Tracker", page_icon="\U0001f4b0", layout="wide")


# ── HTTP helpers (DO NOT MODIFY) ──
def _get(path: str, params: dict | None = None) -> httpx.Response:
    return httpx.get(
        f"{API_BASE_URL}{path}",
        params=params,
        headers=HEADERS,
        timeout=30.0,
        follow_redirects=True,
    )


def _post(path: str, json_body: dict) -> httpx.Response:
    return httpx.post(
        f"{API_BASE_URL}{path}",
        json=json_body,
        headers=HEADERS,
        timeout=60.0,
        follow_redirects=True,
    )


def _patch(path: str, json_body: dict) -> httpx.Response:
    return httpx.patch(
        f"{API_BASE_URL}{path}",
        json=json_body,
        headers=HEADERS,
        timeout=30.0,
        follow_redirects=True,
    )


def _delete(path: str) -> httpx.Response:
    return httpx.delete(
        f"{API_BASE_URL}{path}",
        headers=HEADERS,
        timeout=30.0,
        follow_redirects=True,
    )


def _ensure_api_reachable() -> None:
    """Check API health on startup."""
    try:
        resp = _get("/health")
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
            "cd target-apps/expense-tracker\n"
            ".venv\\Scripts\\Activate.ps1  # or source .venv/bin/activate\n"
            "uvicorn app.main:app --reload --port 8000\n"
            "```\n\n"
            "If the API crashed, check the terminal for errors."
        )
        st.stop()
    except Exception as exc:
        st.error(f"Unexpected error reaching API: {exc}")
        st.stop()


_ensure_api_reachable()

# ── Sidebar: API Key input ──
with st.sidebar:
    st.header("\U0001f511 Authentication")
    key_input = st.text_input("API Key", value=API_KEY, type="password")
    if key_input:
        HEADERS["X-API-Key"] = key_input
    role_hint = st.selectbox("Role hint (for tab display)", ["employee", "manager", "admin"])

st.title("\U0001f4b0 Expense Tracker")

# ── Tabs based on role ──
if role_hint == "employee":
    tab_submit, tab_my = st.tabs(["\U0001f4dd Submit Expense", "\U0001f4cb My Expenses"])

    with tab_submit:
        with st.form("submit_expense"):
            amount = st.number_input("Amount", min_value=0.01, step=0.01, format="%.2f")
            currency = st.selectbox("Currency", ["USD", "GBP", "EUR", "CAD", "JPY"])
            category = st.selectbox("Category", ["travel", "meals", "software", "other"])
            description = st.text_area("Description", max_chars=1000)
            expense_date = st.date_input("Expense Date")
            submitted = st.form_submit_button("Submit", type="primary")
            if submitted:
                resp = _post("/api/v1/expenses", {
                    "amount": str(amount),
                    "currency": currency,
                    "category": category,
                    "description": description,
                    "expense_date": expense_date.isoformat(),
                })
                if resp.status_code == 201:
                    st.success("Expense submitted!")
                    st.json(resp.json())
                else:
                    st.error(f"Error {resp.status_code}: {resp.text}")

    with tab_my:
        resp = _get("/api/v1/expenses", params={"page": "1", "size": "50"})
        if resp.status_code == 200:
            data = resp.json()
            items = data.get("items", [])
            if items:
                import pandas as pd
                df = pd.DataFrame(items)
                cols = ["id", "amount", "currency", "amount_usd", "category", "status", "expense_date"]
                display_cols = [c for c in cols if c in df.columns]
                st.dataframe(df[display_cols], width="stretch")
            else:
                st.info("No expenses found.")
        else:
            st.error(f"Error {resp.status_code}: {resp.text}")

elif role_hint == "manager":
    st.subheader("\U0001f4ca Team Summary")
    # Fetch teams
    teams_resp = _get("/api/v1/teams")
    if teams_resp.status_code == 200:
        teams = teams_resp.json()
        if teams:
            team_names = {t["id"]: t["name"] for t in teams}
            selected_team = st.selectbox("Team", list(team_names.keys()), format_func=lambda x: team_names[x])
            col1, col2 = st.columns(2)
            year = col1.number_input("Year", value=2024, min_value=2020, max_value=2030)
            month = col2.number_input("Month", value=6, min_value=1, max_value=12)
            if st.button("Get Summary"):
                resp = _get(f"/api/v1/teams/{selected_team}/expenses/summary", params={"year": str(int(year)), "month": str(int(month))})
                if resp.status_code == 200:
                    data = resp.json()
                    st.metric("Grand Total (USD)", f"${data['grand_total_usd']}")
                    for cat in data.get("categories", []):
                        st.write(f"- **{cat['category']}**: ${cat['total_usd']}")
                else:
                    st.error(f"Error {resp.status_code}: {resp.text}")
        else:
            st.info("No teams found.")
    else:
        st.error(f"Could not fetch teams: {teams_resp.status_code}")

elif role_hint == "admin":
    tab_approve, tab_teams, tab_fx = st.tabs(["\u2705 Approve/Reject", "\U0001f465 Teams", "\U0001f4b1 FX Snapshots"])

    with tab_approve:
        resp = _get("/api/v1/expenses", params={"status": "submitted", "page": "1", "size": "50"})
        if resp.status_code == 200:
            data = resp.json()
            items = data.get("items", [])
            if items:
                for item in items:
                    with st.expander(f"{item['category']} - {item['amount']} {item['currency']} ({item['expense_date']})"):
                        st.json(item)
                        col1, col2 = st.columns(2)
                        reason = st.text_input("Reason", key=f"reason_{item['id']}")
                        if col1.button("Approve", key=f"approve_{item['id']}"):
                            r = _post(f"/api/v1/expenses/{item['id']}/approve", {"reason": reason})
                            if r.status_code == 200:
                                st.success("Approved!")
                                st.rerun()
                            else:
                                st.error(f"Error: {r.text}")
                        if col2.button("Reject", key=f"reject_{item['id']}"):
                            r = _post(f"/api/v1/expenses/{item['id']}/reject", {"reason": reason})
                            if r.status_code == 200:
                                st.warning("Rejected.")
                                st.rerun()
                            else:
                                st.error(f"Error: {r.text}")
            else:
                st.info("No pending expenses.")
        else:
            st.error(f"Error {resp.status_code}: {resp.text}")

    with tab_teams:
        st.subheader("Create Team")
        with st.form("create_team"):
            team_name = st.text_input("Team Name")
            team_desc = st.text_area("Description")
            create_team = st.form_submit_button("Create Team")
            if create_team and team_name:
                r = _post("/api/v1/teams", {"name": team_name, "description": team_desc})
                if r.status_code == 201:
                    st.success("Team created!")
                    st.rerun()
                else:
                    st.error(f"Error: {r.text}")

        st.subheader("Existing Teams")
        teams_resp = _get("/api/v1/teams")
        if teams_resp.status_code == 200:
            teams = teams_resp.json()
            if teams:
                import pandas as pd
                df = pd.DataFrame(teams)
                st.dataframe(df[["id", "name", "description"]], width="stretch")
            else:
                st.info("No teams.")

    with tab_fx:
        st.subheader("Add FX Snapshot")
        with st.form("add_fx"):
            fx_currency = st.text_input("Currency (3-letter ISO)", max_chars=3)
            fx_date = st.date_input("Date")
            fx_rate = st.number_input("Rate to USD", min_value=0.0001, step=0.0001, format="%.4f")
            add_fx = st.form_submit_button("Add/Update")
            if add_fx and fx_currency:
                r = _post("/api/v1/fx-snapshots", {
                    "currency": fx_currency.upper(),
                    "date": fx_date.isoformat(),
                    "rate_to_usd": str(fx_rate),
                })
                if r.status_code == 201:
                    st.success("FX snapshot saved!")
                    st.rerun()
                else:
                    st.error(f"Error: {r.text}")
