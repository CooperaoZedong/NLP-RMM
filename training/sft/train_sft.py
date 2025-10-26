import os, json
from dataclasses import dataclass, field
from typing import Dict
import torch
from transformers import AutoTokenizer, AutoModelForCausalLM, TrainingArguments
from trl import SFTTrainer, DataCollatorForCompletionOnlyLM
from peft import LoraConfig, get_peft_model
from datasets import load_dataset

model_id = os.environ.get("MODEL_ID", "meta-llama/Meta-Llama-3-8B-Instruct")
train_path = os.environ["TRAIN_PATH"]
val_path   = os.environ["VAL_PATH"]
output_dir = os.environ["SM_MODEL_DIR"]

# helpers
def format_example(ex):
    prompt = f"""You are a workflow planner. Convert the user request into a minimal valid .wfl JSON only.
User request:
{ex["input"]}

Respond with JSON only."""
    return {"prompt": prompt, "response": json.dumps(ex["output"], ensure_ascii=False)}

def load_jsonl(path):
    ds = load_dataset("json", data_files=path, split="train")
    ds = ds.map(format_example, remove_columns=ds.column_names)
    return ds

tokenizer = AutoTokenizer.from_pretrained(model_id, use_fast=True)
tokenizer.pad_token = tokenizer.eos_token

bnb_config = {
    "load_in_4bit": True, 
    "bnb_4bit_use_double_quant": True,
    "bnb_4bit_quant_type": "nf4", 
    "bnb_4bit_compute_dtype": torch.bfloat16
}

model = AutoModelForCausalLM.from_pretrained(model_id, device_map="auto", **bnb_config)

peft_cfg = LoraConfig(
    r=int(os.environ.get("LORA_R","8")),
    lora_alpha=16, lora_dropout=0.05,
    target_modules=["q_proj","k_proj","v_proj","o_proj","gate_proj","down_proj","up_proj"],
    task_type="CAUSAL_LM"
)
model = get_peft_model(model, peft_cfg)

train_ds = load_jsonl(train_path)
val_ds   = load_jsonl(val_path)

collator = DataCollatorForCompletionOnlyLM(response_template="", tokenizer=tokenizer)

args = TrainingArguments(
    output_dir=output_dir,
    per_device_train_batch_size=int(os.environ.get("BATCH","2")),
    gradient_accumulation_steps=int(os.environ.get("GRAD_ACC","8")),
    num_train_epochs=float(os.environ.get("EPOCHS","2")),
    learning_rate=float(os.environ.get("LR","2e-4")),
    lr_scheduler_type="cosine", warmup_ratio=0.05,
    logging_steps=10, save_steps=500, evaluation_strategy="steps", eval_steps=500,
    bf16=True, gradient_checkpointing=True, report_to="none"
)

trainer = SFTTrainer(
    model=model, tokenizer=tokenizer, args=args,
    train_dataset=train_ds, eval_dataset=val_ds,
    max_seq_length=int(os.environ.get("SEQ_LEN","2048")),
    dataset_text_field=None,
    formatting_func=lambda ex: [ex["prompt"] + "\n" + ex["response"]],
    data_collator=collator
)
trainer.train()
trainer.model.save_pretrained(output_dir)
tokenizer.save_pretrained(output_dir)
