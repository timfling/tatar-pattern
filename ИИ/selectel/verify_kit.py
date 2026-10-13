"""Offline verification of the unpacked owner's kit (never uploads anything)."""
from pathlib import Path
import hashlib, json
ROOT = Path(__file__).resolve().parents[1]

def main():
    manifest = ROOT / 'kit-manifest.json'
    if not manifest.exists():
        raise SystemExit('kit-manifest.json missing: use the rebuilt owner-upload.zip')
    entries = json.loads(manifest.read_text())['entries']
    for entry in entries:
        path = (ROOT / entry['path']).resolve()
        if not path.is_relative_to(ROOT) or not path.is_file():
            raise SystemExit('Missing or invalid kit entry: ' + entry['path'])
        if hashlib.sha256(path.read_bytes()).hexdigest() != entry['sha256']:
            raise SystemExit('Kit SHA mismatch: ' + entry['path'])
    print(f'Kit verified: {len(entries)} file SHA256 values. This is not GPU smoke.')

if __name__ == '__main__':
    main()
