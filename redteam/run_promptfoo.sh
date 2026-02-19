#!/usr/bin/env bash
set -euo pipefail

mkdir -p redteam/results
promptfoo eval -c redteam/promptfoo.yaml \
  --output redteam/results/results.html \
  --output redteam/results/results.json
