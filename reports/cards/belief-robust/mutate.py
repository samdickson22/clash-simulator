"""Mutation check for bot/fullpool/test_belief_robust.py (cards/belief-robust).

    python reports/cards/belief-robust/mutate.py [REPO]      # exit 0 iff the baseline passes and every mutation is killed

Copies the files the tests need (bot/, the frozen DerivedPublicState and s1 Belief sources) into a fresh temp dir and
runs the test file there:
1. Baseline (unmodified code): the whole test file must pass (pytest exit 0), else exit 2.
2. Each mutation reverts one guard / fix and runs its target test. KILLED only on pytest exit 1 (tests ran and
   failed). Exit 0 is SURVIVED; any other code (collection / import / usage error) is ERROR, never a kill.
Exit 1 if any mutation SURVIVED or ERRORed.
"""
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

PY = sys.executable
TEST = 'bot/fullpool/test_belief_robust.py'
FILES = ('reports/explore/s1/belief.py', 'reports/strategy_council_20260928/engine-speed/stage5/derived_public_state.py')
B, P = 'bot/fullpool/belief.py', 'bot/live/player.py'
MUTS = [
    ('champion guard removed', B, "if len(seen) >= 8 or (c in CHAMPIONS and champ):", "if len(seen) >= 8:",
     'test_second_champion_is_dropped_before_eight_cards'),
    ('8-card guard removed', B, "if len(seen) >= 8 or (c in CHAMPIONS and champ):", "if (c in CHAMPIONS and champ):",
     'test_impossible_reveals_are_dropped_not_fatal'),
    ('share validation removed', B,
     "    except ValueError:\n        return REBUILD_SHARE\n    return v if math.isfinite(v) and 0. < v <= 1. else REBUILD_SHARE",
     "    except ValueError:\n        raise\n    return v", 'test_rebuild_share_validated'),
    ('fresh share per job', B, "                if self._job is not None and cut is None:",
     "                if self._job is not None:", 'test_one_rebuild_cutoff_per_update'),
    ('coarse replay (s1 whole-array steps)', B, "    fine = s1 is not None and base.update is s1.update", "    fine = False",
     'test_rebuild_overshoot_bounded'),
    ('coarse cumsum (one step)', B, "def cumsum_work(w, rows=4 * BLOCK_ROWS, out=None):",
     "def cumsum_work(w, rows=10**9, out=None):", 'test_rebuild_overshoot_bounded'),
    ('coarse prior (64 draws per step)', B, "def prior_work(sampler, n=N_DECKS, require=(), block=1):",
     "def prior_work(sampler, n=N_DECKS, require=(), block=64):", 'test_rebuild_overshoot_bounded'),
    ('stale -> TimeoutError fallback', B, "                    self.stale = True\n",
     "                    raise TimeoutError('belief')\n", 'test_rebuild_suspends_resumes_and_includes_new_late_event'),
    ('unknown -> KeyError (no placeholder)', B, "    return UNKNOWN + (n or 'unknown')", "    raise KeyError(name)",
     'test_unknown_alias_and_valid_engine_sample'),
    ('compaction corrupts a queue cell', B, "                o += m\n            b.states, b.weights = S[:total], W[:total]",
     "                o += m\n            S[0, 6] ^= 1\n            b.states, b.weights = S[:total], W[:total]",
     'test_unknown_under_deadline_equals_synchronous'),
    ('compaction corrupts a weight', B, "                o += m\n            b.states, b.weights = S[:total], W[:total]",
     "                o += m\n            W[0] *= 2\n            b.states, b.weights = S[:total], W[:total]",
     'test_unknown_under_deadline_equals_synchronous'),
    ('refill shift skipped in place', B, "                S[start:start + len(part)] = part\n            b.queue_len -= 1",
     "                pass\n            b.queue_len -= 1", 'test_rebuild_overshoot_bounded'),
    ('cumsum carry dropped', B, "else np.cumsum(np.concatenate(([carry], chunk)))[1:]", "else np.cumsum(chunk) + carry",
     'test_cumsum_work_is_bit_identical_on_float_weights'),
    # C56 LiveBelief (rollback path), r3
    ('C56 completion in one step', P, "def completed_prior_work(prior, revealed, max_decks=400, block=100):",
     "def completed_prior_work(prior, revealed, max_decks=400, block=10**9):", 'test_c56_live_belief_overshoot_bounded'),
    ('C56 catalog weights in one step', B, "            if weights_work is not None and any(c not in self.costs for c in revealed):",
     "            if False:", 'test_c56_live_belief_overshoot_bounded'),
    ('C56 merge order broken (ties by deck reversed)', P, "    key = lambda kv: (-kv[1], kv[0])",
     "    key = lambda kv: (-kv[1], tuple(reversed(kv[0])))", 'test_completed_prior_work_equals_one_step_reference'),
    ('C56 non-finite weight guard removed', P, "        if not math.isfinite(w):\n            continue\n", "",
     'test_completed_prior_skips_non_finite_weights'),
    ('C56 top-k off by one', P, "        if len(top) >= max_decks:", "        if len(top) >= max_decks - 1:",
     'test_completed_prior_work_equals_one_step_reference'),
]


def run(root, target):
    return subprocess.run([PY, '-m', 'pytest', '-q', '-x', '-p', 'no:cacheprovider', target], cwd=root,
                          capture_output=True, text=True)


def last(r):
    out = (r.stdout.strip() or r.stderr.strip()).splitlines()
    return out[-1] if out else ''


def main(repo=None):
    repo = Path(repo or Path(__file__).resolve().parents[3])
    root = Path(tempfile.mkdtemp(prefix='belief-mutate-'))
    try:
        shutil.copytree(repo / 'bot', root / 'bot', ignore=shutil.ignore_patterns('__pycache__'))
        for f in FILES:
            (root / f).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(repo / f, root / f)
        base = run(root, TEST)
        print(f'BASELINE rc={base.returncode}: {last(base)}')
        if base.returncode != 0:
            print('BASELINE_FAILED')
            return 2
        bad = 0
        for label, path, old, new, test in MUTS:
            f = root / path
            orig = f.read_text()
            if orig.count(old) != 1:
                print(f'ERROR: {label}: anchor found {orig.count(old)} times in {path}')
                bad += 1
                continue
            f.write_text(orig.replace(old, new))
            try:
                r = run(root, f'{TEST}::{test}')
            finally:
                f.write_text(orig)
            verdict = {1: 'KILLED', 0: 'SURVIVED'}.get(r.returncode, f'ERROR(rc={r.returncode})')
            bad += verdict != 'KILLED'
            print(f'{verdict}: {label} -> {test} ({last(r)})')
        print(f'{len(MUTS) - bad}/{len(MUTS)} killed', 'ALL_KILLED' if not bad else 'NOT_ALL_KILLED')
        return 1 if bad else 0
    finally:
        shutil.rmtree(root, ignore_errors=True)


if __name__ == '__main__':
    sys.exit(main(*sys.argv[1:]))
