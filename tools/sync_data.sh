#!/usr/bin/env bash
set -euo pipefail
aws s3 cp data/sft/synth_r1/train.jsonl "s3://${S3_BUCKET}/${S3_DATA_PREFIX:-data}/sft/train.jsonl"
aws s3 cp data/sft/synth_r1/val.jsonl   "s3://${S3_BUCKET}/${S3_DATA_PREFIX:-data}/sft/val.jsonl"
# optional pairs
if [ -f data/sft/synth_r1/pairs.jsonl ]; then
  aws s3 cp data/sft/synth_r1/pairs.jsonl "s3://${S3_BUCKET}/${S3_DATA_PREFIX:-data}/sft/pairs.jsonl"
fi
