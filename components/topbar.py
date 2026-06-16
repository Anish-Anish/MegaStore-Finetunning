import streamlit as st
from api.client import login, get_system_status


def do_login(persona: str):
    """Authenticate as a persona and store identity in session (fallback if backend down)."""
    data = login(persona)
    if not data:
        data = ({"user_id": "priya_001", "name": "Priya", "role": "CEO", "persona": "business",
                 "avatar_initial": "P", "avatar_color": "#7C3AED", "session_token": "tok_local"}
                if persona == "business" else
                {"user_id": "arjun_001", "name": "Arjun", "role": "Data Eng", "persona": "engineer",
                 "avatar_initial": "A", "avatar_color": "#0891B2", "session_token": "tok_local"})
    st.session_state.persona = data["persona"]
    st.session_state.user_id = data["user_id"]
    st.session_state.user_name = data["name"]
    st.session_state.user_role = data["role"]
    st.session_state.avatar_initial = data["avatar_initial"]
    st.session_state.avatar_color = data["avatar_color"]
    st.session_state.token = data["session_token"]
    st.session_state.logged_in = True


def render_topbar():
    """Top bar: brand · live status · persona switch (real buttons) · avatar."""
    sys = get_system_status() or {}
    active = sys.get("active_pipelines", st.session_state.active_pipelines_count)
    is_biz = st.session_state.persona == "business"

    with st.container(key="topbar"):
        c1, c2, c3, c4, c5 = st.columns([2.4, 3.4, 1.2, 1.7, 2.6], vertical_alignment="center")
        with c1:
            st.markdown('<div class="topbar-brand">MegaStore<span> Pulse</span></div>', unsafe_allow_html=True)
        with c2:
            st.markdown(
                f'<div class="topbar-live"><span class="pulse-dot"></span> Flink live · '
                f'{active} pipelines active</div>', unsafe_allow_html=True)
        with c3:
            if st.button("📊 Business", key="ps_biz",
                         type="primary" if is_biz else "secondary", use_container_width=True):
                do_login("business")
                # URL is the source of truth — overwrite it so _sync_query_params agrees.
                active_id = st.session_state.get("active_request_id")
                st.query_params.clear()
                st.query_params["persona"] = "business"
                if active_id:
                    st.query_params["open"] = active_id
                st.rerun()
        with c4:
            if st.button("⚙️ Data Engineer", key="ps_eng",
                         type="primary" if not is_biz else "secondary", use_container_width=True):
                do_login("engineer")
                st.session_state.engineer_tab = "review"
                st.query_params.clear()
                st.query_params["persona"] = "engineer"
                st.query_params["tab"] = "review"
                st.rerun()
        with c5:
            st.markdown(
                f'<div class="topbar-user-wrap">'
                f'<span class="topbar-avatar" style="background:{st.session_state.avatar_color}">'
                f'{st.session_state.avatar_initial}</span>'
                f'<span class="topbar-user">{st.session_state.user_name} ({st.session_state.user_role})</span>'
                f'</div>', unsafe_allow_html=True)
