"""Streamlit UI for hello-fastapi — calls the FastAPI backend over HTTP."""
from __future__ import annotations

import os

import httpx
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")

st.set_page_config(page_title="Hello FastAPI", page_icon="👋", layout="wide")


def _get(path: str) -> httpx.Response:
    return httpx.get(f"{API_BASE_URL}{path}", timeout=10, follow_redirects=True)


def _post(path: str, payload: dict) -> httpx.Response:
    return httpx.post(f"{API_BASE_URL}{path}", json=payload, timeout=10, follow_redirects=True)


def _ensure_api_reachable() -> bool:
    try:
        return _get("/health").status_code == 200
    except httpx.HTTPError:
        return False


st.title("👋 Hello FastAPI")
st.caption("SDLC Agentic AI Platform — Phase A deploy dry run (ECS Fargate + shared ALB)")

if not _ensure_api_reachable():
    st.error(f"API not reachable at {API_BASE_URL}. Is the api container healthy?")
    st.stop()

stats = _get("/api/stats").json()
st.metric("Total greetings", stats["total_greetings"])

tab_list, tab_add = st.tabs(["Greetings", "Add greeting"])

with tab_list:
    greetings = _get("/api/greetings").json()
    if greetings:
        st.dataframe(greetings, width="stretch")
    else:
        st.info("No greetings yet — add one in the next tab.")

with tab_add:
    with st.form("add_greeting"):
        name = st.text_input("Your name", max_chars=80)
        message = st.text_input("Message", max_chars=280)
        submitted = st.form_submit_button("Send", width="stretch")
    if submitted:
        if not name.strip() or not message.strip():
            st.warning("Both name and message are required.")
        else:
            resp = _post("/api/greetings", {"name": name.strip(), "message": message.strip()})
            if resp.status_code == 201:
                st.success("Greeting added!")
                st.rerun()
            else:
                st.error(f"API error {resp.status_code}: {resp.text}")
