import os, json, argparse
from datasets import Dataset
from transformers import AutoTokenizer, AutoModelForCausalLM, TrainingArguments, DataCollatorForLanguageModeling
from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
from trl import SFTTrainer
from .dataset_sft import SFTJsonl
from .prompt_templates import format_example

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
    for f in files:
        with open(f, "r", encoding="utf-8") as fh:
            rows.extend([json.loads(l) for l in fh])
    return rows

def mk_dataset(rows):
    exs = []
    for r in rows:
        exs.append({"text": format_example(r["input"], json.dumps(r["output"], sort_keys=True))})
    return Dataset.from_list(exs)

def main():
    args = get_args()
    use_4bit = args.bnb_4bit.lower() == "true"

    tok = AutoTokenizer.from_pretrained(args.base_model_id, use_auth_token=args.hf_token, trust_remote_code=True)
    if tok.pad_token is None: tok.pad_token = tok.eos_token

    model = AutoModelForCausalLM.from_pretrained(
        args.base_model_id, use_auth_token=args.hf_token, load_in_4bit=use_4bit, trust_remote_code=True
    )
    model = prepare_model_for_kbit_training(model) if use_4bit else model
    model = get_peft_model(model, LoraConfig(r=args.lora_r, lora_alpha=args.lora_alpha, lora_dropout=args.lora_dropout, bias="none", task_type="CAUSAL_LM"))

    train_rows = load_jsonl_dir(args.train_path)
    val_rows   = load_jsonl_dir(args.val_path)

    train_ds = mk_dataset(train_rows)
    val_ds   = mk_dataset(val_rows)

    args_tr = TrainingArguments(
        output_dir=args.output_dir,
        per_device_train_batch_size=args.per_device_train_batch_size,
        per_device_eval_batch_size=args.per_device_eval_batch_size,
        learning_rate=args.learning_rate,
        num_train_epochs=args.num_train_epochs,
        fp16=True,
        logging_steps=50,
        evaluation_strategy="steps",
        eval_steps=500,
        save_steps=1000,
        gradient_checkpointing=True
    )

    trainer = SFTTrainer(
        model=model,
        train_dataset=train_ds,
        eval_dataset=val_ds,
        tokenizer=tok,
        args=args_tr,
        max_seq_length=args.max_seq_length,
        packing=False,  # JSON outputs benefit from un-packed sequences
        dataset_text_field="text"
    )

    trainer.train()
    trainer.save_model(args.output_dir)

    # quick eval: percentage of model generations that pass your validator
    from .eval_wfl import eval_pass_rate
    rate = eval_pass_rate(model, tok, val_rows)
    print(f"eval_pass_rate={rate:.4f}")

if __name__ == "__main__":
    main()
