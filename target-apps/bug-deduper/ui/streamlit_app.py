"""Bug Deduper — Streamlit UI.

Calls the FastAPI backend over HTTP. Never imports from app/ directly.
"""
from __future__ import annotations

import os
import time
from pathlib import Path

import httpx
import streamlit as st
from dotenv import load_dotenv

_APP_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(_APP_ROOT / ".env")

# ── Config ─────────────────────────────────────────────────────────────────
API_BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:8000")
API_KEY = os.getenv("API_KEY_STANDARD", os.getenv("API_KEY", ""))
ADMIN_KEY = os.getenv("API_KEY_ADMIN", "")

HEADERS: dict[str, str] = {}
if API_KEY:
    HEADERS["X-API-Key"] = API_KEY

ADMIN_HEADERS: dict[str, str] = {}
if ADMIN_KEY:
    ADMIN_HEADERS["X-API-Key"] = ADMIN_KEY

st.set_page_config(page_title="Bug Deduper", page_icon="\U0001f41b", layout="wide")


# ── HTTP helpers (DO NOT MODIFY) ───────────────────────────────────────────
def _get(path: str, params: dict | None = None, headers: dict | None = None) -> httpx.Response:
    return httpx.get(
        f"{API_BASE_URL}{path}",
        params=params,
        headers=headers or HEADERS,
        timeout=30.0,
        follow_redirects=True,
    )


def _post(path: str, json_body: dict, headers: dict | None = None) -> httpx.Response:
    return httpx.post(
        f"{API_BASE_URL}{path}",
        json=json_body,
        headers=headers or HEADERS,
        timeout=60.0,
        follow_redirects=True,
    )


def _patch(path: str, json_body: dict, headers: dict | None = None) -> httpx.Response:
    return httpx.patch(
        f"{API_BASE_URL}{path}",
        json=json_body,
        headers=headers or HEADERS,
        timeout=30.0,
        follow_redirects=True,
    )


def _ensure_api_reachable() -> None:
    """Check API health on startup; stop with actionable error if unreachable."""
    last_error: str | None = None
    for attempt in range(3):
        try:
            resp = httpx.get(
                f"{API_BASE_URL}/health",
                headers={},
                timeout=15.0,
                follow_redirects=True,
            )
            if resp.status_code == 200:
                data = resp.json()
                db_status = data.get("checks", {}).get("database")
                if db_status == "ok":
                    return
                last_error = f"database check: {db_status}"
            elif resp.status_code == 503:
                data = resp.json()
                checks = data.get("checks", {})
                db_status = checks.get("database", "unknown")
                failed = [k for k, v in checks.items() if v != "ok"]
                last_error = f"failing checks: {', '.join(failed)} ({db_status})"
            else:
                last_error = f"HTTP {resp.status_code}: {resp.text[:200]}"
        except httpx.ConnectError:
            st.error(
                "Could not reach the API at " + API_BASE_URL + ".\n\n"
                "Start the API first:\n"
                "```\n"
                "cd target-apps/bug-deduper\n"
                ".venv\\Scripts\\Activate.ps1  # or source .venv/bin/activate\n"
                "uvicorn app.main:app --reload --port 8000\n"
                "```\n\n"
                "If the API crashed, check the terminal for errors (common: DATABASE_URL not set in .env)."
            )
            st.stop()
        except Exception as exc:
            last_error = str(exc)

        if attempt < 2:
            time.sleep(1.0)

    st.error(
        f"API is running but unhealthy — {last_error}.\n\n"
        "Troubleshooting:\n"
        f"- Confirm `{API_BASE_URL}/health` shows database ok in your browser\n"
        "- Is DATABASE_URL set in target-apps/bug-deduper/.env?\n"
        "- If uvicorn just reloaded, refresh this page (R)\n"
        "- Is RDS reachable from your machine?"
    )
    st.stop()


# ── Main ────────────────────────────────────────────────────────────────────
_ensure_api_reachable()

