"""Benefits Q&A Desk — Streamlit UI.

Communicates exclusively via HTTP with the FastAPI backend.
"""
from __future__ import annotations

import os

import httpx
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

# ── Config ────────────────────────────────────────────────────────────────────
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")

st.set_page_config(page_title="Benefits Q&A Desk", page_icon="📋", layout="wide")


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


def _post(path: str, json_body: dict | None = None, **kwargs) -> httpx.Response:
    return httpx.post(
        f"{API_BASE_URL}{path}",
        json=json_body,
        headers=_headers(),
        timeout=60.0,
        follow_redirects=True,
        **kwargs,
    )


def _post_file(path: str, files: dict) -> httpx.Response:
    return httpx.post(
        f"{API_BASE_URL}{path}",
        files=files,
        headers=_headers(),
        timeout=120.0,
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
            "cd target-apps/benefits-qa-desk\n"
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
    st.title("📋 Benefits Q&A Desk — Login")
    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Sign In")
        if submitted:
            resp = httpx.post(
                f"{API_BASE_URL}/auth/token",
                json={"username": username, "password": password},
                timeout=15.0,
                follow_redirects=True,
            )
            if resp.status_code == 200:
                data = resp.json()
                st.session_state["token"] = data["access_token"]
                st.session_state["role"] = data["role"]
                st.session_state["username"] = username
                st.rerun()
            else:
                st.error("Invalid credentials. Please try again.")


def logout():
    for key in ["token", "role", "username"]:
        st.session_state.pop(key, None)
    st.rerun()


# ── Role Views ────────────────────────────────────────────────────────────────
def employee_view():
    """Employee: browse collections and ask questions."""
    tab_collections, tab_qa = st.tabs(["📁 Collections", "💬 Ask a Question"])

    with tab_collections:
        resp = _get("/api/v1/collections")
        if resp.status_code == 200:
            collections = resp.json()
            if collections:
                rows = [{"Name": c["name"], "Description": c.get("description") or ""} for c in collections]
                st.dataframe(rows, width="stretch")
            else:
                st.info("No collections available yet.")
        else:
            st.error(f"Error loading collections: {resp.status_code}")

    with tab_qa:
        # Fetch collections for selectbox
        resp = _get("/api/v1/collections")
        if resp.status_code == 200:
            collections = resp.json()
            if not collections:
                st.warning("No collections available for Q&A.")
                return
            options = {c["name"]: c["id"] for c in collections}
            selected = st.selectbox("Select a collection", list(options.keys()))
            question = st.text_area("Your question", placeholder="e.g., What is the deductible for PPO Standard?")
            if st.button("Ask"):
                if not question.strip():
                    st.warning("Please enter a question.")
                else:
                    coll_id = options[selected]
                    with st.spinner("Searching documents..."):
                        ask_resp = _post(f"/api/v1/collections/{coll_id}/ask", {"question": question})
                    if ask_resp.status_code == 200:
                        answer_data = ask_resp.json()
                        st.subheader("Answer")
                        st.write(answer_data["answer"])
                        if answer_data.get("citations"):
                            st.subheader("Citations")
                            for c in answer_data["citations"]:
                                st.markdown(f"**{c['filename']}**: {c['snippet']}")
                    else:
                        st.error(f"Error: {ask_resp.status_code} — {ask_resp.text}")


def contributor_view():
    """Contributor: collections + upload + documents + FAQ + Q&A."""
    tabs = st.tabs(["📁 Collections", "📤 Upload", "📄 Documents", "🏷️ FAQ Topics", "💬 Ask"])

    with tabs[0]:
        # List + Create collections
        resp = _get("/api/v1/collections")
        if resp.status_code == 200:
            collections = resp.json()
            if collections:
                rows = [{"Name": c["name"], "Description": c.get("description") or ""} for c in collections]
                st.dataframe(rows, width="stretch")
            else:
                st.info("No collections yet.")

        st.subheader("Create New Collection")
        with st.form("create_collection"):
            name = st.text_input("Name")
            desc = st.text_input("Description (optional)")
            submitted = st.form_submit_button("Create")
            if submitted and name.strip():
                r = _post("/api/v1/collections", {"name": name, "description": desc or None})
                if r.status_code == 201:
                    st.success(f"Collection '{name}' created!")
                    st.rerun()
                elif r.status_code == 409:
                    st.error("A collection with that name already exists.")
                else:
                    st.error(f"Error: {r.status_code} — {r.text}")

    with tabs[1]:
        # Upload document
        resp = _get("/api/v1/collections")
        if resp.status_code == 200:
            collections = resp.json()
            if not collections:
                st.warning("Create a collection first.")
            else:
                options = {c["name"]: c["id"] for c in collections}
                selected = st.selectbox("Collection", list(options.keys()), key="upload_col")
                uploaded = st.file_uploader("Upload file (PDF, TXT, DOCX)", type=["pdf", "txt", "docx"])
                if st.button("Upload") and uploaded:
                    coll_id = options[selected]
                    # Determine content type
                    ext = uploaded.name.rsplit(".", 1)[-1].lower() if "." in uploaded.name else ""
                    mime_map = {"pdf": "application/pdf", "txt": "text/plain", "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document"}
                    ct = mime_map.get(ext, "application/octet-stream")
                    r = _post_file(
                        f"/api/v1/collections/{coll_id}/documents",
                        files={"file": (uploaded.name, uploaded.getvalue(), ct)},
                    )
                    if r.status_code == 201:
                        st.success(f"Uploaded '{uploaded.name}' — processing started.")
                        st.rerun()
                    elif r.status_code == 422:
                        st.error(f"Upload rejected: {r.json().get('detail', r.text)}")
                    else:
                        st.error(f"Error: {r.status_code} — {r.text}")

    with tabs[2]:
        # List documents per collection
        resp = _get("/api/v1/collections")
        if resp.status_code == 200:
            collections = resp.json()
            if collections:
                options = {c["name"]: c["id"] for c in collections}
                selected = st.selectbox("Collection", list(options.keys()), key="docs_col")
                coll_id = options[selected]
                docs_resp = _get(f"/api/v1/collections/{coll_id}/documents")
                if docs_resp.status_code == 200:
                    docs = docs_resp.json()
                    if docs:
                        rows = [{"Filename": d["filename"], "Status": d["status"], "Uploaded": d.get("uploaded_at") or ""} for d in docs]
                        st.dataframe(rows, width="stretch")
                    else:
                        st.info("No documents in this collection.")

    with tabs[3]:
        # FAQ Topics
        resp = _get("/api/v1/faq-topics")
        if resp.status_code == 200:
            topics = resp.json()
            if topics:
                st.dataframe([{"Label": t["label"]} for t in topics], width="stretch")
        st.subheader("Create FAQ Topic")
        with st.form("create_faq"):
            label = st.text_input("Label")
            sub = st.form_submit_button("Create")
            if sub and label.strip():
                r = _post("/api/v1/faq-topics", {"label": label})
                if r.status_code == 201:
                    st.success(f"Topic '{label}' created!")
                    st.rerun()
                elif r.status_code == 409:
                    st.error("Topic already exists.")
                else:
                    st.error(f"Error: {r.status_code}")

    with tabs[4]:
        # Q&A same as employee
        resp = _get("/api/v1/collections")
        if resp.status_code == 200:
            collections = resp.json()
            if collections:
                options = {c["name"]: c["id"] for c in collections}
                selected = st.selectbox("Collection", list(options.keys()), key="ask_col_contrib")
                question = st.text_area("Your question", key="q_contrib")
                if st.button("Ask", key="ask_btn_contrib"):
                    if question.strip():
                        coll_id = options[selected]
                        with st.spinner("Searching..."):
                            r = _post(f"/api/v1/collections/{coll_id}/ask", {"question": question})
                        if r.status_code == 200:
                            data = r.json()
                            st.subheader("Answer")
                            st.write(data["answer"])
                            if data.get("citations"):
                                for c in data["citations"]:
                                    st.markdown(f"**{c['filename']}**: {c['snippet']}")
                        else:
                            st.error(f"Error: {r.status_code}")


def admin_view():
    """Admin: everything contributor has + audit trail."""
    tabs = st.tabs(["📁 Collections", "📤 Upload", "📄 Documents", "🏷️ FAQ Topics", "💬 Ask", "📊 Audit Trail"])

    with tabs[0]:
        resp = _get("/api/v1/collections")
        if resp.status_code == 200:
            collections = resp.json()
            if collections:
                rows = [{"Name": c["name"], "Description": c.get("description") or ""} for c in collections]
                st.dataframe(rows, width="stretch")
            else:
                st.info("No collections yet.")
        st.subheader("Create New Collection")
        with st.form("admin_create_collection"):
            name = st.text_input("Name")
            desc = st.text_input("Description (optional)")
            submitted = st.form_submit_button("Create")
            if submitted and name.strip():
                r = _post("/api/v1/collections", {"name": name, "description": desc or None})
                if r.status_code == 201:
                    st.success(f"Collection '{name}' created!")
                    st.rerun()
                elif r.status_code == 409:
                    st.error("A collection with that name already exists.")
                else:
                    st.error(f"Error: {r.status_code}")

    with tabs[1]:
        resp = _get("/api/v1/collections")
        if resp.status_code == 200:
            collections = resp.json()
            if not collections:
                st.warning("Create a collection first.")
            else:
                options = {c["name"]: c["id"] for c in collections}
                selected = st.selectbox("Collection", list(options.keys()), key="admin_upload_col")
                uploaded = st.file_uploader("Upload file (PDF, TXT, DOCX)", type=["pdf", "txt", "docx"], key="admin_uploader")
                if st.button("Upload", key="admin_upload_btn") and uploaded:
                    coll_id = options[selected]
                    ext = uploaded.name.rsplit(".", 1)[-1].lower() if "." in uploaded.name else ""
                    mime_map = {"pdf": "application/pdf", "txt": "text/plain", "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document"}
                    ct = mime_map.get(ext, "application/octet-stream")
                    r = _post_file(
                        f"/api/v1/collections/{coll_id}/documents",
                        files={"file": (uploaded.name, uploaded.getvalue(), ct)},
                    )
                    if r.status_code == 201:
                        st.success(f"Uploaded '{uploaded.name}'.")
                        st.rerun()
                    else:
                        st.error(f"Error: {r.status_code}")

    with tabs[2]:
        resp = _get("/api/v1/collections")
        if resp.status_code == 200:
            collections = resp.json()
            if collections:
                options = {c["name"]: c["id"] for c in collections}
                selected = st.selectbox("Collection", list(options.keys()), key="admin_docs_col")
                coll_id = options[selected]
                docs_resp = _get(f"/api/v1/collections/{coll_id}/documents")
                if docs_resp.status_code == 200:
                    docs = docs_resp.json()
                    if docs:
                        rows = [{"Filename": d["filename"], "Status": d["status"], "Uploaded": d.get("uploaded_at") or ""} for d in docs]
                        st.dataframe(rows, width="stretch")
                    else:
                        st.info("No documents.")

    with tabs[3]:
        resp = _get("/api/v1/faq-topics")
        if resp.status_code == 200:
            topics = resp.json()
            if topics:
                st.dataframe([{"Label": t["label"]} for t in topics], width="stretch")
        st.subheader("Create FAQ Topic")
        with st.form("admin_create_faq"):
            label = st.text_input("Label")
            sub = st.form_submit_button("Create")
            if sub and label.strip():
                r = _post("/api/v1/faq-topics", {"label": label})
                if r.status_code == 201:
                    st.success(f"Topic '{label}' created!")
                    st.rerun()
                elif r.status_code == 409:
                    st.error("Topic already exists.")
                else:
                    st.error(f"Error: {r.status_code}")

    with tabs[4]:
        resp = _get("/api/v1/collections")
        if resp.status_code == 200:
            collections = resp.json()
            if collections:
                options = {c["name"]: c["id"] for c in collections}
                selected = st.selectbox("Collection", list(options.keys()), key="admin_ask_col")
                question = st.text_area("Your question", key="admin_q")
                if st.button("Ask", key="admin_ask_btn"):
                    if question.strip():
                        coll_id = options[selected]
                        with st.spinner("Searching..."):
                            r = _post(f"/api/v1/collections/{coll_id}/ask", {"question": question})
                        if r.status_code == 200:
                            data = r.json()
                            st.subheader("Answer")
                            st.write(data["answer"])
                            if data.get("citations"):
                                for c in data["citations"]:
                                    st.markdown(f"**{c['filename']}**: {c['snippet']}")
                        else:
                            st.error(f"Error: {r.status_code}")

    with tabs[5]:
        st.subheader("Audit Trail")
        resp = _get("/api/v1/audit", params={"page": 1, "page_size": 50})
        if resp.status_code == 200:
            data = resp.json()
            items = data.get("items", [])
            if items:
                rows = [
                    {
                        "Timestamp": i.get("timestamp", ""),
                        "User": i.get("user_id", "")[:8] + "...",
                        "Role": i.get("role_at_time", ""),
                        "Action": i.get("action_type", ""),
                        "Resource": i.get("resource_name", ""),
                        "Outcome": i.get("outcome", ""),
                    }
                    for i in items
                ]
                st.dataframe(rows, width="stretch")
            else:
                st.info("No audit events recorded yet.")
            st.caption(f"Total events: {data.get('total', 0)}")
        elif resp.status_code == 403:
            st.error("Access denied — admin only.")
        else:
            st.error(f"Error: {resp.status_code}")


# ── Main ──────────────────────────────────────────────────────────────────────
_ensure_api_reachable()

if "token" not in st.session_state:
    login_form()
else:
    role = st.session_state.get("role", "employee")
    username = st.session_state.get("username", "")
    st.sidebar.title("📋 Benefits Q&A Desk")
    st.sidebar.write(f"Logged in as **{username}** ({role})")
    if st.sidebar.button("Logout"):
        logout()

    if role == "admin":
        admin_view()
    elif role == "contributor":
        contributor_view()
    else:
        employee_view()
