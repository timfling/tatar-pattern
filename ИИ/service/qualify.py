"""Explicit owner-run GPU HTTP qualification, then separate visual acceptance.

Never invoked by server/startup/tests. Does not provision GPU or stop cloud billing.
"""
import argparse
import datetime
import json
import os
from pathlib import Path
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

from workflow import CONTRACT, MODEL, WORKFLOW, sha

MAX_PAIRS = 30  # Fifteen fixed bases, two styles; no parameter grid.


def reviewed_record(paths, requested=None):
    """Combine real successful evidence from one boot/deployment, without inference."""
    selected, identities, hashes = {}, set(), []
    for path in paths:
        evidence = json.loads(path.read_text())
        partial = evidence.get('status') == 'RUNNING' and bool(requested)
        if (evidence.get('status') != 'HTTP_TECHNICAL_PASS' and not partial) or not evidence.get('completedProfiles'):
            raise ValueError('Successful current HTTP evidence required')
        identities.add((evidence['deploymentDigest'], evidence['bootId']))
        hashes.append(sha(path))
        for item in evidence['completedProfiles']:
            pair = item['baseId'] + ':' + item['ornamentStyle']
            if requested and pair not in requested:
                continue
            if partial and item.get('checks') != dict(authWithoutToken=401, submit=202,
                    idempotentReplay=202, conflict=409, poll=200, download=200, pngShaVerified=True):
                raise ValueError('Incomplete per-pair HTTP checks; cannot accept partial run')
            if sha(path.parent / item['image']) != item['outputSha256']:
                raise ValueError('Reviewed output changed/missing')
            if pair in selected and selected[pair] != item:
                raise ValueError('Conflicting evidence for pair; choose one evidence file')
            selected[pair] = item
    if len(identities) != 1 or not selected or len(selected) > MAX_PAIRS:
        raise ValueError('Evidence must share one deployment and Linux boot; select 1–30 pairs')
    if requested and set(selected) != set(requested):
        raise ValueError('Selected pair missing from successful evidence')
    deployment_digest, boot_id = identities.pop()
    return dict(deploymentDigest=deployment_digest, bootId=boot_id,
                completedProfiles=list(selected.values()), passed=True, httpVerified=True,
                evidenceSha256=hashes[0] if len(hashes) == 1 else None, evidenceSha256s=hashes,
                acceptedAt=datetime.datetime.now(datetime.timezone.utc).isoformat())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--owner-run', action='store_true')
    ap.add_argument('--url', default='http://127.0.0.1:8765')
    ap.add_argument('--pair', action='append', help='baseId:graphic or baseId:textured, max 30')
    ap.add_argument('--output', type=Path)
    ap.add_argument('--evidence', type=Path, action='append', help='Repeat to merge successful batches from same boot/deployment')
    ap.add_argument('--record', type=Path)
    ap.add_argument('--accept-reviewed', action='store_true')
    args = ap.parse_args()
    if not args.owner_run:
        ap.error('Requires explicit --owner-run; may invoke paid inference')
    if args.accept_reviewed:
        if not args.evidence or not args.record or args.record.exists():
            ap.error('Set existing --evidence and NEW --record')
        if args.pair:
            requested = set(args.pair)
            if len(requested) != len(args.pair) or not 1 <= len(requested) <= MAX_PAIRS:
                ap.error('Select 1–30 unique completed pairs')
        try:
            record = reviewed_record(args.evidence, args.pair)
        except (ValueError, OSError, KeyError) as error:
            ap.error(str(error))
        selected = record['completedProfiles']
        args.record.parent.mkdir(parents=True, exist_ok=True)
        args.record.write_text(json.dumps(record, indent=2)+'\n')
        print('Accepted reviewed HTTP evidence; restart normal service, backend gates remain separate')
        jobs = ' '.join('--job-id ' + str(uuid.UUID(p['jobId'])) for p in selected)
        print('Then run INSIDE deployed Beget worker namespace (no new inference):')
        print('python -m scripts.ai_gpu_probe --owner-run --worker-namespace ' + jobs)
        return
    if not args.pair or len(args.pair) > MAX_PAIRS or len(set(args.pair)) != len(args.pair) or not args.output:
        ap.error('Supply 1–30 unique --pair and a NEW --output directory')
    url = urllib.parse.urlsplit(args.url)
    if url.scheme != 'http' or url.hostname not in ('127.0.0.1', 'gpu-tunnel') or url.username or url.password or url.path or url.query or url.fragment:
        ap.error('Only agreed loopback/tunnel HTTP origin allowed')
    token = os.environ.get('TP_INFERENCE_TOKEN')
    token_file = os.environ.get('TP_INFERENCE_TOKEN_FILE')
    if bool(token) == bool(token_file):
        ap.error('Set exactly one TP_INFERENCE_TOKEN or TP_INFERENCE_TOKEN_FILE')
    if token_file:
        token = Path(token_file).read_text().strip()
    # Ignore ambient proxies and redirects; URLs are constructed from known routes only.
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *args, **kwargs):
            return None
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())

    def call(method, path, body=None, key=None, auth=True, binary=False):
        headers = {'Content-Type': 'application/json'}
        if auth:
            headers['Authorization'] = 'Bearer '+token
        if key:
            headers['Idempotency-Key'] = key
        request = urllib.request.Request(args.url+path, headers=headers,
                    data=json.dumps(body).encode() if body is not None else None, method=method)
        try:
            response = opener.open(request, timeout=30 if method == 'POST' or binary else 5)
        except urllib.error.HTTPError as error:
            response = error
        with response:
            data = response.read(20*1024**2+1 if binary else 1024*1024)
            if len(data) > 20*1024**2:
                raise ValueError('Result exceeds limit')
            return response.status, data if binary else json.loads(data)

    args.output.mkdir(parents=True, exist_ok=False)
    status, health = call('GET', '/v1/health')
    if status != 503 or health.get('qualificationMode') is not True or not health.get('deploymentDigest') or not health.get('bootId'):
        raise ValueError('Start qualified GPU service with --qualification-mode; health must stay unavailable')
    status, _ = call('GET', '/v1/health', auth=False)
    if status != 401:
        raise ValueError('Bearer is not enforced')
    evidence = dict(status='RUNNING', deploymentDigest=health['deploymentDigest'], bootId=health['bootId'], completedProfiles=[])
    evidence_path = args.output / 'http-evidence.json'
    evidence_path.write_text(json.dumps(evidence, indent=2)+'\n')
    for pair in args.pair:
        pair_start = time.monotonic()
        base, style = pair.split(':')
        profile = next(p for p in health['profiles'] if p['baseId'] == base and p['ornamentStyle'] == style)
        body = dict(contractVersion=CONTRACT, workflowVersion=WORKFLOW, modelVersion=MODEL,
                    catalogVersion=health['catalogVersion'], baseId=base, baseSha256=profile['baseSha256'],
                    ornamentStyle=style, profileVersion=profile['profileVersion'], seed=20261008)
        request_id = str(uuid.uuid4())
        evidence['activeSubmission'] = dict(requestId=request_id, body=body, status='SUBMITTING')
        evidence_path.write_text(json.dumps(evidence, indent=2)+'\n')
        code, submitted = call('POST', '/v1/jobs', body, request_id)
        if code != 202:
            raise ValueError('Submit failed: '+str(submitted))
        job = str(uuid.UUID(submitted['jobId']))
        evidence['activeSubmission'].update(jobId=job, status='POLLING')
        evidence_path.write_text(json.dumps(evidence, indent=2)+'\n')
        code, repeated = call('POST', '/v1/jobs', body, request_id)
        if code != 202 or repeated['jobId'] != job:
            raise ValueError('Idempotent replay failed')
        code, conflict = call('POST', '/v1/jobs', body | {'seed': 20261009}, request_id)
        if code != 409 or conflict.get('error', {}).get('code') != 'IDEMPOTENCY_CONFLICT':
            raise ValueError('Idempotency conflict failed')
        deadline = time.monotonic()+900
        while True:
            code, result = call('GET', '/v1/jobs/'+job)
            if code != 200 or result['status'] == 'failed':
                raise ValueError('Render/poll failed: '+str(result))
            if result['status'] == 'done':
                break
            if time.monotonic() >= deadline:
                raise TimeoutError('Owner HTTP deadline; GPU may still run')
            time.sleep(5)
        meta = result['metadata']
        if meta['deploymentDigest'] != evidence['deploymentDigest'] or meta['profileDigest'] != profile['profileDigest']:
            raise ValueError('Result identity mismatch')
        code, data = call('GET', '/v1/jobs/'+job+'/image', binary=True)
        if code != 200:
            raise ValueError('Download failed')
        image = args.output / (base+'_'+style+'.png')
        image.write_bytes(data)
        from PIL import Image
        with Image.open(image) as im:
            im.load()
            if im.format != 'PNG' or im.mode != 'RGB' or im.size != (1024, 1024) or sha(image) != result['result']['sha256']:
                raise ValueError('Downloaded output invalid')
            metrics = json.loads(im.info['tp_img2img'])
        if (metrics['deployment']['deploymentDigest'] != evidence['deploymentDigest']
                or metrics['metadata'] != {k: v for k, v in meta.items() if k != 'deploymentDigest'}
                or metrics['denoisingSteps'] != int(meta['steps'] * meta['strength'])):
            raise ValueError('PNG runtime metrics/metadata mismatch')
        evidence['completedProfiles'].append(dict(baseId=base, ornamentStyle=style,
            profileDigest=profile['profileDigest'], profileVersion=profile['profileVersion'],
            jobId=job, requestId=request_id, image=image.name, outputSha256=sha(image), metadata=meta,
            metrics=metrics, serverElapsedSeconds=result['elapsedSeconds'],
            submitToDownloadSeconds=time.monotonic()-pair_start,
            checks=dict(authWithoutToken=401, submit=202, idempotentReplay=202, conflict=409,
                        poll=200, download=200, pngShaVerified=True)))
        evidence.pop('activeSubmission', None)
        evidence_path.write_text(json.dumps(evidence, indent=2)+'\n')
    evidence['status'] = 'HTTP_TECHNICAL_PASS'
    evidence_path.write_text(json.dumps(evidence, indent=2)+'\n')
    print('HTTP technical PASS; inspect PNGs before separate --accept-reviewed. Cloud billing continues until owner stops it.')


if __name__ == '__main__':
    main()
