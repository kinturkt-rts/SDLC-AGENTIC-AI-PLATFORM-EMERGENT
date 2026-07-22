"""Streamlit UI for Meeting Room Booking API.

Provides role-based views:
- Standard users: browse rooms, create/cancel own reservations
- Admin users: manage rooms (create/update/deactivate) + all reservations
"""
from __future__ import annotations

import os

import httpx
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

# ── Config ────────────────────────────────────────────────────────────────────
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")

st.set_page_config(page_title="Meeting Room Booking", page_icon="🏢", layout="wide")


# ── HTTP helpers (DO NOT MODIFY) ─────────────────────────────────────────────
def _get_headers() -> dict[str, str]:
    """Return auth headers from session state."""
    api_key = st.session_state.get("api_key", "")
    if api_key:
        return {"X-API-Key": api_key}
    return {}


def _get(path: str, params: dict | None = None) -> httpx.Response:
    return httpx.get(
        f"{API_BASE_URL}{path}",
        params=params,
        headers=_get_headers(),
        timeout=30.0,
        follow_redirects=True,
    )


def _post(path: str, json_body: dict | None = None) -> httpx.Response:
    return httpx.post(
        f"{API_BASE_URL}{path}",
        json=json_body,
        headers=_get_headers(),
        timeout=60.0,
        follow_redirects=True,
    )


def _patch(path: str, json_body: dict) -> httpx.Response:
    return httpx.patch(
        f"{API_BASE_URL}{path}",
        json=json_body,
        headers=_get_headers(),
        timeout=30.0,
        follow_redirects=True,
    )


def _delete(path: str) -> httpx.Response:
    return httpx.delete(
        f"{API_BASE_URL}{path}",
        headers=_get_headers(),
        timeout=30.0,
        follow_redirects=True,
    )


def _ensure_api_reachable() -> None:
    """Check API health on startup; stop with actionable error if unreachable."""
    try:
        resp = httpx.get(f"{API_BASE_URL}/health", timeout=10.0, follow_redirects=True)
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
            "cd target-apps/meeting-room-api\n"
            ".venv\\Scripts\\Activate.ps1  # or source .venv/bin/activate\n"
            "uvicorn app.main:app --reload --port 8000\n"
            "```"
        )
        st.stop()
    except Exception as exc:
        st.error(f"Unexpected error reaching API: {exc}")
        st.stop()


# ── Auth Gate ─────────────────────────────────────────────────────────────────
def _show_login() -> None:
    """Display API key login form."""
    st.title("\U0001f3e2 Meeting Room Booking")
    st.info("Enter your API key to access the system.")
    with st.form("login_form"):
        api_key = st.text_input("API Key", type="password")
        submitted = st.form_submit_button("Login", type="primary")
        if submitted and api_key:
            resp = httpx.get(
                f"{API_BASE_URL}/api/v1/rooms",
                headers={"X-API-Key": api_key},
                timeout=10.0,
                follow_redirects=True,
            )
            if resp.status_code == 200:
                st.session_state["api_key"] = api_key
                # Determine role by trying admin-only endpoint
                test_resp = httpx.post(
                    f"{API_BASE_URL}/api/v1/rooms",
                    headers={"X-API-Key": api_key},
                    json={"name": "__role_probe__", "floor": "0", "capacity": 1},
                    timeout=10.0,
                    follow_redirects=True,
                )
                if test_resp.status_code == 403:
                    st.session_state["role"] = "standard"
                else:
                    st.session_state["role"] = "admin"
                    # Clean up probe room if created
                    if test_resp.status_code == 201:
                        rid = test_resp.json().get("id")
                        if rid:
                            httpx.patch(
                                f"{API_BASE_URL}/api/v1/rooms/{rid}",
                                headers={"X-API-Key": api_key},
                                json={"active": False},
                                timeout=10.0,
                                follow_redirects=True,
                            )
                st.rerun()
            else:
                st.error("Invalid API key.")


# ── Main ──────────────────────────────────────────────────────────────────────
_ensure_api_reachable()

if "api_key" not in st.session_state:
    _show_login()
    st.stop()

