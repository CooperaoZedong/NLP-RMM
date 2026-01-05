#!/usr/bin/env bash
set -euo pipefail

LOG="/var/log/hyperpod-on-create.log"
exec > >(tee -a "${LOG}") 2>&1

echo "=== HyperPod on_create starting ==="
date

if command -v yum >/dev/null 2>&1; then
  yum install -y jq || true
elif command -v apt-get >/dev/null 2>&1; then
  apt-get update && apt-get install -y jq || true
fi

echo "=== HyperPod on_create complete ==="
date
