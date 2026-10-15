"""Oracle replay harness: perfect/noisy perception records -> LiveTranslator -> LivePlayer (LIVE track, exploration).

Two sources.

engine  (--source engine): full matches in OUR engine (bot.players.ours.play_match, X4S loop). The bot sits in seat 0
        and is fed the TRUE public view (fair_player.observe = ContractV5ObservationBuilder.build_public) - this is
        the bot exactly as evaluated. At every poll, each shadow (one per noise config) gets a synthetic perception
        record built from that same true view (bot/live/synth.py), translated by LiveTranslator, and decides with its
        own LivePlayer instance (same tier, same seeds, same pending own command). Agreement = shadow action == truth
        action on the truth's decisions (searched/fast decisions; non-decisions excluded). Deterministic tiers
        (unbounded search, it5s2) make agreement a pure information-loss measure.
t1      (--source t1): recorded official-client (private-server) matches from the T1 TRAIN/VAL split only. The split
        file is filtered to split in {train, val}; every match dir is asserted to be listed there; heldout is never
        opened. A perfect record per poll comes from the labelled objects (labels_v4.BodyLabels identity), the own
        HUD (evaluation-only observation, own seat only) and the accepted events; shadows add noise. Reference =
        the bot on the perfect record. Also gives latency on real-client states and body-mapping coverage.

    PYTHONPATH=. CLASHER_BOT_RUNTIME=... nice -n 19 taskset -c 2-5 python -m bot.live.replay --source engine \
        --tier search --games 4 --out DIR
"""
from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path

import numpy as np

from bot.players.base import Decision, PublicView, WAIT
from bot.live.synth import Noise, PERFECT, SynthPerception, noisy, EventChannel

# Perception-level arms (LIVE LEAD 2026-10-14): val baseline unit identity x owner P .95 / R .42 (fine-tune
# rising), hand 97.9% per slot, elixir MAE .075, tower HP MAE .024. No play events: opponent plays from births.
_P = dict(precision=.95, jitter=.3, hp=.05, tower=.03, hand=.02, elixir=.1, events='own')
NOISE_GRID = {
    'events': PERFECT,                                  # perfect units + every play event (upper bound)
    'births': Noise(events='own'),                      # perfect units, opponent plays derived from births
    'p70': Noise(recall=.70, **_P),
    'p42': Noise(recall=.42, **_P),
    'r42-only': Noise(recall=.42, events='own'),        # recall alone
    'hud-only': Noise(hand=.02, elixir=.1, tower=.03, events='own'),
    'reseed': PERFECT,                                  # 'events' input, search/poll seeds +7: the bot's own noise floor
}
PLAYS_FROM = {'events': 'events', 'reseed': 'events'}                       # every other arm: 'births'
DATA = Path('/mpac/sdicks02/repos/clasher-bot-data')
SPLIT_OK = ('train', 'validation')   # registered labels in t1-split.json (heldout never)


def make_live(rt, tier, wall_ms, threads):
    from bot.live.player import LivePlayer
    return LivePlayer(rt, tier=tier, wall_ms=wall_ms, threads=threads)


class Shadow:
    def __init__(self, rt, name, noise, player, deck, seed):
        from bot.live.translate import LiveTranslator
        self.name, self.noise, self.player = name, noise, player
        self.tr = LiveTranslator(rt, deck, plays_from=PLAYS_FROM.get(name, 'births'))
        self.rng = np.random.default_rng([seed, abs(hash(name)) % (1 << 31)])
        self.events = EventChannel(noise, self.rng)
        self.rows = []

    def act(self, rt, record, view, ch):
        info = self.tr.information(self.events(record))
        try:
            reserved = ch.own_packet(info, rt.R.builder) if ch is not None else info
        except ValueError:
            reserved = info
        sv = PublicView(view.tick, 0, info, reserved, self.tr.public_events, view.pending, view.can_act)
        try:
            return self.player.act(sv)
        except Exception as ex:   # recorded as a disagreement, never silently dropped
            return Decision(WAIT, stats=dict(error=repr(ex)[:300]))


