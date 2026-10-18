"""Mixed LIVE K4L + fast no-crash runs (r1-cards3-phase1 run_mixed.py / run_3m.py, merged; decks and seeds unchanged).

    python run_mixed.py EVAL OUT.jsonl plain|3m
plain: LIVE-K4L-R-gs-rw-fc-w200-t2-p2 and LIVE-fast-it5s2 x decks B1B2A, B1B2B, seed 20261016600 (4 runs).
3m: both tiers x B1B2A with the opponent deploying ThreeMusketeers first, seed 20261016601 (2 runs).
"""
from pathlib import Path
import runpy
import sys

repo, out, mode = Path(sys.argv[1]).resolve(), Path(sys.argv[2]), sys.argv[3]
assert mode in ('plain', '3m') and not out.exists()
sys.path.insert(0, str(repo))
m = runpy.run_path(str(repo / 'reports/cards/runtime/tools/noncore_matches.py'), run_name='release_d_noncore')
m['DECKS']['B1B2A'] = ['RoyalGiant', 'ThreeMusketeers', 'GiantBuffer', 'BattleHealer', 'Freeze', 'Rage', 'Clone',
                       'Graveyard']
m['DECKS']['B1B2B'] = ['GoblinGiant', 'RoyalRecruits', 'RageBarbarian', 'SkeletonBalloon', 'GoblinCage', 'Tombstone',
                       'Fisherman', 'ElectroWizard']
decks, seed = (('B1B2A', 'B1B2B'), '20261016600') if mode == 'plain' else (('B1B2A',), '20261016601')
if mode == '3m':
    Original = m['RandomMaskPlayer']

    class ThreeMusketeersFirst(Original):
        def act(self, view):
            from bot.players.base import Decision, WAIT
            if not getattr(self, 'deployed_3m', False):
                if view.tick % 10:
                    return Decision(WAIT)
                token = self.rt.R.builder.token_id('ThreeMusketeers', namespace='card_action')
                hand = view.reserved.packet.observation.hand_ids
                slots = [i for i, t in enumerate(hand[:4]) if int(t) == token]
                if slots:
                    mask = self.mask.build(self.inp.from_confidence_observation(view.reserved.packet))
                    legal = [i for i in range(WAIT) if mask[i] and i // 576 in slots]
                    if legal:
                        self.deployed_3m = True
                        return Decision(legal[len(legal) // 2])
                    return Decision(WAIT)
            return super().act(view)
    m['main'].__globals__['RandomMaskPlayer'] = ThreeMusketeersFirst
for tier in ('LIVE-K4L-R-gs-rw-fc-w200-t2-p2', 'LIVE-fast-it5s2'):
    for deck in decks:
        sys.argv = ['noncore_matches.py', '--player', tier, '--opponent', 'random', '--deck', deck, '--own-deck', deck,
                    '--games', '1', '--seed', seed, '--max-ticks', '2401', '--probe-own', '--out', str(out)]
        m['main']()
