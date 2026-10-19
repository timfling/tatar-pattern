"""Owner-run verification of existing GPU results from the deployed worker namespace.

Never submits inference. Run only in an explicitly authorized HTTP/GPU window.
The proof is deployment/boot/origin/pair specific and expires after 24 hours.
"""
import argparse
import json
import os
from pathlib import Path
import time
from uuid import uuid4

from app import ai_catalog
from app.ai_provider import configured_provider, CONTRACT, CATALOG, ProviderError


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--owner-run', action='store_true', required=True)
    parser.add_argument('--worker-namespace', action='store_true', required=True)
    parser.add_argument('--job-id', action='append', required=True)
    args = parser.parse_args()
    if os.getenv('TP_ENVIRONMENT') in ('local_project', 'isolated_test'):
        raise SystemExit('Proof requires deployed worker namespace; local tests cannot qualify readiness')
    provider = configured_provider()
    if provider is None or provider.proof_file is None:
        raise SystemExit('Configure GPU adapter and AI_GPU_HTTP_PROOF_FILE')
    try:
        health = provider.health(refresh=True)
        pairs = []
        evidence = []
        for job_id in args.job_id:
            status = provider.poll(job_id, timeout=15)
            if status.state != 'done':
                raise ProviderError('AI_GPU_RESULT_NOT_READY')
            meta = status.metadata
            if meta['deploymentDigest'] != health['deploymentDigest']:
                raise ProviderError('AI_GPU_METADATA_MISMATCH')
            _, profile = ai_catalog.select_profile(meta['baseId'], meta['ornamentStyle'], meta['profileVersion'])
            pair = next((q for q in health['profiles'] if provider._pair_matches(profile, q)), None)
            if pair is None:
                raise ProviderError('AI_GPU_PAIR_UNVERIFIED')
            provider.download(job_id, timeout=30, max_bytes=20 * 1024 * 1024)
            if pair not in pairs:
                pairs.append(pair)
            evidence.append({'jobId': job_id, 'sha256': provider._results[job_id]['sha256']})
        after = provider.health(refresh=True)
        if (after['deploymentDigest'], after['bootId']) != (health['deploymentDigest'], health['bootId']):
            raise ProviderError('AI_GPU_CONFIGURATION_CHANGED')
        proof = dict(schemaVersion='tp-gpu-worker-proof/1.0', checkedAt=time.time(), workerNamespace=True,
                     baseUrl=provider.base_url, contractVersion=CONTRACT, catalogVersion=CATALOG,
                     workflowVersion=provider.workflow_version, modelVersion=provider.model_version,
                     deploymentDigest=health['deploymentDigest'], bootId=health['bootId'], profiles=pairs,
                     results=evidence)
        path = provider.proof_file
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(path.name + '.' + uuid4().hex + '.tmp')
        try:
            with temporary.open('x') as stream:
                temporary.chmod(0o600)
                json.dump(proof, stream, ensure_ascii=False)
            temporary.replace(path)
        finally:
            temporary.unlink(missing_ok=True)
    except (ProviderError, ValueError, OSError) as exc:
        raise SystemExit(exc.code if isinstance(exc, ProviderError) else 'AI_GPU_PROBE_FAILED') from None
    print('GPU_WORKER_HTTP_VERIFIED: proof saved; release and material-transfer gates unchanged')


if __name__ == '__main__':
    main()
