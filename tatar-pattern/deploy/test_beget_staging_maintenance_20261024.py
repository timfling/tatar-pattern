"""Offline safety regressions; fake Docker/DB, temporary storage only."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch, Mock
import beget_staging_maintenance_20261024 as m


def worker(state='running', code=0):
    return {'Id': 'a' * 64, 'State': {'Status': state, 'ExitCode': code, 'OOMKilled': False,
            'StartedAt': '2026-10-24T11:00:00Z', 'FinishedAt': '2026-10-24T12:00:00Z'}}


class Safety(unittest.TestCase):
    def test_drain_exit75_and_missing_marker_fail(self):
        for after, logs in [(worker('exited', 75), b'AI_WORKER_DRAINED:'), (worker('exited'), b'')]:
            with self.subTest(after=after, logs=logs), tempfile.TemporaryDirectory() as tmp:
                dc = Mock()
                with patch.object(m, 'worker_info', return_value=after), patch.object(m.subprocess, 'check_output', return_value=logs):
                    with self.assertRaises(RuntimeError):
                        m.drain(dc, worker(), Path(tmp))
                self.assertFalse(json.loads((Path(tmp) / m.LEDGER).read_text())['confirmed'])
                dc.assert_called_once_with('stop', '-t', '960', 'ai-worker')

    def test_container_replacement_blocks_drain(self):
        after = worker('exited'); after['Id'] = 'b' * 64
        with tempfile.TemporaryDirectory() as tmp, patch.object(m, 'worker_info', return_value=after):
            with self.assertRaisesRegex(RuntimeError, 'changed'):
                m.drain(Mock(), worker(), Path(tmp))

    def test_successful_drain_ledger_binds_container_and_run(self):
        after = worker('exited')
        with tempfile.TemporaryDirectory() as tmp, patch.object(m, 'worker_info', return_value=after), \
             patch.object(m.subprocess, 'check_output', return_value=b'AI_WORKER_DRAINED: saved') as logs:
            root = Path(tmp)
            m.drain(Mock(), worker(), root)
            self.assertEqual(logs.call_args.args[0][-1], worker()['Id'])
            m.stopped_worker_safe(Mock(), after, root)
            changed = copy.deepcopy(after); changed['State']['StartedAt'] = 'new run'
            with self.assertRaises(RuntimeError):
                m.stopped_worker_safe(Mock(), changed, root)

    def test_preexisting_failed_worker_blocks_snapshot_before_stop_or_dump(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(m, 'worker_info', return_value=worker('exited', 75)):
            ops = Mock(); dc = Mock(return_value=b'db backend frontend proxy gpu-tunnel')
            with self.assertRaises(RuntimeError):
                m.snapshot(dc, {'RELEASE': 'test'}, ops, Path(tmp))
            ops.pg.assert_not_called()
            self.assertFalse(any(c.args[0] == 'stop' for c in dc.call_args_list))
            self.assertFalse(list(Path(tmp).rglob('manifest.json')))

    def test_uncertain_drain_never_dumps_restarts_or_stops_tunnel(self):
        events = []
        def dc(*args, **kwargs):
            events.append(args)
            return b'db backend frontend proxy ai-worker gpu-tunnel'
        with tempfile.TemporaryDirectory() as tmp, patch.object(m, 'worker_info', return_value=worker()), \
             patch.object(m, 'drain', side_effect=RuntimeError('uncertain')):
            ops = Mock()
            with self.assertRaises(RuntimeError):
                m.snapshot(dc, {'RELEASE': 'test'}, ops, Path(tmp))
            ops.pg.assert_not_called()
            self.assertFalse(any(e[0] == 'start' for e in events))
            self.assertFalse(any('gpu-tunnel' in e for e in events))
            self.assertFalse(list(Path(tmp).rglob('manifest.json')))

    def test_successful_backup_drains_before_dump_and_restores_only_flat(self):
        events = []
        def dc(*args, **kwargs):
            events.append(args)
            return b'db backend frontend proxy ai-worker gpu-tunnel'
        with tempfile.TemporaryDirectory() as tmp, patch.object(m, 'worker_info', return_value=worker()), \
             patch.object(m, 'drain', side_effect=lambda *a: events.append(('drain-confirmed',))):
            root = Path(tmp); (root / 'storage').mkdir()
            ops = Mock()
            ops.pg.side_effect = lambda *a: events.append(('dump',)) or b'x' * 101
            ops.storage_hashes.return_value = {}; ops.counts.return_value = {'users': 0}
            ops.digest.return_value = 'hash'
            target = m.snapshot(dc, {'RELEASE': 'test'}, ops, root)
            self.assertTrue((target / 'manifest.json').is_file())
            self.assertLess(events.index(('drain-confirmed',)), events.index(('dump',)))
            self.assertEqual(events[-1], ('start', '--wait', 'proxy', 'frontend', 'backend'))
            self.assertFalse(any('gpu-tunnel' in e for e in events))

    def test_missing_worker_with_unfinished_jobs_rejected(self):
        with self.assertRaisesRegex(RuntimeError, 'unfinished'):
            m.stopped_worker_safe(Mock(return_value=b'1'), None)
        m.stopped_worker_safe(Mock(return_value=b'0'), None)


if __name__ == '__main__':
    unittest.main()
