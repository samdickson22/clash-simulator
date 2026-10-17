"""Behaviour diagnostics (SC1 add-on; cycle-model owner; exploration): descriptive per-game rates from play logs plus
per-poll boards, for sim L16 driver rows and live runs. These are not rewards. Definitions are fixed in advance:

Unit value = the card's elixir cost / the number of units the card deploys (cardtable.json from the runtime config;
sim body classes map to cards through body_card; live units use the detector class names (units_yolo, e.g.
'spear-goblin'), matched to body names case- and dash-insensitively, since the card labels are noisier). Enemy units =
troops and buildings of the opponent (towers excluded).

(a) spell_casts, swarm_casts: one of our Zap/Fireball/Arrows casts is a swarm cast if, at the last poll at or before its
    execution, it covers >= N_SWARM = 3 enemy units or >= its own cost in enemy unit elixir within the radius of the target.
    tower_only_casts: covers no enemy unit and is aimed within 4 tiles of an enemy tower.
(b) a spell window at a poll: a spell is in our hand and some centre (an enemy unit's position) has >= N_SWARM = 3
    enemy units AND >= cost + 1 elixir of enemy units within the radius. missed_windows: our elixir >= the cost and no
    cast of ANY of our spells in [t, t + 20 ticks]; short_windows: the same, but our elixir < the cost of every
    qualifying spell (the banking question); taken_window_polls: a spell was cast within 20 ticks. Consecutive
    qualifying polls (gap <= 20 ticks) count as one window. Tower-kill windows are not counted (crown damage isn't in
    the config). The 3-unit floor keeps single tanks (a Giant in Zap range) out; fixed before any corpus run.
    lethal_*: the same counts using only units the spell kills from full HP at level 11 (max HP from the runtime config
    <= the spell's damage x waves; units of unknown HP are left out). Levels are 11 for both sides here, as in the
    planner (live opponents are often lower: s79-m05's L7 Barbarians die to our L9 Fireball, L11 ones do not).
Spell radius and damage come from the runtime config (cardtable.json 'spell': Zap 2.5, Fireball 2.5, Arrows spread
3.5); RADIUS below is the fallback and the set of spells measured.
(c) push_elixir: our elixir when an enemy push reaches our bridge. A push = >= 3 elixir of enemy units in our bridge band
    (12 <= y < 17, our frame) in one lane (x < 9 / x >= 9) after >= 100 ticks without one in that lane.
(d) giant_plays: our Giant plays by zone (y <= 6 back/behind the king, y >= 13 at the bridge, else mid) and our elixir at
    the last poll before the play.

(e) swarm_response (play sequences only, so humans can be compared): an opponent play of a swarm card (one that
    deploys >= 3 units: cost / unit value >= 3) is answered if we cast a small area spell (a config spell with damage
    and cost <= 4: Zap, Log, Snowball, Arrows, Fireball, Poison, ...) within 120 ticks (6 s) after it; counted only in
    games where we cast such a spell at least once (deck proxy). Live opponent plays are the detector's play events
    (incomplete), sim ones the opponent's play_log.
(f) idle_play_share (s81 review; PT1 amendment 2): share of our plays of cards with a Troop/Building unit (body_cards)
    with no enemy unit within IDLE_TILES = 6 tiles of the deploy tile at the last poll before the play.
(g) wincon_dump_rate (s81 review): per opponent play of a win-condition card (cardtable 'wincon': a unit with
    stats.only_buildings, a data rule; Goblin Barrel / Graveyard / Miner / X-Bow are not in it), whether we made a play
    in the DUMP_TICKS = 60 ticks (3 s) before it after which our elixir (first poll after our play, before the reveal)
    was <= DUMP_ELIXIR = 1.0. Sim: the opponent's play_log; live: the detector's play events (incomplete).
(h) elixir at the enemy's cross: bot.livediag.l16_report's elixir_cross_p50 (not recomputed here).
Human replays (IL_Replay, internal eval only; no board, so (a)-(c) are unavailable): (d) uses our own elixir by
accounting (start 5; +1 per 56 ticks, per 28 after tick 2400, per 18.67 after 3600; cap 10; minus card costs) and (e).

    python -m bot.livediag.behaviour_diag sim CARDTABLE PLAYER DIR [DIR ...]   (L16 driver rows: packet_perc + play_log)
    python -m bot.livediag.behaviour_diag live CARDTABLE RUN_DIR [RUN_DIR ...] (live runs: perception.jsonl + decisions.jsonl)
    python -m bot.livediag.behaviour_diag human CARDTABLE PARQUET [PARQUET ...] (royaleapi replay parquet; side 'team')
"""
from __future__ import annotations