class ShadowingPlayer:
    """Seat-0 Player for play_match: truth decides and is executed; shadows decide on translated records."""

    def __init__(self, rt, truth, shadows, deck_of_seat0):
        self.rt, self.truth, self.shadows = rt, truth, shadows
        self.name, self.deadline_seconds = truth.name, truth.deadline_seconds
        self.deck = deck_of_seat0
        self.ch = None
        self.rows = []
        self.synth = SynthPerception(rt)
        self.cards = [c for c in sorted(rt.R.costs) if self.synth.cb.main.get(c)]   # confusions among unit cards

    def start(self, ctx):
        self.truth.start(ctx)
        from dataclasses import replace
        for s in self.shadows:
            s.tr.set_own_order(ctx.own_order)
            s.player.start(replace(ctx, seed=ctx.seed + 7) if s.name == 'reseed' else ctx)

    def act(self, view):
        d = self.truth.act(view)
        self.last_events = view.public_events
        record = self.synth.record(view)
        for s in self.shadows:
            sd = s.act(self.rt, noisy(record, s.noise, s.rng, self.deck, self.cards), view, self.ch)
            if d.stats is not None:
                self.rows.append(dict(tick=view.tick, shadow=s.name, truth=int(d.action), action=int(sd.action),
                                      agree=int(d.action) == int(sd.action),
                                      truth_play=int(d.action) < WAIT, shadow_play=int(sd.action) < WAIT,
                                      error=(sd.stats or {}).get('error')))
        return d

    def close(self):
        self.truth.close()
        for s in self.shadows:
            s.player.close()


def run_engine(rt, a, out):
    from bot.players.ours import play_match, x4s_setup
    import bot.players.ours as ours
    from clasher.analysis.loss_review.delay_fixes import CommandQueue
    from bot.eval.headline import make_player
    # Let the shadowing player see its own seat's CommandQueue (pending reservation for the shadows' views).
    original = CommandQueue.__init__
    queues = []

    def init(self, *args, **kw):
        original(self, *args, **kw)
        queues.append(self)
    names = [n for n in a.noise.split(',')]
    summary = []
    for g in range(a.start, a.start + a.games):
        case = x4s_setup(rt, g, a.base)
        decks = case['decks'] if case['seat'] == 0 else case['decks'][::-1]   # bot always seat 0
        truth = make_live(rt, a.tier, a.wall_ms, a.threads)
        shadows = [Shadow(rt, n, NOISE_GRID[n], make_live(rt, a.tier, a.wall_ms, a.threads), decks[0], case['seed'])
                   for n in names]
        sp = ShadowingPlayer(rt, truth, shadows, decks[0])
        queues.clear()
        CommandQueue.__init__ = init
        try:
            t0 = time.time()
            orig_act = sp.act

            def act(view, orig_act=orig_act):
                sp.ch = queues[0] if queues else None
                return orig_act(view)
            sp.act = act   # the first CommandQueue play_match builds is seat 0's
            res = play_match(rt, {0: sp, 1: make_player(rt, a.opponent)}, seed=case['seed'], decks=decks,
                             max_ticks=a.max_ticks)
        finally:
            CommandQueue.__init__ = original
        dec = truth.decisions
        with open(out / 'agreement.jsonl', 'a') as f:
            for r in sp.rows:
                f.write(json.dumps(dict(r, game=g, tier=a.tier)) + '\n')
        with open(out / 'decisions.jsonl', 'a') as f:
            for s in dec:
                f.write(json.dumps(dict(s, game=g, tier=a.tier, role='truth')) + '\n')
        stats = {s.name: dict(s.tr.stats, **{f'tracker:{k}': v for k, v in s.tr.tracker.stats.items()},
                              derived_plays=len(s.tr.derived_plays),
                              true_opp_plays=sum(e['seat'] == 1 and e['kind'] == 'card' for e in sp.last_events))
                 for s in shadows}
        stats['_synth'] = dict(sp.synth.stats)
        summary.append(dict(game=g, seed=case['seed'], winner=res['winner'], ticks=res['ticks'],
                            secs=round(time.time()-t0, 1), translator=stats,
                            belief_rebuilds=max((d.get('belief_rebuilds', 0) for d in dec), default=0)))
        with open(out / 'games.jsonl', 'a') as f:
            f.write(json.dumps(summary[-1]) + '\n')
        print(json.dumps(summary[-1])[:400], flush=True)
    return summary


# ---------------------------------------------------------------------------------------------------------------
# T1 recorded matches (train/val only)

def t1_matches(split_path=DATA / 't1-split.json', root=DATA / 't1-trainval'):
    split = json.loads(Path(split_path).read_text())
    allowed = {m['episode']: m for m in split['matches'] if m['split'] in SPLIT_OK}
    dirs = sorted(p for p in Path(root).iterdir() if p.is_dir())
    for p in dirs:
        assert p.name in allowed, f'{p.name} is not a registered train/val match: refusing'
        assert allowed[p.name]['split'] in SPLIT_OK
    return [(p, allowed[p.name]) for p in dirs]


