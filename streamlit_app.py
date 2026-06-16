"""
MegaStore Pulse — AI Pipeline Studio (Streamlit)
Two personas, one app:
  📊 Business (Priya)      — ask questions, watch the animated journey, see live answers + charts
  ⚙️ Data Engineer (Arjun) — review AI pipelines (readable YAML editor), approve & auto-deploy, monitor

Run:
  Terminal 1:  uvicorn backend_mock:app --port 8000 --reload
  Terminal 2:  streamlit run streamlit_app.py
"""
import os
import streamlit as st
import streamlit.components.v1 as components

from utils.state import init_state
from components.topbar import render_topbar, do_login
from components.sidebar import render_sidebar
from views.business_view import render_business
from views.engineer_view import render_engineer

st.set_page_config(page_title="MegaStore Pulse — AI Pipeline Studio",
                   page_icon="📊", layout="wide", initial_sidebar_state="expanded")


def _inject_css():
    path = os.path.join(os.path.dirname(__file__), "assets", "style.css")
    try:
        with open(path) as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
    except FileNotFoundError:
        pass


# A guaranteed, always-visible sidebar toggle. Streamlit's native expand control is
# unreliable here (it slides off-screen with the sidebar), so we inject our own
# floating ☰ button into the PARENT document that clicks whichever native control exists.
_TOGGLE_JS = """
<script>
(function(){
  try {
    var doc = window.parent.document;
    var q = function(s){ return doc.querySelector(s); };
    function expandCtl(){
      return q('[data-testid="stExpandSidebarButton"]')
          || q('[data-testid="collapsedControl"] button')
          || q('[data-testid="stSidebarCollapsedControl"] button');
    }
    function collapseCtl(){ return q('[data-testid="stSidebarCollapseButton"]'); }
    var btn = doc.getElementById('mp-sidebar-toggle');
    if (!btn) {
      btn = doc.createElement('button');
      btn.id = 'mp-sidebar-toggle';
      btn.innerHTML = '☰';
      btn.title = 'Show / hide conversations';
      Object.assign(btn.style, {position:'fixed', top:'12px', left:'12px', zIndex:'2000000',
        width:'38px', height:'38px', borderRadius:'10px', cursor:'pointer', padding:'0',
        background:'rgba(255,255,255,.92)', color:'#4338CA', border:'1px solid #DDE0EB',
        fontSize:'16px', lineHeight:'36px', backdropFilter:'blur(6px)',
        boxShadow:'0 2px 10px rgba(13,17,23,.10)', transition:'all .15s'});
      btn.onmouseenter = function(){ btn.style.background='#4338CA'; btn.style.color='#fff';
        btn.style.borderColor='#4338CA'; btn.style.boxShadow='0 4px 14px rgba(67,56,202,.35)'; };
      btn.onmouseleave = function(){ btn.style.background='rgba(255,255,255,.92)'; btn.style.color='#4338CA';
        btn.style.borderColor='#DDE0EB'; btn.style.boxShadow='0 2px 10px rgba(13,17,23,.10)'; };
      // Always-visible TOGGLE: open if collapsed, otherwise close. Works in both states.
      btn.addEventListener('click', function(e){
        e.preventDefault(); e.stopPropagation();
        var ex = expandCtl(); if (ex) { ex.click(); return; }
        var co = collapseCtl(); if (co) { co.click(); }
      });
      doc.body.appendChild(btn);
    }
  } catch (err) { /* parent not reachable — native control still available */ }
})();
</script>
"""


def _inject_sidebar_toggle():
    components.html(_TOGGLE_JS, height=0, width=0)


def _sync_query_params():
    qp = st.query_params

    # Handle conversation deletion via query parameters
    delete_id = qp.get("delete")
    if delete_id:
        from api.client import delete_pipeline
        delete_pipeline(delete_id, st.session_state.token)
        if st.session_state.active_request_id == delete_id:
            st.session_state.active_request_id = None
            st.session_state._last_open = None
        st.query_params.clear()
        st.query_params["persona"] = st.session_state.persona
        st.toast("🗑️ Conversation deleted")
        st.rerun()

    persona = qp.get("persona")
    if persona in ("business", "engineer") and persona != st.session_state.persona:
        do_login(persona)
    tab = qp.get("tab")
    if tab in ("review", "deployed", "monitor"):
        st.session_state.engineer_tab = tab
    # A suggestion chip was clicked → submit that question (chat-style)
    q = qp.get("q")
    if q is not None and q != st.session_state._last_q:
        st.session_state._pending_ask = q
        st.session_state._last_q = q
    open_id = qp.get("open")
    if open_id and open_id != st.session_state._last_open:
        st.session_state.active_request_id = open_id
        st.session_state._last_open = open_id

    # Notify pill (journey header) → register Slack notification once
    if qp.get("notify") and open_id and not st.session_state.get(f"notified_{open_id}"):
        from api.client import set_notification
        set_notification(open_id, st.session_state.user_id, st.session_state.token)
        st.session_state[f"notified_{open_id}"] = True
        st.toast("🔔 You'll be notified on Slack the moment this is live / changes")


def main():
    init_state()
    _inject_css()
    if not st.session_state.logged_in:
        do_login(st.session_state.persona)
    _sync_query_params()

    render_topbar()

    with st.sidebar:
        render_sidebar()

    if st.session_state.persona == "business":
        render_business()
    else:
        render_engineer()

    _inject_sidebar_toggle()


if __name__ == "__main__":
    main()
