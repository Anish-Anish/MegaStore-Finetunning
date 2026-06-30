
from unsloth import FastLanguageModel
import torch
from safe_generate import safe_generate

print("Loading model...")
model, tokenizer = FastLanguageModel.from_pretrained(
    "./final_model",
    load_in_4bit=True,
)
print("✅ Model loaded. Type 'exit' to quit.\n")

while True:
    query = input("👉 Describe your pipeline: ")
    if query.lower() == "exit":
        break
    prompt = f"### Instruction:\n{query}\n\n### Response:\n"
    yaml_output = safe_generate(model, tokenizer, prompt, max_new_tokens=300)
    print("\n📄 Generated YAML:\n", yaml_output)
    print("-" * 60)
