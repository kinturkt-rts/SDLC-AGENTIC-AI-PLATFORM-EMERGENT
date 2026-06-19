"""Streamlit UI for PR Diff Summarizer."""

import os
import streamlit as st
import requests
from datetime import datetime
from typing import Optional

# Configuration
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")
API_KEY = os.getenv("API_KEY", "")

# HTTP helpers with follow_redirects=True
def _get(path: str, params: Optional[dict] = None) -> requests.Response:
    """GET request with API key auth."""
    headers = {"X-API-Key": API_KEY}
    return requests.get(f"{API_BASE_URL}{path}", headers=headers, params=params, follow_redirects=True)

def _post(path: str, json_data: dict) -> requests.Response:
    """POST request with API key auth."""
    headers = {"X-API-Key": API_KEY}
    return requests.post(f"{API_BASE_URL}{path}", headers=headers, json=json_data, follow_redirects=True)

def _ensure_api_reachable():
    """Check if API is reachable and healthy."""
    try:
        response = requests.get(f"{API_BASE_URL}/health", timeout=5)
        if response.status_code != 200:
            st.error(f"❌ API health check failed: {response.status_code}")
            st.stop()
    except requests.exceptions.RequestException as e:
        st.error(f"❌ Cannot reach API at {API_BASE_URL}: {e}")
        st.stop()

# Startup check
_ensure_api_reachable()

# Main app
st.set_page_config(
    page_title="PR Diff Summarizer",
    page_icon="📊",
    layout="wide"
)

st.title("📊 PR Diff Summarizer")
st.markdown("Analyze pull request diffs with AI-powered risk scoring")

# Sidebar configuration
with st.sidebar:
    st.header("Configuration")
    st.text(f"API: {API_BASE_URL}")
    st.text(f"API Key: {'✅ Set' if API_KEY else '❌ Missing'}")
    
    if not API_KEY:
        st.error("API_KEY environment variable not set")
        st.stop()

# Tab layout
tab1, tab2, tab3 = st.tabs(["🔍 Analyze Diff", "📋 Review History", "📊 Statistics"])

with tab1:
    st.header("Analyze New PR Diff")
    
    with st.form("diff_analysis_form"):
        title = st.text_input(
            "PR Title",
            placeholder="Add user authentication middleware",
            help="Brief description of the pull request"
        )
        
        diff_text = st.text_area(
            "Diff Content",
            height=300,
            placeholder="""diff --git a/app/auth.py b/app/auth.py
new file mode 100644
index 0000000..abc123
--- /dev/null
+++ b/app/auth.py
@@ -0,0 +1,25 @@
+from fastapi import HTTPException, Request
+
+def authenticate_request(request: Request):
+    api_key = request.headers.get("X-API-Key")
+    if not api_key or not validate_key(api_key):
+        raise HTTPException(status_code=401)""",
            help="Paste the git diff output here"
        )
        
        submitted = st.form_submit_button("🔍 Analyze Diff", type="primary")
        
        if submitted:
            if not title.strip():
                st.error("Please enter a PR title")
            elif not diff_text.strip():
                st.error("Please paste the diff content")
            else:
                with st.spinner("Analyzing diff with AI..."):
                    try:
                        response = _post("/reviews/", {
                            "title": title.strip(),
                            "diff_text": diff_text.strip()
                        })
                        
                        if response.status_code == 201:
                            result = response.json()
                            
                            # Display results
                            st.success("✅ Analysis Complete!")
                            
                            col1, col2, col3 = st.columns(3)
                            with col1:
                                risk_score = result["risk_score"]
                                color = "🟢" if risk_score <= 30 else "🟡" if risk_score <= 70 else "🔴"
                                st.metric("Risk Score", f"{risk_score}/100", delta=f"{color} {result['risk_band'].upper()}")
                            
                            with col2:
                                st.metric("Files Changed", result["file_count"])
                            
                            with col3:
                                st.metric("Lines Changed", f"+{result['lines_added']} -{result['lines_removed']}")
                            
                            st.subheader("📝 AI Summary")
                            st.write(result["summary"])
                            
                            st.subheader("📄 Analysis Details")
                            st.json({
                                "ID": result["id"],
                                "Risk Band": result["risk_band"],
                                "Model": result["model_id"],
                                "Analyzed At": result["submitted_at"]
                            })
                            
                        elif response.status_code == 401:
                            st.error("❌ Authentication failed. Check your API key.")
                        elif response.status_code == 413:
                            st.error("❌ Diff content too large. Please reduce the size.")
                        else:
                            st.error(f"❌ Analysis failed: {response.json().get('detail', 'Unknown error')}")
                            
                    except requests.exceptions.RequestException as e:
                        st.error(f"❌ Connection error: {e}")

