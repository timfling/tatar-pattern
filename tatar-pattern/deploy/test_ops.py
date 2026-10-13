"""Release gate regression checks; never starts Docker or publishes."""
import unittest
from unittest.mock import patch
import json
import sys
import ops

class ReleaseGateTests(unittest.TestCase):
    def test_floor_and_exact_match(self):
        for version in ('16.3.8', '16.4.0', '17.0.0'):
            ops.validate_next_version(version, version)
        for version in ('15.9.99', '16.3.7', '16.2.99'):
            with self.subTest(version=version), self.assertRaises(RuntimeError):
                ops.validate_next_version(version, version)
        with self.assertRaisesRegex(RuntimeError, 'differs'):
            ops.validate_next_version('16.3.8', '16.4.0')
        for version in ('16.4.0-canary.1', '^16.4.0', 'garbage', '16.4', '016.4.0'):
            with self.subTest(version=version), self.assertRaises(RuntimeError):
                ops.validate_next_version(version, '16.4.0')
        with self.assertRaises(RuntimeError):
            ops.validate_next_version('16.4.0', '^16.4.0')

    def test_runtime_reads_inspected_image(self):
        metadata = json.dumps([{'Os': 'linux', 'Architecture': 'amd64', 'Id': 'sha256:test'}]).encode()
        with patch.object(ops.subprocess, 'check_output', side_effect=[metadata, b'16.4.0\n']) as docker:
            result = ops.check_frontend('test')
        self.assertEqual(result['sourceNext'], result['runtimeNext'])
        command = docker.call_args_list[1].args[0]
        self.assertIn('sha256:test', command)
        self.assertIn("require('next/package.json').version", command)
        self.assertIn('none', command)

    def test_arm64_rejected_before_run(self):
        metadata = json.dumps([{'Os': 'linux', 'Architecture': 'arm64', 'Id': 'sha256:test'}]).encode()
        with patch.object(ops.subprocess, 'check_output', return_value=metadata) as docker:
            with self.assertRaisesRegex(RuntimeError, 'platform'):
                ops.check_frontend('test')
            self.assertEqual(docker.call_count, 1)

    def test_failed_gate_never_starts_public_services(self):
        values = {'DOMAIN': 'test.example', 'RELEASE': 'test'}
        with patch.object(sys, 'argv', ['ops.py', 'publish', '--confirm-public']), \
             patch.object(ops, 'read_env', return_value=values), \
             patch.object(ops, 'compose') as compose, \
             patch.object(ops, 'check_frontend', side_effect=RuntimeError('blocked')):
            with self.assertRaises(RuntimeError):
                ops.main()
            compose.return_value.assert_not_called()

if __name__ == '__main__':
    unittest.main()
