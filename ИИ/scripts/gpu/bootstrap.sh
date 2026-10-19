#!/usr/bin/env bash
# Owner runs on the rented VM. No provider API, driver replacement, or billing actions.
set -euo pipefail
if [[ "${1:-}" != "--owner-run" ]]; then
  echo 'Usage on your immers.cloud VM: bash scripts/gpu/bootstrap.sh --owner-run'
  exit 2
fi
cd "$(dirname "$0")/../.."
python3 scripts/gpu/verify_kit.py
python3 -c 'import sys; assert sys.version_info[:2] in [(3,11),(3,12)], "Python 3.11/3.12 required"'
if ! command -v nvidia-smi >/dev/null; then
  echo 'NVIDIA driver missing. Use a confirmed GPU image/instruction supplied by the owner.'
  exit 3
fi
nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv
python3 -m venv .venv
export HF_HOME="$PWD/gpu-runtime/model-cache"
export HF_HUB_DISABLE_TELEMETRY=1
export DO_NOT_TRACK=1
requirements_sha=$(python3 -c 'import hashlib; from pathlib import Path; print(hashlib.sha256(Path("pilot/requirements-gpu.txt").read_bytes()).hexdigest())')
if [[ ! -f .venv/tp-requirements.sha ]] || [[ "$(cat .venv/tp-requirements.sha)" != "$requirements_sha" ]]; then
  .venv/bin/python -m pip install 'pip==25.2'
  .venv/bin/python -m pip install --index-url https://download.pytorch.org/whl/cu128 'torch==2.8.0' 'torchvision==0.23.0'
  .venv/bin/python -m pip install -r pilot/requirements-gpu.txt
  .venv/bin/python -m pip check
  printf '%s\n' "$requirements_sha" > .venv/tp-requirements.sha
fi
.venv/bin/python -m pip check
.venv/bin/python scripts/gpu/preflight.py
.venv/bin/python pilot/launch_train.py
mkdir -p gpu-runtime
.venv/bin/python -m pip freeze > gpu-runtime/pip-freeze.txt
nvidia-smi > gpu-runtime/nvidia-smi.txt
echo 'Environment prepared. No training or model download executed. Billing continues until VM Shelve/deletion confirmed in the provider console.'
