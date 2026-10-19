"""Read-only operator expiry report. No health call, submit or renewal; not readiness proof."""
import json
import math
import os
from datetime import datetime,timezone
from pathlib import Path
import time


def main():
    path=Path(os.environ['AI_GPU_HTTP_PROOF_FILE'])
    try:
        proof=json.loads(path.read_text());checked=float(proof['checkedAt']);now=time.time()
        if not math.isfinite(checked) or not 0<=checked<=now:raise ValueError('Invalid timestamp')
        remaining=checked+86400-now
        stamp=lambda t:datetime.fromtimestamp(t,timezone.utc).isoformat()
        print(json.dumps(dict(checkedAtUTC=stamp(checked),expiresAtUTC=stamp(checked+86400),
                             remainingSeconds=max(0,int(remaining)),expired=remaining<0,
                             pairCount=len(proof['profiles']),bootId=proof['bootId'],deploymentDigest=proof['deploymentDigest'],
                             refreshCommand='python -m scripts.ai_gpu_probe --owner-run --worker-namespace --job-id <each retained accepted qualification UUID>',
                             healthStillRequired=True)))
        if remaining<=0:raise SystemExit(1)
    except (OSError,ValueError,KeyError,TypeError):
        raise SystemExit('GPU_PROOF_MISSING_OR_INVALID; operator GET-probe required; no automatic inference') from None

if __name__=='__main__':main()
