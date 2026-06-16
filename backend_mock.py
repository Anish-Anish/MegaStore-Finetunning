"""
FastAPI mock backend for MegaStore Pulse.
Run: uvicorn backend_mock:app --port 8000 --reload

Everything is modelled as a *conversation* (one per business question), each with a
stable conversation_id, persisted to data/conversations.json so it survives restarts
(feels DB-backed). The full demo flow:

  ask -> FT model generates pipeline+answer (async) -> pending_review
       -> engineer approves -> deploying (Flink) -> live

"""
import asyncio
import json
import os
import random
import time
from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import StreamingResponse
from typing import Optional

app = FastAPI(title="MegaStore Pulse — Mock Backend")

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
DATA_FILE = os.path.join(DATA_DIR, "conversations.json")
os.makedirs(DATA_DIR, exist_ok=True)

# ════════════════════════════════════════════════════════════════════════════
#  YAML (exact colored markup for the diff view + plain text for the editor)
# ════════════════════════════════════════════════════════════════════════════
YAML_CATEGORY = """<span class="yd-cm"># pipeline: category_regional_sales  (FT model · Mistral-7B+LoRA · 4.2s)</span>
<span class="yd-add">+ source:</span>
<span class="yd-add">+   type: <span class="yd-str">postgres_cdc</span>   connection: <span class="yd-str">megastore_primary</span></span>
<span class="yd-add">+   tables: [orders, order_items, products, stores, categories]</span>
<span class="yd-ctx">  </span>
<span class="yd-add">+ transforms:</span>
<span class="yd-add">+   - filter: <span class="yd-str">"payment_type NOT IN ('gift_card','return')"</span></span>
<span class="yd-add">+   - join: <span class="yd-str">stores ON orders.store_id = stores.store_id</span></span>
<span class="yd-add">+   - join: <span class="yd-str">products ON order_items.product_id = products.product_id</span></span>
<span class="yd-add">+   - join: <span class="yd-str">categories ON products.category_id = categories.category_id</span></span>
<span class="yd-add">+   - window: { type: <span class="yd-str">TUMBLING</span>, size: <span class="yd-val">10</span>, unit: <span class="yd-str">MINUTES</span> }</span>
<span class="yd-add">+   - group_by: <span class="yd-str">["store_id","region","category_name"]</span></span>
<span class="yd-add">+   - aggregate: { total_sales: SUM(amount), tx_count: COUNT(*) }</span>
<span class="yd-ctx">  </span>
<span class="yd-add">+ sink: { type: <span class="yd-str">snowflake</span>, table: <span class="yd-str">"category_regional_sales"</span>, mode: <span class="yd-str">upsert</span> }</span>"""

YAML_FULL_CATEGORY = """pipeline:
  name: category_regional_sales
  parallelism: 4
source:
  type: postgres_cdc
  connection: megastore_primary
  tables: [orders, order_items, products, stores, categories]
transforms:
  - filter: "payment_type NOT IN ('gift_card','return')"
  - join: stores ON orders.store_id = stores.store_id
  - join: products ON order_items.product_id = products.product_id
  - join: categories ON products.category_id = categories.category_id
  - window:
      type: TUMBLING
      size: 10
      unit: MINUTES
  - group_by: ["store_id", "region", "category_name"]
  - aggregate:
      total_sales: SUM(amount)
      tx_count: COUNT(*)
sink:
  type: snowflake
  table: category_regional_sales
  mode: upsert"""

YAML_RETURNS = """<span class="yd-cm"># pipeline: high_returns_alert  (FT model · Mistral-7B+LoRA · 3.8s)</span>
<span class="yd-add">+ source: { type: <span class="yd-str">postgres_cdc</span>, tables: [returns, orders, stores] }</span>
<span class="yd-add">+ transforms:</span>
<span class="yd-add">+   - filter: <span class="yd-str">"return_status = 'REQUESTED'"</span></span>
<span class="yd-add">+   - join: <span class="yd-str">orders ON returns.order_id = orders.order_id</span></span>
<span class="yd-add">+   - join: <span class="yd-str">stores ON orders.store_id = stores.store_id</span></span>
<span class="yd-add">+   - window: { type: <span class="yd-str">TUMBLING</span>, size: <span class="yd-val">30</span>, unit: <span class="yd-str">MINUTES</span> }</span>
<span class="yd-add">+   - group_by: <span class="yd-str">["store_id","store_name","region"]</span></span>
<span class="yd-add">+   - aggregate: { return_count: COUNT(*) }</span>
<span class="yd-add">+   - filter_post: <span class="yd-str">"return_count > 20"</span></span>
<span class="yd-add">+ sink: { type: <span class="yd-str">slack</span>, channel: <span class="yd-str">"#ops-alerts"</span>, webhook: <span class="yd-str">"${env.SLACK_WEBHOOK_OPS}"</span> }</span>"""

