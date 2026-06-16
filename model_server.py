# model_server.py
# This is your model.py — UNCHANGED loading code — kept running so it can answer
# many requests. The ONLY difference: the query is no longer hardcoded; it comes
# dynamically from the request the app sends. Run it where model.py works:
#     python model_server.py        (base env, next to model.py)

import sys
import os
from fastapi import FastAPI
from pydantic import BaseModel
import uvicorn

# ── (copied from model.py — loads the model ONCE at startup) ──────────────────
notebooks_path = os.path.join(os.path.dirname(__file__), "Notebooks")
sys.path.insert(0, notebooks_path)

from unsloth import FastLanguageModel
from safe_generate import safe_generate   # now found inside Notebooks/

model_path = os.path.join(notebooks_path, "final_model")
model, tokenizer = FastLanguageModel.from_pretrained(model_path, load_in_4bit=True)

print("=" * 64)
print("✅ MODEL LOADED — ready. POST a {\"query\": \"...\"} to /generate")
print("=" * 64)
# ──────────────────────────────────────────────────────────────────────────────

app = FastAPI(title="MegaStore Pulse — FT Model")


class GenRequest(BaseModel):
    query: str
    max_new_tokens: int = 300


@app.get("/health")
def health():
    return {"ok": True}


@app.post("/generate")
def generate(req: GenRequest):
    # ── same 3 lines as model.py, but `query` = the USER's question (dynamic) ──
    query = req.query
    prompt = f"### Instruction:\n{query}\n\n### Response:\n"
    yaml_output = safe_generate(model, tokenizer, prompt, max_new_tokens=req.max_new_tokens)
    print("📄 Generated YAML for:", query)
    return {"yaml": yaml_output}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "9000")))
