"""Data Engineer persona (Arjun). MCP monitor bar on top · 3 tabs below."""
import streamlit as st
from api.client import get_review_queue, get_review_yaml, get_deployed_pipelines, get_mcp_status
from components.review_card import render_review_card
from components.monitor_panel import render_monitor


def _mcp_topbar():
    """Always-on MCP tools monitor strip at the very top, with breathing green dots."""
    mcp = get_mcp_status(st.session_state.token)
    if not mcp:
        return
    chips = ['<span class="mcp-title">🔌 MCP TOOLS</span>']
    for t in mcp["tools"]:
        connecting = t["status"] != "connected"
        dot = '<span class="live-dot amber"></span>' if connecting else '<span class="live-dot"></span>'
        lat = "connecting" if t["latency_ms"] is None else f'{t["latency_ms"]}ms'
        chips.append(f'<span class="mcp-chip">{dot}{t["name"]} <span class="lat">· {lat}</span></span>')
    st.markdown(f'<div class="mcp-topbar">{"".join(chips)}</div>', unsafe_allow_html=True)


def _tabs(active: str, pending: int):
    badge = f'<span class="etab-badge">{pending}</span>' if pending else ""
    a = lambda n: "active" if active == n else ""
    st.markdown(
        '<div class="eng-tabs">'
        f'<a class="etab {a("review")}" href="?persona=engineer&tab=review" target="_self">Pipeline Review {badge}</a>'
        f'<a class="etab {a("deployed")}" href="?persona=engineer&tab=deployed" target="_self">Deployed</a>'
        f'<a class="etab {a("monitor")}" href="?persona=engineer&tab=monitor" target="_self">Live Monitor</a>'
        '</div>',
        unsafe_allow_html=True,
    )


def render_engineer():
    tab = st.session_state.get("engineer_tab", "review")
    queue = get_review_queue(st.session_state.token) or {"total_pending": 0, "queue": []}

    _mcp_topbar()
    _tabs(tab, queue["total_pending"])

    if tab == "review":
        with st.container(key="engtools"):
            c1, c2 = st.columns([6, 1], vertical_alignment="center")
            with c1:
                st.markdown('<div class="section-label" style="margin:0">📥 PENDING YOUR APPROVAL</div>',
                            unsafe_allow_html=True)
            with c2:
                if st.button("🔄 Refresh", key="refresh_queue", use_container_width=True):
                    st.rerun()

        if not queue["queue"]:
            st.markdown(
                '<div class="eng-panel"><div style="text-align:center;padding:48px;color:#6B7385">'
                '<div style="font-size:34px;opacity:.3">✓</div>'
                '<p style="margin-top:8px;font-size:13px">No pipelines awaiting review</p></div></div>',
                unsafe_allow_html=True,
            )
        else:
            st.markdown('<div class="eng-panel" style="padding-top:6px">', unsafe_allow_html=True)
            for item in queue["queue"]:
                yaml_data = get_review_yaml(item["request_id"], st.session_state.token)
                if yaml_data:
                    render_review_card(item, yaml_data)
            st.markdown('</div>', unsafe_allow_html=True)

    elif tab == "deployed":
        deployed = get_deployed_pipelines(st.session_state.token) or {"deployed": []}
        cards = '<div class="eng-panel"><div class="section-label">🟢 RUNNING PIPELINES</div>'
        for p in deployed["deployed"]:
            cards += (
                '<div class="dep-card"><div class="dep-head"><div>'
                f'<div class="dep-name">{p["pipeline_name"]}</div>'
                '<div class="dep-meta">'
                '<span class="badge badge-green"><span class="live-dot"></span> Running</span>'
                f'<span>Job ID: {p["flink_job_id"]} · approved by {p["approved_by"]} · {p["minutes_ago"]} mins ago</span>'
                '</div></div>'
                f'<div class="dep-rps">{p["events_per_second"]} events/s</div></div>'
                f'<div class="dep-tables">Requested by <strong>{p["requested_by"]}</strong> · '
                f'Sink: Snowflake → {p["sink_table"]} · commit {p["github_commit"]}</div></div>'
            )
        cards += "</div>"
        st.markdown(cards, unsafe_allow_html=True)

    elif tab == "monitor":
        render_monitor()