YAML_FULL_RETURNS = """pipeline:
  name: high_returns_alert_30min
  parallelism: 4
source:
  type: postgres_cdc
  tables: [returns, orders, stores]
transforms:
  - filter: "return_status = 'REQUESTED'"
  - join: orders ON returns.order_id = orders.order_id
  - join: stores ON orders.store_id = stores.store_id
  - window:
      type: TUMBLING
      size: 30
      unit: MINUTES
  - group_by: ["store_id", "store_name", "region"]
  - aggregate:
      return_count: COUNT(*)
  - filter_post: "return_count > 20"
sink:
  type: slack
  channel: "#ops-alerts"
  webhook: "${env.SLACK_WEBHOOK_OPS}" """

YAML_BY_KIND = {
    "sales_by_category": (YAML_CATEGORY, YAML_FULL_CATEGORY,
                          ["All 5 tables exist in schema", "Join keys validated", "No circular joins",
                           "Window syntax correct", "Sink table writable"]),
    "high_returns": (YAML_RETURNS, YAML_FULL_RETURNS,
                     ["All 3 tables exist", "Join keys valid", "Slack env var set", "Filter threshold sensible"]),
}


def yaml_for(kind):
    return YAML_BY_KIND.get(kind, YAML_BY_KIND["sales_by_category"])


# Point this at the folder containing model.py + Notebooks/ (override with MEGASTORE_MODEL_DIR).
MODEL_DIR = os.getenv("MEGASTORE_MODEL_DIR", "/workspace/shared/code space/Megastorepipeline")
MODEL_ENABLED = os.path.isdir(MODEL_DIR)   # real FT model only runs where the folder exists (the GPU workspace)
real_model = None
real_tokenizer = None
real_safe_generate = None

def load_real_model():
    global real_model, real_tokenizer, real_safe_generate
    if real_model is not None:
        return True
    if not os.path.exists(MODEL_DIR):
        return False
    try:
        import sys
        notebooks_path = os.path.join(MODEL_DIR, "Notebooks")
        if notebooks_path not in sys.path:
            sys.path.insert(0, notebooks_path)
        from unsloth import FastLanguageModel
        from safe_generate import safe_generate
        real_safe_generate = safe_generate
        model_path = os.path.join(notebooks_path, "final_model")
        real_model, real_tokenizer = FastLanguageModel.from_pretrained(model_path, load_in_4bit=True)
        return True
    except Exception as e:
        print(f"Error loading real model: {e}")
        return False


def _generate_real_yaml(question: str):
    if not load_real_model():
        return None
    try:
        prompt = f"### Instruction:\n{question}\n\n### Response:\n"
        yaml_output = real_safe_generate(real_model, real_tokenizer, prompt, max_new_tokens=300)
        return yaml_output
    except Exception as e:
        print(f"Error running model: {e}")
        return None


def _format_yaml_html(yaml_text: str) -> str:
    lines = []
    for line in yaml_text.splitlines():
        escaped = line.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        if escaped.strip().startswith("#"):
            lines.append(f'<span class="yd-cm">{escaped}</span>')
        else:
            lines.append(f'<span class="yd-add">{escaped}</span>')
    return "\n".join(lines)


def _extract_pipeline_name(yaml_text: str) -> str:
    """Pull the pipeline name out of the generated YAML (the line under 'pipeline:')."""
    try:
        for line in yaml_text.splitlines():
            s = line.strip()
            if s.startswith("name:"):
                return s.split("name:", 1)[1].strip().strip('"\'') + " — FT-generated pipeline"
    except Exception:
        pass
    return "ai_generated_pipeline — FT model"


@app.on_event("startup")
async def _startup_preload():
    if MODEL_ENABLED:
        print(f"[FT model] ENABLED — preloading from: {MODEL_DIR}")
        asyncio.create_task(asyncio.to_thread(load_real_model))
    else:
        print(f"[FT model] DISABLED — using mock YAML. Set MEGASTORE_MODEL_DIR to a folder "
              f"with model.py + Notebooks/ (and run on the GPU workspace) to use the real model.")


# ════════════════════════════════════════════════════════════════════════════
#  ANSWER builders (kpis + table + insight).
# ════════════════════════════════════════════════════════════════════════════
def _badges_live():
    return [{"cls": "badge-green", "html": '<span class="pulse-dot" style="width:5px;height:5px"></span> Live'}]


