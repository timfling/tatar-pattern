#!/usr/bin/env python3
"""Read current GPU environment offline; no torch import, downloads or inference.

Run with existing GPU .venv/bin/python. Produces private diagnostic JSON, not proof.
"""
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import importlib.util
import json
import os
from pathlib import Path
import platform
import subprocess
import tempfile

RUNTIME = Path('/srv/tatar-lora-kit')
# Populated from sealed53 payload by preparation on Mac.
EXPECTED = {'ai-assets/f03-wreath.png': '819bec8c84bbf7316694ad1cb60feafa18a87bf2219115e2709cdaf6facfbf60', 'ai-assets/f03-wreath.recipe.json': 'fb1e612138b7fb6f47222435d5889f2f941e4be0afa033e0d247016bcbd531f2', 'ai-assets/f07-hanging.png': 'ee76b52fa7d694344b1f09e2804bc5c40b813af954f13327d63d5016fa8cf060', 'ai-assets/f07-hanging.recipe.json': '2abc6c4cdf7b5f0cb681c6467e1415d125ae5be781552e9f70a543f356437763', 'ai-assets/f07-repeat.png': '91213803d6da70a30f57cf72dda187651018109eaa2a85b7ab281c08ffedb5eb', 'ai-assets/f07-repeat.recipe.json': '47e95765b15ac187e18a6309ae7e1075fb9b50b66fa806820e51fb506ef432dd', 'ai-assets/f08-directed.png': '01a8c335b36b5e81f72dfb407d7f12f29fbc61ad224a79c2a4b33489172fb1d4', 'ai-assets/f08-directed.recipe.json': '3d17650bb7aa89153e28976a4e419f39df735bf51f74722291138b7d3a8dc341', 'ai-assets/f10-directed.png': '2c4566b5fc57aff7aca75bad23c2c2fdee307a8b8f755ecb9de6fdd210098d7f', 'ai-assets/f10-directed.recipe.json': '18174c9e88eeb4374a24d7316cb5926c9ed5f73b1442a67bbd4d8d1f6eb883eb', 'ai-assets/f10-wreath.png': '5032b6b6ad6365873c147b72b2642326b261db2888c50be2f08014814699d25b', 'ai-assets/f10-wreath.recipe.json': '54817fbc4d43eb5607dfec432e5c3b649175d8d59d420858e88fb786596aad04', 'ai-assets/f14-directed.png': '8eee57a9476705e2d09c134906162878ea7dc45811c9f96da219c363c7d6ba9a', 'ai-assets/f14-directed.recipe.json': '79f81c9c4b32d33123c23fd91e849cba2c35d81627f1ff775b358fe5f7d2de7e', 'ai-assets/f14-panel.png': 'a41b2fe83eabfa9df69efe6b698d377d2b44fb81c2fbe0202eb89fd849585471', 'ai-assets/f14-panel.recipe.json': '8449d45888ba5b50f52c682cff3250f3aa5a45d1941edd4c4e3d7babd98902aa', 'ai-assets/f16-wreath.png': '2bc0dc229164940d8b9959e76d9a787340b8304cb1ea569e9812489698aef6c9', 'ai-assets/f16-wreath.recipe.json': '44f91d64c2f2b771ffdfe191cc5789ac6d8622ab2f89c0750e0b05b77460ebc8', 'ai-assets/f17-wreath.png': '08b811a9bb04dba3e2144d5c76640fcb197ba94aa2fbf17e8c491bdba9d2689b', 'ai-assets/f17-wreath.recipe.json': '2abd366b229922a7996917b7950714296ed39c23b6ffb5a00a54122a6327829f', 'ai-assets/f18-hanging.png': '4b434444ff92edf1d82b466cebba07fd5c3a93b147d361d6fc36c0d8b53323d9', 'ai-assets/f18-hanging.recipe.json': '9f31630e13046afe6ca7ef844ed5aa4e4a90c9d8e5b5f8b91a8b7f90392bb6fd', 'ai-assets/f21-panel.png': '84f00097bfafd4ac252e50707da39b521e6732f70a05ea8c290e5813b4ad8678', 'ai-assets/f21-panel.recipe.json': 'ce51e9f0a2b62176b34f2baba1f40c5253209df4e14acce8f5fefa2d2999511c', 'ai-assets/f24-wreath.png': '76d781b54f19b5e7c2dbdfeb983ac7011b3d5e817831f6fb0d7020acc960b8f9', 'ai-assets/f24-wreath.recipe.json': '50100cfaea677725e3de942648d75bc7482cc7d9ca836a16bdbea4fdb8d76eaa', 'ai-assets/f25-directed.png': '996079ec6d183c155fea51fa594c013956528734e72cd3736b45b98cf9e40ced', 'ai-assets/f25-directed.recipe.json': 'f283d8f4e01dc394b318830b058562996e89e24c6c35ba0789d8920e01ce8348', 'ai-assets/f25-panel.png': '1bebbe8cec764d7373deb8dc2fc4aabe4f03d2694deba7f08e4fee4ed3407fdf', 'ai-assets/f25-panel.recipe.json': 'd99215b40292f04a92b1cf1290dd6b3fa1e6f31401d03f523b32fcac518c8608', 'ai-assets/index.json': '0b4db23c05bd1df610b26908de4c7be035a684884c56a6e38c8af0a78d7e1764', 'service/profiles.json': 'ac91327148eb91a6db1d3b8bc60b2a98127993788d5f421ee64c73064eb63213', 'service/qualify.py': '0db54bc8f9ffb02491cb7817c29c5ff0df9680d0c9ac63a510d16ff672444f36', 'service/render_one.py': '5a537846c6a65715cbf8a714708f5e3bb3a4626ec208a645e0035d40e629ed0f', 'service/server.py': 'b2f7413b49e055ea07d107ab03752b3e9d810211c9a9aeb30bd8d9bf2db55a5f', 'service/workflow.py': 'd9f6748d38c1f7d3b5aa6ed72e3457d98b14f7ed5c1142b04413d93f1ff9f768'}


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def command(args):
    try:
        result = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60)
        return {'exitCode': result.returncode, 'stdout': result.stdout.decode(errors='replace'),
                'stderr': result.stderr.decode(errors='replace')}
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {'error': type(exc).__name__}


