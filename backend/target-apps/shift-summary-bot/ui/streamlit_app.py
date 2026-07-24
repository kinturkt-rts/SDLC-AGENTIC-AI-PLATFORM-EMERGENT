"""Shift Handoff Helper - Streamlit UI.

Calls the FastAPI backend over HTTP. Never imports from app/.
Auth: shared API key entered via login form, sent as Authorization: Bearer header.
"""
from __future__ import annotations

import os

import httpx
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

# ── Config ─────────────────────────────────────────────────────────────────────
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")

st.set_page_config(page_title="Shift Handoff Helper", page_icon="\U0001f4cb", layout="wide")


# ── Session state init ────────────────────────────────────────────────────────
if "api_key" not in st.session_state:
    st.session_state.api_key = ""


def _headers() -> dict[str, str]:
    """Build auth headers from session state."""
    return {"Authorization": f"Bearer {st.session_state.api_key}"}


# ── HTTP helpers ─────────────────────────────────────────────────────────────
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
            "cd target-apps/shift-summary-bot\n"
            ".venv\\Scripts\\Activate.ps1  # or source .venv/bin/activate\n"
            "uvicorn app.main:app --reload --port 8000 --reload-dir app --reload-dir schemas\n"
            "```\n\n"
            "If the API crashed, check the terminal for errors (common: DATABASE_URL not set in .env)."
        )
        st.stop()
    except Exception as exc:
        st.error(f"Unexpected error reaching API: {exc}")
        st.stop()


# ── Login gate ───────────────────────────────────────────────────────────────
def _login_form() -> None:
    """Show API key entry form; block all views until key is entered."""
    st.title("\U0001f510 Shift Handoff Helper")
    st.info("Enter your shared API key to continue.")
    with st.form("login_form"):
        key = st.text_input("API Key", type="password")
        submitted = st.form_submit_button("Connect", type="primary")
        if submitted:
            if not key.strip():
                st.error("API key cannot be empty.")
            else:
                test_resp = httpx.get(
                    f"{API_BASE_URL}/api/v1/handoffs",
                    headers={"Authorization": f"Bearer {key.strip()}"},
                    timeout=10.0,
                    follow_redirects=True,
                )
                if test_resp.status_code == 401:
                    st.error("Invalid API key. Please check and try again.")
                elif test_resp.status_code in (200, 503):
                    st.session_state.api_key = key.strip()
                    st.rerun()
                else:
                    st.error(f"Unexpected response ({test_resp.status_code}). Is the API healthy?")


# ── Main UI ─────────────────────────────────────────────────────────────────
_ensure_api_reachable()

if not st.session_state.api_key:
    _login_form()
    st.stop()

st.title("\U0001f4cb Shift Handoff Helper")

# Sidebar logout
with st.sidebar:
    st.markdown("### \U0001f511 Authenticated")
    if st.button("Logout"):
        st.session_state.api_key = ""
        st.rerun()

tab_submit, tab_history = st.tabs(["\U0001f4dd Submit Note", "\U0001f4da History"])

# ── Submit Tab ───────────────────────────────────────────────────────────────
with tab_submit:
    st.subheader("Paste your shift note")
    note_text = st.text_area(
        "Shift Note",
        height=200,
        placeholder="Describe what happened during your shift: incidents handled, tickets worked, outstanding issues...",
    )

    if st.button("\U0001f680 Generate Handoff", type="primary"):
        if not note_text.strip():
            st.warning("Please enter your shift note before submitting.")
        else:
            with st.spinner("Generating structured handoff..."):
                resp = _post("/api/v1/handoffs/summarise", {"note": note_text})

            if resp.status_code == 200:
                result = resp.json()
                if result["was_refused"]:
                    st.warning("\U0001f6ab Refusal")
                    st.info(result.get("refusal_message", "Insufficient context."))
                else:
                    st.success("\u2705 Structured handoff generated!")
                    handoff = result["structured_handoff"]
                    if handoff:
                        col1, col2 = st.columns(2)
                        with col1:
                            st.markdown("#### \u2705 Work Completed")
                            for item in handoff.get("work_completed", []):
                                st.markdown(f"- {item}")

                            st.markdown("#### \u26a0\ufe0f Urgency")
                            for item in handoff.get("urgency", []):
                                st.markdown(f"- {item}")
                        with col2:
                            st.markdown("#### \U0001f534 Open Issues")
                            for item in handoff.get("open_issues", []):
                                st.markdown(f"- {item}")

                            st.markdown("#### \U0001f50d Suggested First Checks")
                            for item in handoff.get("suggested_first_checks", []):
                                st.markdown(f"- {item}")
            elif resp.status_code == 401:
                st.error("Authentication failed. Please logout and re-enter your API key.")
            else:
                st.error(f"Error {resp.status_code}: {resp.text}")

# ── History Tab ──────────────────────────────────────────────────────────────
with tab_history:
    st.subheader("Recent Handoffs")
    resp = _get("/api/v1/handoffs", params={"limit": 20})
    if resp.status_code == 200:
        handoffs = resp.json()
        if not handoffs:
            st.info("No handoffs yet. Submit a shift note to get started!")
        else:
            for h in handoffs:
                status_icon = "\U0001f6ab" if h["was_refused"] else "\u2705"
                with st.expander(f"{status_icon} {h['submitted_at'][:19]} \u2014 {h.get('preview', 'N/A')[:80]}"):
                    if h["was_refused"]:
                        st.warning("This note was refused (too vague).")
                    elif h.get("structured_output"):
                        output = h["structured_output"]
                        st.markdown("**Work Completed:**")
                        for item in output.get("work_completed", []):
                            st.markdown(f"- {item}")
                        st.markdown("**Open Issues:**")
                        for item in output.get("open_issues", []):
                            st.markdown(f"- {item}")
                        st.markdown("**Urgency:**")
                        for item in output.get("urgency", []):
                            st.markdown(f"- {item}")
                        st.markdown("**Suggested First Checks:**")
                        for item in output.get("suggested_first_checks", []):
                            st.markdown(f"- {item}")
    elif resp.status_code == 401:
        st.error("Authentication failed. Please logout and re-enter your API key.")
    else:
        st.error(f"Failed to load history: {resp.status_code}")
