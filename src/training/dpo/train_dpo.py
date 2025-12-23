import argparse, os, tarfile
os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")

import torch
from transformers import AutoTokenizer, AutoModelForCausalLM, BitsAndBytesConfig
from trl import DPOTrainer, DPOConfig
from peft import LoraConfig, PeftConfig, PeftModel, get_peft_model, prepare_model_for_kbit_training
from training.dpo.dataset_dpo import load_pairs

def get_args():
    p = argparse.ArgumentParser()
    p.add_argument("--base_model_id", type=str, required=True)
    p.add_argument("--hf_token", type=str, default=None)
    p.add_argument("--pairs_path", type=str, default="/opt/ml/input/data/pairs")
    p.add_argument("--eval_pairs_path", type=str, default="/opt/ml/input/data/eval_pairs")
    p.add_argument("--output_dir", type=str, default="/opt/ml/model-dpo")
    p.add_argument("--beta", type=float, default=0.1)
    p.add_argument("--lr", type=float, default=5e-6)
    p.add_argument("--epochs", type=int, default=1)
    p.add_argument("--bnb_4bit", type=str, default="true")
    return p.parse_args()

def resolve_base_model_path(path: str) -> str:
    # If it's a tarball (SFT artifact from S3), extract it
    if os.path.isfile(path) and path.endswith(".tar.gz"):
        target = path[:-7]  # strip .tar.gz
        if not os.path.exists(target):
            os.makedirs(target, exist_ok=True)
            with tarfile.open(path, "r:gz") as tar:
                tar.extractall(target)
        return target
    return path

def main():
    args = get_args()
    use_4bit = args.bnb_4bit.lower() == "true"

    sft_dir = resolve_base_model_path(args.base_model_id)
    peft_cfg = PeftConfig.from_pretrained(sft_dir)
    base_id = peft_cfg.base_model_name_or_path

    tok = AutoTokenizer.from_pretrained(base_id, token=args.hf_token, trust_remote_code=True)
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


    base_model = AutoModelForCausalLM.from_pretrained(
        base_id,
        token=args.hf_token,
        trust_remote_code=True,
        quantization_config=quant_config,
        torch_dtype=torch.bfloat16 if torch.cuda.is_available() else torch.float32,
        device_map="auto"
    )
    base_model.config.use_cache = False
    if use_4bit:
        base_model = prepare_model_for_kbit_training(base_model)

    model = PeftModel.from_pretrained(
        base_model,
        sft_dir,
        is_trainable=True,
    )

    train_ds = load_pairs(args.pairs_path)
    val_ds = load_pairs(args.eval_pairs_path)

    if torch.cuda.is_available():
        torch.backends.cuda.matmul.allow_tf32 = True
        print("Enabled TF32 matmul on CUDA")

    trainer = DPOTrainer(
        model=model,
        ref_model=None,  # defaults to frozen copy
        args=DPOConfig(
            output_dir=args.output_dir,
            per_device_train_batch_size=1,
            per_device_eval_batch_size=1,
            gradient_accumulation_steps=16,
            num_train_epochs=args.epochs,
            bf16=False,
            fp16=False,
            learning_rate=args.lr,
            beta=args.beta,
            max_prompt_length=512,
            max_length=2048,
            logging_steps=50,
            remove_unused_columns=False,
            precompute_ref_log_probs=False,
            #precompute_ref_batch_size=1,
            gradient_checkpointing=True,
            reference_free=True,
            eval_accumulation_steps=1
        ),
        processing_class=tok,
        train_dataset=train_ds,
        eval_dataset=val_ds
        #max_target_length=1024
    )
    train_result = trainer.train()
    trainer.save_model(args.output_dir)

    metrics = train_result.metrics
    trainer.log_metrics("train", metrics)
    trainer.save_metrics("train", metrics)

    eval_metrics = trainer.evaluate()
    trainer.log_metrics("eval", eval_metrics)
    trainer.save_metrics("eval", eval_metrics)

    print(f"dpo_train_loss={metrics['train_loss']:.4f}")
    print(f"dpo_eval_loss={eval_metrics.get('eval_loss', float('nan')):.4f}")

if __name__ == "__main__":
    main()
