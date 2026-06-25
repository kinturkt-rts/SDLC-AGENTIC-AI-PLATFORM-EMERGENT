"""Support Knowledge Hub — Streamlit UI.

Role-gated multi-page app that calls the FastAPI backend over HTTP.
Never imports from app/ directly.
"""
from __future__ import annotations

import os

import httpx
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

# ── Config ──────────────────────────────────────────────────────────────────
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")

st.set_page_config(page_title="Support Knowledge Hub", page_icon="📚", layout="wide")


# ── HTTP helpers (DO NOT MODIFY) ───────────────────────────────────────────
def _headers() -> dict[str, str]:
    h: dict[str, str] = {}
    token = st.session_state.get("token")
    if token:
        h["Authorization"] = f"Bearer {token}"
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
                "- Is the RDS/Postgres instance reachable from your machine?"
            )
            st.stop()
    except httpx.ConnectError:
        st.error(
            f"Could not reach the API at {API_BASE_URL}.\n\n"
            "Start the API first:\n"
            "```\n"
            "cd target-apps/support-knowledge-hub\n"
            "source .venv/bin/activate  # or .venv\\Scripts\\Activate.ps1\n"
            "uvicorn app.main:app --reload --port 8000\n"
            "```"
        )
        st.stop()
    except Exception as exc:
        st.error(f"Unexpected error reaching API: {exc}")
        st.stop()


# ── Startup check ─────────────────────────────────────────────────────────
_ensure_api_reachable()


# ── Session init ──────────────────────────────────────────────────────────
if "token" not in st.session_state:
    st.session_state["token"] = None
    st.session_state["role"] = None


# ── Login form ───────────────────────────────────────────────────────────
def show_login() -> None:
    st.title("📚 Support Knowledge Hub")
    st.subheader("Login")
    with st.form("login_form"):
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Login")
        if submitted:
            resp = httpx.post(
                f"{API_BASE_URL}/api/v1/auth/login",
                json={"email": email, "password": password},
                timeout=15.0,
                follow_redirects=True,
            )
            if resp.status_code == 200:
                data = resp.json()
                st.session_state["token"] = data["access_token"]
                st.session_state["role"] = data["role"]
                st.rerun()
            else:
                st.error("Invalid credentials")


def show_logout_button() -> None:
    if st.sidebar.button("Logout"):
        st.session_state["token"] = None
        st.session_state["role"] = None
        st.rerun()


# ── Employee View ────────────────────────────────────────────────────────
def view_employee() -> None:
    tab_search, tab_pinned = st.tabs(["🔍 Search", "📌 Pinned Articles"])

    with tab_search:
        st.subheader("Semantic Search")
        # Load categories for filter
        cats_resp = _get("/api/v1/categories")
        categories = cats_resp.json() if cats_resp.status_code == 200 else []
        cat_options = {"All": None}
        for c in categories:
            cat_options[c["name"]] = c["id"]

        with st.form("search_form"):
            query = st.text_input("Search query")
            cat_choice = st.selectbox("Category filter", list(cat_options.keys()))
            submitted = st.form_submit_button("Search")

        if submitted and query:
            payload = {"query": query, "top_k": 10}
            if cat_options[cat_choice]:
                payload["category_id"] = cat_options[cat_choice]
            resp = _post("/api/v1/search", payload)
            if resp.status_code == 200:
                results = resp.json()
                if not results:
                    st.info("No results found.")
                for r in results:
                    with st.expander(f"{r['rank']}. {r['title']}"):
                        st.write(r["excerpt"])
            else:
                st.error(f"Search error: {resp.status_code}")

    with tab_pinned:
        st.subheader("Pinned Articles")
        cats_resp2 = _get("/api/v1/categories")
        cats2 = cats_resp2.json() if cats_resp2.status_code == 200 else []
        for cat in cats2:
            pins_resp = _get(f"/api/v1/pins/{cat['id']}")
            if pins_resp.status_code == 200:
                pins = pins_resp.json()
                if pins:
                    st.write(f"**{cat['name']}**")
                    for pin in pins:
                        st.write(f"  - [{pin['article_id']}] (order {pin['display_order']})")


