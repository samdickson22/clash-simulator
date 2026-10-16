"""No-crash run: our player (C56 X-deck) vs an opponent holding a non-C56 deck, in our engine, full card scope.

    CLASHER_BOT_RUNTIME=<root> CLASHER_BOT_RUNTIME_PINS=r1-cards1 python noncore_matches.py \
        --player LIVE-K4L-R-gs-rw-fc-w200-t4-p4 --opponent R3a --deck D1 --games 2 --out OUT.jsonl
    (--deck X<i>: the opponent plays X4S deck i, a C56 control)

Opponents: any bot.live.player.make_live_player name (R3a, v1, ...) or 'random' (every 10 ticks, P=0.35, a uniformly
random legal play from the v5 public action mask: guarantees the new cards get played). Per game: the match result,
every exception (a crash ends the game and is recorded), our player's decision sources, errors, panics, native
failures and search failures, and from a spy on R.root: roots built, root failures (exceptions in R.root), roots
whose opponent hand/cycle holds a non-C56 card, and the non-C56 entity stats names seen in the native roots.
"""
import argparse
import json
import random
import sys
import time
import traceback
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

DECKS = dict(
    D1=['GoblinCage', 'SpearGoblins', 'Tombstone', 'Bomber', 'Graveyard', 'Freeze', 'Mortar', 'Fisherman'],
    D2=['BarbarianHut', 'Witch', 'Pekka', 'MegaMinion', 'Mirror', 'ElectroWizard', 'RoyalGiant', 'Heal'],
    D3=['GoblinDrill', 'SkeletonKing', 'LavaHound', 'Clone', 'Rage', 'GoldenKnight', 'Phoenix', 'Monk'],
    D4=['ElixirGolem', 'SkeletonBalloon', 'DarkWitch', 'GoblinCurse', 'Vines', 'DarkMagic', 'BattleRam', 'Elixir Collector'],
    # mixed: four new cards + four C56 cards
    M1=['GoblinCage', 'SpearGoblins', 'Tombstone', 'Bomber', 'Knight', 'Fireball', 'HogRider', 'Musketeer'],
)


class RandomMaskPlayer:
    deadline_seconds = None

    def __init__(self, rt, seed):
        self.rt, self.seed, self.name = rt, seed, 'random'

    def start(self, ctx):
        from clasher.rl.public_action_mask import PublicActionMaskInput
        self.inp = PublicActionMaskInput
        self.mask = self.rt.R.bots['balanced'].mask_builder
        self.rng = random.Random(self.seed + ctx.seat)

    def act(self, view):
        from bot.players.base import Decision, WAIT
        if view.tick % 10 or self.rng.random() > 0.35:
            return Decision(WAIT)
        m = self.mask.build(self.inp.from_confidence_observation(view.reserved.packet))
        legal = [i for i in range(WAIT) if m[i]]
        return Decision(self.rng.choice(legal) if legal else WAIT)

    def close(self):
        pass


