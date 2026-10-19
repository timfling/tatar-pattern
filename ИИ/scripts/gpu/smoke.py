"""Owner-run real render, then a separate explicit visual acceptance. No cloud API."""
from pathlib import Path
import argparse, datetime, hashlib, json, os, signal, subprocess, sys
ROOT = Path(__file__).resolve().parents[2]

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--owner-run', action='store_true')
    ap.add_argument('--config', type=Path, required=True)
    ap.add_argument('--accept-reviewed-result', action='store_true')
    a = ap.parse_args()
    if not a.owner_run:
        raise SystemExit('Requires --owner-run inside your approved GPU window')
    config_path = a.config.resolve()
    c = json.loads(config_path.read_text())
    adapter = Path(c['adapter_path'])
    if sha(adapter) != c['adapter_sha256']:
        raise SystemExit('Adapter SHA mismatch')
    folder = ROOT/'gpu-runtime/smoke'
    record_path = folder/'record.json'
    image_path = folder/'result.png'
    if a.accept_reviewed_result:
        record = json.loads(record_path.read_text())
        if (record['config_sha256'] != sha(config_path) or
            record['adapter_sha256'] != sha(adapter) or
            record['png_sha256'] != sha(image_path)):
            raise SystemExit('Smoke inputs/result changed; rerun on this VM')
        record.update(passed=True, owner_reviewed=True,
                      accepted_utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
        record_path.write_text(json.dumps(record, indent=2)+'\n')
        print('Accepted real smoke:', record_path)
        return
    folder.mkdir(parents=True, exist_ok=False)
    subprocess.run([sys.executable, str(ROOT/'scripts/gpu/preflight.py')], check=True)
    workflow = json.loads((ROOT/'pilot/selected/workflow.json').read_text())
    if workflow['adapterSHA256'] != c['adapter_sha256']:
        raise SystemExit('Config must use the selected adapter')
    request = dict(workflowVersion=c['workflow_version'], modelVersion=c['adapter_sha256'],
                   scenario='motif', prompt='tptrx, isolated ornamental motif, a blue lobed flower with visible fine fibers, centered on a white background.',
                   seed=20261008, width=1024, height=1024, steps=30,
                   guidanceScale=5.0, loraScale=workflow['loraScale'], templateId=None)
    request_path = folder/'request.json'
    request_path.write_text(json.dumps(request, indent=2)+'\n')
    with (folder/'render.log').open('w') as log:
        process = subprocess.Popen([sys.executable, str(ROOT/'service/render_one.py'),
                                    str(request_path), str(image_path), str(config_path)],
                                   stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        try:
            process.wait(timeout=600)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait()
            raise SystemExit('Smoke timeout. Save logs and end rental manually.')
        if process.returncode:
            raise SystemExit('Real render failed; inspect gpu-runtime/smoke/render.log')
    from PIL import Image
    with Image.open(image_path) as im:
        im.load()
        if im.format != 'PNG' or im.size != (1024, 1024) or image_path.stat().st_size > 20*1024**2:
            raise SystemExit('Invalid render output')
    record = dict(passed=False, owner_reviewed=False, adapter_sha256=sha(adapter),
                  png_sha256=sha(image_path), config_sha256=sha(config_path),
                  workflow_version=c['workflow_version'], base_revision=c['base_revision'],
                  created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                  preflight_sha256=sha(ROOT/'gpu-runtime/preflight.json'),
                  metrics=json.loads(image_path.with_suffix('.metrics.json').read_text()))
    record_path.write_text(json.dumps(record, indent=2)+'\n')
    print('Real render saved:', image_path)
    print('Review image, then rerun with --accept-reviewed-result. No HTTP smoke yet.')

if __name__ == '__main__':
    main()