# ── Contributor View ─────────────────────────────────────────────────────
def view_contributor() -> None:
    tab_editor, tab_articles, tab_search = st.tabs(["✏️ Editor", "📝 My Articles", "🔍 Search"])

    with tab_editor:
        st.subheader("Create Article")
        cats_resp = _get("/api/v1/categories")
        categories = cats_resp.json() if cats_resp.status_code == 200 else []
        cat_map = {c["name"]: c["id"] for c in categories}

        with st.form("article_form"):
            title = st.text_input("Title")
            body = st.text_area("Body (Markdown)", height=300)
            cat_sel = st.selectbox("Category", list(cat_map.keys()) if cat_map else [""])
            tags_str = st.text_input("Tags (comma-separated)")
            submitted = st.form_submit_button("Save Draft")

        if submitted and title and body and cat_sel:
            tags = [t.strip() for t in tags_str.split(",") if t.strip()] if tags_str else []
            payload = {
                "title": title,
                "body": body,
                "category_id": cat_map[cat_sel],
                "tags": tags,
            }
            resp = _post("/api/v1/articles", payload)
            if resp.status_code == 201:
                art = resp.json()
                st.success(f"Draft created: {art['id']}")
                # Check similar articles
                sim_resp = _post(f"/api/v1/articles/{art['id']}/similar", {"body": body})
                if sim_resp.status_code == 200:
                    sims = sim_resp.json()
                    if sims:
                        st.warning("Similar articles found:")
                        for s in sims:
                            st.write(f"  - {s['title']} (score: {s['score']:.2f})")
                st.rerun()
            else:
                st.error(f"Error: {resp.status_code} - {resp.text}")

    with tab_articles:
        st.subheader("My Articles")
        resp = _get("/api/v1/articles")
        if resp.status_code == 200:
            articles = resp.json()
            if articles:
                st.dataframe(articles)
            else:
                st.info("No articles found.")

    with tab_search:
        view_employee()


# ── Admin View ───────────────────────────────────────────────────────────
def view_admin() -> None:
    tab_articles, tab_categories, tab_pins, tab_analytics = st.tabs(
        ["📝 All Articles", "🗂️ Categories", "📌 Pins", "📊 Analytics"]
    )

    with tab_articles:
        st.subheader("All Articles")
        resp = _get("/api/v1/articles")
        if resp.status_code == 200:
            st.dataframe(resp.json())

    with tab_categories:
        st.subheader("Category Management")
        cats_resp = _get("/api/v1/categories")
        categories = cats_resp.json() if cats_resp.status_code == 200 else []
        if categories:
            st.dataframe(categories)

        with st.form("new_cat_form"):
            name = st.text_input("New category name")
            submitted = st.form_submit_button("Create Category")
        if submitted and name:
            resp = _post("/api/v1/categories", {"name": name})
            if resp.status_code == 201:
                st.success(f"Category created: {resp.json()['name']}")
                st.rerun()
            else:
                st.error(f"Error: {resp.text}")

    with tab_pins:
        st.subheader("Pin Management")
        cats_resp = _get("/api/v1/categories")
        categories = cats_resp.json() if cats_resp.status_code == 200 else []
        cat_map = {c["name"]: c["id"] for c in categories}

        selected_cat = st.selectbox("Category", list(cat_map.keys()) if cat_map else [""])
        if selected_cat and cat_map.get(selected_cat):
            pins_resp = _get(f"/api/v1/pins/{cat_map[selected_cat]}")
            if pins_resp.status_code == 200:
                pins = pins_resp.json()
                if pins:
                    st.dataframe(pins)
                    pin_to_delete = st.selectbox(
                        "Select pin to remove",
                        [p["id"] for p in pins],
                    )
                    if st.button("Remove pin"):
                        del_resp = _delete(f"/api/v1/pins/{pin_to_delete}")
                        if del_resp.status_code == 204:
                            st.success("Pin removed")
                            st.rerun()
                else:
                    st.info("No pins in this category.")

    with tab_analytics:
        st.subheader("Gap Analytics")
        resp = _get("/api/v1/analytics/gaps")
        if resp.status_code == 200:
            data = resp.json()
            if data:
                st.dataframe(data)
            else:
                st.info("No gap data available yet.")
        else:
            st.error(f"Error loading analytics: {resp.status_code}")


# ── Leadership View ─────────────────────────────────────────────────────
def view_leadership() -> None:
    st.subheader("📊 Analytics Dashboard")
    resp = _get("/api/v1/analytics/gaps")
    if resp.status_code == 200:
        data = resp.json()
        if data:
            st.dataframe(data)
        else:
            st.info("No gap data available yet.")
    else:
        st.error(f"Error loading analytics: {resp.status_code}")


# ── Main routing ──────────────────────────────────────────────────────────
if not st.session_state["token"]:
    show_login()
else:
    show_logout_button()
    role = st.session_state["role"]
    st.sidebar.write(f"Logged in as: **{role}**")

    if role == "employee":
        st.title("📚 Support Knowledge Hub")
        view_employee()
    elif role == "contributor":
        st.title("📚 Support Knowledge Hub — Contributor")
        view_contributor()
    elif role == "knowledge_admin":
        st.title("📚 Support Knowledge Hub — Admin")
        view_admin()
    elif role == "leadership":
        st.title("📚 Support Knowledge Hub — Leadership")
        view_leadership()
    else:
        st.warning(f"Unknown role: {role}")
