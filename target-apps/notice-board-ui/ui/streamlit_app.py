"""Team Notice Board — Streamlit UI.

Calls the FastAPI backend over HTTP only.
NEVER import from app/.

Two audiences:
  - Readers: Browse active notices, filter by category, search
  - Organizers: Manage notices & categories using shared secret
"""
from __future__ import annotations

import os

import httpx
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

# ── Config ────────────────────────────────────────────────────────────────────
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")
ORGANIZER_SECRET = os.getenv("ORGANIZER_SECRET", "")

st.set_page_config(
    page_title="Team Notice Board",
    page_icon="📋",
    layout="wide",
)

# ── HTTP helpers (DO NOT MODIFY) ──────────────────────────────────────────────
def _get(path: str, params: dict | None = None, headers: dict | None = None) -> httpx.Response:
    return httpx.get(
        f"{API_BASE_URL}{path}",
        params=params,
        headers=headers or {},
        timeout=30.0,
        follow_redirects=True,
    )


def _post(path: str, json_body: dict, headers: dict | None = None) -> httpx.Response:
    return httpx.post(
        f"{API_BASE_URL}{path}",
        json=json_body,
        headers=headers or {},
        timeout=60.0,
        follow_redirects=True,
    )


def _put(path: str, json_body: dict, headers: dict | None = None) -> httpx.Response:
    return httpx.put(
        f"{API_BASE_URL}{path}",
        json=json_body,
        headers=headers or {},
        timeout=30.0,
        follow_redirects=True,
    )


def _delete(path: str, headers: dict | None = None) -> httpx.Response:
    return httpx.delete(
        f"{API_BASE_URL}{path}",
        headers=headers or {},
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
            f"Could not reach the API at {API_BASE_URL}.\n\n"
            "Start the API first:\n"
            "```\n"
            "cd target-apps/notice-board-ui\n"
            ".venv\\Scripts\\Activate.ps1  # or: source .venv/bin/activate\n"
            "uvicorn app.main:app --reload --port 8000\n"
            "```\n\n"
            "If the API crashed, check the terminal for errors "
            "(common: DATABASE_URL not set in .env)."
        )
        st.stop()
    except Exception as exc:
        st.error(f"Unexpected error reaching API: {exc}")
        st.stop()


# ── Helpers ───────────────────────────────────────────────────────────────────
def _organizer_headers(secret: str) -> dict[str, str]:
    return {"X-Organizer-Secret": secret}


def _fetch_categories() -> list[dict]:
    resp = _get("/api/v1/categories")
    if resp.status_code == 200:
        return resp.json().get("items", [])
    return []


def _category_map(categories: list[dict]) -> dict[str, int]:
    """Return {name: id} mapping for selectboxes."""
    return {c["name"]: c["id"] for c in categories}


# ── Startup check ─────────────────────────────────────────────────────────────
_ensure_api_reachable()

st.title("📋 Team Notice Board")

# ── Sidebar: Organizer login ──────────────────────────────────────────────────
with st.sidebar:
    st.header("🔑 Organizer Access")
    secret_input = st.text_input(
        "Organizer Secret",
        type="password",
        value=ORGANIZER_SECRET,
        help="Enter the organizer secret to unlock management features.",
    )
    if secret_input:
        # Quick validation against API
        if "organizer_validated" not in st.session_state or st.session_state.get("validated_secret") != secret_input:
            # Test by trying to list categories (public) — we validate secret on write ops
            st.session_state["organizer_secret"] = secret_input
            st.session_state["organizer_validated"] = True
            st.session_state["validated_secret"] = secret_input
        st.success("✅ Organizer mode active")
    else:
        st.session_state["organizer_secret"] = ""
        st.session_state["organizer_validated"] = False
        st.info("Enter secret above to manage notices.")

    st.divider()
    st.caption("Browse notices without a secret. Write operations require the organizer secret.")

is_organizer = bool(st.session_state.get("organizer_secret", ""))
org_secret = st.session_state.get("organizer_secret", "")

# ── Tabs ──────────────────────────────────────────────────────────────────────
if is_organizer:
    tab_browse, tab_create, tab_edit, tab_categories = st.tabs(
        ["📖 Browse", "➕ Post Notice", "✏️ Manage Notices", "🗂️ Categories"]
    )
else:
    tab_browse, = st.tabs(["📖 Browse"])
    tab_create = None
    tab_edit = None
    tab_categories = None

