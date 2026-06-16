"""Static HTML snapshots of the v2 views (charts, journey, sidebar) — no servers needed.
Animations are frozen to their end-state so the rasterised image shows final charts."""
import os
from backend_mock import build_answer, JOURNEY_LABELS, yaml_for
from components.answer_card import _kpi_row, _table, _insight, trust_badge_html

HERE = os.path.dirname(__file__)
CSS = open(os.path.join(HERE, "assets", "style.css")).read()
FREEZE = ("*{animation:none !important}"
          ".answer-card,.review-card,.dep-card,.m-card,.chart-card,.conv-item,.chip,.badge,"
          ".journey-trail,.j-step .j-icon,.c-dot,.c-area-fill,.mcp-tool,.mcp-chip,.live-dot,.notify-pill,.trust-badge,"
          ".chat-landing,.chat-logo,.sugg-card,.chat-row,.bubble-user,.stage-item,.stage-num,"
          ".results-area,.eng-panel{opacity:1 !important;transform:none !important}"
          ".c-line{stroke-dashoffset:0 !important}")
SHIM = (".snap-main{display:grid;grid-template-columns:312px 1fr} body{margin:0}"
        "section{} .snap-side{background:#fff;border-right:1px solid var(--border);padding:14px;min-height:100vh}"
        ".snap-right{min-height:100vh}")


def topbar(persona):
    biz = persona == "business"
    return ('<div class="topbar"><div class="topbar-brand">MegaStore<span> Pulse</span></div>'
            '<div class="topbar-mid"></div><div class="topbar-right">'
            '<span class="topbar-live"><span class="pulse-dot"></span> Flink live · 3 pipelines active</span>'
            '<div class="persona-switcher">'
            f'<a class="ps-btn {"active" if biz else ""}" href="#">📊 Business</a>'
            f'<a class="ps-btn {"" if biz else "active"}" href="#">⚙️ Data Engineer</a></div>'
            f'<div class="topbar-avatar" style="background:{"#7C3AED" if biz else "#0891B2"}">{"P" if biz else "A"}</div>'
            f'<span class="topbar-user">{"Priya (CEO)" if biz else "Arjun (Data Eng)"}</span></div></div>')


STAGES = [("✍️", "Ask in plain English", "You type a business question"),
          ("🤖", "AI builds the pipeline", "Fine-tuned model generates it"),
          ("👤", "Engineer reviews", "SME approves or edits the config"),
          ("⚙️", "Auto-deploy to Flink", "MCP agents ship it live"),
          ("📊", "Live answer", "Results stream straight back to you")]


def sidebar():
    items = "".join(
        f'<div class="stage-item"><div class="stage-num">{ico}</div><div class="stage-text">'
        f'<div class="stage-title">{title}</div><div class="stage-desc">{desc}</div></div></div>'
        for ico, title, desc in STAGES)
    return ('<div class="snap-side"><div class="sidebar-brand">MegaStore<span> Pulse</span></div>'
            '<div style="background:linear-gradient(135deg,#4338CA,#818CF8);color:#fff;border-radius:12px;'
            'padding:10px;text-align:center;font-weight:600;font-size:13px;margin-bottom:6px">＋  New question</div>'
            '<div class="stage-head">⛓ HOW IT WORKS · 5 STAGES</div>'
            f'<div class="stage-list">{items}</div></div>')


def journey():
    parts = []
    for i, lbl in enumerate(JOURNEY_LABELS):
        parts.append(f'<div class="j-step done"><div class="j-icon">✓</div><div class="j-label">{lbl}</div></div>')
        if i < len(JOURNEY_LABELS) - 1:
            parts.append('<div class="j-connector done"></div>')
    return ('<div class="journey-trail"><div class="journey-head-row">'
            '<div class="journey-head">⚡ HOW YOUR ANSWER IS BEING BUILT</div>'
            '<a class="notify-pill" href="#">🔔 Notify me on Slack</a></div>'
            f'<div class="journey-steps">{"".join(parts)}</div></div>')


def mcp_topbar():
    tools = [("DB Schema MCP", "12ms", False), ("GitHub MCP", "89ms", False), ("Flink REST MCP", "34ms", False),
             ("Slack MCP", "156ms", False), ("Chart MCP", "21ms", False), ("Snowflake MCP", "connecting", True)]
    chips = '<span class="mcp-title">🔌 MCP TOOLS</span>'
    for n, l, amb in tools:
        dot = '<span class="live-dot amber"></span>' if amb else '<span class="live-dot"></span>'
        chips += f'<span class="mcp-chip">{dot}{n} <span class="lat">· {l}</span></span>'
    return f'<div class="mcp-topbar">{chips}</div>'


