"""Download ONLY the fixed SDXL Base fp16 snapshot. Owner executes on VM."""
import argparse
from pathlib import Path
from common import REPO, REVISION, sha, write_json

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--owner-run', action='store_true')
    ap.add_argument('--output', type=Path, required=True)
    args = ap.parse_args()
    if not args.owner_run:
        raise SystemExit('Requires --owner-run')
    if args.output.exists():
        raise SystemExit('Inventory exists; use a new output filename')
    from huggingface_hub import snapshot_download
    folder = Path(snapshot_download(REPO, revision=REVISION,
                  allow_patterns=['model_index.json', '*/config.json', 'scheduler/*.json',
                                  'tokenizer/*', 'tokenizer_2/*', '*/*.fp16.safetensors'],
                  ignore_patterns=['*.bin', '*.onnx', '*.msgpack']))
    entries = [dict(path=str(p.relative_to(folder)), bytes=p.stat().st_size, sha256=sha(p))
               for p in sorted(folder.rglob('*')) if p.is_file()]
    write_json(args.output, dict(repo=REPO, revision=REVISION, snapshot_path=str(folder.resolve()), files=entries))
    print('Pinned snapshot saved; inventory:', args.output)

if __name__ == '__main__':
    main()
