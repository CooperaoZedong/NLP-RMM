#!/usr/bin/env bash
set -euo pipefail
here="$(cd "$(dirname "$0")/.."; pwd)"
cd "$here"
tar -czf src.tar.gz src
aws s3 cp src.tar.gz "s3://${S3_BUCKET}/${S3_CODE_PREFIX:-code}/src.tar.gz"