def answer_sales_by_category():
    return {
        "title": "Sales by Category · by Region",
        "subtitle": "10-minute rolling window · updated 23 seconds ago · excluding returns & gift cards",
        "badges": _badges_live(),
        "kpis": [
            {"val": "₹3.87L", "label": "Total sales (10 min)", "delta": "↑ +12% vs last window", "delta_cls": "up"},
            {"val": "287", "label": "Transactions", "delta": "↑ +8 vs last window", "delta_cls": "up"},
            {"val": "₹1,347", "label": "Avg order value", "delta": "↑ ₹230 improvement", "delta_cls": "up"},
            {"val": "6", "label": "Active stores", "delta": "across 4 regions", "delta_cls": "flat"},
        ],
        "table": {
            "columns": ["#", "Category", "Region", "Sales (10 min)", "Txns", "Trend"],
            "rows": [
                ['<span class="rank">1</span>', "Electronics", "SOUTH", "₹1,24,500", "42", '<span class="trend-up">↑ 18%</span>'],
                ['<span class="rank">2</span>', "Apparel", "WEST", "₹89,200", "67", '<span class="trend-up">↑ 9%</span>'],
                ['<span class="rank">3</span>', "Mobile Phones", "NORTH", "₹76,800", "31", '<span class="trend-up">↑ 5%</span>'],
                ['<span class="rank">4</span>', "Groceries", "EAST", "₹54,300", "119", '<span class="trend-down">↓ 3%</span>'],
                ['<span class="rank">5</span>', "Home &amp; Furniture", "CENTRAL", "₹41,900", "28", '<span class="trend-up">↑ 2%</span>'],
            ],
        },
        "insight": {"icon": "💡", "tone": "brand",
                    "html": "<strong>AI insight:</strong> Electronics in SOUTH region is outperforming its 7-day "
                            "average by 18%. Store #042 Chennai is driving 34% of this. Consider checking inventory."},
    }


def answer_high_returns_live():
    return {
        "title": "High Returns Alert — by Store",
        "subtitle": "30-minute window · threshold: 20 returns per store · live now",
        "badges": [{"cls": "badge-red", "html": "⚠ 1 store breaching"}] + _badges_live(),
        "kpis": [
            {"val": "1", "label": "Stores over threshold", "delta": "↑ +1 vs last window", "delta_cls": "down"},
            {"val": "63", "label": "Total returns (30 min)", "delta": "↑ +14", "delta_cls": "down"},
            {"val": "21", "label": "Peak store returns", "delta": "Chennai #042", "delta_cls": "flat"},
            {"val": "₹2.1L", "label": "Refund value", "delta": "↑ +9%", "delta_cls": "down"},
        ],
        "table": {
            "columns": ["#", "Store", "Region", "Returns (30 min)", "Threshold", "Status"],
            "rows": [
                ['<span class="rank">1</span>', "Chennai #042", "SOUTH", '<span style="color:var(--red);font-weight:600">21</span>', "20", '<span class="badge badge-red">🚨 Breached</span>'],
                ['<span class="rank">2</span>', "Mumbai #007", "WEST", "18", "20", '<span class="badge badge-amber">Watch</span>'],
                ['<span class="rank">3</span>', "Delhi #115", "NORTH", "12", "20", '<span style="color:var(--green);font-size:11px">Normal</span>'],
                ['<span class="rank">4</span>', "Hyderabad #033", "SOUTH", "7", "20", '<span style="color:var(--green);font-size:11px">Normal</span>'],
            ],
        },
        "insight": {"icon": "🔴", "tone": "red",
                    "html": "<strong>Alert:</strong> Chennai #042 crossed the 20-return threshold (21 in 30 min). "
                            "A Slack alert was sent to #ops-alerts. Top reason: \"size/fit\"."},
    }


