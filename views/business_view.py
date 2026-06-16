"""Business persona (Priya) — chat-style.

Landing (no active conversation): greeting + suggestion chips + docked chat input.
A conversation renders as chat bubbles (user question → AI journey/answer). Live
status updates use an st.fragment that re-renders ONLY the conversation area
(run_every) — NOT a full page reload — so the rest of the page never flashes.
Language rule: never expose pipeline/YAML/Flink/Kafka jargon to the business user.
"""
import streamlit as st
from urllib.parse import quote
from api.client import ask_question, get_pipeline_status, get_pipeline_answer, get_suggestions
from components.journey_trail import render_journey
from components.answer_card import render_answer_card

_FALLBACK_CHIPS = [
    {"label": "Sales by category", "icon": "📊", "question": "Sales by category, exclude returns, 10-min window by store and region"},
    {"label": "High return stores", "icon": "↩️", "question": "Which stores have more than 20 returns in the last 30 minutes?"},
    {"label": "Platinum customer spend", "icon": "💎", "question": "PLATINUM customer spend by region this hour"},
    {"label": "Quality alerts", "icon": "🔍", "question": "Top products with quality issues today"},
    {"label": "Channel GMV", "icon": "🛒", "question": "Hourly GMV by channel — ONLINE vs IN_STORE"},
]
_NON_TERMINAL = ("generating", "validating", "pending_review", "approved", "deploying")


def render_business():
    # A suggestion chip was clicked → ask it immediately.
    if st.session_state.get("_pending_ask"):
        q = st.session_state._pending_ask
        st.session_state._pending_ask = None
        _handle_ask(q)

    rid = st.session_state.active_request_id
    if rid:
        _conversation(rid)
    else:
        _render_landing()
        # Reset the chat input submit button style when on the landing page
        st.markdown(
            """
            <style>
            [data-testid="stChatInput"] button[data-testid="stChatInputSubmitButton"] svg {
                display: block !important;
            }
            [data-testid="stChatInput"] button[data-testid="stChatInputSubmitButton"]::after {
                display: none !important;
            }
            </style>
            """,
            unsafe_allow_html=True,
        )

    # Docked chat input (bottom) — the single-line text bar of the chat app.
    typed = st.chat_input("Ask a business question…  e.g. which stores are trending up right now?")
    if typed and typed.strip():
        _handle_ask(typed.strip())


# ── Landing: greeting + suggestion chips only ──────────────────────────────────
def _render_landing():
    name = (st.session_state.user_name or "there").split()[0]
    suggestions = get_suggestions("business", st.session_state.token)
    chip_data = suggestions["suggestions"] if suggestions else _FALLBACK_CHIPS
    chips = "".join(
        f'<a class="sugg-card" href="?persona=business&q={quote(c["question"])}" target="_self">'
        f'<span class="sugg-ico">{c.get("icon", "•")}</span><span class="sugg-txt">{c["label"]}</span></a>'
        for c in chip_data
    )
    st.markdown(
        '<div class="chat-landing">'
        '<div class="chat-logo">📊</div>'
        f'<div class="chat-greeting">Hi {name} 👋 What would you like to know?</div>'
        '<div class="chat-sub">Ask anything about your stores, sales, inventory or customers in plain English — '
        'your data engineer never needs to get involved unless you want them to.</div>'
        '<div class="chips-label" style="text-align:center;margin-top:26px">💡 TRY ASKING</div>'
        f'<div class="chat-suggests">{chips}</div>'
        '</div>',
        unsafe_allow_html=True,
    )


# ── Conversation: a fragment that re-renders only itself while building ─────────
@st.fragment(run_every=2)
def _conversation(rid):
    data = get_pipeline_status(rid, st.session_state.token)
    if data is None:
        st.warning("Connection to backend lost — showing last known state")
        return
    _convo_body(rid, data)


def _convo_body(rid, data):
    status = data["status"]
    question = data.get("question", "")

    st.markdown('<div class="chat-thread">', unsafe_allow_html=True)
    if question:
        st.markdown(
            f'<div class="chat-row user"><div class="bubble-user">{question}</div>'
            f'<div class="avatar-msg" style="background:{st.session_state.avatar_color}">'
            f'{st.session_state.avatar_initial}</div></div>',
            unsafe_allow_html=True,
        )
    st.markdown('<div class="chat-row asst"><div class="avatar-msg ai">🧠</div>'
                '<div class="bubble-asst">', unsafe_allow_html=True)

    # Notify pill only while it's in the engineer's approval stage (not once live).
    notify_href = f"?persona=business&open={rid}&notify=1" if status == "pending_review" else None
    render_journey(data["journey_steps"], notify_href=notify_href,
                   notify_on=st.session_state.get(f"notified_{rid}", False))

    if status in ("generating", "validating"):
        retries = data.get("agent_status", {}).get("self_correction_attempt", 0)
        msg = (f"🤖 The fine-tuned model is auto-correcting a small issue (attempt {retries}/3)…"
               if retries else "🤖 The fine-tuned model is building your pipeline… this takes a few seconds.")
        _banner(msg)

    elif status == "pending_review":
        _banner("🕐 <strong>Arjun is reviewing your request</strong> — the live answer appears the moment he approves.",
                amber=True)
        _pending_card()

    elif status in ("approved", "deploying"):
        _banner("⚡ <strong>Engineer approved!</strong> Connecting your data feed — deploying to Flink &amp; "
                "verifying the Snowflake sink…")

    elif status == "live":
        answer = get_pipeline_answer(rid, st.session_state.token)
        if answer:
            render_answer_card(answer)

    elif status == "rejected":
        msg = data.get("rejection_reason_for_user", "Please refine your question and try again.")
        st.markdown(
            f'<div style="background:#FEE2E2;border:1px solid #FECACA;border-radius:13px;'
            f'padding:13px 18px;font-size:13px;color:#991B1B">'
            f'ℹ️ <strong>Your request needs adjustment:</strong> {msg}</div>',
            unsafe_allow_html=True,
        )

    st.markdown('</div></div></div>', unsafe_allow_html=True)  # bubble-asst, chat-row, chat-thread


def _banner(html, amber=False):
    cls = "proc-banner amber" if amber else "proc-banner"
    st.markdown(f'<div class="{cls}"><div class="proc-spinner"></div><div>{html}</div></div>',
                unsafe_allow_html=True)


def _pending_card():
    st.markdown(
        '<div class="answer-card"><div class="answer-header"><div>'
        '<div class="answer-title">Your answer is being prepared</div>'
        '<div class="answer-sub">A data pipeline was generated from your question</div></div>'
        '<div class="answer-meta"><span class="badge badge-amber">⏳ Engineer reviewing</span></div></div>'
        '<div class="review-state"><div class="big">🔄</div>'
        '<div class="ttl">Pipeline in review</div>'
        '<div class="desc">Your question became a live data pipeline. Arjun is reviewing the AI-generated '
        'configuration — the live answer will appear here automatically the moment he approves.</div>'
        '<div class="pill">You\'ll get a Slack notification when it\'s live ✓</div></div></div>',
        unsafe_allow_html=True,
    )


def _handle_ask(question: str):
    with st.spinner("Sending your question to the AI model…"):
        resp = ask_question(question, st.session_state.user_id, st.session_state.token)
    if resp:
        st.session_state.active_request_id = resp["request_id"]
        st.session_state._last_open = resp["request_id"]
        st.rerun()
    else:
        st.error("Couldn't reach the backend. Is it running on port 8000?")
