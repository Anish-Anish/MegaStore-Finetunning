import streamlit as st
import json
from streamlit_ace import st_ace
from api.client import approve_pipeline, reject_pipeline, edit_pipeline
from components.answer_card import trust_badge_html


def render_review_card(item: dict, yaml_data: dict):
    cid = item["request_id"]
    initial = item["requested_by"][0].upper()
    conf = int(item["model_confidence"] * 100)
    trust = item.get("trust_10") or yaml_data.get("trust_10")
    editing = st.session_state.get("editing_card") == cid

    with st.container(key=f"rc_{cid}"):
        # ── Header ────────────────────────────────────────────────────────────
        st.markdown(
            '<div class="rc-header"><div>'
            f'<div class="rc-title">{item["pipeline_name"]}</div>'
            '<div class="rc-meta">'
            f'<span class="rc-requester"><span class="avatar {item.get("avatar_cls", "av-p")}">{initial}</span> '
            f'{item["requested_by"]} ({item.get("requested_by_role", "")}) · {item["minutes_ago"]} mins ago</span>'
            '<span class="badge badge-green">✓ Schema valid</span>'
            '<span class="badge badge-green">✓ Syntax valid</span>'
            f'<span class="badge badge-brand">AI confidence: {conf}%</span>'
            '</div></div>'
            f'<div style="display:flex;flex-direction:column;align-items:flex-end;gap:6px">'
            f'{trust_badge_html(trust)}<span class="badge badge-amber">Pending</span></div></div>'
            f'<div class="business-question">"{item["question"]}"</div>',
            unsafe_allow_html=True,
        )

        # ── Readable YAML editor (inline-editable) ────────────────────────────
        head = ("✏️ EDITING — change the YAML and click Save"
                if editing else "📄 GENERATED PIPELINE · read-only — click Edit to modify")
        st.markdown(f'<div class="rc-yaml-wrap"><div class="rc-yaml-head">{head}</div></div>',
                    unsafe_allow_html=True)
        edited_yaml = st_ace(
            value=yaml_data.get("yaml_full", ""),
            language="yaml", theme="tomorrow_night_bright", keybinding="vscode",
            font_size=13, tab_size=2, wrap=True, show_gutter=True,
            readonly=not editing, auto_update=True, min_lines=10, max_lines=10, key=f"ace_{cid}",
        )

        # ── Validation (animated badges) ──────────────────────────────────────
        validation = "".join(f'<span class="badge badge-green">✓ {c}</span>' for c in yaml_data["validation"])
        st.markdown(f'<div class="validation-row">{validation}</div>', unsafe_allow_html=True)

        deploy_box = st.empty()

        # ── Action buttons (live inside the card) ─────────────────────────────
        if editing:
            s, c, _ = st.columns([1.6, 1, 4], vertical_alignment="center")
            with s:
                save_clicked = st.button("💾 Save & re-validate", key=f"save_{cid}",
                                         type="primary", use_container_width=True)
            with c:
                cancel_clicked = st.button("Cancel", key=f"cancel_{cid}", use_container_width=True)
            if save_clicked:
                res = edit_pipeline(cid, edited_yaml, st.session_state.user_id, st.session_state.token)
                if res and res.get("validation_passed"):
                    st.session_state.editing_card = None
                    st.toast("✓ Edited YAML re-validated — ready to deploy")
                    st.rerun()
                else:
                    st.error("Edited YAML failed validation — check and retry")
            if cancel_clicked:
                st.session_state.editing_card = None
                st.rerun()
        else:
            b1, b2, b3, _ = st.columns([2, 1.4, 1, 4], vertical_alignment="center")
            with b1:
                approve_clicked = st.button("✓ Approve & Auto-Deploy", key=f"approve_{cid}",
                                            use_container_width=True)
            with b2:
                edit_clicked = st.button("✏️ Edit pipeline", key=f"edit_{cid}", use_container_width=True)
            with b3:
                reject_clicked = st.button("Reject", key=f"reject_{cid}", use_container_width=True)

            if edit_clicked:
                st.session_state.editing_card = cid
                st.rerun()
            if reject_clicked:
                reject_pipeline(cid, st.session_state.user_id, "Needs more detail on the time window.",
                                st.session_state.token)
                st.toast("Rejection sent to requester via Slack")
                st.rerun()
            if approve_clicked:
                _stream_deploy(cid, deploy_box)


def _stream_deploy(cid: str, container):
    """Consume the SSE deploy stream and render the dark animated deploy log."""
    lines = []
    try:
        stream = approve_pipeline(cid, st.session_state.user_id, st.session_state.token)
        for event in stream.events():
            if not event.data:
                continue
            d = json.loads(event.data)
            status, label = d["status"], d["label"]
            detail, agent = d.get("detail", ""), d.get("agent", "")
            cls = "done" if status in ("done", "complete") else ("running" if status == "running" else "")
            icon = "✓" if status in ("done", "complete") else ("⠿" if status == "running" else "·")
            detail_html = f'<span class="dp-detail">{detail}</span>' if detail else ""
            agent_html = f'<span class="dp-agent">[{agent}]</span>' if agent else ""
            lines.append(f'<div class="dp-step {cls}">{icon} {label}{detail_html}{agent_html}</div>')
            container.markdown(f'<div class="deploy-progress">{"".join(lines)}</div>', unsafe_allow_html=True)
            if status == "complete":
                st.session_state.active_pipelines_count += 1
                st.toast("Pipeline approved successfully!", icon="✅")
                import time
                time.sleep(3)
                st.rerun()
    except Exception as e:
        st.error(f"Deployment error: {e}")
