"""Board-noise injection for the L16 driver (BN1, cycle-model owner; exploration): own units shown as ENEMY units on the
board OUR player plans on, as the live owner model does (v1.1 vs v1.4c).

Measured input (board_noise_runs.json, from the translator owner's BOARD-OWN-AS-ENEMY.json, 13 adjudicated live battles):
per battle, runs of consecutive translator records (~1 sim poll each) in which >= 1 own unit of a card was owned ENEMY in
the bot's units. Per arm: the pooled (card, run length) list, the per-battle run counts, units per record per card. It is a
lower bound (cards in both decks excluded). Form = RELABEL: the same body flips owner (gone from our side, present as
enemy), per the LIVE LEAD.

Arms (spec): 'v11' (v1.1 rates), 'v14c' (v1.4c rates), 'v11x3' (three times the v1.1 run count). Per battle (seeded by the case
seed, the seat and the arm, so arms stay paired and a case replays identically):
  K = the run count of one of the 13 battles drawn uniformly (x3 for x3 arms); K runs (card, length) drawn from the pooled
  list; start tick uniform in [START_TICK, END_TICK). At its first poll at/after the start, a run anchors on an own Troop
  of that card on the board, preferring our half (seat frame y < 16), nearest our king; if none is present it waits up to
  WAIT_TICKS, else it is dropped (counted). For `length` polls it relabels the round(units_per_record[card]) own units of
  that card nearest the anchor (within TRACK_TILES of it; the anchor follows them) as ENEMY; if none remain it ends.

Only the packets our player receives change (view.info.packet and view.reserved.packet, entity columns 2/3 = own/enemy);
the engine, the opponent, the public play streams (D1 rows, events) and the hand are untouched. Wrapper:
BoardNoisePlayer(rt, inner, spec, seed, seat) - act(view) transforms the view, then delegates; counts in .noise.counts
(the driver records them as noise_counts): runs_scheduled/applied/dropped, flipped_unit_polls, by card, and
plays made while a phantom was shown with the deploy tile within NEAR_TILES of it (phantom_near_plays/_elixir).
With no wrapper (token absent) the driver is unchanged; spec 'off' is the identity (parity check).
"""
from __future__ import annotations

import hashlib
import json
import math
import random
from dataclasses import replace
from pathlib import Path

START_TICK, END_TICK = 60, 3600          # runs start within regulation (3 min), after the first second
WAIT_TICKS = 600                          # a run waits up to 30 s for an own unit of its card
TRACK_TILES = 3.0
NEAR_TILES = 4.0
WAIT = 2304
SPECS = ('off', 'v11', 'v14c', 'v11x3', 'v14cx3')
_DATA = None


def data():
    global _DATA
    if _DATA is None:
        _DATA = json.loads((Path(__file__).with_name('board_noise_runs.json')).read_text())
    return _DATA


def _rng(*key):
    return random.Random(int.from_bytes(hashlib.sha256(repr(key).encode()).digest()[:8], 'big'))


def schedule(spec, seed, seat):
    """[(start_tick, card, length)] for one battle, deterministic in (spec, seed, seat)."""
    if spec not in SPECS:
        raise ValueError(f'board noise spec {spec!r}; expected one of {SPECS}')
    if spec == 'off':
        return []
    base, mult = (spec[:-2], 3) if spec.endswith('x3') else (spec, 1)
    d = data()['v1.1' if base == 'v11' else 'v1.4c']
    rng = _rng('board-noise', spec, int(seed), int(seat))
    k = rng.choice(d['per_battle']) * mult
    runs = [tuple(rng.choice(d['runs'])) for _ in range(k)]
    return sorted((rng.randrange(START_TICK, END_TICK), card, int(length)) for card, length in runs)


