"""Support Knowledge Hub — Streamlit UI.

Role-gated multi-page app. Calls FastAPI over HTTP (never imports app/ directly).
"""
from __future__ import annotations

import os

import httpx
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

# ── Config ───────────────────────────────────────────────────────────────────
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")

st.set_page_config(page_title="Support Knowledge Hub", page_icon="📚", layout="wide")


# ── HTTP helpers (DO NOT MODIFY) ────────────────────────────────────────
def _headers() -> dict[str, str]:
    """Return auth headers with JWT if logged in."""
    token = st.session_state.get("access_token")
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
                "- Is the RDS/Postgres instance reachable from your machine?\n"
                "- Run `curl http://localhost:8000/health` for details."
            )
            st.stop()
    except httpx.ConnectError:
        st.error(
            "Could not reach the API at " + API_BASE_URL + ".\n\n"
            "Start the API first:\n"
            "```\n"
            "cd target-apps/support-knowledge-hub\n"
            ".venv\\Scripts\\Activate.ps1  # or source .venv/bin/activate\n"
            "uvicorn app.main:app --reload --port 8000\n"
            "```\n\n"
            "If the API crashed, check the terminal for errors."
        )
        st.stop()
    except Exception as exc:
        st.error(f"Unexpected error reaching API: {exc}")
        st.stop()


# ── Session state init ─────────────────────────────────────────────────
if "access_token" not in st.session_state:
    st.session_state["access_token"] = None
    st.session_state["user_role"] = None


# ── Login page ────────────────────────────────────────────────────────
def show_login():
    st.title("📚 Support Knowledge Hub")
    st.subheader("Login")
    with st.form("login_form"):
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Login")
        if submitted:
            resp = httpx.post(
                f"{API_BASE_URL}/auth/token",
                json={"email": email, "password": password},
                timeout=10.0,
                follow_redirects=True,
            )
            if resp.status_code == 200:
                data = resp.json()
                st.session_state["access_token"] = data["access_token"]
                st.session_state["user_role"] = data["role"]
                st.rerun()
            else:
                st.error("Invalid credentials")


# ── Employee view ─────────────────────────────────────────────────────
def show_employee():
    st.title("🔍 Knowledge Search")
    tab_search, tab_browse = st.tabs(["Search", "Browse Articles"])

    with tab_search:
        query = st.text_input("Search for help articles", placeholder="e.g., how to reset VPN")
        if st.button("Search", key="search_btn") and query:
            resp = _post("/search", {"query": query, "top_n": 10})
            if resp.status_code == 201:
                data = resp.json()
                if data["results"]:
                    for r in data["results"]:
                        with st.expander(f"⭐ {r['article_id']} (score: {r['score']:.2f})"):
                            st.write(r["excerpt"])
                            col1, col2 = st.columns(2)
                            with col1:
                                if st.button("👍 Helpful", key=f"h_{r['article_id']}"):
                                    _post("/feedback", {
                                        "search_event_id": data["search_event_id"],
                                        "article_id": r["article_id"],
                                        "rating": "helpful",
                                    })
                                    st.success("Thanks for your feedback!")
                            with col2:
                                if st.button("👎 Not helpful", key=f"nh_{r['article_id']}"):
                                    _post("/feedback", {
                                        "search_event_id": data["search_event_id"],
                                        "article_id": r["article_id"],
                                        "rating": "not_helpful",
                                    })
                                    st.info("Feedback recorded.")
                else:
                    st.info("No results found.")
            else:
                st.error(f"Search error: {resp.status_code}")

    with tab_browse:
        resp = _get("/articles")
        if resp.status_code == 200:
            articles = resp.json()
            for art in articles:
                with st.expander(f"{art['title']} [{art['status']}]"):
                    st.write(art["body"][:500])
                    st.caption(f"Category: {art['category_id']} | Tags: {art.get('tags', [])}")


