#!/usr/bin/env bash
set -euo pipefail

mkdir -p redteam/results

echo "Checking server availability at /chat ..."
health_resp="$(curl -fsS http://localhost:8000/chat \
  -H 'Content-Type: application/json' \
  -d '{"query":"health check"}')"
echo "Server check response received (${#health_resp} bytes)."

ts="$(date +%Y%m%d-%H%M%S)"
out_dir="redteam/results/${ts}"
mkdir -p "${out_dir}"

echo "Running promptfoo eval ..."
promptfoo eval -c redteam/promptfoo.yaml \
  --output "${out_dir}/results.html" \
  --output "${out_dir}/results.json"

echo "Promptfoo artifacts written to ${out_dir}"
