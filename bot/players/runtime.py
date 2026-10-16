"""Bootstrap the frozen X4S/S1 search-player runtime into this process.

Nothing here reimplements game or player logic. It only reproduces the import
path that `reports/explore/x4s/run.py` + `runtime.sh` build, against a runtime
root that holds the pieces git does not track (native clasher_core 44874fd6,
src/clasher/analysis/loss_review/{delay_fixes,search_ab,tempo}.py,
c56/engine/root-v3/human_deck_catalog.json, student-source/exit_r3, checkpoints).

Default runtime root: the read-only Mac E4 v3 runtime on 127x05, which carries
exactly the X4S pins (native 44874fd6, v1 d77005d5, R3a 37509a43). Override with
CLASHER_BOT_RUNTIME. Never write into the runtime root (PYTHONDONTWRITEBYTECODE).
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import sys

BOT_REPO = Path(__file__).resolve().parents[2]
DEFAULT_RUNTIME = Path('/mpac/sdicks02/jobs/clasher/e4v3-20261010-r1')

PINS = dict(
    native_sha256='44874fd6047aa53f8f5c46fd3a77e4e2c8672f98dbcf6d758fbf90ee043a5be2',
    v1_sha256='d77005d59d6ed40ce7f9bfcfde569b54958bebf056e00653b10dcee3957272ed',
    r3a_sha256='37509a4331bd02ae110b76e1825a2adb23fa78e0e70188e199b6ef90d19ade85',
    # X4S plan.json student.threshold (label-free R3 calibration e3003533…).
    r3a_threshold=0.5005528330802917,
)

# Baseline gamedata.json (r1 = engine-cards/py): pinned for the card-scope roots, so a root with an overlaid gamedata
# (e.g. live16402's 16.402 stats) can't pass for r1-cards1/r1-cards2 just because native and checkpoints match.
BASE_GAMEDATA = '892fbfa01e2ef9c3e4bd2293939dc336550fa626fa7ffb4ef9f91553cafd2f65'

# Per-runtime pin sets, selected by CLASHER_BOT_RUNTIME_PINS (default r1 = PINS, unchanged).
# r2 = r1 plus the calibrated engine (reports/bot/calibration/BATCH1.md, BATCH2.md) and its rebuilt native core;
# the checkpoints are r1's. Set CLASHER_BOT_RUNTIME to the matching root (clasher-bot-runtime/r2).
PIN_SETS = dict(
    r1=PINS,
    r2=dict(PINS, native_sha256='c50cb06622e42c5ba9bd43854e9bdf10b615ce84a3d08309e5067d82e776ef27'),
    # r1-total = r1 with the panic-free native (every config.cards lookup total; outputs identical on valid states,
    # reports/bot/learned-opponent/NATIVE-TOTAL.md). Keep CLASHER_BOT_RUNTIME=clasher-bot-runtime/r1 and set
    # CLASHER_DELAY_NATIVE_DIR=clasher-bot-runtime/native-total-r1.
    **{'r1-total': dict(PINS, native_sha256='681b5f2c866ba3df1aa9903d1bf40d565e21feb6f541319bef84ee493c72066b')},
    # r1-cards1 = r1-total + the full ladder card pool in R.config/meta/costs/templates (bot/cards/scope.py; C56-only
    # outputs bit-identical, reports/cards/runtime/SCOPE.md). Root: an assembled clasher-bot-runtime/r1-cards1
    # (bot/cards/build_runtime.py) with the native in <root>/native.
    # fc_side_cut: the fc root cut also drops unreachable side-table entries (bot/cards/fc_cut.py).
    **{'r1-cards1': dict(PINS, native_sha256='681b5f2c866ba3df1aa9903d1bf40d565e21feb6f541319bef84ee493c72066b',
                         card_scope='full', fc_side_cut=True, gamedata_sha256=BASE_GAMEDATA)},
    # live16402 = r1-cards1 + RoyaleSim 16.402.19 card stats for every pool card (bot/cards/balance_overlay.py; stats
    # change by design, so no C56 bit-identity; reports/cards/live16402/RESULTS.md). Root: an assembled live16402
    # root (bot/cards/build_live16402.py), native in <root>/native; gamedata_sha256 pins its overlay gamedata.
    # tournament_crown_from_gamedata: spells whose crown % 16.402 changed; their level-11 crown damage pin in
    # clasher.balance (measured on the earlier client) is dropped so the engine derives it from the overlay.
    **{'live16402': dict(PINS, native_sha256='681b5f2c866ba3df1aa9903d1bf40d565e21feb6f541319bef84ee493c72066b',
                         card_scope='full', fc_side_cut=True,
                         gamedata_sha256='a7de3e93eb4320c48775da97cd0e5113fb793ea57782ba0eb006af0bd6eb0ccb',
                         tournament_crown_from_gamedata=('Fireball', 'Poison'))},
    # r1-cards2 = r1-cards1 + Batch A mechanics + review fixes (b7c6976e4); dev builds and gates: reports/cards/r1-cards2/.
    **{'r1-cards2': dict(PINS, native_sha256='5f07238c3c3c1eafa7ada7b87aae00f9c40f69f78680aca206a4733c7b729252',
                         card_scope='full', fc_side_cut=True, gamedata_sha256=BASE_GAMEDATA)},
    # live16402b = r1-cards2 + the same 16.402.19 stat overlay; select its matching dev root explicitly.
    **{'live16402b': dict(PINS, native_sha256='5f07238c3c3c1eafa7ada7b87aae00f9c40f69f78680aca206a4733c7b729252',
                         card_scope='full', fc_side_cut=True,
                         gamedata_sha256='a7de3e93eb4320c48775da97cd0e5113fb793ea57782ba0eb006af0bd6eb0ccb',
                         tournament_crown_from_gamedata=('Fireball', 'Poison'))},
)


def selected_pins():
    name = os.environ.get('CLASHER_BOT_RUNTIME_PINS', 'r1')
    if name not in PIN_SETS:
        raise ValueError(f'CLASHER_BOT_RUNTIME_PINS={name!r}; known: {sorted(PIN_SETS)}')
    return PIN_SETS[name]


def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as stream:
        for block in iter(lambda: stream.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


class Runtime:
    """Process-wide frozen resources (≈15 s CPU to build Resources once)."""

    def __init__(self, root=None, *, v1=None, student=None, verify=True):
        self.root = Path(root or os.environ.get('CLASHER_BOT_RUNTIME', DEFAULT_RUNTIME)).resolve()
        self.native_dir = Path(os.environ.get('CLASHER_DELAY_NATIVE_DIR', self.root / 'native'))
        self.v1_path = Path(v1 or self.root / 'main02.pt')
        self.student_path = Path(student or self.root / 'R3a.pt')
        self._bootstrap_paths()
        self.pins = selected_pins()
        if verify:
            assert sha256(self.native_dir / 'clasher_core.abi3.so') == self.pins['native_sha256'], 'native pin'
            assert sha256(self.v1_path) == self.pins['v1_sha256'], 'v1 checkpoint pin'
            assert sha256(self.student_path) == self.pins['r3a_sha256'], 'R3a checkpoint pin'
            if 'gamedata_sha256' in self.pins:  # the engine reads $CLASHER_ROOT/gamedata.json (set in _bootstrap_paths)
                gamedata = Path(os.environ['CLASHER_ROOT']) / 'gamedata.json'
                assert sha256(gamedata) == self.pins['gamedata_sha256'], 'gamedata pin'
        import torch
        torch.set_num_threads(1)
        if self.pins.get('tournament_crown_from_gamedata'):
            from clasher.balance import TOURNAMENT_SPELL_OVERRIDES
            for name in self.pins['tournament_crown_from_gamedata']:
                TOURNAMENT_SPELL_OVERRIDES.get(name, {}).pop('crown_tower_damage', None)
        from fair_player import Resources
        from quickwin_resources import cached_resources
        from clasher.analysis.loss_review.human import make_catalog
        self.R = cached_resources(Resources)()
        if self.pins.get('card_scope', 'c56') != 'c56':
            from bot.cards.scope import extend
            extend(self.R, self.pins['card_scope'])
        if self.pins.get('fc_side_cut'):
            from bot.cards.fc_cut import install
            install()
        self.CAT = make_catalog(self.R.builder)
        council = self.root / 'reports/strategy_council_20260928'
        self.PRIOR = json.loads((council / 'c56/engine/root-v3/human_deck_catalog.json').read_text())
        from imitation.model import load_policy
        self.POLICY = load_policy(self.v1_path)
        assert self.POLICY.model.temperatures.tolist() == [1., 1., 1.]
        self._student = None

    @property
    def STUDENT(self):
        if self._student is None:
            from proposals import load_student
            self._student = load_student(self.student_path, self.pins['r3a_threshold'])
        return self._student

    def _bootstrap_paths(self):
        r = self.root
        council = r / 'reports/strategy_council_20260928'
        x4s = BOT_REPO / 'reports/explore/x4s'  # sdefault.py (X4S, git-tracked)
        os.environ.setdefault('CLASHER_ROOT', str(r))
        os.environ.setdefault('CLASHER_EVAL_RUNTIME_ROOT', str(r))
        os.environ.setdefault('CLASHER_DELAY_NATIVE_DIR', str(self.native_dir))
        sys.dont_write_bytecode = True
        # Effective sys.path order of x4s/run.py after initialize(): first match wins
        # for the duplicated module names (planner, belief, derived_public_state, ...).
        order = [r / 'engine-rs', council / 'engine-speed/stage5', council / 'search-noise-s6',
                 self.native_dir, r / 'src', x4s, r, r / 'engine-rs', x4s,
                 r / 'reports/explore/s1', r / 'student-source', r / 'reports/explore/e1',
                 council / 'engine-speed', council / 'search-noise-s4',
                 r / 'reports/perf-audit/quickwins']
        # Drop this repo's own entries so the runtime's `clasher`/`imitation` win.
        sys.path[:] = [p for p in sys.path if not p.startswith(str(BOT_REPO / 'src'))]
        for path in reversed(list(dict.fromkeys(str(p) for p in order))):
            if path in sys.path:
                sys.path.remove(path)
            sys.path.insert(0, path)
        # bot.players itself stays importable from the bot repo root.
        if str(BOT_REPO) not in sys.path:
            sys.path.append(str(BOT_REPO))

    def x4s_decks(self):
        """The five X4S decks: most frequent human deck per archetype (run.py:304-307)."""
        from clasher.analysis.loss_review.metrics import archetype
        return [max((d for d in self.PRIOR['decks'] if archetype(d['cards']) == f),
                    key=lambda d: d['frequency'])['cards']
                for f in ('bridge_wincon', 'siege', 'beatdown', 'bait', 'chip')]