def answer_platinum():
    return {
        "title": "PLATINUM Customer Spend · by Region",
        "subtitle": "This hour · orders over ₹10,000 only · 22 mins ago",
        "badges": _badges_live(),
        "kpis": [
            {"val": "₹8.4L", "label": "Total spend this hour", "delta": "↑ +24% vs last hour", "delta_cls": "up"},
            {"val": "63", "label": "Platinum orders", "delta": "↑ +11 orders", "delta_cls": "up"},
            {"val": "₹13.3K", "label": "Avg order value", "delta": "↑ ₹1.1K higher", "delta_cls": "up"},
            {"val": "87%", "label": "Paid via UPI / Card", "delta": "13% BNPL", "delta_cls": "flat"},
        ],
        "table": {
            "columns": ["#", "Region", "Platinum Spend", "Customers", "Avg Value", "Trend"],
            "rows": [
                ['<span class="rank">1</span>', "SOUTH", "₹2,84,000", "21", "₹13,524", '<span class="trend-up">↑ 31%</span>'],
                ['<span class="rank">2</span>', "WEST", "₹2,10,500", "17", "₹12,382", '<span class="trend-up">↑ 19%</span>'],
                ['<span class="rank">3</span>', "NORTH", "₹1,93,200", "14", "₹13,800", '<span class="trend-up">↑ 22%</span>'],
                ['<span class="rank">4</span>', "EAST", "₹98,400", "8", "₹12,300", '<span class="trend-down">↓ 4%</span>'],
                ['<span class="rank">5</span>', "CENTRAL", "₹54,900", "3", "₹18,300", '<span class="trend-up">↑ 7%</span>'],
            ],
        },
        "insight": {"icon": "💡", "tone": "brand",
                    "html": "<strong>AI insight:</strong> SOUTH region PLATINUM spend is up 31% — driven by high "
                            "Electronics + Mobile AOV. Consider targeted push notifications in EAST."},
    }


def answer_top_returns():
    return {
        "title": "Top Products by Return Rate · Last Hour",
        "subtitle": "Only products with 5+ returns shown · 1 hr ago",
        "badges": [{"cls": "badge-red", "html": "⚠ 2 alerts"}] + _badges_live(),
        "kpis": [
            {"val": "38%", "label": "Worst return rate", "delta": "Samsung M34", "delta_cls": "down"},
            {"val": "46", "label": "Total returns (1 hr)", "delta": "↑ +12", "delta_cls": "down"},
            {"val": "2", "label": "SKUs flagged High", "delta": "needs action", "delta_cls": "down"},
            {"val": "₹1.4L", "label": "Refund exposure", "delta": "↑ +18%", "delta_cls": "down"},
        ],
        "table": {
            "columns": ["#", "Product", "Category", "Returns", "Orders", "Return Rate", "Signal"],
            "rows": [
                ['<span class="rank">1</span>', "Samsung Galaxy M34 (Blue)", "Mobile", "18", "47", '<span style="color:var(--red);font-weight:600">38%</span>', '<span class="badge badge-red">🚨 High</span>'],
                ['<span class="rank">2</span>', "Nike Air Max 270 (Size 9)", "Footwear", "12", "38", '<span style="color:var(--red);font-weight:600">31%</span>', '<span class="badge badge-red">🚨 High</span>'],
                ['<span class="rank">3</span>', "Philips Air Fryer 2.5L", "Home", "6", "31", '<span style="color:var(--amber);font-weight:600">19%</span>', '<span class="badge badge-amber">Watch</span>'],
                ['<span class="rank">4</span>', "Levi\'s 511 Slim Jeans (32)", "Apparel", "5", "44", '<span style="color:var(--amber)">11%</span>', '<span class="badge badge-amber">Watch</span>'],
                ['<span class="rank">5</span>', "Dell Wireless Mouse M215", "Electronics", "5", "72", "7%", '<span style="color:var(--green);font-size:11px">Normal</span>'],
            ],
        },
        "insight": {"icon": "🔴", "tone": "red",
                    "html": "<strong>Quality alert:</strong> Samsung Galaxy M34 (Blue) has a 38% return rate this hour "
                            "— 3× its daily average. Top reason: \"defective screen\". Recommend pausing this SKU."},
    }


ANSWER_BUILDERS = {
    "sales_by_category": answer_sales_by_category,
    "high_returns": answer_high_returns_live,
    "platinum": answer_platinum,
    "top_returns": answer_top_returns,
}


def build_answer(kind: str, seed: int, question: str = ""):
    q = question.lower()
    if "return" in q or "alert" in q:
        builder = answer_high_returns_live
    elif "platinum" in q or "spend" in q:
        builder = answer_platinum
    elif "product" in q or "quality" in q:
        builder = answer_top_returns
    else:
        builder = ANSWER_BUILDERS.get(kind, answer_sales_by_category)
    return builder()


# ════════════════════════════════════════════════════════════════════════════
#  JOURNEY (6 steps, "Pending with engineer" added in between)
# ════════════════════════════════════════════════════════════════════════════
JOURNEY_LABELS = ["Question received", "AI built pipeline", "Pending with engineer",
                  "Engineer approved", "Flink deployed", "Live answer below"]