def main():
    os.umask(0o077)
    service = RUNTIME / 'service'
    report = {'checkedAt': datetime.now(timezone.utc).isoformat(),
              'bootId': Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
              'python': platform.python_version(), 'pythonExecutable': os.sys.executable,
              'uname': list(platform.uname()), 'osRelease': Path('/etc/os-release').read_text(),
              'noInference': True, 'currentQualification': False}
    report['distributions'] = sorted([{'name': d.metadata['Name'], 'version': d.version,
                                      'requires': d.requires or []}
                                     for d in importlib.metadata.distributions()], key=lambda d: d['name'].lower())
    report['runtimeSource'] = {name: {'expectedSha256': expected,
                                   'actualSha256': sha(RUNTIME / name) if (RUNTIME / name).is_file() else None}
                               for name, expected in EXPECTED.items()}
    same = all(v['actualSha256'] == v['expectedSha256'] for v in report['runtimeSource'].values())
    report['sourceMatchesSealedBaseline'] = same
    if same:
        # workflow.py baseline imports only standard library and verifies local SHA.
        spec = importlib.util.spec_from_file_location('tp_inventory_workflow', service / 'workflow.py')
        workflow = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(workflow)
        cfg = json.loads((service / 'config.json').read_text())
        try:
            report['deployment'] = workflow.deployment(cfg)
        except Exception as exc:
            report['deploymentVerificationError'] = str(exc)
        inventory = json.loads(Path(cfg['base_inventory_path']).read_text())
        report['baseInventory'] = inventory
        snapshot = inventory.get('snapshot_path')
        if snapshot:
            root = Path(snapshot)
            report['baseSnapshotFileSet'] = [{'path': str(p.relative_to(root)), 'symlink': p.is_symlink(),
                                             'resolved': str(p.resolve()), 'size': p.stat().st_size}
                                            for p in sorted(root.rglob('*')) if p.is_file()]
        paths = [RUNTIME, service, service / 'state', Path(cfg['adapter_path']),
                 Path(cfg['profiles_path']), Path(cfg['assets_dir']), Path(cfg['base_inventory_path'])]
        report['permissions'] = [{'path': str(p), 'uid': p.stat().st_uid, 'gid': p.stat().st_gid,
                                  'mode': oct(p.stat().st_mode & 0o7777)} for p in paths if p.exists()]
    report['system'] = {name: command(args) for name, args in {
        'gpu': ['nvidia-smi', '--query-gpu=name,driver_version,memory.total', '--format=csv,noheader'],
        'packages': ['dpkg-query', '-W', '-f=${Package}\t${Version}\n'],
        'listeners': ['ss', '-lnt'], 'ufw': ['ufw', 'status', 'verbose'],
        'ipv4Rules': ['iptables-save'], 'ipv6Rules': ['ip6tables-save'],
        'service': ['systemctl', 'show', 'tatar-inference.service', '-p', 'ActiveState', '-p', 'SubState',
                    '-p', 'User', '-p', 'KillMode', '-p', 'TimeoutStopUSec', '-p', 'Restart', '-p', 'UnitFileState'],
    }.items()}
    dest = Path('/srv/tatar-gpu-evidence')
    dest.mkdir(mode=0o700, exist_ok=True)
    descriptor, name = tempfile.mkstemp(prefix='runtime-inventory-', suffix='.json', dir=dest)
    os.close(descriptor)
    output = Path(name)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    output.chmod(0o600)
    print('GPU RUNTIME INVENTORY SAVED: ' + str(output))
    print('Runtime source matches sealed executable/assets baseline: ' + str(same))
    print('No inference; not security/qualification/worker proof. Download for review before qualification.')


if __name__ == '__main__':
    main()