# ─────────────────────────────────────────────────────────────────────────────
# TAB 1: BROWSE
# ─────────────────────────────────────────────────────────────────────────────
with tab_browse:
    st.subheader("Browse Active Notices")

    categories = _fetch_categories()
    cat_map = _category_map(categories)

    col1, col2 = st.columns([2, 3])
    with col1:
        cat_options = ["All Categories"] + list(cat_map.keys())
        selected_cat_name = st.selectbox("Filter by Category", cat_options, key="browse_cat")
    with col2:
        search_term = st.text_input("🔍 Search (title or body)", key="browse_search")

    params: dict = {}
    if selected_cat_name != "All Categories":
        params["category_id"] = cat_map[selected_cat_name]
    if search_term:
        params["search"] = search_term

    page = st.number_input("Page", min_value=1, value=1, step=1, key="browse_page")
    params["page"] = page
    params["limit"] = 10

    resp = _get("/api/v1/notices", params=params)
    if resp.status_code == 200:
        payload = resp.json()
        total = payload["total"]
        pages = payload["pages"]
        items = payload["items"]

        st.caption(f"Showing {len(items)} of {total} active notices | Page {page} of {pages}")

        if not items:
            st.info("No active notices found. Try changing filters or check back later.")
        else:
            for notice in items:
                cat_label = ""
                if notice.get("category_id"):
                    cat_name_lookup = next(
                        (c["name"] for c in categories if c["id"] == notice["category_id"]),
                        f"Cat #{notice['category_id']}",
                    )
                    cat_label = f" · 🗂️ {cat_name_lookup}"
                schedule = ""
                if notice.get("start_date") or notice.get("end_date"):
                    s = notice.get("start_date", "—")
                    e = notice.get("end_date", "—")
                    schedule = f" · 📅 {s} → {e}"

                with st.expander(f"**{notice['title']}**{cat_label}{schedule}"):
                    st.write(notice["body"])
                    st.caption(
                        f"Posted by **{notice['author_display_name']}** "
                        f"on {notice['created_at'][:10]}"
                    )
    else:
        st.error(f"Failed to load notices: {resp.status_code} — {resp.text}")

# ─────────────────────────────────────────────────────────────────────────────
# TAB 2: POST NOTICE (organizer only)
# ─────────────────────────────────────────────────────────────────────────────
if tab_create is not None:
    with tab_create:
        st.subheader("Post a New Notice")

        categories_create = _fetch_categories()
        cat_map_create = _category_map(categories_create)

        with st.form("create_notice_form"):
            title = st.text_input("Title *", max_chars=200)
            body = st.text_area("Body *", height=200)
            author = st.text_input("Your Display Name *", max_chars=100)

            cat_options_create = ["(No Category)"] + list(cat_map_create.keys())
            selected_cat_create = st.selectbox("Category", cat_options_create)

            col_s, col_e = st.columns(2)
            with col_s:
                start_date = st.date_input("Publish From (optional)", value=None)
            with col_e:
                end_date = st.date_input("Publish Until (optional)", value=None)

            submitted = st.form_submit_button("📢 Post Notice")

        if submitted:
            if not title.strip() or not body.strip() or not author.strip():
                st.error("Title, body, and display name are required.")
            else:
                payload: dict = {
                    "title": title.strip(),
                    "body": body.strip(),
                    "author_display_name": author.strip(),
                }
                if selected_cat_create != "(No Category)":
                    payload["category_id"] = cat_map_create[selected_cat_create]
                if start_date:
                    payload["start_date"] = str(start_date)
                if end_date:
                    payload["end_date"] = str(end_date)

                resp = _post(
                    "/api/v1/notices",
                    payload,
                    headers=_organizer_headers(org_secret),
                )
                if resp.status_code == 201:
                    st.success(f"✅ Notice '{title}' posted successfully!")
                    st.json(resp.json())
                    st.rerun()
                elif resp.status_code == 401:
                    st.error("❌ Invalid organizer secret. Check your secret in the sidebar.")
                else:
                    st.error(f"Error {resp.status_code}: {resp.text}")