_STATE_MAP = {
    "generating":     ["done", "active", "waiting", "waiting", "waiting", "waiting"],
    "validating":     ["done", "active", "waiting", "waiting", "waiting", "waiting"],
    "pending_review": ["done", "done", "active", "waiting", "waiting", "waiting"],
    "approved":       ["done", "done", "done", "done", "active", "waiting"],
    "deploying":      ["done", "done", "done", "done", "active", "waiting"],
    "live":           ["done", "done", "done", "done", "done", "done"],
    "rejected":       ["done", "done", "rejected", "waiting", "waiting", "waiting"],
}


def journey_for(status):
    states = _STATE_MAP.get(status, _STATE_MAP["generating"])
    return [{"label": JOURNEY_LABELS[i], "state": states[i]} for i in range(6)]


# ════════════════════════════════════════════════════════════════════════════
#  CONVERSATION STORE (persisted)
# ════════════════════════════════════════════════════════════════════════════
conversations = {}   # conversation_id -> dict
_counter = [100]


def _save():
    try:
        with open(DATA_FILE, "w") as f:
            json.dump({"conversations": conversations, "counter": _counter[0]}, f)
    except OSError:
        pass


def _now():
    return time.time()


def minutes_ago(conv):
    return int((_now() - conv.get("created_ts", _now())) / 60)


def new_conv(cid, question, kind, status, requester, requester_role, age_min=0, confidence=0.95):
    return {
        "conversation_id": cid, "question": question, "kind": kind, "status": status,
        "requester": requester, "requester_role": requester_role,
        "created_ts": _now() - age_min * 60, "seed": abs(hash(cid)) % 100000,
        "confidence": confidence, "generation_time_ms": random.randint(3500, 4800),
        "self_correction_attempts": 1 if kind == "high_returns" else 0,
        "approved_by": "Arjun" if status == "live" else None,
        "flink_job_id": f"flink-job-48{random.randint(10, 99)}" if status == "live" else None,
        "live_since": "just now" if status == "live" else None,
        "deploy_status": {}, "rejection_reason_for_user": None,
    }


def _seed_defaults():
    seeds = [
        ("conv_category", "Show sales broken down by product category, excluding returns and gift cards, "
         "using a 10-minute window, grouped by store and region", "sales_by_category", "pending_review",
         "Deepa", "Analyst", 4, 0.97),
        ("conv_returns", "Alert when any store has more than 20 returns in 30 minutes", "high_returns",
         "pending_review", "Priya", "CEO", 8, 0.94),
        ("conv_sales", "Sales by category, exclude returns, 10-min window by store & region",
         "sales_by_category", "live", "Priya", "CEO", 4, 0.97),
        ("conv_platinum", "Which PLATINUM customers spent over ₹10,000 this hour by region?", "platinum",
         "live", "Priya", "CEO", 22, 0.96),
        ("conv_topreturns", "Top 5 products by returns last hour — possible quality issue?", "top_returns",
         "live", "Priya", "CEO", 60, 0.95),
        ("conv_channel", "Hourly GMV by channel — ONLINE vs IN_STORE today", "sales_by_category",
         "live", "Priya", "CEO", 95, 0.93),
    ]
    for cid, q, kind, status, who, role, age, conf in seeds:
        conversations[cid] = new_conv(cid, q, kind, status, who, role, age, conf)


# Load persisted store or seed fresh
if os.path.exists(DATA_FILE):
    try:
        with open(DATA_FILE) as f:
            blob = json.load(f)
        conversations = blob.get("conversations", {})
        _counter[0] = blob.get("counter", 100)
    except (OSError, json.JSONDecodeError):
        conversations = {}
if not conversations:
    _seed_defaults()
    _save()


# ════════════════════════════════════════════════════════════════════════════
#  AUTH
# ════════════════════════════════════════════════════════════════════════════
@app.post("/auth/login")
def login(body: dict):
    if body.get("persona") == "business":
        return {"user_id": "priya_001", "name": "Priya", "role": "CEO", "persona": "business",
                "avatar_initial": "P", "avatar_color": "#7C3AED", "session_token": "tok_priya_123"}
    return {"user_id": "arjun_001", "name": "Arjun", "role": "Data Eng", "persona": "engineer",
            "avatar_initial": "A", "avatar_color": "#0891B2", "session_token": "tok_arjun_456"}


