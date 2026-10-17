"""Mutation checks for bot/fullpool/test_belief_robust.py on a scratch copy: each mutation must make its test fail."""
import subprocess, sys
from pathlib import Path
M = Path('/tmp/sdicks02-br/mut'); F = M / 'bot/fullpool/belief.py'; ORIG = F.read_text()
PY = '/mpac/sdicks02/repos/clasher-bot/.venv/bin/python'
MUTS = [
    ('champion guard removed', "if len(seen) >= 8 or (c in CHAMPIONS and champ):", "if len(seen) >= 8:",
     'test_second_champion_is_dropped_before_eight_cards'),
    ('8-card guard removed', "if len(seen) >= 8 or (c in CHAMPIONS and champ):", "if (c in CHAMPIONS and champ):",
     'test_impossible_reveals_are_dropped_not_fatal'),
    ('share validation removed', "        v = float(raw) if raw else REBUILD_SHARE\n    except ValueError:\n        return REBUILD_SHARE\n    return v if math.isfinite(v) and 0. < v <= 1. else REBUILD_SHARE",
     "        v = float(raw) if raw else REBUILD_SHARE\n    except ValueError:\n        raise\n    return v",
     'test_rebuild_share_validated'),
    ('fresh share per job', "                if self._job is not None and cut is None:", "                if self._job is not None:",
     'test_one_rebuild_cutoff_per_update'),
    ('coarse replay (s1 whole-array steps)', "    fine = s1 is not None and base.update is s1.update", "    fine = False",
     'test_rebuild_overshoot_bounded'),
    ('coarse cumsum (one step)', "def cumsum_work(w, rows=4 * BLOCK_ROWS, out=None):", "def cumsum_work(w, rows=10**9, out=None):",
     'test_rebuild_overshoot_bounded'),
    ('coarse prior (64 draws per step)', "def prior_work(sampler, n=N_DECKS, require=(), block=1):",
     "def prior_work(sampler, n=N_DECKS, require=(), block=64):", 'test_rebuild_overshoot_bounded'),
    ('stale -> TimeoutError fallback', "                    self.stale = True\n", "                    raise TimeoutError('belief')\n",
     'test_rebuild_suspends_resumes_and_includes_new_late_event'),
    ('unknown -> KeyError (no placeholder)', "    return UNKNOWN + (n or 'unknown')", "    raise KeyError(name)",
     'test_unknown_alias_and_valid_engine_sample'),
    ('compaction corrupts a queue cell', "                o += m\n            b.states, b.weights = S[:total], W[:total]",
     "                o += m\n            S[0, 6] ^= 1\n            b.states, b.weights = S[:total], W[:total]",
     'test_unknown_under_deadline_equals_synchronous'),
    ('compaction corrupts a weight', "                o += m\n            b.states, b.weights = S[:total], W[:total]",
     "                o += m\n            W[0] *= 2\n            b.states, b.weights = S[:total], W[:total]",
     'test_unknown_under_deadline_equals_synchronous'),
    ('refill shift skipped in place', "                S[start:start + len(part)] = part\n            b.queue_len -= 1",
     "                pass\n            b.queue_len -= 1", 'test_rebuild_overshoot_bounded'),
    ('cumsum carry dropped', "else np.cumsum(np.concatenate(([carry], chunk)))[1:]", "else np.cumsum(chunk) + carry",
     'test_cumsum_work_is_bit_identical_on_float_weights'),
]
bad = 0
for label, old, new, test in MUTS:
    assert ORIG.count(old) == 1, label
    F.write_text(ORIG.replace(old, new))
    r = subprocess.run([PY, '-m', 'pytest', '-q', '-x', '-p', 'no:cacheprovider', f'bot/fullpool/test_belief_robust.py::{test}'],
                       cwd=M, capture_output=True, text=True)
    killed = r.returncode != 0
    bad += not killed
    print(f"{'KILLED' if killed else 'SURVIVED'}: {label} -> {test} ({r.stdout.strip().splitlines()[-1] if r.stdout.strip() else r.stderr[-200:]})")
F.write_text(ORIG)
print('ALL_KILLED' if not bad else f'{bad} SURVIVED')
