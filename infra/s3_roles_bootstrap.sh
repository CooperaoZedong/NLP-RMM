#!/usr/bin/env bash
set -euo pipefail

REGION=${REGION:-us-east-1}
BUCKET=${BUCKET:-VSA_BUCKET}
ROLE_NAME=${ROLE_NAME:-SageMakerExecRole}

aws s3 mb s3://$BUCKET --region $REGION || true

aws iam create-role --role-name $ROLE_NAME \
  --assume-role-policy-document '{
    "Version": "2012-10-17","Statement":[{"Effect":"Allow",
    "Principal":{"Service":"sagemaker.amazonaws.com"},
    "Action":"sts:AssumeRole"}]}' || true

aws iam put-role-policy --role-name $ROLE_NAME \
  --policy-name ${ROLE_NAME}Inline \
  --policy-document file://infra/iam-policy-sagemaker-exec.json
