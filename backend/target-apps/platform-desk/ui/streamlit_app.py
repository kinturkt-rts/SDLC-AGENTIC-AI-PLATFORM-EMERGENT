"""Streamlit UI for Platform Desk (Runbook Vector Desk).

Role-gated views:
  - Viewer: Search, Browse Active Runbooks, Log Incident Touch
  - Editor: + Draft Management, Step Editor, Activate/Retire
  - Admin: + Service Catalog, Analytics Dashboard, Index Refresh
"""
from __future__ import annotations

import os

import httpx
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

# -- Config --
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")
API_KEY = os.getenv("API_KEY", "")

HEADERS: dict[str, str] = {}
if API_KEY:
    HEADERS["X-API-Key"] = API_KEY

st.set_page_config(page_title="Runbook Vector Desk", page_icon="\U0001f4d6", layout="wide")


# -- HTTP helpers (DO NOT MODIFY) --
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


def _put(path: str, json_body: dict) -> httpx.Response:
    return httpx.put(
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
                "- Is the RDS/Postgres instance reachable?\n"
                "- Run `curl http://localhost:8000/health` for details."
            )
            st.stop()
    except httpx.ConnectError:
        st.error(
            "Could not reach the API at " + API_BASE_URL + ".\n\n"
            "Start the API first:\n"
            "```\n"
            "cd target-apps/platform-desk\n"
            ".venv\\Scripts\\Activate.ps1  # or source .venv/bin/activate\n"
            "uvicorn app.main:app --reload --port 8000\n"
            "```"
        )
        st.stop()
    except Exception as exc:
        st.error(f"Unexpected error reaching API: {exc}")
        st.stop()


# -- Main --
_ensure_api_reachable()

st.title("\U0001f4d6 Runbook Vector Desk")

# Role selection (simplified for MVP; in production would come from API key lookup)
if "role" not in st.session_state:
    st.session_state.role = "admin"

role = st.sidebar.selectbox(
    "Current Role",
    ["viewer", "editor", "admin"],
    index=["viewer", "editor", "admin"].index(st.session_state.role),
)
st.session_state.role = role

st.sidebar.info(f"Logged in as: **{role}**")

# Build tabs based on role
tab_names = ["\U0001f50d Search", "\U0001f4da Browse Runbooks", "\U0001f4dd Log Incident Touch"]
if role in ("editor", "admin"):
    tab_names.append("\u270f\ufe0f Draft Management")
if role == "admin":
    tab_names.extend(["\U0001f3e2 Service Catalog", "\U0001f4ca Analytics"])

tabs = st.tabs(tab_names)

# -- Tab: Search --
with tabs[0]:
    st.subheader("Symptom Search")
    query = st.text_area("Paste alert text or describe the symptom", height=100)

    # Fetch services for filter
    svc_resp = _get("/api/v1/services", params={"limit": 100})
    services_list = []
    if svc_resp.status_code == 200:
        services_list = svc_resp.json().get("items", [])

    service_options = [""] + [s["name"] for s in services_list]
    service_filter = st.selectbox("Filter by service (optional)", service_options)

    top_k = st.slider("Max results", 1, 10, 5)

    if st.button("Search", type="primary"):
        if query.strip():
            svc_id = None
            if service_filter:
                matched = [s for s in services_list if s["name"] == service_filter]
                if matched:
                    svc_id = matched[0]["id"]
            search_body = {"query": query, "top_k": top_k}
            if svc_id:
                search_body["service_id"] = svc_id
            resp = _post("/api/v1/search", search_body)
            if resp.status_code == 200:
                results = resp.json().get("results", [])
                if results:
                    for r in results:
                        with st.expander(
                            f"[{r['service_name']}] {r['runbook_title']} \u2014 Step {r['step_number']}: {r['step_title']} (score: {r['score']:.2f})"
                        ):
                            st.write(f"**Excerpt:** {r['excerpt']}")
                            if r.get("summary"):
                                st.info(f"Summary: {r['summary']}")
                else:
                    st.warning("No results found.")
            else:
                st.error(f"Search failed: {resp.status_code} - {resp.text}")
        else:
            st.warning("Please enter a search query.")

