"""Offline safety checks; no SSH, Docker, GPU, or database access."""
from pathlib import Path
from types import SimpleNamespace
import sys
import unittest

import beget_flat_only_20261025 as flat

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
from app import ai_catalog


class UnreachableGPU:
    @property
    def ready(self):
        raise AssertionError('GPU readiness accessed while AI disabled')

    def readiness_snapshot(self):
        raise AssertionError('GPU snapshot requested while AI disabled')

    def ready_for(self, *args):
        raise AssertionError('GPU pair probe requested while AI disabled')


class Safety(unittest.TestCase):
    def original(self):
        draft = Path(__file__).with_name('beget-ai-window-20261024') / 'compose.site-window.proposed.yml'
        return draft.read_text().replace('# External override draft preserving the verified HTTP1.0 runtime correction.',
                                        '# Owner approved closed f10-wreath:graphic window; totalguestbudget2')

    def test_unknown_mount_or_flag_cannot_be_overwritten(self):
        original = self.original()
        for changed in (original.replace('"2"', '"3"'), original.replace('/etc/tatar-pattern/ai-window/', '/tmp/'),
                        original + '  unexpected: {}\n'):
            with self.assertRaisesRegex(RuntimeError, 'Unknown'):
                flat.closed_override(changed)

    def test_closed_plan_is_idempotent_and_preserves_every_bind(self):
        original = self.original()
        closed = flat.closed_override(original)
        self.assertEqual(flat.closed_override(closed), closed)
        self.assertEqual(closed.count('AI_MVP_ENABLED: "false"'), 2)
        self.assertEqual(closed.count('GUEST_GPU_BUDGET: "0"'), 2)
        self.assertEqual(original.split('    volumes:', 1)[1].split('  ai-worker:')[0],
                         closed.split('    volumes:', 1)[1].split('  ai-worker:')[0])
        self.assertEqual(original[original.index('  ai-worker:'):].split('    volumes:', 1)[1],
                         closed[closed.index('  ai-worker:'):].split('    volumes:', 1)[1])

    def test_disabled_catalog_never_contacts_unreachable_gpu(self):
        # Use real catalog/profile files and their integrity checks, with a provider
        # that fails if any readiness/network hook is even invoked.
        result = ai_catalog.catalog_response(SimpleNamespace(ai_mvp_enabled=False), UnreachableGPU())
        self.assertFalse(result['available'])
        self.assertTrue(result['bases'])
        for base in result['bases']:
            for style in base['styles']:
                self.assertFalse(style['available'])
                self.assertIn('AI_DISABLED', style['unavailableReasons'])

if __name__ == '__main__':
    unittest.main()
