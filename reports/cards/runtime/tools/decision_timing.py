"""Per-phase cost of complete live K4L decisions (scope c56 vs full; C56 vs non-C56 opponent decks).

    CLASHER_BOT_RUNTIME=<root> CLASHER_BOT_RUNTIME_PINS=<pins> python decision_timing.py --deck X1 --out OUT.jsonl \
        [--player LIVE-K4L-R-gs-rw-fc-w20000-t1-p2] [--decisions 120] [--save-roots R.jsonl.gz]

The live recipe's code path (LivePlayer -> WallLearnedPlayer -> reduce_fast, LiveBelief) with a wall so large that
every decision completes: deterministic, so the two scopes play the same game and pair decision by decision.
Opponent: noncore_matches.RandomMaskPlayer (seeded). Per search decision (one JSON row):
  prep:   poll (R3a cutoff-default poller), belief_update, propose (student), candidates, sample, root (R.root, incl.
          the payload json + native parse)
  json:   _ConfigJson.dumps calls / ms / payload bytes (the fc-cut root payload)
  ship:   LearnedPool.begin ms (root.snapshot + split + send to the P workers), snapshot bytes, config bytes sent
  search: reduce_fast phase_ms (ship, native, learned, parse, chunk), rollouts, candidates, completed
  total:  wall of the whole search-tier act
"""
import argparse
import gzip
import json
import random
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))
sys.path.insert(0, str(Path(__file__).resolve().parent))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--deck', required=True)
    ap.add_argument('--player', default='LIVE-K4L-R-gs-rw-fc-w20000-t1-p2')
    ap.add_argument('--decisions', type=int, default=120)
    ap.add_argument('--seed', type=int, default=20261016200)
    ap.add_argument('--save-roots')
    ap.add_argument('--out', required=True)
    ap.add_argument('--side-cut', action='store_true', help='install bot/cards/fc_cut.py before the pool forks')
    a = ap.parse_args()
    from bot.players.runtime import Runtime
    rt = Runtime()
    from bot.players.ours import play_match
    from bot.live.player import make_live_player
    from bot.search import lopp_fast
    from noncore_matches import DECKS, RandomMaskPlayer
    R = rt.R
    cur = {}
    rows = []
    saver = gzip.open(a.save_roots, 'wt') if a.save_roots else None

    def timed(name, fn):
        def wrapper(*args, **kw):
            t0 = time.perf_counter()
            try:
                return fn(*args, **kw)
            finally:
                cur[name] = cur.get(name, 0.) + 1e3 * (time.perf_counter() - t0)
        return wrapper

    base_root = R.root
    nroots = [0]

    def root(info, opponent, rng):
        r = timed('root', base_root)(info, opponent, rng)
        nroots[0] += 1
        if saver is not None and nroots[0] % 3 == 0:
            saver.write(json.dumps(dict(deck=a.deck, seat=int(info.seat), tick=int(info.tick), snapshot=r.snapshot())) + '\n')
        return r
    R.root = root

    begin = lopp_fast.LearnedPool.begin

    def begin_timed(self, root, *args, **kw):
        t0 = time.perf_counter()
        snap = root.snapshot()
        cur['snapshot_ms'] = cur.get('snapshot_ms', 0.) + 1e3 * (time.perf_counter() - t0)
        parts = lopp_fast.split_snapshot(snap)
        cur['snapshot_bytes'] = len(snap)
        cur['config_bytes'] = len(parts[1]) if parts else None
        sent_before = getattr(self, 'config', None)
        t0 = time.perf_counter()
        out = begin(self, root, *args, **kw)
        cur['begin_ms'] = cur.get('begin_ms', 0.) + 1e3 * (time.perf_counter() - t0)
        cur['config_resent'] = self.config is not sent_before
        return out
    lopp_fast.LearnedPool.begin = begin_timed

    if a.side_cut:
        from bot.cards import fc_cut
        fc_cut.install()
    ours = make_live_player(rt, a.player)
    start = ours.start

    def start_patched(ctx):
        start(ctx)
        s = ours.search
        p = s.p
        p.belief.update = timed('belief_update', p.belief.update)
        p.belief.sample = timed('sample', p.belief.sample)
        p.core.candidates = timed('candidates', p.core.candidates)
        s.cached.propose = timed('propose', s.cached.propose)
        s.poller.poll = timed('poll', s.poller.poll)
        shim = getattr(rt, '_fast_prep_shim', None)
        if shim is not None and not getattr(shim, '_timed', False):
            dumps = shim.dumps

            def dumps_timed(obj, *args, **kw):
                t0 = time.perf_counter()
                text = dumps(obj, *args, **kw)
                cur['json_ms'] = cur.get('json_ms', 0.) + 1e3 * (time.perf_counter() - t0)
                cur['json_calls'] = cur.get('json_calls', 0) + 1
                cur['payload_bytes'] = len(text)
                return text
            shim.dumps = dumps_timed
            shim._timed = True
        sact = s.act

        def act(view, **kw):
            cur.clear()
            t0 = time.perf_counter()
            d = sact(view, **kw)
            total = 1e3 * (time.perf_counter() - t0)
            if d.stats is not None:
                st = d.stats
                rows.append(dict(cur, tick=int(view.tick), total_ms=round(total, 2),
                                 phase_ms=st.get('phase_ms'), rollouts=st.get('rollouts'),
                                 candidates=st.get('candidates'), completed=st.get('completed'), hit=st.get('hit'),
                                 action=int(d.action)))
                if len(rows) >= a.decisions:
                    raise StopIteration
            return d
        s.act = act
    ours.start = start_patched

    seat = 0
    rng = random.Random(a.seed)
    mine = list(rt.x4s_decks()[0])
    theirs = list(rt.x4s_decks()[int(a.deck[1:])]) if a.deck[0] == 'X' else list(DECKS[a.deck])
    rng.shuffle(mine); rng.shuffle(theirs)
    opp = RandomMaskPlayer(rt, a.seed)
    t0 = time.time()
    res = None
    try:
        res = play_match(rt, {seat: ours, 1 - seat: opp}, seed=a.seed, decks=[mine, theirs], max_ticks=6001)
    except StopIteration:
        pass
    except RuntimeError as ex:          # StopIteration raised inside a generator frame surfaces as RuntimeError
        if 'StopIteration' not in repr(ex):
            raise
    if saver is not None:
        saver.close()
    with open(a.out, 'w') as fh:
        fh.write(json.dumps(dict(deck=a.deck, player=a.player, scope=getattr(R, 'card_scope', 'c56') + ('+side' if a.side_cut or getattr(lopp_fast, '_side_cut_installed', False) else ''),
                                 config_cards=len(R.config['cards']), decisions=len(rows), wall_s=round(time.time() - t0, 1),
                                 command_sha256=res and res['command_sha256'])) + '\n')
        for r in rows:
            fh.write(json.dumps(r) + '\n')


if __name__ == '__main__':
    main()
