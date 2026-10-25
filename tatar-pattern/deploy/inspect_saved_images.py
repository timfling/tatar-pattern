"""Read saved OCI/Docker images without Docker or executing their contents."""
import hashlib
import json
from pathlib import Path
import tarfile

import argparse
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--root',type=Path,required=True)
parser.add_argument('--output',type=Path,required=True)
args=parser.parse_args()
release=args.root.resolve()
records = json.loads((release / "deploy/IMAGES.json").read_text())["images"]
def sha(raw): return hashlib.sha256(raw).hexdigest()
expected = {}
for zone, prefix in [("backend/app", "app/backend/app"), ("backend/scripts", "app/backend/scripts"),
                     ("db/migrations", "app/db/migrations"), ("frontend/src", "app/src"),
                     ("frontend/public", "app/public")]:
    for path in (release / zone).rglob("*"):
        if path.is_file():
            expected[prefix + "/" + path.relative_to(release / zone).as_posix()] = sha(path.read_bytes())
expected["opt/tunnel-entrypoint.py"] = sha((release / "deploy/tunnel-entrypoint.py").read_bytes())
report = {"executedImages": False, "images": []}
release_manifest=json.loads((release/'deploy/RELEASE-MANIFEST.json').read_text())
with tarfile.open(release / release_manifest['images']['archive']['path']) as archive:
    manifests = json.load(archive.extractfile("manifest.json"))
    for image in records:
        saved = next(m for m in manifests if image["tag"] in (m.get("RepoTags") or []))
        raw = archive.extractfile(saved["Config"]).read()
        config = json.loads(raw)
        assert "sha256:" + sha(raw) == image["configDigest"]
        assert config["rootfs"]["diff_ids"] == image["rootfsDiffIds"]
        assert config["architecture"] == "amd64" and config["os"] == "linux"
        selected = ["app/backend/app/", "app/backend/scripts/", "app/db/migrations/"] if "-backend:" in image["tag"] else ["app/src/", "app/public/"] if "-frontend:" in image["tag"] else ["opt/tunnel-entrypoint.py"] if "-tunnel:" in image["tag"] else []
        found = {}
        if selected:
            for layer in saved["Layers"]:
                # Streaming nested tar; no extraction or execution of image files.
                with tarfile.open(fileobj=archive.extractfile(layer), mode="r|*") as contents:
                    for entry in contents:
                        name = entry.name.removeprefix("./").lstrip("/")
                        if any(name.startswith(p) for p in selected):
                            if "/.wh." in name:
                                raise RuntimeError("Whiteout requires explicit overlay handling: " + name)
                            if entry.isfile(): found[name] = sha(contents.extractfile(entry).read())
        relevant = {n: h for n, h in expected.items() if any(n.startswith(p) for p in selected)}
        missing = sorted(set(relevant) - found.keys())
        changed = sorted(n for n in relevant if n in found and relevant[n] != found[n])
        extra = sorted(set(found) - relevant.keys())
        assert not (missing or changed or extra), (image["tag"], missing, changed, extra)
        report["images"].append({"tag": image["tag"], "configDigest": image["configDigest"],
            "platform": "linux/amd64", "rootfsMetadataMatches": True,
            "snapshotSourceFilesVerified": len(relevant), "sourceMatch": True if relevant else None})
args.output.write_text(json.dumps(report, indent=2)+"\n")
print(json.dumps(report, indent=2))