# ── Contributor view ─────────────────────────────────────────────────
def show_contributor():
    st.title("✏️ Contributor Panel")
    tab_create, tab_drafts, tab_search = st.tabs(["Create Article", "My Articles", "Search"])

    with tab_create:
        with st.form("create_article"):
            title = st.text_input("Title")
            body = st.text_area("Body (Markdown)", height=300)
            category_id = st.text_input("Category ID")
            tags = st.text_input("Tags (comma-separated)")
            submitted = st.form_submit_button("Create Draft")
            if submitted:
                tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else []
                resp = _post("/articles", {
                    "title": title,
                    "body": body,
                    "category_id": category_id,
                    "tags": tag_list,
                })
                if resp.status_code == 201:
                    st.success("Article created as draft!")
                    st.json(resp.json())
                else:
                    st.error(f"Error {resp.status_code}: {resp.text}")

    with tab_drafts:
        resp = _get("/articles", params={"status": "draft"})
        if resp.status_code == 200:
            articles = resp.json()
            for art in articles:
                with st.expander(f"{art['title']} [{art['status']}]"):
                    st.write(art["body"][:500])
                    if st.button(f"Publish {art['id'][:8]}...", key=f"pub_{art['id']}"):
                        resp2 = _patch(f"/articles/{art['id']}", {"status": "published"})
                        if resp2.status_code == 200:
                            data = resp2.json()
                            st.success("Published!")
                            if data.get("similar_articles"):
                                st.warning("⚠️ Similar articles found:")
                                for s in data["similar_articles"]:
                                    st.write(f"- {s['title']} (score: {s['score']:.2f})")
                        else:
                            st.error(f"Error: {resp2.text}")

    with tab_search:
        show_employee()


# ── Admin view ────────────────────────────────────────────────────────
def show_admin():
    st.title("🛠️ Admin Console")
    tab_articles, tab_cats, tab_analytics = st.tabs(["All Articles", "Categories", "Analytics"])

    with tab_articles:
        resp = _get("/articles")
        if resp.status_code == 200:
            articles = resp.json()
            st.write(f"Total articles: {len(articles)}")
            for art in articles:
                with st.expander(f"{art['title']} [{art['status']}]"):
                    st.write(art["body"][:300])
                    col1, col2 = st.columns(2)
                    with col1:
                        if art["status"] != "archived":
                            if st.button(f"Archive {art['id'][:8]}", key=f"arch_{art['id']}"):
                                _patch(f"/articles/{art['id']}", {"status": "archived"})
                                st.rerun()
                    with col2:
                        if art["status"] == "draft":
                            if st.button(f"Publish {art['id'][:8]}", key=f"apub_{art['id']}"):
                                _patch(f"/articles/{art['id']}", {"status": "published"})
                                st.rerun()

    with tab_cats:
        st.subheader("Create Category")
        with st.form("create_cat"):
            name = st.text_input("Name")
            slug = st.text_input("Slug")
            if st.form_submit_button("Create"):
                resp = _post("/categories", {"name": name, "slug": slug})
                if resp.status_code == 201:
                    st.success("Category created!")
                else:
                    st.error(f"Error: {resp.text}")

    with tab_analytics:
        show_analytics()


# ── Analytics view ─────────────────────────────────────────────────────
def show_analytics():
    st.subheader("📊 Popular Gaps")
    resp = _get("/admin/analytics/gaps", params={"limit": 20})
    if resp.status_code == 200:
        data = resp.json()
        if data["gaps"]:
            for gap in data["gaps"]:
                st.write(f"- **{gap['query_text']}** — {gap['count']} searches, {gap['helpful_rate']:.0%} helpful")
        else:
            st.info("No gap data yet.")
    else:
        st.error(f"Could not load analytics: {resp.status_code}")


# ── Leadership view ───────────────────────────────────────────────────
def show_leadership():
    st.title("📊 Leadership Analytics")
    show_analytics()


# ── Main routing ──────────────────────────────────────────────────────
_ensure_api_reachable()

if not st.session_state["access_token"]:
    show_login()
else:
    role = st.session_state["user_role"]
    # Sidebar with logout
    with st.sidebar:
        st.write(f"Logged in as: **{role}**")
        if st.button("Logout"):
            st.session_state["access_token"] = None
            st.session_state["user_role"] = None
            st.rerun()

    if role == "employee":
        show_employee()
    elif role == "contributor":
        show_contributor()
    elif role == "knowledge_admin":
        show_admin()
    elif role == "leadership":
        show_leadership()
    else:
        st.error(f"Unknown role: {role}")