def answer_card(ans):
    badges = "".join(f'<span class="badge {b["cls"]}">{b["html"]}</span>' for b in ans.get("badges", []))
    header = (f'<div class="answer-header"><div><div class="answer-title">{ans["title"]}</div>'
              f'<div class="answer-sub">{ans["subtitle"]}</div>'
              f'<div class="answer-sub" style="margin-top:4px">✓ Reviewed &amp; approved by <strong>Arjun</strong> '
              f'(Data Engineer) · live now</div></div>'
              f'<div class="answer-meta">{trust_badge_html(ans["trust_10"])}{badges}</div></div>')
    body = _kpi_row(ans["kpis"]) + _table(ans["table"]) + _insight(ans["insight"])
    return f'<div class="answer-card">{header}{body}</div>'


def ask_zone():
    chips = "".join(f'<a class="chip" href="#"><span class="chip-ico">{i}</span>{l}</a>' for i, l in
                    [("📊", "Sales by category"), ("↩️", "High return stores"), ("💎", "Platinum customer spend"),
                     ("🔍", "Quality alerts"), ("🛒", "Channel GMV")])
    return ('<div class="st-key-askzone" style="background:linear-gradient(180deg,#fff,#fcfcff);'
            'border:1px solid var(--border);border-radius:16px;padding:18px 20px 16px;margin:14px;'
            'box-shadow:0 6px 24px rgba(13,17,23,.05)">'
            '<div class="ask-label" style="color:var(--brand)">✨ ASK A BUSINESS QUESTION</div>'
            '<div style="display:flex;gap:10px"><textarea style="flex:1;border:1.5px solid var(--border);'
            'border-radius:13px;padding:13px 16px;background:var(--surface-2);font-size:14px;resize:none;height:52px;'
            'font-family:var(--sans)" placeholder="e.g. Show me which stores had the highest return rate…"></textarea>'
            '<button style="background:linear-gradient(135deg,#4338CA,#6366F1);color:#fff;border:none;'
            'border-radius:13px;font-weight:700;padding:0 22px">Ask  →</button></div>'
            '<div class="chips-label">💡 Try asking</div>'
            f'<div class="ask-chips">{chips}</div></div>')


def review_card(cid, kind, title, who, role, av, mins, conf, trust):
    yhtml, yfull, checks = yaml_for(kind)
    initial = who[0]
    validation = "".join(f'<span class="badge badge-green">✓ {c}</span>' for c in checks)
    yaml_lines = yfull.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return (
        '<div class="review-card">'
        '<div class="rc-header"><div>'
        f'<div class="rc-title">{title}</div><div class="rc-meta">'
        f'<span class="rc-requester"><span class="avatar {av}">{initial}</span> {who} ({role}) · {mins} mins ago</span>'
        '<span class="badge badge-green">✓ Schema valid</span><span class="badge badge-green">✓ Syntax valid</span>'
        f'<span class="badge badge-brand">AI confidence: {conf}%</span></div></div>'
        f'<div style="display:flex;flex-direction:column;align-items:flex-end;gap:6px">{trust_badge_html(trust)}'
        '<span class="badge badge-amber">Pending</span></div></div>'
        f'<div class="business-question">"{title}"</div>'
        '<div class="rc-yaml-wrap"><div class="rc-yaml-head">📄 GENERATED PIPELINE · read-only — click Edit to modify</div></div>'
        f'<pre style="background:#1d1f21;color:#c5c8c6;padding:14px 18px;font-family:var(--mono);font-size:12px;'
        f'line-height:1.7;margin:0;overflow-x:auto">{yaml_lines}</pre>'
        f'<div class="validation-row">{validation}</div>'
        '<div style="padding:12px 18px;display:flex;gap:8px">'
        '<button style="background:#16A34A;color:#fff;border:none;border-radius:10px;padding:8px 18px;font-size:12px;font-weight:600">✓ Approve &amp; Auto-Deploy</button>'
        '<button style="background:#fff;border:1px solid var(--border);border-radius:10px;padding:8px 14px;font-size:12px">✏️ Edit pipeline</button>'
        '<button style="background:#fff;color:var(--red);border:1px solid #FECACA;border-radius:10px;padding:8px 14px;font-size:12px">Reject</button>'
        '</div></div>')


