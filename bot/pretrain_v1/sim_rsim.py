"""RoyaleSim producer for pretrain-v1: simulator state -> the live reader's PRIVATE frame -> the same (vendored,
deployed) FrameBuilder -> record + RF extras -> policy.Session. Plus `PolicyV1Player`, a bot.players Player for the
RoyaleSim harness (bot/players/royalesim_match.play_match: 5-tick polls from tick 90, CommandQueue(27, capacity 1)).

Frame construction, per acting seat, in that seat's own frame (seat 1 rotated 180 degrees, exactly as
royalesim_adapter.action_to_command maps actions back), so the record's screen frame IS the action frame:
  world = own-frame tiles * 1000; our king always at the low end; sim binding screen_x_flip {low: False, high: False}
  e          own elixir_milli * 10 (record elixir = e / 10000), own seat only
  h, n       own hand / next as indices into the own deck order (players[seat].deck), own seat only
  u          every entity: [uid, side (0 = acting seat), x, y, native card id of the CREATING card (-1 towers), hp,
             max hp, body name (RoyaleSim unit_type = client character name; KingTower / PrincessTower)].
             Enemy entities RoyaleSim flags underground or invisible are omitted (as royalesim_translate does).
             In-flight carriers (spells with FLIGHT motion and a card in rfextras.SPELL_CARRIERS) become a nameless-
             body row '<Card>Spell' with their aim in `p`, as the live reader exposes FireballSpell & co.
Nothing from players[1 - seat] is read. FrameBuilder runs with the same 5-tick cadence constants as the dataset.
"""
from __future__ import annotations

import json
import zlib
from types import SimpleNamespace

from . import dataset as D
from . import featurize as F
from .policy import Session

UNDERGROUND, INVISIBLE = 1, 2
SIM_BINDING = SimpleNamespace(tile=1000, world_w=18000, world_h=32000, elixir_unit=10000,
                              screen_x_flip={'low': False, 'high': False},
                              tower_names={'king': frozenset({'KingTower'}),
                                           'princess': frozenset({'PrincessTower', 'Cannoneer', 'DaggerDuchess',
                                                                  'ChefTower'})})
SUB = 18000                                         # RoyaleSim subtiles per tile
NATIVE_ID = {name: cid for cid, name in D.BY_ID.items()}
CARRIERS = frozenset(F.catalog().carriers)


class RsimFrames:
    """One seat of one RoyaleSim battle -> reader frames -> records (call `record(state)` once per poll)."""

    def __init__(self, battle_names, unit_types, seat, entity_fields, spell_fields, our_card):
        self.names = battle_names                     # RoyaleSim catalogue index -> RoyaleSim card name
        self.types = unit_types
        self.seat = seat
        self.F = {f: i for i, f in enumerate(entity_fields)}
        self.S = {f: i for i, f in enumerate(spell_fields)}
        self.our = our_card                           # RoyaleSim card name -> bot card name
        self.builder = None
        self.order = None
        self.token = zlib.crc32(f'rsim-{seat}'.encode()) + 1
        self.stats = {}

    def _bump(self, k):
        self.stats[k] = self.stats.get(k, 0) + 1

    def _xy(self, x, y):
        tx, ty = x/SUB, y/SUB
        if self.seat == 1:
            tx, ty = 18 - tx, 32 - ty
        return int(round(tx*1000)), int(round(ty*1000))

    def frame(self, state):
        me = state['players'][self.seat]
        if self.order is None:
            self.order = [self.our(self.names[c]) for c in me['deck']]
            self.builder = new_builder(self.order)
        deck_ids = list(me['deck'])
        if any(c < 0 for c in me['hand']) or me['next_card'] < 0:
            return None
        h = [deck_ids.index(c) for c in me['hand']]
        n = deck_ids.index(me['next_card'])
        F_ = self.F
        u, p = [], []
        for e in state['entities']:
            team = e[F_['team']]
            if team != self.seat and e[F_['status_flags']] & (UNDERGROUND | INVISIBLE):
                self._bump('hidden_enemy')
                continue
            cid = e[F_['card_id']]
            native = -1 if cid < 0 else NATIVE_ID.get(self.our(self.names[cid]), -1)
            x, y = self._xy(e[F_['x']], e[F_['y']])
            u.append([int(e[F_['uid']]) + 1, 0 if team == self.seat else 1, x, y, native, int(e[F_['hp']]),
                      int(e[F_['max_hp']]), str(self.types[e[F_['unit_type']]])])
        S = self.S
        for sp in state['spells']:
            cid = sp[S['card_id']]
            if cid < 0 or sp[S['motion']] != 0:          # FLIGHT carriers only
                continue
            card = self.our(self.names[cid])
            if card not in CARRIERS or card not in NATIVE_ID:
                continue
            x, y = self._xy(sp[S['x']], sp[S['y']])
            ax, ay = self._xy(sp[S['aim_x']], sp[S['aim_y']])
            # one id per carrier INSTANCE: launch tick (tick - ticks_flown) separates repeat casts at one aim (a
            # Fireball then a Mirror-Fireball); ids are reader tracking metadata only, never features
            launch = int(state['tick']) - int(sp[S['ticks_flown']])
            uid = (1 << 40) + zlib.crc32(f"{sp[S['team']]}|{cid}|{sp[S['aim_x']]}|{sp[S['aim_y']]}|{launch}".encode())
            u.append([uid, 0 if sp[S['team']] == self.seat else 1, x, y, NATIVE_ID[card], -1, -1, f'{card}Spell'])
            p.append([uid, ax, ay])
        return dict(t=int(state['tick']), b=self.token, s=0, e=int(me['elixir_milli'])*10, h=h, n=n, u=u, p=p, m=0)

    def record(self, state, builder=None):
        """-> ((record, extras), None, reader-frame line) or (None, reason, line)."""
        f = self.frame(state)
        if f is None:
            return None, 'hand_hole', None
        line = json.dumps(f)
        got, why = record_from_line(line, self.builder)
        return got, why, line