st.title("\U0001f41b Bug Deduper")
st.caption("Submit bugs with duplicate detection powered by vector search.")

tab1, tab2, tab3 = st.tabs(["Submit Bug", "Lookup Bug", "Admin Actions"])

# ── Tab 1: Submit Bug ──────────────────────────────────────────────────
with tab1:
    st.subheader("Submit a New Bug Report")
    with st.form("submit_bug_form"):
        title = st.text_input("Bug Title", placeholder="e.g. Login page returns 500 error")
        description = st.text_area(
            "Description",
            placeholder="Describe the bug in detail...",
            height=200,
        )
        submitted = st.form_submit_button("Submit Bug")
        if submitted:
            if not title or not description:
                st.warning("Both title and description are required.")
            else:
                resp = _post("/bugs", {"title": title, "description": description})
                if resp.status_code == 201:
                    data = resp.json()
                    st.success(f"Bug created! ID: {data['bug']['id']}")
                    if data["likely_duplicate"]:
                        st.warning(
                            f"\u26a0\ufe0f Likely duplicate detected! "
                            f"Top match: {data['top_match_id']}"
                        )
                    if data["similar_bugs"]:
                        st.write("**Similar open bugs:**")
                        for sb in data["similar_bugs"]:
                            st.write(
                                f"- **{sb['title']}** (ID: {sb['id']}, "
                                f"score: {sb['similarity_score']:.3f})"
                            )
                else:
                    st.error(f"Error {resp.status_code}: {resp.text}")

# ── Tab 2: Lookup Bug ──────────────────────────────────────────────────
with tab2:
    st.subheader("Lookup Bug by ID")
    bug_id = st.text_input("Bug ID (UUID)", placeholder="b2000000-0000-0000-0000-000000000001")
    if st.button("Fetch Bug"):
        if not bug_id:
            st.warning("Enter a bug ID.")
        else:
            resp = _get(f"/bugs/{bug_id}")
            if resp.status_code == 200:
                data = resp.json()
                st.json(data)
            elif resp.status_code == 404:
                st.warning("Bug not found.")
            else:
                st.error(f"Error {resp.status_code}: {resp.text}")

# ── Tab 3: Admin Actions ───────────────────────────────────────────────
with tab3:
    st.subheader("Admin Actions")
    st.info("These actions require the admin API key (set API_KEY_ADMIN in .env).")

    col1, col2 = st.columns(2)

    with col1:
        st.write("**Mark as Duplicate**")
        dup_bug_id = st.text_input("Bug ID to mark", key="dup_bug")
        canonical_id = st.text_input("Canonical Bug ID", key="canonical_bug")
        if st.button("Mark Duplicate"):
            if not dup_bug_id or not canonical_id:
                st.warning("Both fields required.")
            elif not ADMIN_KEY:
                st.error("API_KEY_ADMIN not set in .env")
            else:
                resp = _post(
                    f"/bugs/{dup_bug_id}/duplicate",
                    {"canonical_bug_id": canonical_id},
                    headers=ADMIN_HEADERS,
                )
                if resp.status_code == 200:
                    st.success("Bug marked as duplicate!")
                    st.json(resp.json())
                else:
                    st.error(f"Error {resp.status_code}: {resp.text}")

    with col2:
        st.write("**Resolve Bug**")
        resolve_bug_id = st.text_input("Bug ID to resolve", key="resolve_bug")
        if st.button("Resolve"):
            if not resolve_bug_id:
                st.warning("Enter a bug ID.")
            elif not ADMIN_KEY:
                st.error("API_KEY_ADMIN not set in .env")
            else:
                resp = _post(
                    f"/bugs/{resolve_bug_id}/resolve",
                    {},
                    headers=ADMIN_HEADERS,
                )
                if resp.status_code == 200:
                    st.success("Bug resolved!")
                    st.json(resp.json())
                else:
                    st.error(f"Error {resp.status_code}: {resp.text}")