class BoardNoise:
    def __init__(self, rt, spec, seed, seat):
        from bot.live.births import CardBodies
        self.rt, self.spec, self.seat = rt, spec, seat
        self.pending = schedule(spec, seed, seat)
        self.active = []                 # dicts: card, left (polls), anchor (x, y) tiles in the seat frame
        self.counts = dict(runs_scheduled=len(self.pending), runs_applied=0, runs_dropped=0, flipped_unit_polls=0,
                           phantom_polls=0, phantom_near_plays=0, phantom_near_elixir=0.0)
        self.upr = data()['v1.1' if spec.startswith('v11') else 'v1.4c']['units_per_record'] if spec != 'off' else {}
        cb = CardBodies(rt)
        self.bodies = {}
        for _, card, _ in self.pending:
            if card not in self.bodies:
                self.bodies[card] = {int(t) for t, k in cb.bodies_of(card) if k == 0}   # troop bodies of the card
        self.last_tick = None
        self.shown = []                  # phantom positions (tiles) shown at the current poll

    @staticmethod
    def _rows(obs):
        m = obs.entity_mask
        return [i for i in range(len(m)) if m[i]]

    def _own_troops(self, obs, card):
        toks = self.bodies.get(card, set())
        out = []
        for i in self._rows(obs):
            f = obs.entity_features[i]
            if f[2] > .5 and int(obs.entity_ids[i]) in toks and int(f[4:9].argmax()) == 0:
                out.append((i, float(f[0]) * 18, float(f[1]) * 32))
        return out

    def step(self, obs, tick):
        """Advance the schedule to `tick` (once per distinct tick) and return the row indices of `obs` to relabel."""
        new_tick = tick != self.last_tick
        self.last_tick = tick
        flips, self.shown = [], []
        if new_tick:
            while self.pending and self.pending[0][0] <= tick:
                start, card, length = self.pending.pop(0)
                self.active.append(dict(card=card, left=length, anchor=None, start=start))
        keep = []
        for run in self.active:
            cands = self._own_troops(obs, run['card'])
            if run['anchor'] is None:
                if not cands:
                    if tick - run['start'] > WAIT_TICKS:
                        self.counts['runs_dropped'] += 1
                        continue
                    keep.append(run)
                    continue
                ours = [c for c in cands if c[2] < 16] or cands
                run['anchor'] = min(ours, key=lambda c: math.hypot(c[1] - 9, c[2] - 3))[1:]
                self.counts['runs_applied'] += 1
                self.counts[f'runs_applied:{run["card"]}'] = self.counts.get(f'runs_applied:{run["card"]}', 0) + 1
            ax, ay = run['anchor']
            near = sorted((math.hypot(x - ax, y - ay), i, x, y) for i, x, y in cands
                          if math.hypot(x - ax, y - ay) <= TRACK_TILES and i not in flips)
            n = max(1, round(self.upr.get(run['card'], 1.0)))
            pick = near[:n]
            if not pick:
                continue                  # the unit is gone: the run ends
            for _, i, x, y in pick:
                flips.append(i)
                self.shown.append((x, y))
            run['anchor'] = (sum(p[2] for p in pick) / len(pick), sum(p[3] for p in pick) / len(pick))
            if new_tick:
                run['left'] -= 1
                self.counts['flipped_unit_polls'] += len(pick)
            if run['left'] > 0:
                keep.append(run)
        self.active = keep
        if new_tick and flips:
            self.counts['phantom_polls'] += 1
        return flips

    @staticmethod
    def relabel(packet, rows):
        """packet with entity rows `rows` turned from own to enemy (columns 2/3)."""
        if not rows:
            return packet
        obs = packet.observation
        f = obs.entity_features.copy()
        for i in rows:
            f[i, 2], f[i, 3] = 0.0, 1.0
        return replace(packet, observation=replace(obs, entity_features=f))

    def match_rows(self, src_obs, rows, dst_obs):
        """The rows of dst_obs equal (token, features) to rows of src_obs (the reserved packet adds own reservations)."""
        want = [(int(src_obs.entity_ids[i]), src_obs.entity_features[i].tobytes()) for i in rows]
        out, used = [], set()
        for tok, fb in want:
            for j in self._rows(dst_obs):
                if j not in used and int(dst_obs.entity_ids[j]) == tok and dst_obs.entity_features[j].tobytes() == fb:
                    out.append(j)
                    used.add(j)
                    break
        return out

    def note_play(self, view, action):
        if not self.shown or action >= WAIT:
            return
        slot, rest = divmod(int(action), 576)
        row, col = divmod(rest, 18)
        hand = list((view.info.own or {}).get('hand') or [])
        card = hand[slot] if slot < len(hand) else None
        if any(math.hypot(col + .5 - x, row + .5 - y) <= NEAR_TILES for x, y in self.shown):
            self.counts['phantom_near_plays'] += 1
            self.counts['phantom_near_elixir'] += float(self.rt.R.costs.get(card, 0.0)) if card else 0.0


class BoardNoisePlayer:
    """View wrapper around OUR player: board noise in its packets; everything else delegated."""

    def __init__(self, rt, inner, spec, seed, seat, name=None):
        self.rt, self.inner, self.spec = rt, inner, spec
        self.seed, self.seat = seed, seat
        self.name = name or f'bn-{spec}:{getattr(inner, "name", "?")}'
        self.deadline_seconds = getattr(inner, 'deadline_seconds', None)
        self.noise = None

    def __getattr__(self, k):
        return getattr(self.inner, k)

    def start(self, ctx):
        self.noise = BoardNoise(self.rt, self.spec, self.seed, self.seat)
        return self.inner.start(ctx)

    def act(self, view):
        bn = self.noise
        obs = view.info.packet.observation
        rows = bn.step(obs, int(view.tick))
        if rows:
            info = replace(view.info, packet=bn.relabel(view.info.packet, rows))
            rrows = bn.match_rows(obs, rows, view.reserved.packet.observation)
            view = replace(view, info=info, reserved=replace(view.reserved, packet=bn.relabel(view.reserved.packet, rrows))
                           if hasattr(view.reserved, 'packet') else view.reserved)
        d = self.inner.act(view)
        if view.can_act:
            bn.note_play(view, int(d.action))
        return d

    def close(self):
        return self.inner.close()

    def bind_rsim(self, m):
        if hasattr(self.inner, 'bind_rsim'):
            self.inner.bind_rsim(m)