import bisect
import collections
import glob
import json
import math
import statistics
import sys
from pathlib import Path

RADIUS = {'Zap': 2.5, 'Fireball': 2.5, 'Arrows': 3.5}
N_SWARM = 3
WINDOW_GAP = 20
PUSH_VALUE, PUSH_QUIET = 3.0, 100
RESPONSE_TICKS = 120
IDLE_TILES = 6.0
DUMP_TICKS, DUMP_ELIXIR = 60, 1.0
BRIDGE = (12.0, 17.0)
ENEMY_TOWERS = [(3.5, 25.5), (14.5, 25.5), (9.0, 29.0)]


class Table:
    def __init__(self, path):
        t = json.loads(Path(path).read_text())
        self.cost, self.unit, self.body = t['card_cost'], t['card_unit_value'], t['body_card']
        self.body_hp, self.card_hp = t.get('body_hp', {}), t.get('card_hp', {})
        self.radius = {c: v['radius'] for c, v in t.get('spell', {}).items() if c in RADIUS}
        self.damage = {c: v['damage'] for c, v in t.get('spell', {}).items() if c in RADIUS}
        self.fold = {k.replace('-', '').replace('_', '').casefold(): k for k in list(self.body) + list(self.unit)}
        self.small_spells = {c for c, v in t.get('spell', {}).items() if v.get('damage') and self.cost.get(c, 99) <= 4}
        self.body_cards, self.wincon = set(t.get('body_cards', [])), set(t.get('wincon', []))
        cards = list(self.cost)
        self.card_fold = {k.replace('-', '').replace('_', '').replace('.', '').replace(' ', '').casefold(): k for k in cards}

    def card(self, key):
        """Card name for a royaleapi card key ('the-log', 'giant', 'minion-horde-ev1')."""
        k = key.rsplit('-ev', 1)[0] if '-ev' in key else key
        f = k.replace('-', '').casefold()
        return self.card_fold.get(f) or self.card_fold.get(f.replace('the', '', 1))

    def swarm(self, card):
        v = self.unit.get(card)
        return bool(v) and round(self.cost.get(card, 0) / v) >= N_SWARM

    def card_of(self, name):
        if name in self.unit:
            return name
        return self.body.get(name)

    def resolve(self, name):
        """(body or card name, card) for a body / card / detector class name."""
        if not name:
            return None, None
        if self.card_of(name):
            return name, self.card_of(name)
        f = name.replace('-', '').replace('_', '').casefold()
        k = self.fold.get(f) or self.fold.get(f + 's')
        return (k, self.card_of(k)) if k else (None, None)

    def value(self, name):
        _, c = self.resolve(name)
        return self.unit.get(c, 0.0) if c else 0.0

    def unit_info(self, name):
        """(elixir value, max HP at level 11 or None)."""
        k, c = self.resolve(name)
        if c is None:
            return 0.0, None
        hp = self.body_hp.get(k)
        if hp is None and k == c:
            hp = self.card_hp.get(c)
        return self.unit.get(c, 0.0), hp