# ════════════════════════════════════════════════════════════════════════════
#  ASK  ->  FT MODEL GENERATION (async)
# ════════════════════════════════════════════════════════════════════════════
@app.post("/pipelines/ask")
async def ask(body: dict, authorization: Optional[str] = Header(None)):
    _counter[0] += 1
    cid = f"conv_{_counter[0]:04d}"
    conversations[cid] = new_conv(cid, body["question"], "sales_by_category", "generating",
                                  "Priya", "CEO", 0, 0.95)
    _save()
    asyncio.create_task(_call_ft_model(cid))
    return {"request_id": cid, "conversation_id": cid, "status": "generating",
            "journey_state": "generating", "estimated_wait_seconds": 6}


async def _call_ft_model(cid):
    """AI builds pipeline: hit the fine-tuned model with the user's question and get real YAML.

    Falls back to canned YAML only if the model folder/GPU isn't available (e.g. local dev),
    so the demo still works without the workspace.
    """
    c = conversations.get(cid)
    if not c:
        return

    # brief "validating" flash so the journey feels alive while the model runs
    await asyncio.sleep(0.5)
    c["status"] = "validating"
    _save()

    yaml_output = None
    if MODEL_ENABLED:
        try:
            import time as _t
            t0 = _t.time()
            yaml_output = await asyncio.wait_for(
                asyncio.to_thread(_generate_real_yaml, c["question"]),
                timeout=300.0,   # first call may include model load; inference itself is quick
            )
            c["generation_time_ms"] = int((_t.time() - t0) * 1000)
        except Exception as e:
            print(f"[FT model] generation error/timeout: {e}")
            yaml_output = None

    if yaml_output:
        # Real model output → flows to the data engineer for review exactly like the mock did.
        c["yaml_full"] = yaml_output
        c["yaml_html"] = _format_yaml_html(yaml_output)
        c["pipeline_name_real"] = _extract_pipeline_name(yaml_output)
        c["self_correction_attempts"] = 0
        c["model_name"] = "Qwen2.5-14B (MegaStore-LoRA)"
    else:
        # No real model here → short canned fallback (NOT a 2-minute wait).
        if not MODEL_ENABLED:
            await asyncio.sleep(2.5)
        c["self_correction_attempts"] = 1

    c["status"] = "pending_review"
    _save()


@app.get("/pipelines/{cid}/status")
def get_status(cid: str, authorization: Optional[str] = Header(None)):
    c = conversations.get(cid)
    if not c:
        raise HTTPException(404, "Not found")
    return {
        "request_id": cid, "conversation_id": cid, "status": c["status"],
        "question": c["question"],
        "journey_steps": journey_for(c["status"]),
        "agent_status": {"self_correction_attempt": c.get("self_correction_attempts", 0)},
        "deploy_status": c.get("deploy_status", {}),
        "trust_10": round(c["confidence"] * 10, 1),
        "approved_by": c.get("approved_by"), "flink_job_id": c.get("flink_job_id"),
        "live_since": c.get("live_since"),
        "rejection_reason_for_user": c.get("rejection_reason_for_user"),
    }


@app.get("/pipelines/suggestions")
def get_suggestions(persona: str = "business"):
    return {"suggestions": [
        {"label": "Sales by category", "icon": "📊",
         "question": "Sales by category, exclude returns, 10-min window by store and region"},
        {"label": "High return stores", "icon": "↩️",
         "question": "Which stores have more than 20 returns in the last 30 minutes?"},
        {"label": "Platinum customer spend", "icon": "💎",
         "question": "PLATINUM customer spend by region this hour"},
        {"label": "Quality alerts", "icon": "🔍",
         "question": "Top products with quality issues today"},
        {"label": "Channel GMV", "icon": "🛒",
         "question": "Hourly GMV by channel — ONLINE vs IN_STORE"},
    ]}


@app.get("/pipelines/history")
def get_history(persona: str = "business", user_id: str = "priya_001"):
    items = []
    for c in sorted(conversations.values(), key=lambda x: x.get("created_ts", 0), reverse=True):
        if c["requester"] != "Priya":   # Priya only sees her own conversations
            continue
        items.append({"request_id": c["conversation_id"], "conversation_id": c["conversation_id"],
                      "question": c["question"], "status": c["status"],
                      "minutes_ago": minutes_ago(c), "trust_10": round(c["confidence"] * 10, 1)})
    return {"requests": items}


@app.get("/pipelines/{cid}/answer")
def get_answer(cid: str, authorization: Optional[str] = Header(None)):
    c = conversations.get(cid)
    if not c:
        raise HTTPException(404, "Not found")
    ans = build_answer(c["kind"], c["seed"], c.get("question", ""))
    ans["request_id"] = cid
    ans["conversation_id"] = cid
    ans["trust_10"] = round(c["confidence"] * 10, 1)
    ans["approved_by_name"] = c.get("approved_by") or "Arjun"
    ans["live_since"] = c.get("live_since") or "just now"
    return ans


