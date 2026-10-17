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

    python -m bot.livediag.behaviour_diag sim CARDTABLE PLAYER DIR [DIR ...]   (L16 driver rows: packet_perc + play_log)
    python -m bot.livediag.behaviour_diag live CARDTABLE RUN_DIR [RUN_DIR ...] (live runs: perception.jsonl + decisions.jsonl)
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


def game_metrics(polls, plays, table):
    """polls: [(tick, enemy_units [(x, y, value, hp)], hand [cards], elixir)] sorted; plays: [(tick, card, x, y)] ours."""
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

    def count(kind, t):
        if last.get(kind) is None or t - last[kind] > WINDOW_GAP:
            m[kind + '_windows'] += 1
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
                count(pre + 'missed', t)
            else:
                count(pre + 'short', t)
    last_push = {0: -10 ** 9, 1: -10 ** 9}
    for t, units, hand, elixir in polls:
        for lane in (0, 1):
            v = sum(u[2] for u in units if BRIDGE[0] <= u[1] < BRIDGE[1] and (u[0] >= 9) == bool(lane))
            if v >= PUSH_VALUE:
                if t - last_push[lane] >= PUSH_QUIET:
                    pushes.append(elixir)
                last_push[lane] = t
    return m, pushes, giants


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
            games.append(game_metrics(polls, plays, table))
    return games


def live_games(table, runs):
    games = []
    for d in runs:
        d = Path(d)
        if not (d / 'perception.jsonl').exists():
            continue
        polls = []
        for line in open(d / 'perception.jsonl'):
            q = json.loads(line)
            if q.get('tick') is None:
                continue
            us, yolo = q.get('units') or [], q.get('units_yolo')
            names = yolo if isinstance(yolo, list) and len(yolo) == len(us) else [u.get('card') or u.get('cls') for u in us]
            units = [(u['x'], u['y'], *table.unit_info(nm)) for u, nm in zip(us, names) if int(u.get('owner', 0)) == 1]
            hand = [c for c in ((q.get('hand') or {}).get('cards') or []) if c]
            polls.append((float(q['tick']), units, hand, float(q.get('elixir') or 0)))
        polls.sort(key=lambda p: p[0])
        plays = []
        if (d / 'decisions.jsonl').exists():
            for line in open(d / 'decisions.jsonl'):
                x = json.loads(line)
                if x.get('submitted') and x.get('card'):
                    row, col = divmod(int(x['action']) % 576, 18)
                    plays.append((float(x['tick']), x['card'], col + .5, row + .5))
        games.append(game_metrics(polls, plays, table))
    return games


def main(argv=None):
    a = list(sys.argv[1:] if argv is None else argv)
    mode, table = a[0], Table(a[1])
    if mode == 'sim':
        out = summarise(sim_games(table, a[2], a[3:]))
        out['player'] = a[2]
    elif mode == 'live':
        out = summarise(live_games(table, a[2:]))
    else:
        raise SystemExit(__doc__)
    print(json.dumps(out, indent=1))


if __name__ == '__main__':
    main()