with tab2:
    st.header("📋 Review History")
    
    col1, col2 = st.columns([2, 1])
    with col1:
        risk_filter = st.selectbox(
            "Filter by Risk Band",
            options=["All", "low", "medium", "high"],
            help="Filter reviews by risk level"
        )
    
    with col2:
        limit = st.number_input("Records per page", min_value=10, max_value=100, value=20)
    
    if st.button("🔄 Refresh History"):
        params = {"limit": limit}
        if risk_filter != "All":
            params["risk_band"] = risk_filter
            
        try:
            response = _get("/reviews/", params=params)
            
            if response.status_code == 200:
                data = response.json()
                
                st.info(f"📊 Showing {len(data['items'])} of {data['total']} reviews")
                
                for review in data["items"]:
                    with st.container():
                        col1, col2, col3, col4 = st.columns([3, 1, 1, 1])
                        
                        with col1:
                            st.write(f"**{review['title']}**")
                            st.caption(f"ID: {review['id'][:8]}...")
                        
                        with col2:
                            risk_score = review["risk_score"]
                            color = "🟢" if risk_score <= 30 else "🟡" if risk_score <= 70 else "🔴"
                            st.write(f"{color} {risk_score}/100")
                        
                        with col3:
                            st.write(f"📁 {review['file_count']} files")
                        
                        with col4:
                            submitted = datetime.fromisoformat(review["submitted_at"].replace("Z", "+00:00"))
                            st.write(submitted.strftime("%m/%d %H:%M"))
                        
                        with st.expander("📄 Summary"):
                            st.write(review["summary"])
                            st.json({
                                "Lines Added": review["lines_added"],
                                "Lines Removed": review["lines_removed"],
                                "Risk Band": review["risk_band"],
                                "Model": review["model_id"]
                            })
                        
                        st.divider()
                        
            elif response.status_code == 401:
                st.error("❌ Authentication failed. Check your API key.")
            else:
                st.error(f"❌ Failed to load reviews: {response.json().get('detail', 'Unknown error')}")
                
        except requests.exceptions.RequestException as e:
            st.error(f"❌ Connection error: {e}")

with tab3:
    st.header("📊 Review Statistics")
    
    if st.button("📈 Load Statistics"):
        try:
            response = _get("/stats")
            
            if response.status_code == 200:
                stats = response.json()
                
                st.subheader("📅 Last 30 Days Overview")
                
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    total_reviews = sum(stats["last_30_days"].values())
                    st.metric("Total Reviews", total_reviews)
                
                with col2:
                    st.metric("🟢 Low Risk", stats["last_30_days"]["low"])
                
                with col3:
                    st.metric("🟡 Medium Risk", stats["last_30_days"]["medium"])
                
                with col4:
                    st.metric("🔴 High Risk", stats["last_30_days"]["high"])
                
                st.subheader("📊 Risk Distribution")
                
                if total_reviews > 0:
                    # Create a simple bar chart
                    risk_data = {
                        "Low": stats["last_30_days"]["low"],
                        "Medium": stats["last_30_days"]["medium"], 
                        "High": stats["last_30_days"]["high"]
                    }
                    
                    st.bar_chart(risk_data)
                    
                    st.subheader("📈 Average Risk Score")
                    avg_score = stats["avg_risk_score"]
                    color = "🟢" if avg_score <= 30 else "🟡" if avg_score <= 70 else "🔴"
                    st.metric("Average Risk", f"{avg_score:.1f}/100", delta=f"{color}")
                    
                    # Risk breakdown percentages
                    st.subheader("📋 Risk Breakdown")
                    for risk_level, count in risk_data.items():
                        percentage = (count / total_reviews) * 100
                        st.write(f"**{risk_level}**: {count} reviews ({percentage:.1f}%)")
                        
                else:
                    st.info("📭 No reviews in the last 30 days")
                    
            elif response.status_code == 401:
                st.error("❌ Authentication failed. Check your API key.")
            else:
                st.error(f"❌ Failed to load statistics: {response.json().get('detail', 'Unknown error')}")
                
        except requests.exceptions.RequestException as e:
            st.error(f"❌ Connection error: {e}")

# Footer
st.markdown("---")
st.markdown("💡 **Tip**: Use `git diff` command to generate diff content for analysis")