# ─────────────────────────────────────────────────────────────────────────────
# TAB 3: MANAGE NOTICES (organizer only)
# ─────────────────────────────────────────────────────────────────────────────
if tab_edit is not None:
    with tab_edit:
        st.subheader("Manage Existing Notices")

        categories_edit = _fetch_categories()
        cat_map_edit = _category_map(categories_edit)

        # Fetch all notices (active) for editing
        resp_all = _get("/api/v1/notices", params={"limit": 100, "page": 1})
        all_notices = []
        if resp_all.status_code == 200:
            all_notices = resp_all.json().get("items", [])

        if not all_notices:
            st.info("No active notices to manage.")
        else:
            notice_titles = [f"[{n['id']}] {n['title']}" for n in all_notices]
            selected_label = st.selectbox("Select Notice to Edit/Archive", notice_titles)
            selected_id = int(selected_label.split("]")[0].strip("["))
            selected_notice = next(n for n in all_notices if n["id"] == selected_id)

            st.divider()
            action = st.radio("Action", ["✏️ Edit Notice", "🗄️ Archive Notice"], horizontal=True)

            if action == "✏️ Edit Notice":
                with st.form("edit_notice_form"):
                    new_title = st.text_input("Title", value=selected_notice["title"], max_chars=200)
                    new_body = st.text_area("Body", value=selected_notice["body"], height=150)
                    new_author = st.text_input(
                        "Author Display Name",
                        value=selected_notice["author_display_name"],
                        max_chars=100,
                    )
                    cat_options_edit = ["(No Category)"] + list(cat_map_edit.keys())
                    current_cat_name = next(
                        (c["name"] for c in categories_edit if c["id"] == selected_notice.get("category_id")),
                        "(No Category)",
                    )
                    default_cat_idx = cat_options_edit.index(current_cat_name) if current_cat_name in cat_options_edit else 0
                    new_cat = st.selectbox("Category", cat_options_edit, index=default_cat_idx)

                    save_btn = st.form_submit_button("💾 Save Changes")

                if save_btn:
                    update_payload: dict = {
                        "title": new_title.strip(),
                        "body": new_body.strip(),
                        "author_display_name": new_author.strip(),
                    }
                    if new_cat != "(No Category)":
                        update_payload["category_id"] = cat_map_edit[new_cat]
                    else:
                        update_payload["category_id"] = None

                    resp_update = _put(
                        f"/api/v1/notices/{selected_id}",
                        update_payload,
                        headers=_organizer_headers(org_secret),
                    )
                    if resp_update.status_code == 200:
                        st.success(f"✅ Notice #{selected_id} updated!")
                        st.rerun()
                    elif resp_update.status_code == 401:
                        st.error("❌ Invalid organizer secret.")
                    elif resp_update.status_code == 404:
                        st.error("Notice not found.")
                    else:
                        st.error(f"Error {resp_update.status_code}: {resp_update.text}")

            elif action == "🗄️ Archive Notice":
                st.warning(
                    f"Are you sure you want to archive **{selected_notice['title']}**? "
                    "It will be hidden from the browse view but preserved in the database."
                )
                if st.button("🗄️ Confirm Archive", type="primary"):
                    resp_arch = _delete(
                        f"/api/v1/notices/{selected_id}/archive",
                        headers=_organizer_headers(org_secret),
                    )
                    if resp_arch.status_code == 200:
                        st.success(f"✅ Notice #{selected_id} archived.")
                        st.rerun()
                    elif resp_arch.status_code == 401:
                        st.error("❌ Invalid organizer secret.")
                    elif resp_arch.status_code == 404:
                        st.error("Notice not found.")
                    else:
                        st.error(f"Error {resp_arch.status_code}: {resp_arch.text}")

# ─────────────────────────────────────────────────────────────────────────────
# TAB 4: CATEGORIES (organizer only)
# ─────────────────────────────────────────────────────────────────────────────
if tab_categories is not None:
    with tab_categories:
        st.subheader("Manage Categories")

        col_list, col_create = st.columns([1, 1])

        with col_list:
            st.markdown("#### Existing Categories")
            resp_cats = _get("/api/v1/categories")
            if resp_cats.status_code == 200:
                cats_data = resp_cats.json()
                if cats_data["total"] == 0:
                    st.info("No categories yet. Create one →")
                else:
                    for cat in cats_data["items"]:
                        desc = cat.get("description") or "(no description)"
                        st.markdown(f"**{cat['name']}** — {desc}")
            else:
                st.error(f"Failed to load categories: {resp_cats.status_code}")

        with col_create:
            st.markdown("#### Add New Category")
            with st.form("create_category_form"):
                cat_name = st.text_input("Category Name *", max_chars=100)
                cat_desc = st.text_area("Description (optional)", height=80)
                cat_submit = st.form_submit_button("➕ Add Category")

            if cat_submit:
                if not cat_name.strip():
                    st.error("Category name is required.")
                else:
                    resp_cat = _post(
                        "/api/v1/categories",
                        {"name": cat_name.strip(), "description": cat_desc.strip() or None},
                        headers=_organizer_headers(org_secret),
                    )
                    if resp_cat.status_code == 201:
                        st.success(f"✅ Category '{cat_name}' created!")
                        st.rerun()
                    elif resp_cat.status_code == 401:
                        st.error("❌ Invalid organizer secret.")
                    elif resp_cat.status_code == 409:
                        st.error(f"Category '{cat_name}' already exists.")
                    else:
                        st.error(f"Error {resp_cat.status_code}: {resp_cat.text}")
