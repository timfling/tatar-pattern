"""Owner-only fixed pilot matrix. All actual images come from CUDA Diffusers."""
from pathlib import Path
import argparse, subprocess, sys, time, os, signal
AI=Path(__file__).resolve().parents[1]
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--owner-run',action='store_true');a=ap.parse_args()
    if not a.owner_run:raise SystemExit('Use --owner-run only inside your approved GPU window')
    run=AI/'pilot/runs/sdxl-r8-v1';out=AI/'pilot/results';start=time.time()
    variants=[('baseline',None,0.0)]
    for step in [200,400,600]:
        p=run/f'checkpoint-{step}/pytorch_lora_weights.safetensors'
        if step==600 and not p.exists():p=run/'pytorch_lora_weights.safetensors'
        if not p.exists():raise SystemExit(f'Missing real checkpoint: {p}')
        for scale in [0.5,0.8]:variants.append((f'step{step}_scale{scale}',p,scale))
    for name,adapter,scale in variants:
        remaining=2*3600-(time.time()-start)
        if remaining<=60:raise SystemExit('Evaluation time cap reached; stop GPU session manually')
        cmd=[sys.executable,str(AI/'pilot/evaluate.py'),'--output',str(out/name),'--scale',str(scale)]
        if adapter:cmd+=['--adapter',str(adapter)]
        p=subprocess.Popen(cmd,start_new_session=True)
        try:
            p.wait(timeout=remaining)
            if p.returncode:raise SystemExit(f'Evaluation failed: {name}; preserve log and stop GPU')
        except subprocess.TimeoutExpired:
            os.killpg(p.pid,signal.SIGKILL);p.wait();raise SystemExit('Evaluation cap reached; stop GPU session manually')
    subprocess.run([sys.executable,str(AI/'pilot/build_comparison_sheets.py')],check=True)
    print('84 images generated. Stop GPU session; compare locally, choose one winner, do not automatically retrain.')
if __name__=='__main__':main()