# Sidebar
with st.sidebar:
    st.title("\U0001f3e2 Rooms")
    role = st.session_state.get("role", "standard")
    st.write(f"**Role:** {role}")
    if st.button("Logout"):
        st.session_state.pop("api_key", None)
        st.session_state.pop("role", None)
        st.rerun()

# Tabs
if role == "admin":
    tab_rooms, tab_reservations, tab_manage = st.tabs(
        ["Browse Rooms", "Reservations", "Manage Rooms"]
    )
else:
    tab_rooms, tab_reservations = st.tabs(["Browse Rooms", "Reservations"])
    tab_manage = None

# ── Browse Rooms ──────────────────────────────────────────────────────────────
with tab_rooms:
    st.header("Available Rooms")
    col1, col2, col3 = st.columns(3)
    with col1:
        f_floor = st.text_input("Floor", key="rf_floor")
    with col2:
        f_cap = st.number_input("Min Capacity", min_value=0, value=0, key="rf_cap")
    with col3:
        f_active = st.selectbox("Status", ["Active", "All", "Inactive"], key="rf_status")

    params: dict = {}
    if f_floor:
        params["floor"] = f_floor
    if f_cap > 0:
        params["min_capacity"] = f_cap
    if f_active == "Active":
        params["active"] = True
    elif f_active == "Inactive":
        params["active"] = False

    rooms_resp = _get("/api/v1/rooms", params=params)
    if rooms_resp.status_code == 200:
        rooms_data = rooms_resp.json()
        if rooms_data:
            rows = [
                {
                    "Name": r["name"],
                    "Floor": r["floor"],
                    "Capacity": r["capacity"],
                    "Amenities": r.get("amenities") or "",
                    "Active": "Yes" if r["active"] else "No",
                }
                for r in rooms_data
            ]
            st.dataframe(rows, width="stretch")
        else:
            st.info("No rooms match filters.")
    else:
        st.error(f"Error: {rooms_resp.status_code}")

# ── Reservations ──────────────────────────────────────────────────────────────
with tab_reservations:
    st.header("Reservations")
    # Fetch rooms for selectbox
    all_rooms_resp = _get("/api/v1/rooms")
    room_map: dict[str, str] = {}
    if all_rooms_resp.status_code == 200:
        for r in all_rooms_resp.json():
            room_map[f"{r['name']} (Floor {r['floor']})"] = r["id"]

    view_tab, create_tab = st.tabs(["View", "Create"])

    with view_tab:
        c1, c2 = st.columns(2)
        with c1:
            sel_room = st.selectbox("Room", ["All"] + list(room_map.keys()), key="rv_room")
        with c2:
            sel_email = st.text_input("Organizer Email", key="rv_email")

        rp: dict = {}
        if sel_room != "All":
            rp["room_id"] = room_map[sel_room]
        if sel_email:
            rp["organizer_email"] = sel_email

        res_resp = _get("/api/v1/reservations", params=rp)
        if res_resp.status_code == 200:
            res_data = res_resp.json()
            if res_data:
                disp = [
                    {
                        "Title": r["title"],
                        "Organizer": r["organizer_email"],
                        "Start": r["start_time"],
                        "End": r["end_time"],
                        "Status": r["status"],
                    }
                    for r in res_data
                ]
                st.dataframe(disp, width="stretch")

                # Cancel
                active_res = [r for r in res_data if r["status"] == "active"]
                if active_res:
                    st.subheader("Cancel a Reservation")
                    opts = {f"{r['title']} ({r['start_time'][:16]})": r["id"] for r in active_res}
                    choice = st.selectbox("Select", list(opts.keys()), key="cancel_sel")
                    if st.button("Cancel", key="cancel_btn"):
                        cr = _post(f"/api/v1/reservations/{opts[choice]}/cancel")
                        if cr.status_code == 200:
                            st.success("Cancelled!")
                            st.rerun()
                        else:
                            st.error(cr.json().get("detail", cr.text))
            else:
                st.info("No reservations found.")
        else:
            st.error(f"Error: {res_resp.status_code}")

    with create_tab:
        st.subheader("Book a Room")
        with st.form("book_form"):
            if room_map:
                book_room = st.selectbox("Room", list(room_map.keys()), key="bk_room")
            else:
                book_room = None
                st.warning("No rooms available.")
            bk_title = st.text_input("Title")
            bk_email = st.text_input("Organizer Email")
            c_s, c_e = st.columns(2)
            with c_s:
                bk_sdate = st.date_input("Start Date")
                bk_stime = st.time_input("Start Time")
            with c_e:
                bk_edate = st.date_input("End Date")
                bk_etime = st.time_input("End Time")
            bk_notes = st.text_area("Notes (optional)")
            sub = st.form_submit_button("Book", type="primary")

            if sub and book_room and bk_title and bk_email:
                payload = {
                    "room_id": room_map[book_room],
                    "title": bk_title,
                    "organizer_email": bk_email,
                    "start_time": f"{bk_sdate}T{bk_stime}:00+00:00",
                    "end_time": f"{bk_edate}T{bk_etime}:00+00:00",
                }
                if bk_notes:
                    payload["notes"] = bk_notes
                br = _post("/api/v1/reservations", json_body=payload)
                if br.status_code == 201:
                    st.success("Booked!")
                    st.rerun()
                elif br.status_code == 409:
                    st.error(f"Conflict: {br.json().get('detail', '')}")
                else:
                    st.error(f"Error {br.status_code}: {br.text}")