def game_metrics(polls, plays, table, log=None, opp_plays=None):
    """polls: [(tick, enemy_units [(x, y, value, hp)], hand [cards], elixir)] sorted; plays: [(tick, card, x, y)] ours.
    log: optional list, gets (kind, tick, elixir, spells) at each window start."""
    ticks = [p[0] for p in polls]
    m = collections.Counter()
    pushes, giants = [], []

    def at(t):
        i = bisect.bisect_right(ticks, t) - 1
        return polls[i] if i >= 0 else None

    def radius(card):
        return table.radius.get(card, RADIUS[card])

    spell_ticks = sorted(t for t, c, _, _ in plays if c in RADIUS)
    for t, card, x, y in plays:
        p = at(t)
        if card in RADIUS and p is not None:
            cov = [u[2] for u in p[1] if math.hypot(u[0] - x, u[1] - y) <= radius(card)]
            m['spell_casts'] += 1
            if len(cov) >= N_SWARM or sum(cov) >= table.cost.get(card, 99):
                m['swarm_casts'] += 1
            if not cov and min(math.hypot(x - a, y - b) for a, b in ENEMY_TOWERS) <= 4.0:
                m['tower_only_casts'] += 1
        if card == 'Giant' and p is not None:
            zone = 'back' if y <= 6 else 'bridge' if y >= 13 else 'mid'
            giants.append((zone, p[3]))
    last = {}

    def window(units, card, lethal):
        r, need, dmg = radius(card), table.cost[card] + 1, table.damage.get(card, 0.0)
        pool = [u for u in units if u[3] is not None and u[3] <= dmg] if lethal else units
        for cx, cy, _, _ in pool:
            cov = [u[2] for u in pool if math.hypot(u[0] - cx, u[1] - cy) <= r]
            if len(cov) >= N_SWARM and sum(cov) >= need:
                return True
        return False

    def count(kind, t, elixir=None, spells=()):
        if last.get(kind) is None or t - last[kind] > WINDOW_GAP:
            m[kind + '_windows'] += 1
            if log is not None:
                log.append((kind, t, elixir, tuple(spells)))
        last[kind] = t

    for t, units, hand, elixir in polls:
        for pre, lethal in (('', False), ('lethal_', True)):
            spells = [c for c in hand if c in RADIUS and c in table.cost and window(units, c, lethal)]
            if not spells:
                continue
            j = bisect.bisect_left(spell_ticks, t)
            if j < len(spell_ticks) and spell_ticks[j] <= t + WINDOW_GAP:
                m[pre + 'taken_window_polls'] += 1
            elif any(elixir >= table.cost[c] for c in spells):
                count(pre + 'missed', t, elixir, spells)
            else:
                count(pre + 'short', t, elixir, spells)
    for t, card, x, y in plays:                       # (f) idle plays
        p = at(t)
        if card in table.body_cards and p is not None:
            m['body_plays'] += 1
            if not any(math.hypot(u[0] - x, u[1] - y) <= IDLE_TILES for u in p[1]):
                m['idle_plays'] += 1
    for t, card in (opp_plays or []):                  # (g) spend-down before a revealed win condition
        if card not in table.wincon:
            continue
        m['opp_wincon_plays'] += 1
        for tp, c2, _, _ in plays:
            if t - DUMP_TICKS <= tp < t:
                i = bisect.bisect_right(ticks, tp)       # first poll after our play
                if i < len(polls) and polls[i][0] <= t and polls[i][3] <= DUMP_ELIXIR:
                    m['wincon_dumps'] += 1
                    break
    last_push = {0: -10 ** 9, 1: -10 ** 9}
    for t, units, hand, elixir in polls:
        for lane in (0, 1):
            v = sum(u[2] for u in units if BRIDGE[0] <= u[1] < BRIDGE[1] and (u[0] >= 9) == bool(lane))
            if v >= PUSH_VALUE:
                if t - last_push[lane] >= PUSH_QUIET:
                    pushes.append(elixir)
                last_push[lane] = t
    return m, pushes, giants


def swarm_response(opp_plays, our_plays, table):
    """(swarm plays, answered) for one game; (0, 0) if we never cast a small spell (deck proxy)."""
    ours = sorted(t for t, c in our_plays if c in table.small_spells)
    if not ours:
        return 0, 0
    n = k = 0
    for t, c in opp_plays:
        if table.swarm(c):
            n += 1
            j = bisect.bisect_right(ours, t)
            k += j < len(ours) and ours[j] <= t + RESPONSE_TICKS
    return n, k


def elixir_accounting(plays, table):
    """Our elixir just before each of our plays [(tick, card)] (sorted), from regeneration and costs only."""
    e, t0, out = 5.0, 0.0, []
    for t, c in plays:
        while t0 < t:                                     # integrate piecewise regeneration up to t
            rate = 1 / 56 if t0 < 2400 else 1 / 28 if t0 < 3600 else 1 / 18.67
            nxt = min(t, 2400 if t0 < 2400 else 3600 if t0 < 3600 else t)
            e = min(10.0, e + (nxt - t0) * rate)
            t0 = nxt
        out.append(e)
        e = max(0.0, e - table.cost.get(c, 0.0))
    return out


def human_games(table, paths):
    import pyarrow.parquet as pq
    games = []
    for path in paths:
        for js in pq.read_table(path, columns=['payload_json']).column(0).to_pylist():
            ev = [x for x in json.loads(js).get('events', []) if x.get('kind') == 'play_card']
            team, opp = [], []
            for x in ev:
                c = table.card(x.get('card_key') or '')
                if c is None:
                    continue
                w = (x.get('coordinates') or {}).get('native_world_units') or {}
                rec = (int(x['replay_tick_20hz']), c, w.get('x', 0) / 1000, w.get('y', 0) / 1000)
                (team if x.get('side') == 'team' else opp).append(rec)
            team.sort()
            m = collections.Counter()
            n, k = swarm_response([(t, c) for t, c, _, _ in opp], [(t, c) for t, c, _, _ in team], table)
            m['opp_swarm_plays'] += n
            m['swarm_responses'] += k
            el = elixir_accounting([(t, c) for t, c, _, _ in team], table)
            giants = [('back' if y <= 6 else 'bridge' if y >= 13 else 'mid', e)
                      for (t, c, x, y), e in zip(team, el) if c == 'Giant']
            games.append((m, [], giants))
    return games


