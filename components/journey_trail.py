import streamlit as st


def render_journey(steps: list, notify_href: str = None, notify_on: bool = False):
    """Render the animated 6-step journey/progress bar.

    Each step: {"label": str, "state": "done"|"active"|"waiting"|"rejected"}.
    States come straight from GET /pipelines/{id}/status — never computed here.
    A "Notify me on Slack" pill sits on the right of the header (point: notify when
    the engineer approves / the answer changes).
    """
    parts = []
    for i, step in enumerate(steps):
        state = step["state"]
        icon = {"done": "✓", "active": "", "rejected": "✗"}.get(state, str(i + 1))
        parts.append(
            f'<div class="j-step {state}"><div class="j-icon">{icon}</div>'
            f'<div class="j-label">{step["label"]}</div></div>'
        )
        if i < len(steps) - 1:
            nxt = steps[i + 1]["state"]
            conn = "done" if (state == "done" and nxt == "done") else ("active" if (state == "done" and nxt == "active") else "")
            parts.append(f'<div class="j-connector {conn}"></div>')

    notify = ""
    if notify_href:
        if notify_on:
            notify = '<span class="notify-pill on">🔔 You\'ll be notified on Slack</span>'
        else:
            notify = f'<a class="notify-pill" href="{notify_href}" target="_self">🔔 Notify me on Slack</a>'

    st.markdown(
        '<div class="journey-trail">'
        '<div class="journey-head-row">'
        '<div class="journey-head">⚡ HOW YOUR ANSWER IS BEING BUILT</div>'
        f'{notify}</div>'
        f'<div class="journey-steps">{"".join(parts)}</div></div>',
        unsafe_allow_html=True,
    )
