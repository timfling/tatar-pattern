"""Manual health-only check from worker namespace; never writes HTTP proof.

No redirects, secrets or response bodies are printed. Does not enable AI or submit jobs.
"""
import json
import os
import sys
import urllib.request
from pathlib import Path


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def main():
    try:
        expected_workflow = os.environ.get('GPU_EXPECTED_WORKFLOW_VERSION', '')
        expected_model = os.environ.get('GPU_EXPECTED_MODEL_VERSION', '')
        if not expected_workflow or not expected_model:
            raise ValueError('Expected img2img versions not configured')
        token = Path('/run/secrets/gpu_bearer').read_text().strip()
        if not 32 <= len(token) <= 4096 or not token.isascii() or any(c in token for c in '\r\n'):
            raise ValueError('Invalid token file')
        request = urllib.request.Request('http://gpu-tunnel:18765/v1/health',
                                         headers={'Authorization': 'Bearer ' + token})
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
        with opener.open(request, timeout=5) as response:
            raw = response.read(65537)
            if len(raw) > 65536 or response.status != 200:
                raise ValueError('Invalid health response')
            body = json.loads(raw)
        if body.get('contractVersion') != 'tp-gpu-img2img/1.0' or body.get('catalogVersion') != '2026-10-18.1' or body.get('qualificationMode') is not False or body.get('draining') is not False or not body.get('deploymentDigest') or not body.get('bootId'):
            raise ValueError('Unexpected or draining GPU deployment')
        if body.get('status') != 'ready' or body.get('modelVersion') != expected_model or body.get('workflowVersion') != expected_workflow:
            raise ValueError('GPU not ready')
    except Exception:
        print('GPU_HTTP_HEALTH_UNAVAILABLE')
        return 1
    print('GPU_HTTP_HEALTH_OK_ONLY; no proof written, AI enablement not authorized')
    return 0


if __name__ == '__main__':
    sys.exit(main())