# -- Tab: Browse Runbooks --
with tabs[1]:
    st.subheader("Active Runbooks")
    browse_svc = st.selectbox("Filter by service", [""] + [s["name"] for s in services_list], key="browse_svc")
    params: dict = {"lifecycle_status": "active", "limit": 50}
    if browse_svc:
        matched = [s for s in services_list if s["name"] == browse_svc]
        if matched:
            params["service_id"] = matched[0]["id"]

    rb_resp = _get("/api/v1/runbooks", params=params)
    if rb_resp.status_code == 200:
        runbooks = rb_resp.json().get("items", [])
        if runbooks:
            for rb in runbooks:
                with st.expander(f"{rb['title']} (Severity: {rb['default_severity']})"):
                    st.write(f"**Author:** {rb['author']}")
                    st.write(f"**Summary:** {rb.get('short_summary', 'N/A')}")
                    # Load steps
                    steps_resp = _get(f"/api/v1/runbooks/{rb['id']}/steps")
                    if steps_resp.status_code == 200:
                        steps = steps_resp.json()
                        for s in steps:
                            st.markdown(
                                f"**Step {s['step_number']}: {s['title']}** "
                                f"({'~' + str(s['estimated_minutes']) + ' min' if s.get('estimated_minutes') else 'N/A'})"
                            )
                            st.write(s["body_text"])
                            if s.get("warning_callout"):
                                st.warning(f"\u26a0\ufe0f {s['warning_callout']}")
        else:
            st.info("No active runbooks found.")
    else:
        st.error(f"Failed to load runbooks: {rb_resp.status_code}")

# -- Tab: Log Incident Touch --
with tabs[2]:
    st.subheader("Log Incident Touch")
    # Fetch active runbooks for selection
    active_rb_resp = _get("/api/v1/runbooks", params={"lifecycle_status": "active", "limit": 100})
    active_rbs = []
    if active_rb_resp.status_code == 200:
        active_rbs = active_rb_resp.json().get("items", [])

    if active_rbs:
        rb_options = {f"{rb['title']} ({rb['id'][:8]}...)": rb["id"] for rb in active_rbs}
        selected_rb = st.selectbox("Runbook", list(rb_options.keys()), key="touch_rb")
        with st.form("incident_touch_form"):
            ticket_ref = st.text_input("Ticket Reference (required)", placeholder="INC-1234")
            step_num = st.number_input("Step Number (optional)", min_value=0, value=0)
            notes = st.text_area("Notes (optional)")
            submitted = st.form_submit_button("Log Touch")
            if submitted:
                if not ticket_ref.strip():
                    st.error("Ticket reference is required.")
                else:
                    touch_body: dict = {
                        "runbook_id": rb_options[selected_rb],
                        "ticket_reference": ticket_ref.strip(),
                    }
                    if step_num > 0:
                        touch_body["step_number"] = step_num
                    if notes.strip():
                        touch_body["notes"] = notes.strip()
                    resp = _post("/api/v1/incident-touches", touch_body)
                    if resp.status_code == 201:
                        st.success("Incident touch logged!")
                        st.rerun()
                    else:
                        st.error(f"Error: {resp.status_code} - {resp.text}")
    else:
        st.info("No active runbooks available.")

