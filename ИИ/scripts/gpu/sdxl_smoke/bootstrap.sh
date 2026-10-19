#!/usr/bin/env bash
set -euo pipefail
[[ "${1:-}" == '--owner-run' ]] || { echo 'Use --owner-run on your GPU machine'; exit 2; }
cd "$(dirname "$0")"
python3 -c 'import sys; assert sys.version_info[:2] in [(3,11),(3,12)], "Use Python 3.11 or 3.12"'
nvidia-smi
python3 -m venv .venv
.venv/bin/python -m pip install 'pip==25.2'
.venv/bin/python -m pip install --index-url https://download.pytorch.org/whl/cu128 'torch==2.8.0'
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m pip check
mkdir -p runtime
.venv/bin/python -m pip freeze > runtime/pip-freeze.txt
nvidia-smi > runtime/nvidia-smi.txt
.venv/bin/python - <<'PY'
import sys, torch
from common import write_json
assert torch.__version__.split('+')[0] == '2.8.0'
assert torch.version.cuda == '12.8'
assert torch.cuda.is_available(), 'CUDA unavailable; ask provider about driver/image'
x = torch.ones((4, 4), device='cuda'); assert (x @ x).sum().item() == 64
torch.cuda.synchronize()
p = torch.cuda.get_device_properties(0)
write_json('runtime/preflight.json', dict(python=sys.version, torch=torch.__version__, cuda=torch.version.cuda,
           gpu=p.name, vram_bytes=p.total_memory, cuda_operation='PASS'))
PY
echo 'Environment ready; no model download, generation, or provider operation performed.'
