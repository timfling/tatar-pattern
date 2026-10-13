#!/usr/bin/env python3
"""Repack an already verified release tree, with deterministic tar/gzip metadata."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tarfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True, help='Archive path outside the project tree')
    args = parser.parse_args()
    root = Path(__file__).resolve().parent.parent
    output = args.output.resolve()
    if output.is_relative_to(root):
        raise SystemExit('Archive must be outside the release root')
    subprocess.run([sys.executable, '-B', str(root/'deploy/verify_release.py')], check=True)
    manifest = json.loads((root/'deploy/RELEASE-MANIFEST.json').read_text())
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('xb') as target:
        with gzip.GzipFile(filename='', mode='wb', fileobj=target, mtime=0, compresslevel=1) as compressed:
            with tarfile.open(fileobj=compressed, mode='w', format=tarfile.PAX_FORMAT) as archive:
                files = sorted(p for p in root.rglob('*') if p.is_file())
                for path in files:
                    item = archive.gettarinfo(str(path), arcname='tatar-pattern/'+path.relative_to(root).as_posix())
                    item.uid = item.gid = 0
                    item.uname = item.gname = ''
                    item.mode = 0o644
                    item.mtime = manifest['archiveEpoch']
                    item.pax_headers = {}
                    with path.open('rb') as stream:
                        archive.addfile(item, stream)
    with output.open('rb') as stream:
        digest = hashlib.file_digest(stream, 'sha256').hexdigest()
    output.with_name(output.name+'.sha256').write_text(f'{digest}  {output.name}\n')
    print(json.dumps({'archive':str(output),'sha256':digest,'sizeBytes':output.stat().st_size}))

if __name__ == '__main__':
    main()
