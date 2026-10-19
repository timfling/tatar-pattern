"""NEXT STAGE ONLY: loopback HTTP smoke after inference and a separately prepared server."""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from common import write_json
from verify_results import verify

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--owner-run', action='store_true')
    ap.add_argument('--inference-run', type=Path, required=True)
    ap.add_argument('--base-url', default='http://127.0.0.1:8765')
    ap.add_argument('--workflow-version', required=True)
    ap.add_argument('--output', type=Path, required=True)
    args = ap.parse_args()
    if not args.owner_run:
        raise SystemExit('Requires --owner-run AFTER successful inference')
    verify(args.inference_run)
    run = json.loads((args.inference_run / 'run.json').read_text())
    url = urllib.parse.urlsplit(args.base_url)
    if (url.scheme != 'http' or url.hostname not in ['127.0.0.1', 'localhost'] or url.username or url.password
            or url.path not in ['', '/'] or url.query or url.fragment):
        raise SystemExit('Use loopback HTTP, locally or through a verified SSH tunnel')
    token = os.environ.get('TP_INFERENCE_TOKEN', '')
    if len(token) < 32:
        raise SystemExit('Set TP_INFERENCE_TOKEN in protected environment, length >=32')
    args.output.mkdir(parents=True, exist_ok=False)
    record = dict(status='STARTED', quality='NOT_ACCEPTED', inference_run=str(args.inference_run.resolve()))
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    def request(path, method='GET', body=None, auth=True, key=None):
        headers = {'Accept': 'application/json'}
        if auth:
            headers['Authorization'] = 'Bearer ' + token
        if key:
            headers['Idempotency-Key'] = key
        data = None
        if body is not None:
            data = json.dumps(body, sort_keys=True).encode(); headers['Content-Type'] = 'application/json'
        req = urllib.request.Request(args.base_url.rstrip('/') + path, data=data, headers=headers, method=method)
        try:
            response = opener.open(req, timeout=30)
        except urllib.error.HTTPError as exc:
            response = exc
        with response:
            raw = response.read(20 * 1024**2 + 1)
            if len(raw) > 20 * 1024**2:
                raise ValueError('HTTP response exceeds 20MiB')
            return response.code, raw, response.headers.get_content_type()
    try:
        if request('/v1/health', auth=False)[0] != 401:
            raise ValueError('Expected unauthenticated health 401')
        status, raw, _ = request('/v1/health'); health = json.loads(raw)
        if (status != 200 or health['status'] != 'ready' or health['queueDepth'] != 0
                or health['modelVersion'] != run['converted_lora_sha256']
                or health['workflowVersion'] != args.workflow_version):
            raise ValueError('Service not ready/empty or deployment version mismatch')
        body = dict(workflowVersion=args.workflow_version, modelVersion=run['converted_lora_sha256'],
                    scenario='motif', prompt='tptrx, textured ornament, one isolated blue lobed flower, centered on a white background, generous empty margins',
                    seed=20261008, width=1024, height=1024, steps=30, guidanceScale=5.0, loraScale=1.0, templateId=None)
        bad = dict(body, scenario='unsupported_smoke_scenario')
        if request('/v1/jobs', 'POST', bad, key=str(uuid.uuid4()))[0] != 422:
            raise ValueError('Expected unsupported scenario 422')
        key = str(uuid.uuid4())
        write_json(args.output / 'request.json', dict(idempotency_key=key, body=body))
        record['status'] = 'SUBMISSION_STARTED_NO_AUTOMATIC_RETRY'
        write_json(args.output / 'http.json', record)
        status, raw, _ = request('/v1/jobs', 'POST', body, key=key)
        if status != 202:
            raise ValueError(f'Submit HTTP {status}; inspect separately prepared service; do not retry blindly')
        submitted = json.loads(raw); job = str(uuid.UUID(submitted['jobId']))
        record.update(job_id=job, status='SUBMITTED'); write_json(args.output / 'http.json', record)
        status, raw, _ = request('/v1/jobs', 'POST', body, key=key)
        if status != 202 or json.loads(raw)['jobId'] != job:
            raise ValueError('Same idempotency key/body did not return same job')
        if request('/v1/jobs', 'POST', dict(body, prompt=body['prompt'] + '.'), key=key)[0] != 409:
            raise ValueError('Expected idempotency conflict 409')
        deadline = time.monotonic() + 900
        while True:
            status, raw, _ = request('/v1/jobs/' + job); state = json.loads(raw)
            if status != 200 or state['status'] not in ['queued', 'running', 'done', 'failed']:
                raise ValueError('Invalid job status')
            record['last_job_status'] = state['status']; write_json(args.output / 'http.json', record)
            if state['status'] == 'failed':
                raise ValueError('GPU HTTP job failed')
            if state['status'] == 'done':
                break
            if time.monotonic() > deadline:
                raise TimeoutError('HTTP deadline; GPU may still be running; inspect VM before stopping')
            time.sleep(5)
        status, raw, mime = request('/v1/jobs/' + job + '/image')
        meta = state['result']
        if status != 200 or mime != 'image/png' or hashlib.sha256(raw).hexdigest() != meta['sha256'] or len(raw) != meta['bytes']:
            raise ValueError('Result HTTP/MIME/SHA/size mismatch')
        from PIL import Image
        with Image.open(io.BytesIO(raw)) as im:
            im.load()
            if im.format != 'PNG' or im.size != (1024, 1024):
                raise ValueError('Invalid HTTP PNG')
        (args.output / 'result.png').write_bytes(raw)
        write_json(args.output / 'job.json', state)
        record.update(status='HTTP_SMOKE_PASS_REVIEW_REQUIRED', result_sha256=meta['sha256'])
    except Exception as exc:
        record.update(status='FAILED_OR_UNCERTAIN', error=f'{type(exc).__name__}: {exc}')
        raise
    finally:
        write_json(args.output / 'http.json', record)
    print(record['status'])

if __name__ == '__main__':
    main()
