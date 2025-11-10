import argparse, os
from transformers import AutoTokenizer, AutoModelForCausalLM
from trl import DPOTrainer, DPOConfig
from peft import LoraConfig, get_peft_model
from .dataset_dpo import load_pairs

def get_args():
    p = argparse.ArgumentParser()
    p.add_argument("--base_model_id", type=str, required=True)
    p.add_argument("--hf_token", type=str, default=None)
    p.add_argument("--pairs_path", type=str, default="/opt/ml/input/data/pairs")
    p.add_argument("--output_dir", type=str, default="/opt/ml/model-dpo")
    p.add_argument("--beta", type=float, default=0.1)
    p.add_argument("--lr", type=float, default=5e-6)
    p.add_argument("--epochs", type=int, default=1)
    return p.parse_args()

def main():
    a = get_args()
    tok = AutoTokenizer.from_pretrained(a.base_model_id, use_auth_token=a.hf_token, trust_remote_code=True)
    if tok.pad_token is None: tok.pad_token = tok.eos_token

    model = AutoModelForCausalLM.from_pretrained(a.base_model_id, use_auth_token=a.hf_token, load_in_4bit=True, trust_remote_code=True)
    model = get_peft_model(model, LoraConfig(r=16, lora_alpha=32, lora_dropout=0.05, task_type="CAUSAL_LM"))

    ds = load_pairs(a.pairs_path)

    trainer = DPOTrainer(
        model=model,
        ref_model=None,  # defaults to frozen copy
        args=DPOConfig(
            output_dir=a.output_dir,
            per_device_train_batch_size=2,
            gradient_accumulation_steps=8,
            num_train_epochs=a.epochs,
            learning_rate=a.lr,
            beta=a.beta,
            logging_steps=50
        ),
        tokenizer=tok,
        train_dataset=ds,
        max_length=2048,
        max_target_length=1024
    )
    trainer.train()
    trainer.save_model(a.output_dir)

if __name__ == "__main__":
    main()
