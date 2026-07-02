"""PR Diff Summarizer — Streamlit UI.

Three-tab dashboard: Submit a PR, History, Stats.
Communicates with FastAPI exclusively over HTTP.
Never imports from app/.
"""
import os
from pathlib import Path

import streamlit as st
import httpx
from dotenv import load_dotenv

# Load .env from project root
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")
API_KEY = os.getenv("API_KEY", "")

SERVICE_NAME = "PR Diff Summarizer"


def _headers() -> dict:
    return {"X-API-Key": API_KEY}


def _get(path: str, params: dict | None = None) -> httpx.Response:
    return httpx.get(
        f"{API_BASE_URL}{path}",
        headers=_headers(),
        params=params,
        follow_redirects=True,
        timeout=30.0,
    )


def _post(path: str, json: dict | None = None) -> httpx.Response:
    return httpx.post(
        f"{API_BASE_URL}{path}",
        headers=_headers(),
        json=json,
        follow_redirects=True,
        timeout=60.0,
    )


def _ensure_api_reachable():
    """Check API is up before rendering tabs."""
    try:
        resp = httpx.get(f"{API_BASE_URL}/health", timeout=5.0, follow_redirects=True)
        if resp.status_code != 200:
            st.error(f"API returned status {resp.status_code}. Is the server running?")
            st.stop()
    except httpx.ConnectError:
        st.error(
            f"Cannot reach API at {API_BASE_URL}. "
            "Start the API server first: `uvicorn app.main:app --port 8000`"
        )
        st.stop()


def main():
    st.set_page_config(page_title=SERVICE_NAME, layout="wide")
    st.title(SERVICE_NAME)

    _ensure_api_reachable()

    tab1, tab2, tab3 = st.tabs(["Submit a PR", "History", "Stats"])

    # --- Tab 1: Submit ---
    with tab1:
        st.header("Submit a PR Diff for Review")
        title = st.text_input("PR Title", placeholder="e.g. Add user authentication")
        diff_text = st.text_area(
            "Paste diff text",
            height=300,
            placeholder="diff --git a/file.py b/file.py\n...",
        )
        if st.button("Submit for Review", type="primary"):
            if not title.strip():
                st.warning("Please enter a PR title.")
            elif not diff_text.strip():
                st.warning("Please paste a diff.")
            else:
                with st.spinner("Analyzing diff..."):
                    resp = _post("/reviews", json={"title": title, "diff_text": diff_text})
                if resp.status_code == 201:
                    data = resp.json()
                    st.success(f"Review created! Risk band: **{data['risk_band']}** (score: {data['risk_score']})")
                    st.subheader("Summary")
                    st.write(data.get("summary", "N/A"))
                    st.subheader("Risk Factors")
                    for rf in data.get("risk_factors", []):
                        st.write(f"- {rf}")
                    st.subheader("Diff Statistics")
                    col1, col2, col3 = st.columns(3)
                    col1.metric("Files Changed", data.get("file_count", 0))
                    col2.metric("Lines Added", data.get("lines_added", 0))
                    col3.metric("Lines Removed", data.get("lines_removed", 0))
                elif resp.status_code == 422:
                    st.error(f"Validation error: {resp.json().get('detail', 'Unknown')}")
                elif resp.status_code == 502:
                    st.error("AI service error — please try again later.")
                else:
                    st.error(f"Error {resp.status_code}: {resp.text}")

    # --- Tab 2: History ---
    with tab2:
        st.header("Review History")
        band_filter = st.selectbox("Filter by risk band", ["All", "low", "medium", "high"])
        params: dict = {"limit": 50, "offset": 0}
        if band_filter != "All":
            params["risk_band"] = band_filter

        resp = _get("/reviews", params=params)
        if resp.status_code == 200:
            data = resp.json()
            items = data.get("items", [])
            st.write(f"Showing {len(items)} of {data.get('total', 0)} reviews")
            for item in items:
                with st.expander(f"{item['title']} — {item['risk_band']} ({item['risk_score']})"):
                    st.write(f"**Summary:** {item.get('summary', 'N/A')}")
                    st.write(f"**Risk Factors:** {', '.join(item.get('risk_factors', []))}")
                    st.write(
                        f"**Files:** {item.get('file_count', 0)} | "
                        f"+{item.get('lines_added', 0)} / -{item.get('lines_removed', 0)}"
                    )
                    st.write(f"**Submitted:** {item.get('submitted_at', 'N/A')}")
        else:
            st.error(f"Failed to load reviews: {resp.status_code}")

    # --- Tab 3: Stats ---
    with tab3:
        st.header("Risk Distribution — Last 30 Days")
        resp = _get("/stats")
        if resp.status_code == 200:
            data = resp.json()
            last_30 = data["last_30_days"]
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Low Risk", last_30["low"])
            col2.metric("Medium Risk", last_30["medium"])
            col3.metric("High Risk", last_30["high"])
            col4.metric("Avg Score", data["avg_risk_score"])

            # Bar chart
            import pandas as pd
            chart_data = pd.DataFrame({
                "Risk Band": ["Low", "Medium", "High"],
                "Count": [last_30["low"], last_30["medium"], last_30["high"]],
            })
            st.bar_chart(chart_data.set_index("Risk Band"))
        else:
            st.error(f"Failed to load stats: {resp.status_code}")


if __name__ == "__main__":
    main()
