variable "project" {
  type    = string
  default = "nlp-rmm"
}
variable "region" {
  type    = string
  default = "eu-west-1"
}
variable "environment" {
  type    = string
  default = "dev"
}
variable "tags" {
  type    = map(string)
  default = { App = "nlp-rmm" }
}

# S3
variable "s3_bucket" {
  type    = string
  default = "nlp-rmm-artifacts"
}

# Base model + DLC image
variable "base_model_id" {
  type    = string
  default = "meta-llama/Meta-Llama-3.1-8B-Instruct"
}
variable "hf_token" {
  type      = string
  sensitive = true
}                                                      # set via TF_VAR_hf_token
variable "huggingface_dlc_image_uri" { type = string } # e.g. 763104351884.dkr.ecr.us-east-1.amazonaws.com/huggingface-pytorch-tf:2.3.0-transformers4.41.1-gpu-py310-cu121-ubuntu20.04

# Instance sizes
variable "sft_instance_type" {
  type    = string
  default = "ml.g5.2xlarge"
}
variable "dpo_instance_type" {
  type    = string
  default = "ml.g5.2xlarge"
}

# Paths in S3
variable "s3_code_prefix" {
  type    = string
  default = "code"
}
variable "s3_data_prefix" {
  type    = string
  default = "data"
}

variable "eks_cluster_name" {
  type    = string
  default = "nlp-rmm-dev-eks"
}

variable "hyperpod_cluster_name" {
  type    = string
  default = "nlp-rmm-dev-hp"
}

variable "vpc_cidr" {
  type    = string
  default = "10.40.0.0/16"
}

variable "private_subnet_cidrs" {
  type    = list(string)
  default = ["10.40.0.0/19", "10.40.32.0/19", "10.40.64.0/19"]
}

variable "public_subnet_cidrs" {
  type    = list(string)
  default = ["10.40.96.0/19", "10.40.128.0/19", "10.40.160.0/19"]
}

# HyperPod instance group sizing
variable "hyperpod_instance_type" {
  type    = string
  default = "ml.g5.8xlarge"
}

variable "hyperpod_instance_count" {
  type    = number
  default = 2
}