# ── Manage Rooms (Admin) ─────────────────────────────────────────────────────
if tab_manage is not None:
    with tab_manage:
        st.header("Room Management (Admin)")
        cr_tab, upd_tab = st.tabs(["Create Room", "Update Room"])

        with cr_tab:
            with st.form("new_room"):
                nr_name = st.text_input("Name")
                nr_floor = st.text_input("Floor")
                nr_cap = st.number_input("Capacity", min_value=1, value=6)
                nr_amen = st.text_input("Amenities")
                nr_sub = st.form_submit_button("Create", type="primary")
                if nr_sub and nr_name and nr_floor:
                    p = {"name": nr_name, "floor": nr_floor, "capacity": nr_cap}
                    if nr_amen:
                        p["amenities"] = nr_amen
                    rr = _post("/api/v1/rooms", json_body=p)
                    if rr.status_code == 201:
                        st.success("Created!")
                        st.rerun()
                    else:
                        st.error(rr.json().get("detail", rr.text))

        with upd_tab:
            mgmt_resp = _get("/api/v1/rooms")
            if mgmt_resp.status_code == 200:
                mgmt_rooms = mgmt_resp.json()
                if mgmt_rooms:
                    labels = {
                        f"{r['name']} ({'Active' if r['active'] else 'Inactive'})": r
                        for r in mgmt_rooms
                    }
                    sel = st.selectbox("Room", list(labels.keys()), key="upd_sel")
                    rd = labels[sel]
                    with st.form("upd_room"):
                        u_name = st.text_input("Name", value=rd["name"])
                        u_floor = st.text_input("Floor", value=rd["floor"])
                        u_cap = st.number_input("Capacity", min_value=1, value=rd["capacity"])
                        u_amen = st.text_input("Amenities", value=rd.get("amenities") or "")
                        u_active = st.checkbox("Active", value=rd["active"])
                        u_sub = st.form_submit_button("Update", type="primary")
                        if u_sub:
                            up: dict = {}
                            if u_name != rd["name"]:
                                up["name"] = u_name
                            if u_floor != rd["floor"]:
                                up["floor"] = u_floor
                            if u_cap != rd["capacity"]:
                                up["capacity"] = u_cap
                            if u_amen != (rd.get("amenities") or ""):
                                up["amenities"] = u_amen
                            if u_active != rd["active"]:
                                up["active"] = u_active
                            if up:
                                ur = _patch(f"/api/v1/rooms/{rd['id']}", json_body=up)
                                if ur.status_code == 200:
                                    st.success("Updated!")
                                    st.rerun()
                                else:
                                    st.error(ur.json().get("detail", ur.text))
                            else:
                                st.info("No changes.")