def mcp_strip():
    tools = [("DB Schema MCP", "12ms"), ("GitHub MCP", "89ms"), ("Flink REST MCP", "34ms"),
             ("Slack MCP", "156ms"), ("Chart MCP", "21ms"), ("Snowflake MCP", "connecting")]
    chips = "".join(f'<div class="mcp-tool">🟢 <strong>{n}</strong> <span style="color:var(--ink-muted)">· {l}</span></div>'
                    for n, l in tools)
    return ('<div class="eng-panel"><div class="section-label">🔌 MCP TOOLS USED BY AGENTS</div>'
            f'<div class="mcp-strip">{chips}</div></div>')


def page(title, persona, right):
    return (f'<!DOCTYPE html><html><head><meta charset="utf-8"><title>{title}</title>'
            f'<style>{CSS}\n{SHIM}\n{FREEZE}</style></head><body>'
            f'{topbar(persona)}<div class="snap-main">{sidebar()}<div class="snap-right">{right}</div></div></body></html>')


def chat_input_bar():
    return ('<div style="position:fixed;left:312px;right:0;bottom:0;padding:14px 14px 20px;'
            'background:linear-gradient(180deg,rgba(246,247,251,0),#F6F7FB 40%)">'
            '<div style="border:1.5px solid var(--border);border-radius:26px;'
            'background:#fff;box-shadow:0 4px 18px rgba(13,17,23,.07);padding:11px 18px;color:var(--ink-muted);'
            'font-size:14.5px;display:flex;align-items:center;justify-content:space-between">Ask a business question…  '
            'e.g. which stores are trending up right now?<span style="color:var(--brand)">➤</span></div></div>')


def landing():
    chips = "".join(f'<a class="sugg-card" href="#"><span class="sugg-ico">{i}</span>'
                    f'<span class="sugg-txt">{l}</span></a>' for i, l in
                    [("📊", "Sales by category"), ("↩️", "High return stores"), ("💎", "Platinum customer spend"),
                     ("🔍", "Quality alerts"), ("🛒", "Channel GMV")])
    return ('<div class="chat-landing"><div class="chat-logo">📊</div>'
            '<div class="chat-greeting">Hi Priya 👋 What would you like to know?</div>'
            '<div class="chat-sub">Ask anything about your stores, sales, inventory or customers in plain English — '
            'your data engineer never needs to get involved unless you want them to.</div>'
            '<div class="chips-label" style="text-align:center;margin-top:26px">💡 TRY ASKING</div>'
            f'<div class="chat-suggests">{chips}</div></div>') + chat_input_bar()


def conversation():
    ans = build_answer("sales_by_category", 42)
    ans["trust_10"] = 9.7
    bubble = ('<div class="chat-row user"><div class="bubble-user">Sales by category, exclude returns, '
              '10-min window by store &amp; region</div>'
              '<div class="avatar-msg" style="background:#7C3AED">P</div></div>')
    asst = ('<div class="chat-row asst"><div class="avatar-msg ai">🧠</div><div class="bubble-asst">'
            + journey() + answer_card(ans) + '</div></div>')
    return f'<div class="chat-thread">{bubble}{asst}</div>' + chat_input_bar()


def main():
    open(os.path.join(HERE, "preview_business.html"), "w").write(page("Business — landing", "business", landing()))
    open(os.path.join(HERE, "preview_chat.html"), "w").write(page("Business — chat", "business", conversation()))

    tabs = ('<div class="eng-tabs"><a class="etab active" href="#">Pipeline Review <span class="etab-badge">2</span></a>'
            '<a class="etab" href="#">Deployed</a><a class="etab" href="#">Live Monitor</a></div>')
    cards = ('<div class="eng-panel"><div class="section-label">📥 PENDING YOUR APPROVAL</div>'
             + review_card("conv_category", "sales_by_category", "category_regional_sales — 10 min tumbling window",
                           "Deepa", "Analyst", "av-d", 4, 97, 9.7)
             + review_card("conv_returns", "high_returns", "high_returns_alert — 30 min window + Slack sink",
                           "Priya", "CEO", "av-p", 8, 94, 9.4) + '</div>')
    eng = mcp_topbar() + tabs + cards
    open(os.path.join(HERE, "preview_engineer.html"), "w").write(page("Engineer", "engineer", eng))
    print("wrote preview_business.html, preview_engineer.html")


if __name__ == "__main__":
    main()
