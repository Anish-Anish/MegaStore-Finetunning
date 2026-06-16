"""
MegaStore Pulse — Fine-tuned model server.

Run this ON THE GPU WORKSPACE (the box where `python model.py` already works).
It loads the model ONCE at startup and serves a /generate endpoint, so the main
backend can call the real model over HTTP without any unsloth/threading issues.

Setup (on the workspace):
    # put this file next to model.py, i.e. in /workspace/shared/code space/Megastorepipeline/
    pip install fastapi uvicorn          # (unsloth/torch are already installed there)
    uvicorn model_server:app --host 0.0.0.0 --port 9000

Then point the backend at it:
    MODEL_SERVER_URL=http://localhost:9000   (same box)
    # or http://<workspace-public-host>:9000  (if the backend runs elsewhere)

Test it directly:
    curl -s -X POST http://localhost:9000/generate \
      -H 'Content-Type: application/json' \
      -d '{"query":"Alert me when inventory falls below 5 units in any warehouse"}'
"""
import os
import sys
from fastapi import FastAPI
from pydantic import BaseModel

# Folder that contains Notebooks/ (defaults to this file's directory, like model.py).
MODEL_DIR = os.getenv("MEGASTORE_MODEL_DIR", os.path.dirname(os.path.abspath(__file__)))
NOTEBOOKS_PATH = os.path.join(MODEL_DIR, "Notebooks")
MODEL_PATH = os.path.join(NOTEBOOKS_PATH, "final_model")

if NOTEBOOKS_PATH not in sys.path:
    sys.path.insert(0, NOTEBOOKS_PATH)

print(f"[model_server] loading model from {MODEL_PATH} …")
from unsloth import FastLanguageModel          # noqa: E402
from safe_generate import safe_generate        # noqa: E402

model, tokenizer = FastLanguageModel.from_pretrained(MODEL_PATH, load_in_4bit=True)
print("=" * 70)
print("[model_server] ✅ MODEL LOADED — server is ACTIVE and waiting for queries.")
print("[model_server]    POST your question to  http://localhost:9000/generate")
print("[model_server]    (it generates per-request; keep this process running)")
print("=" * 70)

app = FastAPI(title="MegaStore Pulse — FT Model Server")


class GenRequest(BaseModel):
    query: str
    max_new_tokens: int = 300


@app.get("/health")
def health():
    return {"ok": True, "model_path": MODEL_PATH}


@app.post("/generate")
def generate(req: GenRequest):
    print(f"\n[model_server] ► query received: {req.query!r}")
    print("[model_server]   calling the model…")
    prompt = f"### Instruction:\n{req.query}\n\n### Response:\n"
    yaml_output = safe_generate(model, tokenizer, prompt, max_new_tokens=req.max_new_tokens)
    print(f"[model_server] ◄ generated {len(yaml_output)} chars of YAML for this query.")
    return {"yaml": yaml_output}


if __name__ == "__main__":
    # Run with the SAME interpreter that runs model.py (so it uses the ROCm torch):
    #     python model_server.py
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "9000")))
