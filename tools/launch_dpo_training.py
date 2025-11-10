import boto3
from datetime import datetime, timezone
from typing import Dict, Optional
import os

def launch_dpo_training(
        *,
        project: str,
        region: str,
        s3_bucket: str,
        s3_code_prefix: str,
        s3_data_prefix: str,
        role_arn: str,
        dpo_instance_type: str,
        base_model_id: str,
        huggingface_dlc_image_uri: str,
        tags: Optional[Dict[str, str]] = None,
) -> str:
    """
    Launch an DPO training job on SageMaker, equivalent to the Terraform
    aws_sagemaker_training_job.dpo resource.

    Returns the TrainingJobName.
    """

    sm = boto3.client("sagemaker", region_name=region)

    # --- Terraform "locals" recreation -------------------------------------
    s3_code       = f"s3://{s3_bucket}/{s3_code_prefix}/src.tar.gz"
    s3_pairs  = f"s3://{s3_bucket}/{s3_data_prefix}/dpo/pairs.jsonl"
    s3_output_dpo = f"s3://{s3_bucket}/outputs/dpo"

    # make job name unique to avoid "already exists" errors
    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    training_job_name = f"{project}-dpo-{ts}"

    hf_token = os.environ.get("HF_TOKEN", "")

    # --- Hyperparameters (string -> string) --------------------------------
    hyperparameters = {
        "s3_code": s3_code,
        "base_model_id": base_model_id,
        "hf_token": hf_token,
        "per_device_train_batch_size": "2",
        "gradient_accumulation_steps": "8",
        "beta": "0.1",
        "num_train_epochs": "1",
        "learning_rate": "5e-6",
        "bnb_4bit": "true",
        "max_seq_length": "2048"
    }

    # --- Input channels -----------------------------------------------------
    input_data_config = [
        {
            "ChannelName": "pairs",
            "DataSource": {
                "S3DataSource": {
                    "S3DataType": "S3Prefix",
                    "S3Uri": s3_pairs,
                    "S3DataDistributionType": "FullyReplicated",
                }
            }
        }
    ]

    # --- Algorithm spec (HuggingFace DLC) ----------------------------------
    algorithm_specification = {
        "TrainingImage": huggingface_dlc_image_uri,
        "TrainingInputMode": "File",
        "MetricDefinitions": [
            {
                "Name": "eval/pass_rate",
                "Regex": "eval_pass_rate=(.*)",
            }
        ],
    }

    # --- Resource config / stopping condition ------------------------------
    resource_config = {
        "InstanceCount": 1,
        "InstanceType": dpo_instance_type,
        "VolumeSizeInGB": 200,
    }

    stopping_condition = {
        "MaxRuntimeInSeconds": 7200,
    }

    # --- Tags: dict -> list[{"Key","Value"}] -------------------------------
    tag_list = []
    if tags:
        tag_list = [{"Key": k, "Value": str(v)} for k, v in tags.items()]

    # --- Create training job ------------------------------------------------
    resp = sm.create_training_job(
        TrainingJobName=training_job_name,
        RoleArn=role_arn,
        HyperParameters=hyperparameters,
        AlgorithmSpecification=algorithm_specification,
        InputDataConfig=input_data_config,
        OutputDataConfig={"S3OutputPath": s3_output_dpo},
        ResourceConfig=resource_config,
        StoppingCondition=stopping_condition,
        EnableNetworkIsolation=False,  # matches enable_network_isolation = false
        Tags=tag_list,
    )

    print(f"Started training job: {training_job_name}")
    print(f"SageMaker response TrainingJobArn: {resp['TrainingJobArn']}")
    return training_job_name


if __name__ == "__main__":
    # Example usage: fill these from env/config/CLI
    training_job = launch_dpo_training(
        project="my-project",
        region="us-east-1",
        s3_bucket="my-bucket",
        s3_code_prefix="code",
        s3_data_prefix="data",
        role_arn="arn:aws:iam::123456789012:role/sagemaker-exec-role",
        dpo_instance_type="ml.g5.2xlarge",
        base_model_id="meta-llama/Llama-3-8B-Instruct",
        huggingface_dlc_image_uri="763104351884.dkr.ecr.us-east-1.amazonaws.com/huggingface-pytorch-training:2.8.0-transformers4.56.2-gpu-py312-cu129-ubuntu22.04",
        tags={"Project": "nlp-rmm", "Stage": "train"},
    )
    print("Launched:", training_job)
