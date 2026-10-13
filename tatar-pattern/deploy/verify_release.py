#!/usr/bin/env python3
"""Verify the delivered file set; optionally verify loaded Docker image contents."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parent.parent

def sha256(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--images', action='store_true', help='Also inspect loaded images; does not start services')
    parser.add_argument('--allow-local-config', action='store_true', help='Allow only deploy/.env after ops.py init')
    args = parser.parse_args()
    hashes = json.loads((ROOT/'deploy/SOURCE-SHA256.json').read_text())
    expected = set(hashes) | {'deploy/SOURCE-SHA256.json'}
    actual = set()
    for path in ROOT.rglob('*'):
        if path.is_symlink():
            raise SystemExit(f'Symlink forbidden: {path.relative_to(ROOT)}')
        if path.is_file():
            actual.add(path.relative_to(ROOT).as_posix())
    if args.allow_local_config:
        actual.discard('deploy/.env')
    if actual != expected:
        raise SystemExit(f'File set mismatch: missing={sorted(expected-actual)}, extra={sorted(actual-expected)}')
    for name, expected_hash in hashes.items():
        if sha256(ROOT/name) != expected_hash:
            raise SystemExit(f'SHA-256 mismatch: {name}')
    manifest = json.loads((ROOT/'deploy/RELEASE-MANIFEST.json').read_text())
    if manifest['release'] != 'pilot-20261011-2':
        raise SystemExit('Unexpected release')
    if args.images:
        images = json.loads((ROOT/'deploy/IMAGES.json').read_text())['images']
        for item in images:
            # Classic Docker reports the config ID; containerd may report an index ID.
            info = json.loads(subprocess.check_output(['docker','image','inspect',item['tag']]))[0]
            if info['Os']+'/'+info['Architecture'] != 'linux/amd64':
                raise SystemExit(f'Wrong platform: {item["tag"]}')
            if info['RootFS']['Layers'] != item['rootfsDiffIds']:
                raise SystemExit(f'Wrong rootfs: {item["tag"]}')
            if info['Id'] not in {item['sourceImageId'], item['configDigest'], item['platformManifestDigest'], item.get('buildIndexDigest')}:
                raise SystemExit(f'Wrong image ID: {item["tag"]}')
            print(f'IMAGE PASS {item["tag"]} linux/amd64')
    print(f'RELEASE PASS {manifest["release"]}: {len(hashes)} file SHA-256 values, exact file set')

if __name__ == '__main__':
    main()