def with_live_belief(rt, player):
    """After start, swap the search belief's class to LiveBelief exactly as LivePlayer.start does."""
    from bot.live.player import live_belief_class
    start = player.start

    def start_live(ctx):
        start(ctx)
        belief = player.p.belief
        belief.__class__ = live_belief_class()
        belief.human_prior = rt.PRIOR
    player.start = start_live
    return player


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--player', required=True)
    ap.add_argument('--opponent', default='R3a')
    ap.add_argument('--deck', default='D1')
    ap.add_argument('--own-deck', default='X0', help='our deck: a DECKS key or X<i> (X4S deck i; default X0, C56)')
    ap.add_argument('--games', type=int, default=2)
    ap.add_argument('--seed', type=int, default=20261016000)
    ap.add_argument('--max-ticks', type=int, default=6001)
    ap.add_argument('--out', required=True)
    ap.add_argument('--save-roots', help='append every 5th root snapshot (+ deck, seat, tick) to this .jsonl.gz')
    ap.add_argument('--probe-own', action='store_true',
                    help='count non-C56 own-hand slots in planner candidates, the native mask and native scripted picks')
    ap.add_argument('--live-belief', action='store_true',
                    help="a non-LIVE search player gets LivePlayer's open-world belief (bot.live.player.live_belief_class)")
    a = ap.parse_args()
    from bot.players.runtime import Runtime
    rt = Runtime()
    from bot.players.ours import play_match
    from bot.live.player import make_live_player
    from bot.search.lopp_fast import split_snapshot
    R = rt.R
    c56 = set(json.loads((Path(__file__).resolve().parent / 'c56_cards.json').read_text()))
    base_root = R.root
    import gzip
    saver = gzip.open(a.save_roots, 'at') if a.save_roots else None
    spy = dict(roots=0, root_errors=Counter(), opp_noncore_roots=0, entities=Counter(), own_noncore_roots=0)
    names_seen = [set()]

    def root(info, opponent, rng):
        try:
            r = base_root(info, opponent, rng)
        except BaseException as ex:
            spy['root_errors'][repr(ex)[:200]] += 1
            raise
        spy['roots'] += 1
        snap = r.snapshot()
        head, _, _ = split_snapshot(snap)
        if saver is not None and spy['roots'] % 5 == 0:
            saver.write(json.dumps(dict(deck=a.deck, seat=int(info.seat), tick=int(info.tick), snapshot=snap)) + '\n')
        dec = json.JSONDecoder()
        players = dec.raw_decode(head, head.index('"players":') + 10)[0]
        entities = dec.raw_decode(head, head.index('"entities":') + 11)[0]
        opp = players[1 - info.seat]
        if a.probe_own:
            hand = players[info.seat]['hand']
            new = [i for i, c in enumerate(hand[:4]) if c is not None and c not in c56]
            if new:
                mask = list(R.native.public_mask(r, info.seat))
                own['roots_with_new'] += 1
                own['new_slot_legal'] += sum(any(mask[i * 576:(i + 1) * 576]) for i in new)
                for style in ('balanced', 'pressure', 'defense'):
                    act = int(R.native.select_action(r.clone(), info.seat, style))
                    own['native_picks_new'] += act < 2304 and act // 576 in new
        if any(c not in c56 for c in opp['hand'] + opp['cycle']):
            spy['opp_noncore_roots'] += 1
        if any(c not in c56 for c in players[info.seat]['hand'] + players[info.seat]['cycle']):
            spy['own_noncore_roots'] += 1
        for e in entities:
            n = (e.get('stats') or {}).get('name')
            if n is not None and n not in BASE_BODIES:
                spy['entities'][n] += 1
        return r
    own = Counter()

    def probe_candidates(player):
        p = (player.search if getattr(player, 'search', None) is not None else player).p
        cands = p.core.candidates

        def wrapped(packet, *args, **kw):
            out = cands(packet, *args, **kw)
            hand = p.core.info.own['hand']
            new = {i for i, c in enumerate(hand[:4]) if c is not None and c not in c56}
            if new:
                own['candidate_calls_with_new'] += 1
                own['candidates_new_slot'] += sum(1 for x in out[0] if x < 2304 and x // 576 in new)
            return out
        p.core.candidates = wrapped
    BASE_BODIES = set(json.loads((Path(__file__).resolve().parent / 'c56_bodies.json').read_text()))
    R.root = root
    own_deck = list(rt.x4s_decks()[int(a.own_deck[1:])]) if a.own_deck[0] == 'X' else list(DECKS[a.own_deck])
    with open(a.out, 'a') as fh:
        for g in range(a.games):
            seed = a.seed + g
            seat = g % 2
            rng = random.Random(seed)
            mine = own_deck[:]
            theirs = list(rt.x4s_decks()[int(a.deck[1:])]) if a.deck[0] == 'X' else list(DECKS[a.deck])
            rng.shuffle(mine); rng.shuffle(theirs)
            decks = [mine, theirs] if seat == 0 else [theirs, mine]
            for k in ('roots', 'opp_noncore_roots', 'own_noncore_roots'):
                spy[k] = 0
            spy['root_errors'], spy['entities'] = Counter(), Counter()
            ours = make_live_player(rt, a.player)
            if a.live_belief:
                ours = with_live_belief(rt, ours)
            if a.probe_own and hasattr(ours, 'start') and (hasattr(ours, 'search') or a.player.startswith('K4')):
                start0 = ours.start

                def start_probe(ctx, start0=start0, ours=ours):
                    start0(ctx)
                    if getattr(ours, 'search', None) is not None or hasattr(ours, 'p'):
                        probe_candidates(ours)
                ours.start = start_probe
            own.clear()
            opp = RandomMaskPlayer(rt, seed) if a.opponent == 'random' else make_live_player(rt, a.opponent)
            t0 = time.time()
            row = dict(player=a.player, opponent=a.opponent, deck=a.deck, own_deck=a.own_deck, game=g, seed=seed, seat=seat,
                       decks=decks)
            try:
                res = play_match(rt, {seat: ours, 1 - seat: opp}, seed=seed, decks=decks, max_ticks=a.max_ticks,
                                 verbose=True)
                log = res.pop('play_log')
                row.update({k: res[k] for k in ('terminal', 'winner', 'ticks', 'towers', 'plays', 'accepted',
                                                'command_sha256')})
                row['opp_played'] = dict(Counter(c for _, c, _, ok in log[1 - seat] if ok))
                row['own_played'] = dict(Counter(c for _, c, _, ok in log[seat] if ok))
            except BaseException as ex:
                if isinstance(ex, KeyboardInterrupt):
                    raise
                row['crash'] = traceback.format_exc()[-1500:]
            decs = [d for d in getattr(ours, 'decisions', []) if isinstance(d, dict) and 'source' in d]   # LivePlayer rows
            row['sources'] = dict(Counter(d['source'] for d in decs))
            row['errors'] = dict(Counter(d['error'][:160] for d in decs if 'error' in d))
            row['panics'] = getattr(ours, 'panics', None)
            row['fast_errors'] = getattr(ours, 'fast_errors', 0)
            row['native_failures'] = dict(getattr(ours, 'native_failures', {}) or {})
            sf = Counter()
            for d in decs:
                for k, v in (d.get('search_failures') or {}).items():
                    sf[k] += v
            row['search_failures'] = dict(sf)
            srch = [d for d in decs if d['source'] in ('search', 'default-it5s2', 'default-R3a')]
            row['search_detail'] = dict(
                decisions=len(srch), preparation_cutoff=sum('preparation_cutoff' in d for d in srch),
                student_default=sum(bool(d.get('student_default')) for d in srch),
                hit=sum(bool(d.get('hit')) for d in srch),
                completed_mean=round(sum(d.get('completed') or 0 for d in srch) / max(1, len(srch)), 2),
                candidates_mean=round(sum(d.get('candidates') or 0 for d in srch) / max(1, len(srch)), 2),
                search_wall_ms_mean=round(sum(d.get('search_wall_ms') or 0 for d in srch) / max(1, len(srch)), 1))
            row['roots'] = spy['roots']
            row['root_errors'] = dict(spy['root_errors'])
            row['opp_noncore_roots'] = spy['opp_noncore_roots']
            row['own_noncore_roots'] = spy['own_noncore_roots']
            row['noncore_entities_in_roots'] = dict(spy['entities'])
            if a.probe_own:
                row['own_probe'] = dict(own)
                row['own_new_played'] = {k: v for k, v in (row.get('own_played') or {}).items() if k not in c56}
            row['wall_s'] = round(time.time() - t0, 1)
            fh.write(json.dumps(row) + '\n')
            fh.flush()
            if saver is not None:
                saver.flush()
            print(json.dumps({k: row.get(k) for k in ('deck', 'game', 'winner', 'ticks', 'crash', 'sources', 'panics',
                                                      'roots', 'opp_noncore_roots', 'wall_s')}), flush=True)
    if saver is not None:
        saver.close()


if __name__ == '__main__':
    main()