@app.post("/pipelines/{cid}/notify")
def set_notify(cid: str, body: dict, authorization: Optional[str] = Header(None)):
    return {"success": True, "message": "Notification set via Slack"}


@app.delete("/pipelines/{cid}")
def delete_pipeline(cid: str, authorization: Optional[str] = Header(None)):
    if cid in conversations:
        del conversations[cid]
        _save()
        return {"success": True}
    raise HTTPException(404, "Not found")


# ════════════════════════════════════════════════════════════════════════════
#  REVIEW (ENGINEER)
# ════════════════════════════════════════════════════════════════════════════
@app.get("/review/queue")
def review_queue(status: str = "pending_review", authorization: Optional[str] = Header(None)):
    items = []
    for c in sorted(conversations.values(), key=lambda x: x.get("created_ts", 0), reverse=True):
        if c["status"] != "pending_review":
            continue
        items.append({
            "request_id": c["conversation_id"], "conversation_id": c["conversation_id"],
            "pipeline_name": _pipeline_name(c), "question": c["question"],
            "requested_by": c["requester"], "requested_by_role": c["requester_role"],
            "avatar_cls": {"Deepa": "av-d", "Priya": "av-p"}.get(c["requester"], "av-p"),
            "minutes_ago": minutes_ago(c), "model_confidence": c["confidence"],
            "trust_10": round(c["confidence"] * 10, 1),
            "self_correction_attempts": c.get("self_correction_attempts", 0),
        })
    return {"total_pending": len(items), "queue": items}


def _pipeline_name(c):
    # If the real model generated YAML, use the name parsed from it.
    if c.get("pipeline_name_real"):
        return c["pipeline_name_real"]
    q = c.get("question", "").lower()
    if "inventory" in q:
        return "low_inventory_alert — Flink job + Slack sink"
    if "return" in q:
        return "high_returns_alert — 30 min window + Slack sink"
    if "platinum" in q:
        return "platinum_spend_analysis — 1 hr window + Snowflake sink"
    return {"sales_by_category": "category_regional_sales — 10 min tumbling window",
            "high_returns": "high_returns_alert — 30 min window + Slack sink"}.get(
        c["kind"], "ai_generated_pipeline — FT model")


@app.get("/review/{cid}/yaml")
def review_yaml(cid: str, authorization: Optional[str] = Header(None)):
    c = conversations.get(cid)
    if not c:
        raise HTTPException(404, "Not found")
    
    if "yaml_full" in c:
        yfull = c["yaml_full"]
        yhtml = c.get("yaml_html", yfull)
        checks = ["Syntax checks passed", "Schema validates against Flink spec", "Sink table connectivity verified"]
    else:
        yhtml, yfull, checks = yaml_for(c["kind"])
        
    return {
        "request_id": cid, "conversation_id": cid, "pipeline_name": _pipeline_name(c),
        "yaml_html": yhtml, "yaml_full": yfull, "validation": checks,
        "trust_10": round(c["confidence"] * 10, 1),
        "self_correction_attempts": c.get("self_correction_attempts", 0),
        "model_info": {"model": c.get("model_name", "Qwen2.5-14B"), "adapter": "MegaStore-LoRA-v2",
                       "confidence": c["confidence"], "generation_time_ms": c["generation_time_ms"]},
    }


@app.post("/review/{cid}/approve")
async def approve(cid: str, body: dict, authorization: Optional[str] = Header(None)):
    c = conversations.get(cid)
    if c:
        c["status"] = "approved"
        c["approved_by"] = "Arjun"
        c["deploy_status"] = {"github_commit": "waiting", "flink_submit": "waiting",
                              "snowflake_verify": "waiting", "slack_notify": "waiting"}
        _save()

    async def stream():
        steps = [
            (1, "Validating pipeline YAML…", "All checks passed", "validator_agent"),
            (2, "Committing to GitHub via MCP…", "commit: a3f9c12", "git_commit_agent"),
            (3, "Submitting to Flink REST via MCP…", "job_id: flink-job-4822 · RUNNING", "deploy_agent"),
            (4, "Verifying Snowflake sink via MCP…", "sink table created", "deploy_agent"),
            (5, "Notifying requester via Slack MCP…", "sent to #ops-alerts", "notify_agent"),
        ]
        if c:
            c["status"] = "deploying"
            _save()
        for n, label, detail, agent in steps:
            yield f"data: {json.dumps({'step': n, 'label': label, 'status': 'running', 'agent': agent})}\n\n"
            await asyncio.sleep(1.1)
            yield f"data: {json.dumps({'step': n, 'label': label, 'status': 'done', 'detail': detail, 'agent': agent})}\n\n"
            await asyncio.sleep(0.25)
            if c and n == 3:
                c["flink_job_id"] = "flink-job-4822"
        if c:
            c["status"] = "live"
            c["live_since"] = "just now"
            _save()
        final = {"step": 6, "label": "✓ Pipeline live — data is flowing!", "status": "complete",
                 "flink_job_id": "flink-job-4822", "pipeline_name": _pipeline_name(c) if c else "pipeline"}
        yield f"data: {json.dumps(final)}\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream")