# -- Tab: Draft Management (Editor+) --
if role in ("editor", "admin"):
    with tabs[3]:
        st.subheader("Draft Runbook Management")

        # Create new runbook
        with st.expander("\u2795 Create New Runbook"):
            with st.form("create_runbook_form"):
                rb_title = st.text_input("Title")
                rb_svc = st.selectbox("Service", [s["name"] for s in services_list] if services_list else [""], key="create_rb_svc")
                rb_severity = st.selectbox("Default Severity", ["low", "medium", "high", "critical"])
                rb_summary = st.text_area("Short Summary")
                rb_author = st.text_input("Author")
                create_submitted = st.form_submit_button("Create Draft")
                if create_submitted and rb_title and rb_author:
                    svc_match = [s for s in services_list if s["name"] == rb_svc]
                    if svc_match:
                        body = {
                            "title": rb_title,
                            "service_id": svc_match[0]["id"],
                            "default_severity": rb_severity,
                            "short_summary": rb_summary,
                            "author": rb_author,
                        }
                        resp = _post("/api/v1/runbooks", body)
                        if resp.status_code == 201:
                            st.success("Draft runbook created!")
                            st.rerun()
                        else:
                            st.error(f"Error: {resp.status_code} - {resp.text}")
                    else:
                        st.error("Please select a valid service.")

        # List drafts
        st.markdown("---")
        st.subheader("Draft Runbooks")
        draft_resp = _get("/api/v1/runbooks", params={"lifecycle_status": "draft", "limit": 50})
        if draft_resp.status_code == 200:
            drafts = draft_resp.json().get("items", [])
            for draft in drafts:
                with st.expander(f"\U0001f4dd {draft['title']}"):
                    st.write(f"**Service ID:** {draft['service_id']}")
                    st.write(f"**Author:** {draft['author']}")
                    st.write(f"**Summary:** {draft.get('short_summary', '')}")

                    # Steps management
                    steps_resp = _get(f"/api/v1/runbooks/{draft['id']}/steps")
                    if steps_resp.status_code == 200:
                        steps = steps_resp.json()
                        st.write(f"**Steps:** {len(steps)}")
                        for s in steps:
                            st.markdown(f"  - Step {s['step_number']}: {s['title']}")

                    # Add step
                    with st.form(f"add_step_{draft['id']}"):
                        st.markdown("**Add Step:**")
                        sn = st.number_input("Step Number", min_value=1, value=1, key=f"sn_{draft['id']}")
                        s_title = st.text_input("Step Title", key=f"st_{draft['id']}")
                        s_body = st.text_area("Body Text", key=f"sb_{draft['id']}")
                        s_mins = st.number_input("Est. Minutes", min_value=0, value=0, key=f"sm_{draft['id']}")
                        s_warn = st.text_input("Warning Callout (optional)", key=f"sw_{draft['id']}")
                        add_step_sub = st.form_submit_button("Add Step")
                        if add_step_sub and s_title and s_body:
                            step_body: dict = {
                                "step_number": sn,
                                "title": s_title,
                                "body_text": s_body,
                            }
                            if s_mins > 0:
                                step_body["estimated_minutes"] = s_mins
                            if s_warn.strip():
                                step_body["warning_callout"] = s_warn
                            resp = _post(f"/api/v1/runbooks/{draft['id']}/steps", step_body)
                            if resp.status_code == 201:
                                st.success("Step added!")
                                st.rerun()
                            else:
                                st.error(f"Error: {resp.status_code} - {resp.text}")

                    # Activate
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button(f"\u2705 Activate", key=f"activate_{draft['id']}"):
                            resp = _post(f"/api/v1/runbooks/{draft['id']}/activate", {})
                            if resp.status_code == 200:
                                data = resp.json()
                                st.success(f"Activated! Similar runbooks: {len(data.get('similar_runbooks', []))}")
                                st.rerun()
                            else:
                                st.error(f"Error: {resp.status_code} - {resp.json().get('detail', '')}")

        # Active runbooks - retire
        st.markdown("---")
        st.subheader("Active Runbooks (Retire)")
        active_resp = _get("/api/v1/runbooks", params={"lifecycle_status": "active", "limit": 50})
        if active_resp.status_code == 200:
            actives = active_resp.json().get("items", [])
            for arb in actives:
                col1, col2 = st.columns([4, 1])
                with col1:
                    st.write(f"{arb['title']}")
                with col2:
                    if st.button("\U0001f6ab Retire", key=f"retire_{arb['id']}"):
                        resp = _post(f"/api/v1/runbooks/{arb['id']}/retire", {})
                        if resp.status_code == 200:
                            st.success("Retired!")
                            st.rerun()
                        else:
                            st.error(f"Error: {resp.status_code}")

