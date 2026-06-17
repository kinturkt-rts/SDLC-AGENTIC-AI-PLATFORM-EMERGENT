"""Healthcare Clinic Assistant — Streamlit UI.

This UI consumes the FastAPI backend over HTTP. Never imports from app/.
Requires the API to be running on http://localhost:8000.
"""
import httpx
import streamlit as st

API_BASE = "http://localhost:8000"

st.set_page_config(page_title="Healthcare Clinic Assistant", page_icon="🏥", layout="wide")

# ── Sidebar navigation ──────────────────────────────────────────────────────
page = st.sidebar.selectbox("Navigate", ["💬 Chat", "📋 FAQ Browser", "🔧 Staff Admin"])
st.sidebar.caption("**Chat** — no login. Click *Start New Conversation* first.")
st.sidebar.caption("**Staff Admin** — demo login: `admin` / `changeme`")

# ── Helper functions ─────────────────────────────────────────────────────────


def _api_request(method: str, path: str, **kwargs):
    """Call the FastAPI backend; follow redirects (GET /faqs → /faqs/)."""
    try:
        with httpx.Client(base_url=API_BASE, follow_redirects=True, timeout=15.0) as client:
            return client.request(method, path, **kwargs)
    except httpx.ConnectError:
        st.error("Cannot connect to API. Is the backend running on http://localhost:8000?")
        return None


def api_get(path: str, headers: dict | None = None):
    return _api_request("GET", path, headers=headers or {})


def api_post(path: str, json_data: dict, headers: dict | None = None):
    return _api_request("POST", path, json=json_data, headers=headers or {})


def api_put(path: str, json_data: dict, headers: dict | None = None):
    return _api_request("PUT", path, json=json_data, headers=headers or {})


# ── Chat Page ────────────────────────────────────────────────────────────────
if page == "💬 Chat":
    st.title("🏥 Healthcare Clinic Assistant")
    st.caption(
        "⚠️ **POC / Demo** — This is not a production system and does not provide medical advice."
    )

    # Session management
    if "session_id" not in st.session_state:
        st.session_state.session_id = None
        st.session_state.messages = []

    if st.session_state.session_id is None:
        if st.button("Start New Conversation"):
            resp = api_post("/chat/sessions", {"session_label": "Streamlit Session"})
            if resp and resp.status_code == 201:
                st.session_state.session_id = resp.json()["session_id"]
                st.session_state.messages = []
                st.rerun()
    else:
        # Display chat history
        for msg in st.session_state.messages:
            with st.chat_message(msg["role"]):
                st.write(msg["content"])
                if msg["role"] == "assistant" and msg.get("disclaimer"):
                    st.caption(f"_{msg['disclaimer']}_")

        # Chat input
        user_input = st.chat_input("Ask a question about the clinic...")
        if user_input:
            st.session_state.messages.append({"role": "user", "content": user_input})
            with st.chat_message("user"):
                st.write(user_input)

            with st.chat_message("assistant"):
                with st.spinner("Thinking..."):
                    resp = api_post(
                        "/chat/message",
                        {"session_id": st.session_state.session_id, "message": user_input},
                    )
                if resp and resp.status_code == 200:
                    data = resp.json()
                    st.write(data["reply"])
                    st.caption(f"_{data['disclaimer']}_")
                    st.session_state.messages.append(
                        {"role": "assistant", "content": data["reply"], "disclaimer": data["disclaimer"]}
                    )
                elif resp:
                    st.error(f"Error: {resp.status_code} — {resp.text}")

        if st.button("End Conversation"):
            st.session_state.session_id = None
            st.session_state.messages = []
            st.rerun()

# ── FAQ Browser Page ─────────────────────────────────────────────────────────
elif page == "📋 FAQ Browser":
    st.title("📋 FAQ Browser")
    resp = api_get("/faqs")
    if resp is None:
        pass
    elif resp.status_code != 200:
        st.error(f"FAQ API error ({resp.status_code}): {resp.text[:500]}")
    else:
        faqs = resp.json()
        if not faqs:
            st.info("No FAQ entries found. Apply db/sql/011_seed.sql to RDS.")
        else:
            st.caption(f"{len(faqs)} entries from GET /faqs")
            categories = sorted(set(f["category"] for f in faqs))
            for cat in categories:
                st.subheader(cat.replace("_", " ").title())
                for faq in [f for f in faqs if f["category"] == cat]:
                    with st.expander(faq["question"]):
                        st.write(faq["answer"])

# ── Staff Admin Page ─────────────────────────────────────────────────────────
elif page == "🔧 Staff Admin":
    st.title("🔧 Staff Administration")

    # Login
    if "auth_token" not in st.session_state:
        st.session_state.auth_token = None

    if st.session_state.auth_token is None:
        st.subheader("Login Required")
        with st.form("login_form"):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Login")
            if submitted:
                resp = api_post("/auth/login", {"username": username, "password": password})
                if resp and resp.status_code == 200:
                    st.session_state.auth_token = resp.json()["access_token"]
                    st.rerun()
                else:
                    st.error("Invalid credentials.")
    else:
        auth_headers = {"Authorization": f"Bearer {st.session_state.auth_token}"}

        # Stats
        stats_resp = api_get("/admin/stats", headers=auth_headers)
        if stats_resp and stats_resp.status_code == 200:
            stats = stats_resp.json()
            cols = st.columns(4)
            cols[0].metric("Total FAQs", stats["total_faqs"])
            cols[1].metric("Total Sessions", stats["total_sessions"])
            cols[2].metric("Total Messages", stats["total_messages"])
            cols[3].metric("Fallback Rate", f"{stats['fallback_rate']:.1%}")

        st.divider()

        # FAQ Management
        st.subheader("Manage FAQ Entries")
        faqs_resp = api_get("/faqs", headers=auth_headers)
        if faqs_resp and faqs_resp.status_code == 200:
            faqs = faqs_resp.json()
            for faq in faqs:
                with st.expander(f"[{faq['category']}] {faq['question']} (ID: {faq['id']})"):
                    new_q = st.text_input("Question", value=faq["question"], key=f"q_{faq['id']}")
                    new_a = st.text_area("Answer", value=faq["answer"], key=f"a_{faq['id']}")
                    new_cat = st.text_input("Category", value=faq["category"], key=f"c_{faq['id']}")
                    new_active = st.checkbox("Active", value=faq["is_active"], key=f"act_{faq['id']}")
                    if st.button("Save", key=f"save_{faq['id']}"):
                        update_resp = api_put(
                            f"/faqs/{faq['id']}",
                            {"question": new_q, "answer": new_a, "category": new_cat, "is_active": new_active},
                            headers=auth_headers,
                        )
                        if update_resp and update_resp.status_code == 200:
                            st.success("Updated!")
                            st.rerun()
                        else:
                            st.error("Update failed.")

        st.divider()
        st.subheader("Add New FAQ")
        with st.form("add_faq"):
            new_category = st.text_input("Category")
            new_question = st.text_input("Question")
            new_answer = st.text_area("Answer")
            add_submitted = st.form_submit_button("Add FAQ")
            if add_submitted and new_category and new_question and new_answer:
                create_resp = api_post(
                    "/faqs",
                    {"category": new_category, "question": new_question, "answer": new_answer},
                    headers=auth_headers,
                )
                if create_resp and create_resp.status_code == 201:
                    st.success("FAQ added!")
                    st.rerun()
                else:
                    st.error("Failed to add FAQ.")

        if st.button("Logout"):
            st.session_state.auth_token = None
            st.rerun()
