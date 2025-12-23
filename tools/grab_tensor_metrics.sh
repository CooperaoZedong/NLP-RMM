#!/usr/bin/env bash
set -euo pipefail

job=$1

pushd tools
aws s3 sync "s3://nlp-rmm-artifacts/outputs/sft/${job}/output"  ./tb-logs

mkdir -p "./tb-logs/${job}"

tar -xzf ./tb-logs/model.tar.gz -C "./tb-logs/${job}"
popd

python -m tensorboard.main --logdir ./tools/tb-logs --host 0.0.0.0 --port 6006
