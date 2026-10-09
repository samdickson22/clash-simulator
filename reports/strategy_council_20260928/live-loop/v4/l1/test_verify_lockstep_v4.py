"""Fail-closed scope/stream tests, no real payload access."""
from copy import deepcopy
import gzip
from pathlib import Path
import tempfile
import unittest

from lockstep_replay_v4 import sha
from verify_lockstep_v4 import validate_plan, stream, REFERENCE_ROOTS


def plan():
    return dict(schema='clasher.v4.lockstep-equality-plan.v1', captures=[
        dict(epoch=e, episodes=[f'ep-{i}' for i in range(8)],
             original=dict(host='127x02', root='/mpac/sdicks02/repos/clasher-v4-cache/epoch-capture-packed-r1'),
             candidate=dict(host='local', root=f'/mpac/sdicks02/repos/clasher-v4-cache/lockstep-20261009/e{e}'))
        for e in (1, 3, 20)], references={k: dict(host='127x09', root=v) for k, v in REFERENCE_ROOTS.items()})


class VerifyTests(unittest.TestCase):
    def test_required_epoch_match_and_reference_scope(self):
        validate_plan(plan())
        for mutate in (
            lambda p: p['captures'].pop(),
            lambda p: p['captures'][2].update(epoch=4),
            lambda p: p['captures'][0].update(episodes=['one']*8),
            lambda p: p['references'].pop('2'),
            lambda p: p['captures'][1]['original'].update(host='127x03'),
            lambda p: p['captures'][0]['candidate'].update(root='/tmp/other'),
        ):
            p = plan(); mutate(p)
            with self.assertRaises(ValueError):
                validate_plan(p)

    def test_full_hash_and_gzip_eof(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); path = root/'rows.gz'
            with gzip.open(path, 'wb') as f:
                f.write(b'one\ntwo\n')
            target = dict(host='local', root=str(root)); pin = sha(path)
            with stream(target, path.name, pin, True) as lines:
                self.assertEqual(list(lines), [b'one\n', b'two\n'])
            with self.assertRaises(ValueError):
                with stream(target, path.name, pin, True) as lines:
                    next(lines)
            with self.assertRaises(ValueError):
                with stream(target, path.name, '0'*64, True) as lines:
                    list(lines)


if __name__ == '__main__':
    unittest.main(verbosity=2)
