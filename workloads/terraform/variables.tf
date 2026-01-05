variable "region" {
  type    = string
  default = "eu-west-1"
}

variable "tf_state_bucket" {
  type = string
  default = "nlp-rmm-tf-state-eu-west-1"
}

variable "infra_state_key" {
  type = string
  default = "infra/terraform.tfstate"
}

# Inference endpoint settings
variable "inference_namespace" {
  type    = string
  default = "inference"
}

variable "endpoint_name" {
  type    = string
  default = "nlp-rmm-llm-endpoint"
}

# Where the model is in S3 (ready artifact)
# Example: s3://nlp-rmm-artifacts/models/llama3-8b/...
variable "model_s3_bucket" { type = string }
variable "model_s3_prefix" { type = string }

# Inference container image
variable "inference_image" { type = string }

# Training image (contains your python scripts + deps)
variable "training_image" { type = string }
