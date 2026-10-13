"""Owner-run local VM checks, including a real CUDA operation; no generation."""
from pathlib import Path
import json, shutil, sys

def main():
    import torch
    assert sys.version_info[:2] in [(3,11),(3,12)]
    assert torch.cuda.is_available(), 'CUDA unavailable; check NVIDIA driver for CUDA 12.8'
    props = torch.cuda.get_device_properties(0)
    assert props.total_memory >= 23 * 1024**3, '24GB-class GPU required for this pilot'
    x = torch.ones((4,4),device='cuda')
    assert (x @ x).sum().item() == 64
    torch.cuda.synchronize()
    root = Path(__file__).resolve().parents[1]
    free = shutil.disk_usage(root).free
    assert free >= 20 * 1024**3, 'At least 20GiB free required for weights/results; use the proposed 100GB disk'
    report = dict(python=sys.version,torch=torch.__version__,cuda_runtime=torch.version.cuda,
                  gpu=props.name,vram_bytes=props.total_memory,free_disk_bytes=free,
                  cuda_operation_passed=True,gpu_generation_smoke=False)
    folder = root/'selectel/runtime';folder.mkdir(parents=True,exist_ok=True)
    (folder/'preflight.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))

if __name__ == '__main__':
    main()
