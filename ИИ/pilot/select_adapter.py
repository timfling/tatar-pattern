"""After owner reviews actual comparisons, package ONE selected adapter locally."""
from pathlib import Path
import argparse,hashlib,json,shutil
AI=Path(__file__).resolve().parents[1]
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--step',type=int,choices=[200,400,600],required=True);ap.add_argument('--scale',type=float,choices=[.5,.8],required=True);ap.add_argument('--accept-reviewed-result',action='store_true');a=ap.parse_args()
    if not a.accept_reviewed_result:raise SystemExit('Review actual paired images and copying before accepting a winner')
    run=AI/'pilot/runs/sdxl-r8-v1';source=run/f'checkpoint-{a.step}/pytorch_lora_weights.safetensors'
    if a.step==600 and not source.exists():source=run/'pytorch_lora_weights.safetensors'
    measurements=AI/f'pilot/results/step{a.step}_scale{a.scale}/measurements.json'
    if not source.exists() or not measurements.exists():raise SystemExit('Real adapter and measured evaluation required')
    assert len(json.loads(measurements.read_text()))==12
    target=AI/'pilot/selected';target.mkdir(exist_ok=False)
    shutil.copy2(source,target/'texture-lora.safetensors')
    sha=hashlib.sha256(source.read_bytes()).hexdigest()
    record=dict(workflowVersion='tp-sdxl-fiber-v1',base='stabilityai/stable-diffusion-xl-base-1.0',baseRevision='462165984030d82259a11f4367a4eed129e94a7b',adapterSHA256=sha,selectedStep=a.step,loraScale=a.scale,datasetManifestSHA256=json.loads((AI/'dataset/texture-v1/checks.json').read_text())['manifest_sha256'],license='CreativeML Open RAIL++-M restrictions apply; dataset rights owner-declared, no written document',expertAuthenticityConfirmed=False,cloudEndpointVerified=False)
    (target/'workflow.json').write_text(json.dumps(record,indent=2)+'\n')
    shutil.copy2(AI/'research/sdxl-license.md',target/'BASE-LICENSE.md')
    (target/'MODEL-CARD.md').write_text('# TATAR PATTERN fiber texture adapter\n\nOwner selected from actual paired pilot. SDXL-only UNet LoRA rank8.\nSee workflow.json, base licence, dataset manifest and evaluation.\nNo expert cultural authentication, guaranteed alpha or AI seamlessness.\nDo not distribute dataset/adapter beyond owner-declared permitted scope.\n')
    print('One chosen adapter packaged:',sha)
if __name__=='__main__':main()
