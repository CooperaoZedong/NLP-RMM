#!/usr/bin/env bash
set -euo pipefail
aws s3 cp data/synth_r1/train.jsonl "s3://${S3_BUCKET}/${S3_DATA_PREFIX:-data}/sft/train.jsonl"
aws s3 cp data/synth_r1/val.jsonl   "s3://${S3_BUCKET}/${S3_DATA_PREFIX:-data}/sft/val.jsonl"

aws s3 cp data/synth_r1/pairs.jsonl "s3://${S3_BUCKET}/${S3_DATA_PREFIX:-data}/dpo/pairs.jsonl"
aws s3 cp data/synth_r1/eval_pairs.jsonl   "s3://${S3_BUCKET}/${S3_DATA_PREFIX:-data}/dpo/eval_pairs.jsonl"
