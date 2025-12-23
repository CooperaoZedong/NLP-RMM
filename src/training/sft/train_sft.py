import os, json, argparse, math, transformers, trl
from datasets import Dataset
import torch
from transformers import AutoTokenizer, AutoModelForCausalLM, BitsAndBytesConfig, TrainingArguments, DataCollatorForLanguageModeling
from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
from trl import SFTTrainer, SFTConfig
from training.sft.dataset_sft import SFTJsonl
from training.sft.prompt_templates import format_example

def get_args():
    p = argparse.ArgumentParser()
    p.add_argument("--base_model_id", type=str, required=True)
    p.add_argument("--hf_token", type=str, default=None)
    p.add_argument("--train_path", type=str, default="/opt/ml/input/data/train")
    p.add_argument("--val_path", type=str, default="/opt/ml/input/data/validation")
    p.add_argument("--output_dir", type=str, default="/opt/ml/model")
    p.add_argument("--per_device_train_batch_size", type=int, default=4)
    p.add_argument("--per_device_eval_batch_size", type=int, default=4)
    p.add_argument("--num_train_epochs", type=int, default=2)
    p.add_argument("--learning_rate", type=float, default=2e-4)
    p.add_argument("--max_seq_length", type=int, default=2048)
    p.add_argument("--lora_r", type=int, default=16)
    p.add_argument("--lora_alpha", type=int, default=32)
    p.add_argument("--lora_dropout", type=float, default=0.05)
    p.add_argument("--bnb_4bit", type=str, default="true")
    p.add_argument("--eval_strategy", type=str, default="steps")
    p.add_argument("--eval_steps", type=int, default=500)
    p.add_argument("--logging_steps", type=int, default=50)
    p.add_argument("--save_steps", type=int, default=1000)
    return p.parse_args()

def load_jsonl_dir(path):
    # SageMaker mounts single file; support either dir or file
    files = []
    if os.path.isdir(path):
        for n in os.listdir(path):
            if n.endswith(".jsonl"): files.append(os.path.join(path, n))
    else:
        files = [path]
    rows = []
    for fname in files:
        print(f"[load_jsonl_dir] Reading {fname}")
        with open(fname, "r", encoding="utf-8") as fh:
            for lineno, line in enumerate(fh, 1):
                s = line.strip()
                if not s:
                    continue  # skip empty lines

                try:
                    rows.append(json.loads(s))
                except json.JSONDecodeError as e:
                    print(f"[load_jsonl_dir] JSON error in {fname}:{lineno}: {e}")
                    print("[load_jsonl_dir] Offending line (truncated):")
                    print(s[:300])
                    # either re-raise to fail fast
                    #raise

    print(f"[load_jsonl_dir] Loaded {len(rows)} rows total")
    return rows

def mk_dataset(rows):
    exs = []
    for r in rows:
        exs.append({"text": format_example(r["input"], json.dumps(r["output"], sort_keys=True))})
    return Dataset.from_list(exs)

def main():
    args = get_args()
    use_4bit = args.bnb_4bit.lower() == "true"

    print("Transformers version:", transformers.__version__)
    print("TRL version:", trl.__version__)

    train_rows = load_jsonl_dir(args.train_path)
    val_rows   = load_jsonl_dir(args.val_path)

    tok = AutoTokenizer.from_pretrained(args.base_model_id, token=args.hf_token, trust_remote_code=True)
    if tok.pad_token is None: tok.pad_token = tok.eos_token
    tok.padding_side = "right"

    quant_config = None
    if use_4bit:
        quant_config = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_use_double_quant=True,
            bnb_4bit_compute_dtype=torch.bfloat16 if torch.cuda.is_available() else torch.float32,
        )

    model = AutoModelForCausalLM.from_pretrained(
        args.base_model_id,
        token=args.hf_token,
        trust_remote_code=True,
        quantization_config=quant_config,
        device_map="auto",
    )

    # --- Baseline CE on the base model (quantized, no LoRA) ---
    from training.sft.eval_wfl import eval_pass_rate, eval_ce
    ce_base = eval_ce(model, tok, val_rows)
    print(f"cross_entropy_base={ce_base:.4f}")

    if use_4bit:
        model = prepare_model_for_kbit_training(model)

    peft_cfg = LoraConfig(
        r=args.lora_r, lora_alpha=args.lora_alpha, lora_dropout=args.lora_dropout,
        bias="none", task_type="CAUSAL_LM"
    )
    model = get_peft_model(model, peft_cfg)

    train_ds = mk_dataset(train_rows)
    val_ds   = mk_dataset(val_rows)

    if torch.cuda.is_available():
        torch.backends.cuda.matmul.allow_tf32 = True
        print("Enabled TF32 matmul on CUDA")

    print("model dtype summary:")
    for name, p in model.named_parameters():
        if p.requires_grad:
            print(name, p.dtype)
            break

    ex = train_ds[0]
    print(type(ex), ex.keys())
    enc = tok(
        ex["text"],
        return_tensors="pt",
        padding=True,
        truncation=True,
    )
    print("input_ids dtype:", enc["input_ids"].dtype)

    model.config.use_cache = False

    sft_config = SFTConfig(
        output_dir=args.output_dir,
        per_device_train_batch_size=args.per_device_train_batch_size,
        per_device_eval_batch_size=args.per_device_eval_batch_size,
        learning_rate=args.learning_rate,
        num_train_epochs=args.num_train_epochs,
        bf16=False,
        fp16=False,
        logging_steps=args.logging_steps,
        eval_strategy=args.eval_strategy,
        save_strategy=args.eval_strategy,
        eval_steps=args.eval_steps,
        save_steps=args.save_steps,
        gradient_checkpointing=True,
        max_length=args.max_seq_length,
        packing=False,  # JSON outputs benefit from un-packed sequences
        dataset_text_field="text",
        report_to=["tensorboard"]
    )

    trainer = SFTTrainer(
        model=model,
        train_dataset=train_ds,
        eval_dataset=val_ds,
        processing_class=tok,
        args=sft_config
    )

    trainer.train()
    trainer.save_model(args.output_dir)

    # quick eval: percentage of model generations that pass validator
    rate = eval_pass_rate(model, tok, val_rows)
    print(f"eval_pass_rate={rate:.4f}")

    ce_sft  = eval_ce(model, tok, val_rows)

    print(f"cross_entropy_sft={ce_sft:.4f}")
    print(f"delta={(ce_base - ce_sft):.4f}")

    eval_metrics = trainer.evaluate()
    eval_loss = eval_metrics["eval_loss"]
    print(f"eval_loss={eval_loss:.4f}")
    ppl = math.exp(eval_loss)
    print(f"eval_perplexity={ppl:.4f}")

if __name__ == "__main__":
    main()
