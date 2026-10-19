"""New contract/queue checks only. No socket bind, GPU, renderer or remote requests."""
import io
import json
from pathlib import Path
import sqlite3
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

import server
from qualify import reviewed_record
from workflow import BASE_REVISION, CONTRACT, MODEL, WORKFLOW, base_file, digest, inside, registry, resolved, validate

ROOT = Path(__file__).resolve().parents[2]
CFG = dict(assets_dir=str(ROOT/'tatar-pattern/backend/app/ai-assets'),
           profiles_path=str(Path(__file__).with_name('profiles.json')), admission_deadline_epoch=time.time()+600)


def request():
    return dict(contractVersion=CONTRACT, workflowVersion=WORKFLOW, modelVersion=MODEL,
                catalogVersion='2026-10-18.1', baseId='f10-wreath',
                baseSha256='5032b6b6ad6365873c147b72b2642326b261db2888c50be2f08014814699d25b',
                ornamentStyle='graphic', profileVersion='2026-10-18.local-v1', seed=20261008)


class ContractTests(unittest.TestCase):
    def test_hf_snapshot_blob_links_work_without_relaxing_asset_boundary(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            repo = root/'models--stabilityai--stable-diffusion-xl-base-1.0'
            snapshot = repo/'snapshots'/BASE_REVISION
            (snapshot/'unet').mkdir(parents=True)
            blobs = repo/'blobs'; blobs.mkdir()
            blob = blobs/'hash'; blob.write_bytes(b'pinned base fixture')
            link = snapshot/'unet/model.fp16.safetensors'; link.symlink_to(blob)
            self.assertEqual(base_file(snapshot, 'unet/model.fp16.safetensors'), blob.resolve())
            with self.assertRaises(ValueError): inside(snapshot, 'unet/model.fp16.safetensors')
            outside = root/'outside'; outside.write_bytes(b'not base cache')
            link.unlink(); link.symlink_to(outside)
            with self.assertRaises(ValueError): base_file(snapshot, 'unet/model.fp16.safetensors')
            for name in ('../../outside', str(outside)):
                with self.assertRaises(ValueError): base_file(snapshot, name)
            link.unlink(); blob.unlink(); blobs.rmdir(); blobs.symlink_to(root, target_is_directory=True)
            link.symlink_to(outside)
            with self.assertRaises(ValueError): base_file(snapshot, 'unet/model.fp16.safetensors')

    def test_twenty_eight_server_profiles_and_semantics(self):
        _, _, profiles = registry(CFG)
        self.assertEqual(len(profiles), 28)
        for p in profiles.values():
            r = request() | dict(baseId=p['baseId'], baseSha256=p['baseSha256'], ornamentStyle=p['ornamentStyle'], profileVersion=p['version'])
            self.assertIsNone(validate(r, CFG))
            m = resolved(r, CFG)
            self.assertEqual((m['steps'], m['strength']), (p['steps'], p['strength']))
            self.assertEqual(m['profileDigest'], digest(p))
            self.assertEqual(m['scheduler'], 'EulerAncestralDiscreteScheduler')
            self.assertIsNone(m['clipSkip'])
            self.assertIsNone(m['negativePrompt'])
            self.assertEqual(m['loraScale'], 1)

    def test_pending_new_bases_cannot_submit(self):
        for base in ('f17-wreath', 'f25-panel'):
            self.assertEqual(validate(request() | {'baseId': base, 'ornamentStyle': 'textured'}, CFG), 'AI_COMBINATION_UNAVAILABLE')

    def test_strength_is_per_server_profile_and_client_cannot_override_it(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'profiles.json'
            data = json.loads(Path(CFG['profiles_path']).read_text())
            cfg = CFG | {'profiles_path': str(path)}
            for strength in (.60, .65, .53, .54):
                data['profiles'][0]['strength'] = strength
                path.write_text(json.dumps(data))
                self.assertEqual(resolved(request(), cfg)['strength'], strength)
                self.assertEqual(validate(request() | {'strength': .76}, cfg), 'INVALID_PARAMETERS')
            for strength in (True, 0, -.1, 1.1, .001, '0.65', float('nan')):
                data['profiles'][0]['strength'] = strength
                path.write_text(json.dumps(data))
                with self.assertRaises(ValueError): registry(cfg)

    def test_client_cannot_supply_recipe_or_prompt(self):
        for key, value in [('prompt', 'text'), ('strength', .85), ('steps', 10), ('url', 'http://example.com')]:
            self.assertEqual(validate(request() | {key: value}, CFG), 'INVALID_PARAMETERS')

    def test_old_workflow_and_asset_version_are_rejected(self):
        for key, value in [('workflowVersion', 'tp-sdxl-fiber-v1'), ('modelVersion', 'old'),
                           ('baseSha256', 'other'), ('profileVersion', 'old'), ('catalogVersion', 'old')]:
            self.assertEqual(validate(request() | {key: value}, CFG), 'VERSION_MISMATCH')

    def test_untrusted_types_and_seed_limits(self):
        for value in (True, -1, 2147483648, 1.0, '1', None):
            self.assertEqual(validate(request() | {'seed': value}, CFG), 'INVALID_PARAMETERS')
        self.assertIsNone(validate(request() | {'seed': 2147483647}, CFG))
        for value in ([], {}, None, True):
            self.assertEqual(validate(request() | {'baseId': value}, CFG), 'INVALID_PARAMETERS')


class QueueTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = Path(self.temp.name)
        self.patches = patch.multiple(server, CFG=CFG, STORE=self.store, DB=self.store/'test.sqlite',
                                     READY=True, PREFLIGHT=True, QUALIFICATION=False,
                                     IDENTITY={'deploymentDigest': 'test'},
                                     QUALIFIED_PAIRS={('f10-wreath', 'graphic', resolved(request(), CFG)['profileDigest'])},
                                     DRAIN=threading.Event())
        self.patches.start()
        self.identity_patch = patch.object(server, 'current_identity', return_value=True)
        self.identity_patch.start()
        self.process_patch = patch.object(server.subprocess, 'Popen', side_effect=AssertionError('No renderer allowed'))
        self.process_mock = self.process_patch.start()
        with server.connect() as db:
            db.execute('create table jobs(id text primary key,request_key text unique,payload_sha text,status text,created real,finished real,error text,elapsed real,metadata text)')

    def tearDown(self):
        self.process_mock.assert_not_called()
        self.process_patch.stop()
        self.identity_patch.stop()
        self.patches.stop()
        self.temp.cleanup()

    def post(self, body, key='6dcfe0b1-005f-46c5-99da-df745eb1817a'):
        h = object.__new__(server.Handler)
        data = json.dumps(body).encode()
        h.path = '/v1/jobs'
        h.headers = {'Content-Type': 'application/json', 'Content-Length': str(len(data)), 'Idempotency-Key': key}
        h.rfile = io.BytesIO(data)
        h.authorized = lambda: True
        responses = []
        h.send_json = lambda status, payload: responses.append((status, payload))
        h.do_POST()
        return responses[0]

    def test_enqueue_and_idempotent_replay_even_during_drain(self):
        status, first = self.post(request())
        self.assertEqual(status, 202)
        server.DRAIN.set()
        status, replay = self.post(dict(reversed(list(request().items()))))
        self.assertEqual((status, replay['jobId']), (202, first['jobId']))
        status, conflict = self.post(request() | {'seed': 2})
        self.assertEqual((status, conflict['error']['code']), (409, 'IDEMPOTENCY_CONFLICT'))
        with server.connect() as db:
            self.assertEqual(db.execute('select count(*) from jobs').fetchone()[0], 1)

    def test_drain_rejects_new_job_without_queue_mutation(self):
        server.DRAIN.set()
        status, response = self.post(request())
        self.assertEqual((status, response['error']['code']), (503, 'SERVICE_DRAINING'))
        self.assertEqual(server.depth(), 0)

    def test_changed_deployment_does_not_enqueue(self):
        with patch.object(server, 'current_identity', return_value=False):
            status, response = self.post(request())
        self.assertEqual((status, response['error']['code']), (503, 'GPU_UNAVAILABLE'))
        self.assertEqual(server.depth(), 0)

    def test_unqualified_pair_is_blocked(self):
        with patch.object(server, 'QUALIFIED_PAIRS', set()):
            status, response = self.post(request())
        self.assertEqual((status, response['error']['code']), (503, 'GPU_UNAVAILABLE'))
        self.assertEqual(server.depth(), 0)

    def test_restart_does_not_change_persisted_idempotency(self):
        _, first = self.post(request())
        with server.connect() as db:
            db.execute("update jobs set status='failed',error='INFERENCE_INTERRUPTED'")
        with patch.object(server, 'READY', False), patch.object(server, 'current_identity', return_value=False):
            status, replay = self.post(request())
        self.assertEqual((status, replay['jobId'], replay['status']), (202, first['jobId'], 'failed'))

    def test_real_accepted_job_files_survive_daily_cleanup(self):
        _, kept = self.post(request())
        _, expired = self.post(request(), '859629d0-f341-4c57-9959-2c52d417d36e')
        with server.connect() as db:
            db.execute("update jobs set status='done',finished=?", (time.time()-8*86400,))
        for job in (kept['jobId'], expired['jobId']):
            server.file_for(job, '.png').write_bytes(b'unit file, not GPU proof')
        stop = threading.Event()
        with patch.multiple(server, QUALIFIED_JOB_IDS={kept['jobId']}, STOP=stop):
            with patch.object(stop, 'wait', side_effect=lambda seconds: stop.set()):
                server.maintenance()
        self.assertTrue(server.file_for(kept['jobId'], '.png').exists())
        self.assertFalse(server.file_for(expired['jobId'], '.png').exists())
        with server.connect() as db:
            self.assertEqual([r['id'] for r in db.execute('select id from jobs')], [kept['jobId']])


class ReadinessTests(unittest.TestCase):
    def test_restart_same_linux_boot_reuses_acceptance_but_vm_reboot_fails_closed(self):
        _, _, profiles = registry(CFG)
        p = profiles['f10-wreath', 'graphic']
        pair = dict(baseId=p['baseId'], ornamentStyle=p['ornamentStyle'], profileDigest=digest(p))
        record = dict(passed=True, httpVerified=True, deploymentDigest='deployment', bootId='linux-boot', completedProfiles=[pair])
        # In-memory fixtures only, never written to a service acceptance file.
        self.assertEqual(server.accepted_pairs(record, {'deploymentDigest': 'deployment'}, 'linux-boot', profiles, True),
                         {(p['baseId'], p['ornamentStyle'], digest(p))})
        for identity, boot, preflight in [({'deploymentDigest': 'changed'}, 'linux-boot', True),
                                           ({'deploymentDigest': 'deployment'}, 'new-linux-boot', True),
                                           ({'deploymentDigest': 'deployment'}, 'linux-boot', False)]:
            self.assertEqual(server.accepted_pairs(record, identity, boot, profiles, preflight), set())

    def test_merge_evidence_requires_same_boot_and_unchanged_png(self):
        from workflow import sha
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root/'test.png').write_bytes(b'unit fixture, not GPU evidence')
            paths = []
            for base in ('f03-wreath', 'f17-wreath'):
                path = root/(base+'.json')
                item = dict(baseId=base, ornamentStyle='graphic', profileDigest='test', image='test.png', outputSha256=sha(root/'test.png'))
                path.write_text(json.dumps(dict(status='HTTP_TECHNICAL_PASS', bootId='boot', deploymentDigest='deploy', completedProfiles=[item])))
                paths.append(path)
            self.assertEqual(len(reviewed_record(paths)['completedProfiles']), 2)
            d = json.loads(paths[1].read_text()); d['bootId'] = 'other'; paths[1].write_text(json.dumps(d))
            with self.assertRaises(ValueError): reviewed_record(paths)
            (root/'test.png').write_bytes(b'changed')
            with self.assertRaises(ValueError): reviewed_record(paths[:1])

    def test_completed_pair_from_interrupted_batch_can_be_reviewed_without_rerender(self):
        from workflow import sha
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); image = root/'test.png'; image.write_bytes(b'unit fixture only')
            path = root/'evidence.json'
            item = dict(baseId='f03-wreath', ornamentStyle='graphic', image=image.name, outputSha256=sha(image),
                        checks=dict(authWithoutToken=401, submit=202, idempotentReplay=202,
                                    conflict=409, poll=200, download=200, pngShaVerified=True))
            path.write_text(json.dumps(dict(status='RUNNING', deploymentDigest='deploy', bootId='boot',
                completedProfiles=[item], activeSubmission=dict(jobId='unfinished-other-job'))))
            with self.assertRaises(ValueError): reviewed_record([path])
            self.assertEqual(len(reviewed_record([path], ['f03-wreath:graphic'])['completedProfiles']), 1)
            with self.assertRaises(ValueError): reviewed_record([path], ['f03-wreath:textured'])


if __name__ == '__main__':
    unittest.main()
