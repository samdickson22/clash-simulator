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
        if verify:
            assert sha256(self.native_dir / 'clasher_core.abi3.so') == PINS['native_sha256'], 'native pin'
            assert sha256(self.v1_path) == PINS['v1_sha256'], 'v1 checkpoint pin'
            assert sha256(self.student_path) == PINS['r3a_sha256'], 'R3a checkpoint pin'
        import torch
        torch.set_num_threads(1)
        from fair_player import Resources
        from quickwin_resources import cached_resources
        from clasher.analysis.loss_review.human import make_catalog
        self.R = cached_resources(Resources)()
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
            self._student = load_student(self.student_path, PINS['r3a_threshold'])
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
