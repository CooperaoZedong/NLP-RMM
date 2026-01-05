#!/usr/bin/env bash
set -euo pipefail

TARGET_DIR="vendor/sagemaker-hyperpod-cli"

if [[ -d "${TARGET_DIR}" ]]; then
  echo "Already exists: ${TARGET_DIR}"
  exit 0
fi

mkdir -p vendor
git clone https://github.com/aws/sagemaker-hyperpod-cli.git "${TARGET_DIR}"

echo "Vendored into ${TARGET_DIR}"
