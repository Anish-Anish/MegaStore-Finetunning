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

# Folder that contains training/ (defaults to this file's parent directory).
SERVER_DIR = os.path.dirname(os.path.abspath(__file__))
TRAINING_PATH = os.path.abspath(os.path.join(SERVER_DIR, "..", "training"))
MODEL_PATH = os.path.join(TRAINING_PATH, "final_model")

if TRAINING_PATH not in sys.path:
    sys.path.insert(0, TRAINING_PATH)

print(f"[model_server] loading model from {MODEL_PATH} …")
from unsloth import FastLanguageModel          # noqa: E402
from safe_generate import safe_generate        # noqa: E402

model, tokenizer = FastLanguageModel.from_pretrained(MODEL_PATH, load_in_4bit=True)
print("[model_server] model loaded — ready to generate.")

app = FastAPI(title="MegaStore Pulse — FT Model Server")


class GenRequest(BaseModel):
    query: str
    max_new_tokens: int = 300


@app.get("/health")
def health():
    return {"ok": True, "model_path": MODEL_PATH}


@app.post("/generate")
def generate(req: GenRequest):
    prompt = f"### Instruction:\n{req.query}\n\n### Response:\n"
    yaml_output = safe_generate(model, tokenizer, prompt, max_new_tokens=req.max_new_tokens)
    return {"yaml": yaml_output}
