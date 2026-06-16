import streamlit as st
from api.client import get_monitor_metrics, get_event_stream


def _lakhs_or_k(v: int) -> str:
    return f"₹{v / 1000:.0f}K" if v < 100000 else f"₹{v / 100000:.1f}L"


@st.fragment(run_every=3)
def render_monitor():
    # Auto-refreshes ONLY this fragment every 3s — no full-page reload.
    metrics = get_monitor_metrics(st.session_state.token) or {}

    # 4 metric cards (monitor-grid)
    cards = [
        (_lakhs_or_k(metrics.get("total_sales_10min", 0)), "Sales (10 min)"),
        (f'{metrics.get("transaction_count", 0):,}', "Transactions"),
        (str(metrics.get("events_per_second", 0)), "Events/sec"),
        (str(metrics.get("active_pipelines", 3)), "Active pipelines"),
    ]
    grid = "".join(f'<div class="m-card"><div class="m-val">{v}</div>'
                   f'<div class="m-lbl">{l}</div></div>' for v, l in cards)

    pipes = "".join(
        f'<div class="pipeline-row"><span class="pulse-dot"></span>'
        f'<span class="pr-name">{p["name"]}</span>'
        f'<span class="pr-stats">{p["events_per_second"]} events/s</span></div>'
        for p in metrics.get("pipelines", [])
    )

    feed = get_event_stream(st.session_state.token) or {"events": []}
    feed_lines = []
    for e in feed["events"]:
        feed_lines.append(
            f'<span class="feed-ts">[{e["timestamp"]}]</span> '
            f'<span class="feed-store">{e["store"]}</span> · '
            f'<span class="feed-cat">{e["category"]}</span> · '
            f'<span class="feed-amt">₹{e["amount"]:,}</span>'
        )

    st.markdown(
        '<div class="eng-panel">'
        f'<div class="monitor-grid">{grid}</div>'
        '<div class="section-label">PIPELINE THROUGHPUT</div>'
        f'{pipes}'
        '<div class="section-label">EVENT STREAM</div>'
        f'<div class="feed-box">{"<br>".join(feed_lines)}</div>'
        '</div>',
        unsafe_allow_html=True,
    )