def new_builder(order):
    return D.ST.FrameBuilder(SIM_BINDING, order, D.CARDS, extra_bodies=D.EXTRA, spell_events=False)


def record_from_line(line, builder):
    """A logged reader-frame line -> ((record, extras), None) or (None, reason): the offline replay path."""
    try:
        _, pf = D.ST.parse_line(line)
        rec = builder.frame(pf)
    except (ValueError, D.ST.FrameError) as ex:
        return None, f'frame_error:{str(ex)[:40]}'
    if rec is None:
        return None, 'unoriented'
    return (rec, dict(first_seen=list(builder.unit_first_seen), spells=list(builder.spells))), None


class PolicyV1Player:
    """bot.players Player: one forward pass per poll, sampled gate / slot / tile, no search, no timed waits."""

    deadline_seconds = None

    def __init__(self, rt, model, name='pretrain-v1', seed_salt=0, shadow=True):
        self.rt, self.model, self.name, self.salt = rt, model, name, seed_salt
        self.shadow = shadow            # an independent FrameBuilder + History fed the logged (JSON) reader frames
        self.m = None
        self.decisions = []
        self.counts = {}

    def bind_rsim(self, match):
        self.m = match

    def start(self, ctx):
        import royalesim as rs
        from bot.players.royalesim_adapter import our_card
        self.seat = ctx.seat
        self.frames = RsimFrames(self.m.names, self.m.tr.types or json.loads(self.m.b.unit_types_json()), ctx.seat,
                                 rs.ENTITY_FIELDS, rs.SPELL_FIELDS, our_card)
        seed = (int(ctx.seed) ^ (0x9E3779B97F4A7C15*(ctx.seat + 1)) ^ self.salt) % (1 << 63)
        self.session = Session(self.model, seed)
        self.dead = False
        self.sh_builder, self.sh_hist = None, F.History()

    def _count(self, k):
        self.counts[k] = self.counts.get(k, 0) + 1

    def act(self, view):
        from bot.players.base import Decision, WAIT
        if self.dead:
            return Decision(WAIT, 0, None)
        got, why, line = self.frames.record(self.m.state)
        if self.shadow and line is not None:
            if self.sh_builder is None:
                self.sh_builder = new_builder(self.frames.order)
            sh_got, _ = record_from_line(line, self.sh_builder)
        else:
            sh_got = None
        if got is None:
            self._count(why)
            if why.startswith('frame_error'):
                self.dead = True                         # live refuses the rest of the battle
            return Decision(WAIT, 0, None)
        rec, extras = got
        if self.frames.builder.decided(rec['tick']):
            return Decision(WAIT, 0, None)
        try:
            d = self.session.step(rec, extras)
        except F.FeatureError as ex:
            self._count(f'feature_error:{str(ex)[:40]}')
            return Decision(WAIT, 0, None)
        if sh_got is not None:
            sh = F.observe(sh_got[0], sh_got[1], self.sh_hist)
            self._count('shadow_equal' if F.feature_bytes(sh) == F.feature_bytes(self.session.last_feat)
                        else 'shadow_MISMATCH')
        self._count(d.status)
        stats = dict(status=d.status, p_wait=round(d.p_wait, 4), value=round(d.value, 4))
        if d.status == 'play':
            if not view.can_act:
                self._count('channel_mismatch')
                return Decision(WAIT, 0, stats)
            self.session.accepted(d)
            if self.shadow:
                self.sh_hist.submit(d.tick, d.slot, d.card, d.tile)
            self.decisions.append((rec['tick'], d.action, d.card))
            return Decision(int(d.action), 0, stats)
        return Decision(WAIT, 0, stats)

    def close(self):
        pass
