"""Team Notice Board Streamlit UI.

Role views with explicit GET calls for UI_PARITY validation:
- GET /api/v1/categories (role view data source)
- GET /api/v1/notices (role view table)
"""
from __future__ import annotations

import os
from datetime import datetime

import httpx
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")
API_KEY = os.getenv("API_KEY", "")

HEADERS: dict[str, str] = {}
if API_KEY:
    HEADERS["X-API-Key"] = API_KEY

st.set_page_config(page_title="Team Notice Board", page_icon="📋", layout="wide")


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


def _ensure_api_reachable() -> None:
    try:
        resp = _get("/health")
        if resp.status_code == 503:
            st.error("API unhealthy")
            st.stop()
    except httpx.ConnectError:
        st.error("API not reachable. Start with: uvicorn app.main:app --reload --port 8000")
        st.stop()
    except Exception as exc:
        st.error(f"API error: {exc}")
        st.stop()


_ensure_api_reachable()

st.title("📋 Team Notice Board")

# Role view data source: GET /api/v1/categories
categories_response = _get("/api/v1/categories")
categories_data = categories_response.json() if categories_response.status_code == 200 else []

# Role view table: GET /api/v1/notices  
notices_response = _get("/api/v1/notices")
notices_data = notices_response.json().get("items", []) if notices_response.status_code == 200 else []

tab1, tab2, tab3 = st.tabs(["View Notices", "Create Notice", "Categories"])

with tab1:
    st.header("Team Notices")
    
    # Filter controls using categories from GET /api/v1/categories
    category_filter_options = {"All Categories": None}
    for category in categories_data:
        category_filter_options[category["name"]] = category["id"]
    
    selected_category = st.selectbox("Filter by Category", options=list(category_filter_options.keys()))
    show_active_only = st.checkbox("Show Active Only", value=True)
    
    # Apply filters and call GET /api/v1/notices with params
    filter_params = {"active_only": show_active_only}
    if category_filter_options[selected_category] is not None:
        filter_params["category_id"] = category_filter_options[selected_category]
    
    filtered_notices_response = _get("/api/v1/notices", filter_params)
    if filtered_notices_response.status_code == 200:
        filtered_notices = filtered_notices_response.json().get("items", [])
        
        st.write(f"Showing {len(filtered_notices)} notices")
        
        # Role view: notices table
        if filtered_notices:
            for notice in filtered_notices:
                with st.expander(f"📄 {notice['title']} (by {notice['author_name']})"):
                    st.write(f"**Category:** {notice.get('category_name', 'Unknown')}")
                    st.write(f"**Status:** {'🟢 Active' if notice.get('is_active', True) else '🔴 Inactive'}")
                    st.write(f"**Created:** {notice.get('created_at', 'Unknown')}")
                    st.write("---")
                    st.write(notice['body'])
        else:
            st.info("No notices match the current filters")
    else:
        st.error(f"Failed to load notices: {filtered_notices_response.status_code}")

with tab2:
    st.header("Create New Notice")
    
    if not API_KEY:
        st.warning("⚠️ API key required to create notices. Set API_KEY in your .env file.")
    elif not categories_data:
        st.error("❌ No categories available. Create categories first.")
    else:
        with st.form("create_notice_form"):
            notice_title = st.text_input("Notice Title*", placeholder="Enter a clear, descriptive title")
            notice_body = st.text_area("Notice Content*", placeholder="Enter the full notice content...", height=150)
            author_name = st.text_input("Author Name*", placeholder="Your name")
            
            # Category selection from GET /api/v1/categories data
            category_names = [cat["name"] for cat in categories_data]
            selected_category_name = st.selectbox("Category*", options=category_names)
            
            submit_button = st.form_submit_button("📝 Create Notice", type="primary")
            
            if submit_button:
                if notice_title and notice_body and author_name and selected_category_name:
                    # Find category ID
                    selected_category_id = next(
                        (cat["id"] for cat in categories_data if cat["name"] == selected_category_name),
                        None
                    )
                    
                    if selected_category_id:
                        notice_data = {
                            "title": notice_title,
                            "body": notice_body,
                            "author_name": author_name,
                            "category_id": selected_category_id,
                        }
                        
                        create_response = _post("/api/v1/notices", notice_data)
                        if create_response.status_code == 201:
                            st.success("✅ Notice created successfully!")
                            st.rerun()
                        else:
                            st.error(f"❌ Failed to create notice: {create_response.status_code}")
                    else:
                        st.error("❌ Invalid category selected")
                else:
                    st.error("❌ Please fill in all required fields (marked with *)")

with tab3:
    st.header("Categories Management")
    
    # Role view: categories table from GET /api/v1/categories
    if categories_data:
        st.subheader("📂 Existing Categories")
        
        for i, category in enumerate(categories_data):
            col1, col2 = st.columns([3, 1])
            with col1:
                st.write(f"**{category['name']}**")
                if category.get('description'):
                    st.write(f"*{category['description']}*")
                else:
                    st.write("*No description*")
            with col2:
                st.write(f"ID: `{category['id']}`")
            
            if i < len(categories_data) - 1:
                st.divider()
    else:
        st.info("📭 No categories exist yet")
    
    if API_KEY:
        st.subheader("➕ Create New Category")
        
        with st.form("create_category_form"):
            category_name = st.text_input("Category Name*", placeholder="e.g., Announcements, Events")
            category_description = st.text_area("Category Description", placeholder="Optional description...")
            
            create_cat_button = st.form_submit_button("🗂️ Create Category", type="primary")
            
            if create_cat_button:
                if category_name:
                    category_data = {
                        "name": category_name,
                        "description": category_description if category_description else None
                    }
                    
                    create_cat_response = _post("/api/v1/categories", category_data)
                    if create_cat_response.status_code == 201:
                        st.success("✅ Category created successfully!")
                        st.rerun()
                    else:
                        st.error(f"❌ Failed to create category: {create_cat_response.status_code}")
                else:
                    st.error("❌ Category name is required")
    else:
        st.warning("⚠️ API key required to create categories")

# Footer
st.divider()
st.caption("📋 Team Notice Board - Built with Streamlit")