# -- Tab: Service Catalog (Admin) --
if role == "admin":
    with tabs[4]:
        st.subheader("Service Catalog")

        with st.expander("\u2795 Add Service"):
            with st.form("add_service_form"):
                svc_name = st.text_input("Service Name")
                svc_team = st.text_input("Owning Team")
                svc_tier = st.selectbox("Criticality Tier", [1, 2, 3])
                svc_active = st.checkbox("Active Support", value=True)
                svc_submitted = st.form_submit_button("Create Service")
                if svc_submitted and svc_name:
                    body = {
                        "name": svc_name,
                        "owning_team": svc_team,
                        "criticality_tier": svc_tier,
                        "active_support": svc_active,
                    }
                    resp = _post("/api/v1/services", body)
                    if resp.status_code == 201:
                        st.success("Service created!")
                        st.rerun()
                    elif resp.status_code == 409:
                        st.error("Service name already exists.")
                    else:
                        st.error(f"Error: {resp.status_code} - {resp.text}")

        # List services
        all_svc_resp = _get("/api/v1/services", params={"limit": 100})
        if all_svc_resp.status_code == 200:
            all_svcs = all_svc_resp.json().get("items", [])
            if all_svcs:
                import pandas as pd
                df = pd.DataFrame(all_svcs)
                display_cols = ["name", "owning_team", "criticality_tier", "active_support"]
                st.dataframe(df[display_cols] if all(c in df.columns for c in display_cols) else df)
            else:
                st.info("No services registered.")

    # -- Tab: Analytics (Admin) --
    with tabs[5]:
        st.subheader("Search Analytics & Admin")

        col1, col2 = st.columns(2)
        with col1:
            if st.button("\U0001f504 Refresh Vector Index"):
                resp = _post("/api/v1/admin/index-refresh", {})
                if resp.status_code == 200:
                    data = resp.json()
                    st.success(f"Index refreshed! Steps indexed: {data['steps_indexed']}")
                else:
                    st.error(f"Error: {resp.status_code}")

        with col2:
            days = st.number_input("Reliance report days", min_value=1, max_value=365, value=30)

        # Reliance report
        st.markdown("---")
        st.subheader("Service Reliance Report")
        rel_resp = _get("/api/v1/admin/report/reliance", params={"days": days})
        if rel_resp.status_code == 200:
            rel_data = rel_resp.json()
            if rel_data:
                import pandas as pd
                st.dataframe(pd.DataFrame(rel_data))
            else:
                st.info("No incident touches in the selected period.")

        # Search analytics
        st.markdown("---")
        st.subheader("Search Analytics")
        analytics_resp = _get("/api/v1/admin/analytics", params={"top_n": 25})
        if analytics_resp.status_code == 200:
            analytics = analytics_resp.json()

            st.write("**Response Time Stats:**")
            stats = analytics.get("response_time_stats", {})
            st.metric("Median (ms)", f"{stats.get('median_ms', 0):.0f}")
            st.metric("P95 (ms)", f"{stats.get('p95_ms', 0):.0f}")

            st.write("**Top Queries:**")
            top_q = analytics.get("top_queries", [])
            if top_q:
                import pandas as pd
                st.dataframe(pd.DataFrame(top_q))

            st.write("**Weak Match Queries:**")
            weak_q = analytics.get("weak_match_queries", [])
            if weak_q:
                import pandas as pd
                st.dataframe(pd.DataFrame(weak_q))
            else:
                st.info("No weak match queries found.")
