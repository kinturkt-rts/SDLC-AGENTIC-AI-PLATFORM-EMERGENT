"""Streamlit UI template — calls the FastAPI backend over HTTP.

ADAPT checklist:
  - Replace SERVICE_NAME, PAGE_TITLE, PAGE_ICON with app-specific values.
  - Replace the example tabs/forms with your actual UI per the PRD/design.
  - Keep all httpx helper functions and _ensure_api_reachable() unchanged.
  - Every httpx call uses follow_redirects=True (FastAPI 307 redirect fix).
"""
from __future__ import annotations

import os

import httpx
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

# ── Config ────────────────────────────────────────────────────────────────────
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")
API_KEY = os.getenv("API_KEY", "")

HEADERS: dict[str, str] = {}
if API_KEY:
    HEADERS["X-API-Key"] = API_KEY

st.set_page_config(page_title="SERVICE_NAME", page_icon="🔧", layout="wide")


# ── HTTP helpers (DO NOT MODIFY) ─────────────────────────────────────────────
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
    """Check API health on startup; stop with actionable error if unreachable."""
    try:
        resp = _get("/health")
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
            "cd target-apps/<app-name>\n"
            ".venv\\Scripts\\Activate.ps1  # or source .venv/bin/activate\n"
            "uvicorn app.main:app --reload --port 8000 --reload-dir app --reload-dir schemas\n"
            "```\n\n"
            "If the API crashed, check the terminal for errors (common: DATABASE_URL not set in .env)."
        )
        st.stop()
    except Exception as exc:
        st.error(f"Unexpected error reaching API: {exc}")
        st.stop()


# ── Main ──────────────────────────────────────────────────────────────────────
_ensure_api_reachable()

st.title("SERVICE_NAME")

# ADAPT: Replace with your actual tabs/forms per the design doc.
# Example tab structure:
# tab1, tab2 = st.tabs(["Create", "History"])
# with tab1:
#     with st.form("create_form"):
#         field = st.text_input("Field name")
#         submitted = st.form_submit_button("Submit")
#         if submitted:
#             resp = _post("/your-endpoint/", {"field": field})
#             if resp.status_code in (200, 201):
#                 st.success("Created!")
#                 st.json(resp.json())
#             else:
#                 st.error(f"Error {resp.status_code}: {resp.text}")
# with tab2:
#     resp = _get("/your-endpoint/")
#     if resp.status_code == 200:
#         st.dataframe(resp.json())
