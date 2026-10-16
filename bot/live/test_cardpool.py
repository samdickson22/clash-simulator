"""The card-pool switch on the translator side: true card ids for perception units (CLASHER_LIVE_TRUE_IDS), the
full-scope runtime's card set in births (level variants are not cards), and fail-closed loading."""
import hashlib
import json
import os
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
CLASSES = ROOT / 'live/yolo_synth/classes.json'
FULL_RUNTIME = os.environ.get('CLASHER_TEST_FULLPOOL_RUNTIME',
                              '/mpac/sdicks02/jobs/clasher/live-multibody-20261015/runtime-live16402b-r3')
OWN = ['Valkyrie', 'Archers', 'Minions', 'Cannon', 'Fireball', 'Giant', 'MiniPekka', 'Musketeer']


def spec(tmp_path, sha=None, cards=None):
    s = dict(mapping=str(CLASSES), sha256=sha or hashlib.sha256(CLASSES.read_bytes()).hexdigest())
    if cards is not None:
        s['cards'] = cards
    p = tmp_path / 'true-ids.json'
    p.write_text(json.dumps(s))
    return p


class FakeRt:
    def __init__(self, scope):
        self.pins = dict(card_scope=scope)


def test_mapping_gives_true_ids_for_the_allowed_cards_only(tmp_path):
    from bot.live.translate import BATCH_A, load_true_ids
    m = load_true_ids(spec(tmp_path), FakeRt('full'))
    assert set(m.values()) == set(BATCH_A)
    assert m['mega-minion'] == 'MegaMinion' and m['battle-ram'] == 'BattleRam' and m['goblin-brawler'] == 'GoblinCage'
    assert 'knight' not in m and 'hog-rider' not in m                       # C56 classes are not relabelled
    only = load_true_ids(spec(tmp_path, cards=['Bomber']), FakeRt('full'))
    assert set(only.values()) == {'Bomber'}


def test_loading_fails_closed(tmp_path):
    from bot.live.translate import load_true_ids
    with pytest.raises(ValueError, match='sha256'):
        load_true_ids(spec(tmp_path, sha='0'*64), FakeRt('full'))
    with pytest.raises(ValueError, match='full card-scope'):
        load_true_ids(spec(tmp_path), FakeRt('c56'))


class Stub:
    """Just what true_units() reads."""
    def __init__(self, true_ids, cards):
        from collections import Counter
        self.true_ids, self.stats = true_ids, Counter()
        self.cards = type('C', (), {'is_card': staticmethod(lambda c: c in cards)})()


def test_true_units_relabels_by_raw_class_and_keeps_the_alias():
    from bot.live.translate import LiveTranslator
    st = Stub({'mega-minion': 'MegaMinion', 'bomber': 'Bomber'}, {'MegaMinion', 'Bomber', 'Minions', 'Firecracker'})
    rec = dict(units=[dict(cls='Minions', card='Minions', owner=1, x=3., y=20.),
                      dict(cls='Minions', card='Minions', owner=1, x=4., y=20.),
                      dict(cls='Firecracker', card='Firecracker', owner=1, x=9., y=22.)],
               units_yolo=['mega-minion', 'minion', 'bomber'])
    out = LiveTranslator.true_units(st, rec)
    assert [u['card'] for u in out] == ['MegaMinion', 'Minions', 'Bomber']
    assert out[0]['alias'] == 'Minions' and 'alias' not in out[1]
    assert st.stats['true_id:Minions->MegaMinion'] == 1 and st.stats['true_id:Firecracker->Bomber'] == 1
    assert rec['units'][0]['card'] == 'Minions'                                # the caller's record is untouched


def test_unaligned_or_unknown_cards_pass_unchanged():
    from bot.live.translate import LiveTranslator
    st = Stub({'mega-minion': 'MegaMinion'}, {'Minions'})                      # runtime without MegaMinion
    rec = dict(units=[dict(cls='Minions', card='Minions', owner=1, x=3., y=20.)], units_yolo=['mega-minion'])
    assert LiveTranslator.true_units(st, rec)[0]['card'] == 'Minions'
    st = Stub({'mega-minion': 'MegaMinion'}, {'MegaMinion', 'Minions'})
    rec = dict(units=[dict(cls='Minions', card='Minions', owner=1, x=3., y=20.)], units_yolo=[])
    assert LiveTranslator.true_units(st, rec)[0]['card'] == 'Minions' and st.stats['true_ids_unaligned'] == 1


needs_full = pytest.mark.skipif(not Path(FULL_RUNTIME).is_dir(), reason='no live16402b-r3 runtime root on this host')

FULL_CHECK = r"""
import json, os
from bot.players.runtime import Runtime
from bot.live.births import CardBodies
from bot.live.translate import LiveTranslator
rt = Runtime(os.environ['CLASHER_BOT_RUNTIME'])
cb = CardBodies(rt)
out = dict(variants=[c for c in cb.main if ':' in c],
           batch_a=all(cb.is_card(c) for c in ('Bomber', 'GoblinCage', 'Tombstone', 'SpearGoblins', 'Barbarians',
                                               'MegaMinion', 'BattleRam')))
own = ['Valkyrie', 'Archers', 'Minions', 'Cannon', 'Fireball', 'Giant', 'MiniPekka', 'Musketeer']
tr = LiveTranslator(rt, own)
for tick in range(100, 200, 5):
    tr.information(dict(tick=tick, units=[dict(cls='Minions', card='Minions', owner=1, x=4., y=24. - .03*(tick - 100),
                                               hp_frac=1., score=.9)], units_yolo=['mega-minion'], towers=[],
                        hand=dict(cards=own[:4], next=own[4]), elixir=5., events=[]))
out.update(played=[e['name'] for e in tr.public_events if e['seat'] == 1],
           relabelled=tr.stats['true_id:Minions->MegaMinion'])
print('RESULT ' + json.dumps(out))
"""


@needs_full
def test_full_scope_runtime_with_true_ids_end_to_end(tmp_path):
    """In a subprocess: building a full-scope Runtime sets process-wide paths (CLASHER_ROOT, sys.path) that must not
    leak into the C56 tests of this suite."""
    import subprocess
    import sys
    env = dict(os.environ, CLASHER_BOT_RUNTIME=FULL_RUNTIME, CLASHER_BOT_RUNTIME_PINS='live16402b-r3',
               CLASHER_LIVE_TRUE_IDS=str(spec(tmp_path)), PYTHONHASHSEED='0')
    for k in ('CLASHER_ROOT', 'CLASHER_EVAL_RUNTIME_ROOT', 'CLASHER_DELAY_NATIVE_DIR'):
        env.pop(k, None)
    r = subprocess.run([sys.executable, '-c', FULL_CHECK], cwd=ROOT, env=env, capture_output=True, text=True, timeout=600)
    line = next((l for l in r.stdout.splitlines() if l.startswith('RESULT ')), None)
    assert line, r.stdout[-2000:] + r.stderr[-2000:]
    out = json.loads(line[7:])
    assert out['variants'] == [] and out['batch_a']                    # level variants are not cards
    assert out['played'] == ['MegaMinion'] and out['relabelled'] > 0   # a MegaMinion deployment is a MegaMinion play
