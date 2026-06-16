import streamlit as st


def trust_badge_html(trust_10) -> str:
    if trust_10 is None:
        return ""
    cls = "trust-badge" if trust_10 >= 9 else ("trust-badge mid" if trust_10 >= 7.5 else "trust-badge low")
    return f'<span class="{cls}"><span class="t-star">★</span> Trust {trust_10}/10</span>'


def _kpi_row(kpis: list) -> str:
    cells = []
    for k in kpis:
        delta = k.get("delta")
        delta_html = f'<div class="kpi-delta {k.get("delta_cls", "flat")}">{delta}</div>' if delta else ""
        cells.append(
            f'<div class="kpi-cell"><div class="kpi-val {k.get("val_cls", "")}">{k["val"]}</div>'
            f'<div class="kpi-lbl">{k["label"]}</div>{delta_html}</div>'
        )
    return f'<div class="kpi-row">{"".join(cells)}</div>'


def _table(table: dict) -> str:
    head = "".join(f"<th>{c}</th>" for c in table["columns"])
    body = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in row) + "</tr>" for row in table["rows"])
    return ('<div class="detail-label">📋 DETAIL TABLE</div>'
            f'<table class="answer-table"><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>')


def _insight(ins: dict) -> str:
    tone = ins.get("tone", "brand")
    bg = "var(--red-soft)" if tone == "red" else "var(--brand-soft)"
    border = "#FECACA" if tone == "red" else "#C7D2FE"
    color = "var(--red)" if tone == "red" else "var(--brand)"
    return (
        f'<div class="insight-strip" style="background:{bg};border-top-color:{border}">'
        f'<div class="insight-icon">{ins.get("icon", "💡")}</div>'
        f'<div class="insight-text" style="color:{color}">{ins["html"]}</div></div>'
    )


def render_answer_card(answer: dict):
    """Render a business answer card: header + trust + KPIs + table + insight."""
    badges = "".join(f'<span class="badge {b["cls"]}">{b["html"]}</span>' for b in answer.get("badges", []))
    trust = trust_badge_html(answer.get("trust_10"))
    approved = answer.get("approved_by_name")
    approved_line = (f'<div class="answer-sub" style="margin-top:4px">✓ Reviewed &amp; approved by '
                     f'<strong>{approved}</strong> (Data Engineer) · live {answer.get("live_since","now")}</div>'
                     if approved else "")
    header = (
        f'<div class="answer-header"><div>'
        f'<div class="answer-title">{answer["title"]}</div>'
        f'<div class="answer-sub">{answer["subtitle"]}</div>{approved_line}</div>'
        f'<div class="answer-meta">{trust}{badges}</div></div>'
    )

    body = ""
    if answer.get("state"):
        s = answer["state"]
        body = (f'<div class="review-state"><div class="big">{s["icon"]}</div>'
                f'<div class="ttl">{s["title"]}</div><div class="desc">{s["desc"]}</div>'
                f'<div class="pill">{s["pill"]}</div></div>')
    else:
        if answer.get("kpis"):
            body += _kpi_row(answer["kpis"])
        if answer.get("table"):
            body += _table(answer["table"])
        if answer.get("insight"):
            body += _insight(answer["insight"])

    st.markdown(f'<div class="answer-card">{header}{body}</div>', unsafe_allow_html=True)