@app.post("/review/{cid}/reject")
def reject(cid: str, body: dict, authorization: Optional[str] = Header(None)):
    c = conversations.get(cid)
    if c:
        c["status"] = "rejected"
        c["rejection_reason_for_user"] = ("Please refine your question — the engineer needs more detail "
                                          "on the time window.")
        _save()
    return {"success": True, "notified_via": "slack"}


@app.post("/review/{cid}/edit")
def edit(cid: str, body: dict, authorization: Optional[str] = Header(None)):
    c = conversations.get(cid)
    if c and "yaml_edited" in body:
        c["yaml_full"] = body["yaml_edited"]
        c["yaml_html"] = _format_yaml_html(body["yaml_edited"])
        _save()
    return {"success": True, "re_validated": True, "validation_passed": True}


@app.get("/review/deployed")
def get_deployed(authorization: Optional[str] = Header(None)):
    items = []
    for c in conversations.values():
        if c["status"] != "live":
            continue
        items.append({
            "conversation_id": c["conversation_id"],
            "pipeline_name": _pipeline_name(c).split(" — ")[0],
            "flink_job_id": c.get("flink_job_id") or "flink-job-4820", "status": "running",
            "events_per_second": random.randint(50, 360), "approved_by": c.get("approved_by") or "Arjun",
            "minutes_ago": minutes_ago(c), "requested_by": c["requester"],
            "requested_by_role": c["requester_role"], "sink_table": _pipeline_name(c).split(" — ")[0].upper(),
            "github_commit": "a3f9c12"})
    return {"deployed": items}


# ════════════════════════════════════════════════════════════════════════════
#  MONITOR / SYSTEM / MCP
# ════════════════════════════════════════════════════════════════════════════
@app.get("/monitor/metrics")
def monitor_metrics(authorization: Optional[str] = Header(None)):
    return {"total_sales_10min": random.randint(1100000, 1400000),
            "transaction_count": random.randint(1700, 2000),
            "events_per_second": random.randint(300, 400), "active_pipelines": _live_count(),
            "pipelines": [
                {"name": "category_regional_sales", "events_per_second": random.randint(300, 400)},
                {"name": "platinum_spend_by_region", "events_per_second": random.randint(70, 110)},
                {"name": "top_products_return_rate", "events_per_second": random.randint(40, 80)}]}


STORES = ["Chennai 042", "Mumbai 007", "Delhi 115", "Hyderabad 033", "Pune 088", "Bangalore 021"]
CATS = ["Electronics", "Apparel", "Footwear", "Home", "Mobile Phones", "Groceries"]


@app.get("/monitor/event-stream")
def event_stream(limit: int = 50, authorization: Optional[str] = Header(None)):
    now = time.strftime("%H:%M:%S")
    return {"events": [{"timestamp": now, "store": random.choice(STORES), "category": random.choice(CATS),
                        "amount": random.randint(500, 6500)} for _ in range(min(limit, 24))]}


def _live_count():
    return sum(1 for c in conversations.values() if c["status"] == "live")


@app.get("/system/status")
def system_status():
    return {"flink_connected": True, "kafka_connected": True, "active_pipelines": _live_count(),
            "events_per_second": random.randint(300, 400)}


@app.get("/mcp/status")
def mcp_status(authorization: Optional[str] = Header(None)):
    return {"tools": [
        {"name": "DB Schema MCP", "status": "connected", "latency_ms": 12, "description": "Fetches live table/column context"},
        {"name": "GitHub MCP", "status": "connected", "latency_ms": 89, "description": "Commits approved YAML files"},
        {"name": "Flink REST MCP", "status": "connected", "latency_ms": 34, "description": "Submits pipeline jobs"},
        {"name": "Slack MCP", "status": "connected", "latency_ms": 156, "description": "Notifies users on events"},
        {"name": "Snowflake MCP", "status": "connecting", "latency_ms": None, "description": "Verifies sink tables"},
    ]}