def summarise(games):
    n = len(games)
    tot = collections.Counter()
    pushes, giants = [], []
    for m, p, g in games:
        tot.update(m)
        pushes += p
        giants += g
    zones = collections.Counter(z for z, _ in giants)
    out = dict(games=n, per_game={k: round(v / max(n, 1), 3) for k, v in sorted(tot.items())},
               swarm_share=round(tot['swarm_casts'] / max(tot['spell_casts'], 1), 3),
               swarm_response_rate=round(tot['swarm_responses'] / tot['opp_swarm_plays'], 3) if tot['opp_swarm_plays'] else None,
               idle_play_share=round(tot['idle_plays'] / tot['body_plays'], 3) if tot['body_plays'] else None,
               wincon_dump_rate=round(tot['wincon_dumps'] / tot['opp_wincon_plays'], 3) if tot['opp_wincon_plays'] else None,
               push_elixir=dict(n=len(pushes), mean=round(statistics.mean(pushes), 2) if pushes else None,
                                median=round(statistics.median(pushes), 2) if pushes else None),
               giant=dict(n=len(giants), zones={k: round(v / max(len(giants), 1), 3) for k, v in zones.items()},
                          elixir_mean=round(statistics.mean(e for _, e in giants), 2) if giants else None))
    return out


def sim_games(table, player, dirs):
    games = []
    for d in dirs:
        for path in glob.glob(f'{d}/rows/*.json'):
            r = json.load(open(path))
            if r.get('player') != player or r.get('error'):
                continue
            polls = []
            for q in r['packet_perc']:
                units = [(u['x'], u['y'], *table.unit_info(u['cls'])) for u in q['units'] if u['owner'] == 1]
                hand = [c for c in (q.get('hand') or {}).get('cards', []) if c]
                polls.append((q['tick'], units, hand, float(q.get('elixir', 0))))
            plays = []
            for t, card, action, ok in r['result']['play_log'][str(r['seat'])]:
                if ok:
                    row, col = divmod(action % 576, 18)
                    plays.append((t, card, col + .5, row + .5))
            opp = [(t, c) for t, c, _, ok in r['result']['play_log'][str(1 - int(r['seat']))] if ok]
            g = game_metrics(polls, plays, table, opp_plays=opp)
            n, k = swarm_response(opp, [(t, c) for t, c, _, _ in plays], table)
            g[0]['opp_swarm_plays'] += n
            g[0]['swarm_responses'] += k
            games.append(g)
    return games


def live_games(table, runs):
    games = []
    for d in runs:
        d = Path(d)
        if not (d / 'perception.jsonl').exists():
            continue
        polls, opp = [], []
        for line in open(d / 'perception.jsonl'):
            q = json.loads(line)
            if q.get('tick') is None:
                continue
            us, yolo = q.get('units') or [], q.get('units_yolo')
            names = yolo if isinstance(yolo, list) and len(yolo) == len(us) else [u.get('card') or u.get('cls') for u in us]
            units = [(u['x'], u['y'], *table.unit_info(nm)) for u, nm in zip(us, names) if int(u.get('owner', 0)) == 1]
            hand = [c for c in ((q.get('hand') or {}).get('cards') or []) if c]
            polls.append((float(q['tick']), units, hand, float(q.get('elixir') or 0)))
            opp += [(float(q['tick']), e['card']) for e in (q.get('events') or []) if int(e.get('owner', 0)) == 1
                    and e.get('card')]
        polls.sort(key=lambda p: p[0])
        plays = []
        if (d / 'decisions.jsonl').exists():
            for line in open(d / 'decisions.jsonl'):
                x = json.loads(line)
                if x.get('submitted') and x.get('card'):
                    row, col = divmod(int(x['action']) % 576, 18)
                    plays.append((float(x['tick']), x['card'], col + .5, row + .5))
        g = game_metrics(polls, plays, table, opp_plays=sorted(opp))
        n, k = swarm_response(sorted(opp), [(t, c) for t, c, _, _ in plays], table)
        g[0]['opp_swarm_plays'] += n
        g[0]['swarm_responses'] += k
        games.append(g)
    return games


def main(argv=None):
    a = list(sys.argv[1:] if argv is None else argv)
    mode, table = a[0], Table(a[1])
    if mode == 'sim':
        out = summarise(sim_games(table, a[2], a[3:]))
        out['player'] = a[2]
    elif mode == 'live':
        out = summarise(live_games(table, a[2:]))
    elif mode == 'human':
        out = summarise(human_games(table, a[2:]))
    else:
        raise SystemExit(__doc__)
    print(json.dumps(out, indent=1))


if __name__ == '__main__':
    main()