class T1Match:
    """Perfect perception records for one recorded match, seat `seat` as 'us' (rotated to our frame for seat 1)."""

    def __init__(self, rt, path, entry, seat=0):
        import gzip
        import sys
        lab = Path(os.environ.get('CLASHER_LIVE_LABELS', Path(__file__).resolve().parents[2] /
                                  'reports/strategy_council_20260928/live-loop/v4/l1'))
        sys.path.insert(0, str(lab))
        from labels_v4 import BodyLabels, read_objects
        gamedata = Path(rt.root) / 'gamedata.json'
        catalog = lab.parent / 'body-catalog.json'
        self.labels = BodyLabels(gamedata, catalog)
        self.entry, self.seat, self.path = entry, seat, Path(path)
        assert entry['split'] in SPLIT_OK
        self.frames = read_objects(self.path / 'objects.jsonl.gz')
        self.hud = {}
        with gzip.open(self.path / 'evaluation-only.jsonl.gz', 'rt') as f:
            for line in f:
                r = json.loads(line)
                o = r['observation']
                me = [p for p in o['players'] if p['owner'] == seat][0]    # own record ONLY
                self.hud[o['tick']] = me
        ids = {v: k for k, v in json.loads((DATA / 't1-split.json').read_text())['ids'].items()}
        self.card_of = lambda cid: ids.get(cid)
        self.events = [json.loads(l) for l in (self.path / 'events.jsonl').read_text().splitlines()]
        self.events = [e for e in self.events if e.get('accepted')]
        self.deck = list(entry['decks'][seat])
        self.stats = {}

    def frame(self, x, y):
        x, y = x/1000., y/1000.
        return (18-x, 32-y) if self.seat == 1 else (x, y)

    def records(self, every=5):
        from collections import Counter
        st = Counter()
        hud_ticks = sorted(self.hud)
        hi = 0
        last = None
        for fr in self.frames:
            if last is not None and fr['tick']//every == last//every:
                continue
            last = fr['tick']
            tick = fr['tick'] - fr['tick'] % every      # poll tick; the frame is <= every-1 ticks later
            while hi + 1 < len(hud_ticks) and hud_ticks[hi+1] <= tick:
                hi += 1
            me = self.hud[hud_ticks[hi]]
            units, towers = [], {}
            for o in fr['objects']:
                owner = 0 if o['owner'] == self.seat else 1
                if o.get('visible_hint') == 'invisible' and owner == 1:
                    st['hidden_enemy'] += 1
                    continue
                if not o.get('max_hp') or o['max_hp'] <= 0:
                    st['non_hitpoint'] += 1                 # spells, projectiles: not in the perception schema
                    continue
                x, y = self.frame(o['x'], o['y'])
                if o['card_id'] == -1:
                    name, _ = self.labels.identity(o)
                    if name in ('KingTower', 'PrincessTower'):
                        side = None if name == 'KingTower' else ('left' if x < 9 else 'right')
                        towers[(owner, 'king' if name == 'KingTower' else 'princess', side)] = o['hp']/o['max_hp']
                    else:
                        st['unlabelled_tower_like'] += 1
                    continue
                card = self.card_of(o['card_id'])           # perception identity = the spawning card
                if card is None:
                    st['unknown_card_id'] += 1
                    continue
                st['units'] += 1
                units.append(dict(cls=card, card=card, owner=owner, x=x, y=y, hp_frac=o['hp']/o['max_hp'], score=1.))
            tw = [dict(owner=o, kind=k, side=s, hp_frac=hp, alive=hp > 0) for (o, k, s), hp in towers.items()]
            for o in (0, 1):     # a missing tower object after it existed = destroyed
                for k, s in (('king', None), ('princess', 'left'), ('princess', 'right')):
                    if (o, k, s) not in towers:
                        tw.append(dict(owner=o, kind=k, side=s, hp_frac=0., alive=False))
            hand = [self.card_of(c['cardId']) for c in sorted(me['hand'], key=lambda c: c['handIndex'])]
            nxt = self.card_of(me['nextCard']['cardId']) if me.get('nextCard') else None
            events = []
            for e in self.events:
                if e['exec_tick'] > tick:
                    continue
                x, y = e['tile']
                if self.seat == 1:
                    x, y = 18-x, 32-y
                events.append(dict(owner=0 if e['side'] == self.seat else 1, card=e['card'], x=x, y=y,
                                   tick=e['exec_tick']))
            yield dict(tick=tick, units=units, towers=tw, hand=dict(cards=hand, next=nxt),
                       elixir=float(me['elixir']), events=events, schema='clasher.live.perception-frame.v1')
        self.stats = dict(st)


