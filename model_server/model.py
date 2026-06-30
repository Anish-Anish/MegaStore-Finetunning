# /workspace/shared/code space/Megastorepipeline/model.py

import sys
import os

# Add the training folder to Python's module search path
training_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "training"))
sys.path.insert(0, training_path)

from unsloth import FastLanguageModel
from safe_generate import safe_generate   # now found inside training/

# Absolute path to the final model (inside training/)
model_path = os.path.join(training_path, "final_model")
model, tokenizer = FastLanguageModel.from_pretrained(model_path, load_in_4bit=True)

query = "Alert me when inventory falls below 5 units in any warehouse"
prompt = f"### Instruction:\n{query}\n\n### Response:\n"
yaml_output = safe_generate(model, tokenizer, prompt, max_new_tokens=300)
print("📄 Generated YAML:\n", yaml_output)