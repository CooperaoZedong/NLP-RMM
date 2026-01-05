#!/usr/bin/env bash
set -euo pipefail

REGION="${REGION:-eu-west-1}"
TF_STATE_BUCKET="${TF_STATE_BUCKET:-nlp-rmm-tf-state-eu-west-1}"
TF_LOCK_TABLE="${TF_LOCK_TABLE:-nlp-rmm-tf-lock}"

echo "Region: ${REGION}"
echo "Bucket: ${TF_STATE_BUCKET}"
echo "Table : ${TF_LOCK_TABLE}"

if aws s3api head-bucket --bucket "${TF_STATE_BUCKET}" 2>/dev/null; then
  echo "S3 bucket exists: ${TF_STATE_BUCKET}"
else
  aws s3api create-bucket \
    --bucket "${TF_STATE_BUCKET}" \
    --region "${REGION}" \
    --create-bucket-configuration LocationConstraint="${REGION}"
  echo "Created S3 bucket: ${TF_STATE_BUCKET}"
fi

# Enable versioning
aws s3api put-bucket-versioning \
  --bucket "${TF_STATE_BUCKET}" \
  --versioning-configuration Status=Enabled

aws s3api put-bucket-encryption \
  --bucket "${TF_STATE_BUCKET}" \
  --server-side-encryption-configuration '{
    "Rules": [{
      "ApplyServerSideEncryptionByDefault": { "SSEAlgorithm": "AES256" }
    }]
  }'

if aws dynamodb describe-table --table-name "${TF_LOCK_TABLE}" --region "${REGION}" >/dev/null 2>&1; then
  echo "DynamoDB table exists: ${TF_LOCK_TABLE}"
else
  aws dynamodb create-table \
    --table-name "${TF_LOCK_TABLE}" \
    --region "${REGION}" \
    --attribute-definitions AttributeName=LockID,AttributeType=S \
    --key-schema AttributeName=LockID,KeyType=HASH \
    --billing-mode PAY_PER_REQUEST
  echo "Created DynamoDB table: ${TF_LOCK_TABLE}"
fi

echo "Backend bootstrap complete."
