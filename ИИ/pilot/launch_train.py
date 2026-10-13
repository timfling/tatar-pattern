"""Does not upload data. Only run inside an explicitly approved GPU environment."""
from pathlib import Path
import math
import argparse, csv, hashlib, json, subprocess, sys, time, os, signal

AI=Path(__file__).resolve().parents[1]
def digest(p): return hashlib.sha256(p.read_bytes()).hexdigest()

def verify_local():
    folder=AI/'dataset/texture-v1'
    checks=json.loads((folder/'checks.json').read_text())
    assert digest(folder/'training_manifest.csv')==checks['manifest_sha256'], 'manifest changed'
    rows=list(csv.DictReader((folder/'training_manifest.csv').open()))
    for r in rows:
        if r['split']!='train':continue
        for p,h in [(folder/'train'/f"{r['code']}.png",r['rgb_sha256']), (folder/'train'/f"{r['code']}.txt",r['caption_sha256'])]:
            assert digest(p)==h, str(p)
    assert len(list((folder/'train').glob('*.png')))==39
    trainer=AI/'research/train_text_to_image_lora_sdxl.py'
    assert digest(trainer)=='e733e9cce32fbe1802dc61426d75f3ab12ff6e824e3f2ee8fa258a60650bdfeb'
    return folder,trainer,checks

def command(folder,trainer):
    return [sys.executable,'-m','accelerate.commands.launch','--num_processes=1','--num_machines=1','--mixed_precision=fp16',str(trainer),
        '--pretrained_model_name_or_path=stabilityai/stable-diffusion-xl-base-1.0',
        '--revision=462165984030d82259a11f4367a4eed129e94a7b',
        '--variant=fp16',
        f'--train_data_dir={folder / "train"}',f'--output_dir={AI / "pilot/runs/sdxl-r8-v1"}',
        '--resolution=1024','--center_crop','--train_batch_size=1','--gradient_accumulation_steps=4',
        '--gradient_checkpointing','--learning_rate=0.0001','--lr_scheduler=constant','--lr_warmup_steps=0',
        '--rank=8','--max_train_steps=600','--checkpointing_steps=200','--checkpoints_total_limit=3',
        '--seed=20261008','--mixed_precision=fp16','--dataloader_num_workers=0','--report_to=none']

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--execute',action='store_true');ap.add_argument('--owner-run',action='store_true');ap.add_argument('--budget-rub',type=int);ap.add_argument('--hourly-rub',type=float);a=ap.parse_args()
    folder,trainer,checks=verify_local();cmd=command(folder,trainer)
    if not a.execute:
        print(json.dumps({'status':'DRY_RUN_ONLY','command':cmd,'dataset_sha256':checks['manifest_sha256']},indent=2));return
    # Owner-only workflow per instruction 11.10.2026. The agent never runs this.
    if not a.owner_run or a.budget_rub!=1500:
        raise SystemExit('Owner must explicitly run with --owner-run --budget-rub 1500; see START-HERE.md')
    if a.hourly_rub is None or not math.isfinite(a.hourly_rub) or a.hourly_rub<=0:
        raise SystemExit('Provide --hourly-rub from your actual Selectel quote; no inherited DSLab rate')
    import torch
    assert torch.cuda.is_available(), 'CUDA required'
    props=torch.cuda.get_device_properties(0)
    assert props.total_memory>=23*1024**3, '24GB-class GPU required'
    run=AI/'pilot/runs/sdxl-r8-v1';run.mkdir(parents=True,exist_ok=False)
    (run/'command.json').write_text(json.dumps(cmd,indent=2))
    (run/'pip-freeze.txt').write_bytes(subprocess.check_output([sys.executable,'-m','pip','freeze']))
    (run/'gpu.txt').write_bytes(subprocess.check_output(['nvidia-smi']))
    start=time.time();env=dict(os.environ,HF_HUB_DISABLE_TELEMETRY='1',DO_NOT_TRACK='1',WANDB_DISABLED='true')
    status='failed'
    try:
        with (run/'train.log').open('w') as log:
            p=subprocess.Popen(cmd,stdout=log,stderr=subprocess.STDOUT,env=env,start_new_session=True)
            try:p.wait(timeout=6*3600)
            except subprocess.TimeoutExpired:
                os.killpg(p.pid,signal.SIGTERM)
                try:p.wait(timeout=10)
                except subprocess.TimeoutExpired:os.killpg(p.pid,signal.SIGKILL);p.wait()
                raise
        status='process_complete' if p.returncode==0 else 'process_failed'
    except subprocess.TimeoutExpired:status='process_timeout_VM_MUST_BE_FROZEN_OR_DELETED_MANUALLY'
    finally:
        elapsed=time.time()-start
        (run/'execution.json').write_text(json.dumps({'status':status,'elapsed_seconds':elapsed,'estimated_active_process_rub':elapsed*a.hourly_rub/3600,'hourly_rate_rub_owner_supplied':a.hourly_rub,'provider':'selectel-self-hosted','rental_total_cost_not_measured':True,'dataset_sha256':checks['manifest_sha256'],'session_stopped':False},indent=2))
        print(status+'; export results, freeze/delete Selectel VM in console and verify billing; powering off is insufficient.')

if __name__=='__main__': main()