def run_t1(rt, a, out):
    from bot.players.base import MatchContext, POLICY_INTERVAL, START_TICK
    from bot.live.translate import LiveTranslator
    matches = t1_matches()
    rng = np.random.default_rng(a.base)
    pick = rng.choice(len(matches), size=min(a.games, len(matches)), replace=False)
    names = a.noise.split(',')
    for gi, mi in enumerate(sorted(pick)):
        path, entry = matches[mi]
        seat = gi % 2
        m = T1Match(rt, path, entry, seat)
        if any(c not in rt.R.costs for c in m.deck):
            print('skip non-C56 own deck', path.name)
            continue
        records = [r for r in m.records(POLICY_INTERVAL) if r['tick'] >= START_TICK]
        first = records[0]['hand']
        order = list(first['cards']) + ([first['next']] if first['next'] not in first['cards'] else [])
        order += [c for c in m.deck if c not in order]
        ctx = MatchContext(seat=0, seed=entry['seed'], own_order=tuple(order))
        arms = []
        for n in names:
            p = make_live(rt, a.tier, a.wall_ms, a.threads)
            from dataclasses import replace
            p.start(replace(ctx, seed=ctx.seed + 7) if n == 'reseed' else ctx)
            tr = LiveTranslator(rt, m.deck, plays_from=PLAYS_FROM.get(n, 'births'))
            tr.set_own_order(order)
            arms.append(dict(name=n, noise=NOISE_GRID[n], player=p, tr=tr,
                             rng=np.random.default_rng([entry['seed'], len(arms)]), errors=0))
            arms[-1]['events'] = EventChannel(arms[-1]['noise'], arms[-1]['rng'])
        t0 = time.time()
        rows = []
        unit_cards = [c for c in sorted(rt.R.costs) if arms[0]['tr'].cards.main.get(c)]
        for rec in records:
            if rec['tick'] % POLICY_INTERVAL:
                continue
            if a.max_ticks and rec['tick'] > a.max_ticks:
                break
            acts = {}
            for arm in arms:
                r = arm['events'](noisy(rec, arm['noise'], arm['rng'], m.deck, unit_cards))
                try:
                    info = arm['tr'].information(r)
                    view = PublicView(rec['tick'], 0, info, info, arm['tr'].public_events, (), True)
                    d = arm['player'].act(view)
                    acts[arm['name']] = (int(d.action), d.stats)
                except Exception as ex:
                    arm['errors'] += 1
                    acts[arm['name']] = (WAIT, dict(error=repr(ex)[:300]))
            ref, ref_stats = acts[names[0]]
            if ref_stats is None:
                continue
            for n in names:
                act, st = acts[n]
                rows.append(dict(game=gi, episode=path.name, seat=seat, tick=rec['tick'], shadow=n, truth=ref,
                                 action=act, agree=act == ref, truth_play=ref < WAIT, shadow_play=act < WAIT,
                                 wall_ms=(st or {}).get('wall_ms'), source=(st or {}).get('source'),
                                 error=(st or {}).get('error'), tier=a.tier))
        for arm in arms:
            arm['player'].close()
        with open(out / 'agreement.jsonl', 'a') as f:
            for r in rows:
                f.write(json.dumps(r) + '\n')
        g = dict(game=gi, episode=path.name, split=entry['split'], seat=seat, secs=round(time.time()-t0, 1),
                 decisions=len(rows)//max(1, len(names)), records=m.stats,
                 translator={arm['name']: dict(arm['tr'].stats) for arm in arms},
                 errors={arm['name']: arm['errors'] for arm in arms},
                 belief_rebuilds={arm['name']: getattr(arm['player'].search.p.belief, 'rebuilds', 0)
                                  if arm['player'].search else 0 for arm in arms})
        with open(out / 'games.jsonl', 'a') as f:
            f.write(json.dumps(g) + '\n')
        print(json.dumps(g)[:600], flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--source', choices=['engine', 't1'], required=True)
    ap.add_argument('--tier', choices=['search', 'fast'], default='search')
    ap.add_argument('--wall-ms', type=int, default=None, help='None = unbounded deterministic search')
    ap.add_argument('--threads', type=int, default=1)
    ap.add_argument('--games', type=int, default=4)
    ap.add_argument('--start', type=int, default=0)
    ap.add_argument('--base', type=int, default=1455777415631152 + 10**6)   # fresh, not the HEADLINE cases
    ap.add_argument('--opponent', default='v1')
    ap.add_argument('--noise', default='events,births,p70,p42,r42-only,hud-only,reseed')
    ap.add_argument('--max-ticks', type=int, default=6001)
    ap.add_argument('--out', type=Path, required=True)
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    (a.out / f'launch-{int(time.time())}.json').write_text(json.dumps({k: str(v) for k, v in vars(a).items()}))
    import torch
    torch.set_num_threads(1)
    from bot.players.runtime import Runtime
    rt = Runtime()
    if a.source == 'engine':
        run_engine(rt, a, a.out)
    else:
        run_t1(rt, a, a.out)


if __name__ == '__main__':
    main()
