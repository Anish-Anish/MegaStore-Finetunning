import streamlit as st
from api.client import get_pipeline_history

# Exactly these 5 dummy conversations are shown (newest asks don't clutter the list).
DUMMY_IDS = ["conv_sales", "conv_returns", "conv_platinum", "conv_topreturns", "conv_channel"]

STATUS_STYLE = {
    "live":           ("#16A34A", "Live"),
    "generating":     ("#4338CA", "Building…"),
    "validating":     ("#4338CA", "Checking…"),
    "pending_review": ("#D97706", "Awaiting engineer"),
    "approved":       ("#4338CA", "Connecting…"),
    "deploying":      ("#4338CA", "Connecting…"),
    "rejected":       ("#DC2626", "Needs revision"),
}


def _ago(m):
    if not m:
        return "just now"
    if m < 60:
        return f"{m} mins ago"
    h = m // 60
    return "1 hr ago" if h == 1 else f"{h} hrs ago"


def render_sidebar():
    """Sidebar = brand + New question + 5 dummy chat conversations."""
    st.markdown('<div class="sidebar-brand">MegaStore<span> Pulse</span></div>', unsafe_allow_html=True)

    if st.button("＋  New question", key="newq", use_container_width=True):
        if st.session_state.persona != "business":
            from components.topbar import do_login
            do_login("business")
        st.session_state.active_request_id = None
        st.session_state._last_open = None
        st.query_params.clear()
        st.query_params["persona"] = "business"
        st.rerun()

    history = get_pipeline_history(st.session_state.user_id or "priya_001", "business", st.session_state.token)
    requests = history["requests"] if (history and "requests" in history) else []
    # Display the most recent 6 conversations (including newly asked ones)
    requests = requests[:6]

    st.markdown('<div class="conv-list-head">💬 RECENT CHATS</div>', unsafe_allow_html=True)
    items = []
    for req in requests:
        cid = req["request_id"]
        dot, label = STATUS_STYLE.get(req["status"], ("#DDE0EB", req["status"]))
        active = "active" if (st.session_state.persona == "business" and cid == st.session_state.active_request_id) else ""
        items.append(
            f'<div class="conv-item {active}">'
            f'<a class="conv-item-link" href="?persona=business&open={cid}" target="_self">'
            f'<div class="conv-q">{req["question"]}</div>'
            f'<div class="conv-meta"><span class="conv-dot" style="background:{dot}"></span>'
            f'<span>{label} · {_ago(req.get("minutes_ago", 0))}</span></div></a>'
            f'<a class="conv-delete-btn" href="?persona=business&delete={cid}" target="_self" title="Delete conversation">🗑️</a>'
            f'</div>'
        )
    st.markdown(f'<div class="conv-list">{"".join(items)}</div>', unsafe_allow_html=True)

