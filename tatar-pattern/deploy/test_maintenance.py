"""Destructive-boundary regression tests, with only temporary directories/mocked restic."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
import maintenance
import ops

class RetentionTests(unittest.TestCase):
    def test_only_expired_backup_paths_are_removed_and_live_storage_survives(self):
        now = datetime(2026, 10, 19, tzinfo=timezone.utc)
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            for folder in ('backups', 'migration-backups', 'storage', 'logs'):
                (root/folder).mkdir()
            expired = root/'backups/20261001T000000Z-abcdef'
            expired.mkdir(); (expired/'manifest.json').write_text('{}')
            old_dump = root/'migration-backups/backend_20261001.dump'; old_dump.write_bytes(b'x')
            live = root/'storage/job.png'; live.write_bytes(b'keep')
            foreign = root/'backups/foreign-project'; foreign.mkdir()
            for path in (expired, old_dump, live, foreign):
                os.utime(path, (now.timestamp()-20*86400,)*2)
            (root/'logs/runtime-2026-10-01.log').write_text('old')
            recent = root/'logs/runtime-2026-10-19.log'; recent.write_text('keep')
            maintenance.local_retention(root, now, root/'logs')
            self.assertFalse(expired.exists()); self.assertFalse(old_dump.exists())
            self.assertTrue(live.exists()); self.assertTrue(foreign.exists()); self.assertTrue(recent.exists())

    def test_backup_symlink_is_refused(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp); (root/'backups').symlink_to(root/'other')
            with self.assertRaises(RuntimeError):
                maintenance.local_retention(root)

    def test_remote_expiry_deletes_exact_tagged_ids_not_other_snapshots(self):
        now = datetime(2026,10,19,tzinfo=timezone.utc)
        snapshots = [{'id':'old-id','time':'2026-10-01T00:00:00Z','tags':[maintenance.TAG]},
                     {'id':'new-id','time':'2026-10-19T00:00:00Z','tags':[maintenance.TAG]}]
        with patch.dict(os.environ, {'RESTIC_REPOSITORY':'test','RESTIC_PASSWORD_FILE':'unused'}), \
             patch.object(maintenance.subprocess,'check_output',side_effect=[json.dumps(snapshots).encode(), json.dumps(snapshots[1:]).encode()]), \
             patch.object(maintenance.subprocess,'run') as run:
            maintenance.remote_retention(now)
            run.assert_called_once_with(['restic','forget','old-id','--prune'], check=True)

    def test_old_or_foreign_drain_markers_do_not_acknowledge_worker(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root/'runtime-2026-10-19.log').write_text(
                '2026-10-19T12:00:00+00:00 tp-worker AI_WORKER_DRAINED: stale\n'
                '2026-10-19T13:01:00+00:00 tp-other AI_WORKER_DRAINED: foreign\n')
            self.assertEqual(ops.calendar_worker_logs('worker','2026-10-19T13:00:00+00:00',root), b'')
            with (root/'runtime-2026-10-19.log').open('a') as stream:
                stream.write('2026-10-19T13:02:00+00:00 tp-worker AI_WORKER_DRAINED: current\n')
            self.assertIn(b'current',ops.calendar_worker_logs('worker','2026-10-19T13:00:00+00:00',root))

if __name__ == '__main__':
    unittest.main()
