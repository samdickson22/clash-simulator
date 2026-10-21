"""HF IL_Replay human replays rebuilt in our Python match engine (simfid, exploration; reports/bot/simfid-20261020/
REBUILD.md).

A source replay (VanguardX101/IL_Replay payload: both decks with per-card levels and forms, support tower card and
level, every play_card / activate_ability event with its 20 Hz tick and native world coordinate, final crowns and
tower HP) is executed in whichever `clasher` package is first on sys.path (CLASHER_ROOT selects its gamedata;
bot/simfid/rebuild.sh sets both), then the engine terminal is scored against the source result.

Method (independent implementation of the idea in ClashAI research/sandbox_tools/replay_drive.py; no code copied):

1. Opening hand / draw queue: per side, every C(8,4)=70 opening-hand set x 4!=24 queue order (1,680 assignments) is
   run through the ordinary cycle (the played card goes to the back of the queue, the queue front enters the hand)
   against the side's FULL play sequence; inconsistent assignments are rejected. Our engine (and, by the data, the
   source) cycles Champions ordinarily and plays Mirror as an ordinary card, so no special cycle is modelled; a side
   with no consistent assignment is `unsupported-cycle`. The chosen assignment is the first consistent one in a
   fixed enumeration (hands = itertools.combinations of the source deck list, queues = itertools.permutations of
   the rest) - never ranked by outcome. Hand SLOT order is irrelevant here: our engine addresses hand cards by name.
   Setup (one-time, documented): PlayerState(hand=<hand set>, cycle_queue=<queue order>) before tick 0.
2. Levels: the HF `level` fields are DISPLAYED levels (1..16; min over the corpus never below the rarity's first
   level, see REBUILD.md), the engine's card_levels / tower_level unit. Missing/zero/out-of-range -> the match is
   rejected (`level-incomplete` / `level-invalid`), never defaulted. The engine has one tower level per seat (King and
   Princess); the source gives only the support card's level, which is used for both (King level unknown).
3. Commands are injected at engine tick = source tick + OFFSET (frozen after discovery). A rejected command is
   never forced: card not in hand, insufficient elixir, illegal placement, unresolvable Mirror, ability
   unavailable/ambiguous/unsupported are counted. `slack` > 0 retries elixir / refill-pending / ability-unavailable
   rejections each tick for at most `slack` ticks (later commands of the same side wait behind it). Events still
   pending at the engine terminal are counted; an early terminal with pending events is not clean.
4. Forms and supports our engine lacks (evolutions, heroes, Dagger Duchess / Cannoneer / Royal Chef, Spirit Empress
   form choice) are executed as their base card / Tower Princess and the match is labelled `base-form-substitution`
   with the tick its faithful prefix ends; only matches with none are `faithful-supported`.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import itertools
import json
import math
import os
import random
import sys
import time
from collections import Counter, deque
from dataclasses import dataclass, field
from pathlib import Path

HF_REPLAYS = Path(os.environ.get('REBUILD_HF_REPLAYS',
                                  '/mpac/sdicks02/tmp/clashai-research/repo/scratchpad/gauntlet/L67/hf/replays'))
RUN_DIR = Path(os.environ.get('REBUILD_RUN_DIR', '/mpac/sdicks02/jobs/clasher/simfid-20261020/rebuild'))
SIDES = ('team', 'opponent')            # engine seat 0 = team (bottom, y < 16), seat 1 = opponent (top)
TICK_CAP = 7200                          # engine terminal is at most 300 s (+ tiebreak) = 6,000 ticks
DEFAULT_OFFSET = 0                       # frozen by `discover` (REBUILD.md); the CLI default
RARITY_FIRST_LEVEL = {'Common': 1, 'Rare': 3, 'Epic': 6, 'Legendary': 9, 'Champion': 11}

# HF/RoyaleAPI base slug -> engine card name (canonical: resolve_card_name(name) == name). Checked against the engine's
# loader at run time; a slug missing here or in the loader makes the match `unsupported-card`.
SLUG_TO_ENGINE = {
    'archer-queen': 'ArcherQueen', 'archers': 'Archer', 'arrows': 'Arrows', 'baby-dragon': 'BabyDragon',
    'balloon': 'Balloon', 'bandit': 'Assassin', 'barbarian-barrel': 'BarbLog', 'barbarian-hut': 'BarbarianHut',
    'barbarians': 'Barbarians', 'bats': 'Bats', 'battle-healer': 'BattleHealer', 'battle-ram': 'BattleRam',
    'berserker': 'Berserker', 'bomb-tower': 'BombTower', 'bomber': 'Bomber', 'boss-bandit': 'BossBandit',
    'bowler': 'Bowler', 'cannon': 'Cannon', 'cannon-cart': 'MovingCannon', 'clone': 'Clone',
    'dark-prince': 'DarkPrince', 'dart-goblin': 'BlowdartGoblin', 'earthquake': 'Earthquake',
    'electro-dragon': 'ElectroDragon', 'electro-giant': 'ElectroGiant', 'electro-spirit': 'ElectroSpirit',
    'electro-wizard': 'ElectroWizard', 'elite-barbarians': 'AngryBarbarians', 'elixir-collector': 'Elixir Collector',
    'elixir-golem': 'ElixirGolem', 'executioner': 'AxeMan', 'fire-spirit': 'FireSpirits', 'fireball': 'Fireball',
    'firecracker': 'Firecracker', 'fisherman': 'Fisherman', 'flying-machine': 'DartBarrell', 'freeze': 'Freeze',
    'furnace': 'FirespiritHut', 'giant': 'Giant', 'giant-skeleton': 'GiantSkeleton', 'giant-snowball': 'Snowball',
    'goblin-barrel': 'GoblinBarrel', 'goblin-cage': 'GoblinCage', 'goblin-curse': 'GoblinCurse',
    'goblin-demolisher': 'GoblinDemolisher', 'goblin-drill': 'GoblinDrill', 'goblin-gang': 'GoblinGang',
    'goblin-giant': 'GoblinGiant', 'goblin-hut': 'GoblinHut', 'goblin-machine': 'GoblinMachine', 'goblins': 'Goblins',
    'goblinstein': 'Goblinstein', 'golden-knight': 'GoldenKnight', 'golem': 'Golem', 'graveyard': 'Graveyard',
    'guards': 'SkeletonWarriors', 'heal-spirit': 'Heal', 'hog-rider': 'HogRider', 'hunter': 'Hunter',
    'ice-golem': 'IceGolemite', 'ice-spirit': 'IceSpirits', 'ice-wizard': 'IceWizard',
    'inferno-dragon': 'InfernoDragon', 'inferno-tower': 'InfernoTower', 'knight': 'Knight', 'lava-hound': 'LavaHound',
    'lightning': 'Lightning', 'little-prince': 'LittlePrince', 'lumberjack': 'RageBarbarian',
    'magic-archer': 'EliteArcher', 'mega-knight': 'MegaKnight', 'mega-minion': 'MegaMinion',
    'mighty-miner': 'MightyMiner', 'miner': 'Miner', 'mini-pekka': 'MiniPekka', 'minion-horde': 'MinionHorde',
    'minions': 'Minions', 'mirror': 'Mirror', 'monk': 'Monk', 'mortar': 'Mortar', 'mother-witch': 'WitchMother',
    'musketeer': 'Musketeer', 'night-witch': 'DarkWitch', 'pekka': 'Pekka', 'phoenix': 'Phoenix', 'poison': 'Poison',
    'prince': 'Prince', 'princess': 'Princess', 'rage': 'Rage', 'ram-rider': 'RamRider', 'rascals': 'Rascals',
    'rocket': 'Rocket', 'ronin': 'Ronin', 'royal-delivery': 'RoyalDelivery', 'royal-ghost': 'Ghost',
    'royal-giant': 'RoyalGiant', 'royal-hogs': 'RoyalHogs', 'royal-recruits': 'RoyalRecruits',
    'rune-giant': 'GiantBuffer', 'skeleton-army': 'SkeletonArmy', 'skeleton-barrel': 'SkeletonBalloon',
    'skeleton-dragons': 'SkeletonDragons', 'skeleton-king': 'SkeletonKing', 'skeletons': 'Skeletons',
    'sparky': 'ZapMachine', 'spear-goblins': 'SpearGoblins', 'spirit-empress': 'MergeMaiden_Normal',
    'suspicious-bush': 'SuspiciousBush', 'tesla': 'Tesla', 'the-log': 'Log', 'three-musketeers': 'ThreeMusketeers',
    'tombstone': 'Tombstone', 'tornado': 'Tornado', 'valkyrie': 'Valkyrie', 'vines': 'Vines', 'void': 'DarkMagic',
    'wall-breakers': 'Wallbreakers', 'witch': 'Witch', 'wizard': 'Wizard', 'x-bow': 'Xbow', 'zap': 'Zap',
    'zappies': 'MiniSparkys',
}
# Base slugs our engine runs only as an approximation of the source card (labelled, base-form tier only).
APPROX_CARDS = {
    'spirit-empress': 'two play forms (3-elixir ground / 6-elixir air) chosen at play time; the source does not record '
                      'which; executed as the 3-elixir ground MergeMaiden_Normal',
}
# Ability Champions. Which of them the engine can activate (BattleState.activate_champion_ability) is probed per engine
# tree (ability_champions()); rt-live16402b-r3: Archer Queen, Goblinstein, Mighty Miner, Skeleton King.
CHAMPIONS = {'archer-queen', 'boss-bandit', 'golden-knight', 'goblinstein', 'little-prince', 'mighty-miner', 'monk',
             'skeleton-king'}
TOWER_TROOPS = {'tower-princess': True, 'dagger-duchess': False, 'cannoneer': False, 'royal-chef': False}
RETRYABLE = {'elixir', 'refill_pending', 'ability_unavailable'}


def split_form(key: str) -> tuple[str, str]:
    """'knight-ev1' -> ('knight', 'evo'); 'archer-queen-hero' -> ('archer-queen', 'hero')."""
    if key.endswith('-ev1'):
        return key[:-4], 'evo'
    if key.endswith('-hero'):
        return key[:-5], 'hero'
    return key, 'base'


class Reject(Exception):
    """The source cannot be configured faithfully enough to run (reason in args[0])."""


# -- source --------------------------------------------------------------------------------------------------------
@dataclass
class Event:
    tick: int
    order: int
    side: int
    kind: str                     # 'play' | 'ability'
    slug: str | None = None       # base slug (plays)
    form: str | None = None       # deck form of the played card
    x: int | None = None          # native world units (1000 per tile)
    y: int | None = None
    candidates: tuple = ()        # ability source candidates (form-qualified slugs)


@dataclass
class Match:
    key: str                      # '<shard>:<row>'
    tag: str
    mode: str
    battle_type: str
    decks: list                   # per seat: [(base slug, form, level)] in source order
    towers: list                  # per seat: (tower card slug, level)
    winner: int | None            # 0 team, 1 opponent, None draw
    crowns: tuple
    final_hp: list                # per seat: (king, princess_left, princess_right)
    events: list
    timeline_ticks: int
    meta: dict = field(default_factory=dict)

    def plays(self, seat):
        return [e.slug for e in self.events if e.side == seat and e.kind == 'play']


def parse(payload: dict, key: str = '', tag: str = '') -> Match:
    battle = payload['battle']
    decks, towers, hp = [], [], []
    for side in SIDES:
        players = battle[side]['players']
        if len(players) != 1:
            raise Reject('not-1v1')
        pl = players[0]
        deck = []
        for c in pl['deck']:
            base, form = split_form(c['card_key'])
            deck.append((base, form, c.get('level')))
        if len(deck) != 8 or len({b for b, _, _ in deck}) != 8:
            raise Reject('deck-not-8-distinct')
        decks.append(deck)
        tc = pl.get('tower_card') or {}
        towers.append((tc.get('card_key'), tc.get('level')))
        f = pl.get('final_tower_hitpoints') or {}
        hp.append(tuple(int(f.get(k) or 0) for k in ('king', 'princess_left', 'princess_right')))
    events = []
    for e in payload.get('events') or []:
        seat = SIDES.index(e['side'])
        tick, order = int(e['replay_tick_20hz']), int(e['source_index'])
        if e['kind'] == 'activate_ability':
            events.append(Event(tick, order, seat, 'ability', candidates=tuple(e.get('ability_source_candidates') or ())))
        elif e['kind'] == 'play_card':
            base, form = split_form(e['card_key'])
            world = (e.get('coordinates') or {}).get('native_world_units')
            if not world:
                raise Reject('play-without-coordinate')
            if base not in {b for b, _, _ in decks[seat]}:
                raise Reject('play-outside-deck')
            form = next(f for b, f, _ in decks[seat] if b == base)
            events.append(Event(tick, order, seat, 'play', base, form, int(world['x']), int(world['y'])))
        else:
            raise Reject(f"event-kind-{e['kind']}")
    events.sort(key=lambda e: (e.tick, e.order))
    result = battle['result']
    if result not in ('victory', 'defeat', 'draw'):
        raise Reject(f'result-{result}')
    return Match(key=key, tag=tag or (payload.get('source') or {}).get('replay_tag', ''),
                 mode=battle.get('game_mode', ''), battle_type=battle.get('battle_type', ''), decks=decks,
                 towers=towers, winner={'victory': 0, 'defeat': 1, 'draw': None}[result],
                 crowns=(int(battle['team']['crowns']), int(battle['opponent']['crowns'])), final_hp=hp,
                 events=events, timeline_ticks=int(round(float(payload['replay']['duration']['timeline_seconds']) * 20)))


# -- levels, forms, supports -----------------------------------------------------------------------------------------
def levels(m: Match, rarity_of) -> tuple[list, list]:
    """-> ([{engine card: displayed level}] per seat, [tower level] per seat). Raises Reject on an incomplete or
    implausible map (never defaults). rarity_of(engine name) -> engine rarity string or None."""
    cards, towers = [], []
    for seat in (0, 1):
        out = {}
        for base, _, lv in m.decks[seat]:
            if not isinstance(lv, int) or isinstance(lv, bool) or lv <= 0:
                raise Reject('level-incomplete')
            name = SLUG_TO_ENGINE.get(base)
            first = RARITY_FIRST_LEVEL.get(rarity_of(name) if name else None, 1)
            if not first <= lv <= 16:
                raise Reject('level-invalid')
            out[name or base] = lv
        cards.append(out)
        lv = m.towers[seat][1]
        if not isinstance(lv, int) or isinstance(lv, bool) or lv <= 0:
            raise Reject('level-incomplete')
        if lv > 16:
            raise Reject('level-invalid')
        towers.append(lv)
    return cards, towers


def classify(m: Match, supported_names, ability_champions=frozenset(CHAMPIONS)) -> dict:
    """Forms, supports and cards our engine cannot execute faithfully, and where the faithful prefix ends."""
    out = dict(evo_cards=[], hero_cards=[], tower_troops=[], approx_cards=[], unsupported_cards=[])
    first_bad = math.inf
    for seat in (0, 1):
        tower = m.towers[seat][0]
        if tower not in TOWER_TROOPS:
            out['unsupported_cards'].append(f'tower:{tower}')
        elif not TOWER_TROOPS[tower]:
            out['tower_troops'].append(tower)
            first_bad = 0
        for base, form, _ in m.decks[seat]:
            name = SLUG_TO_ENGINE.get(base)
            if name is None or name not in supported_names:
                out['unsupported_cards'].append(base)
            if form == 'evo':
                out['evo_cards'].append(base)
            elif form == 'hero':
                out['hero_cards'].append(base)
            if base in APPROX_CARDS:
                out['approx_cards'].append(base)
    flagged = {(s, b) for s in (0, 1) for b, f, _ in m.decks[s] if f != 'base' or b in APPROX_CARDS}
    plays_flagged = Counter()
    for e in m.events:
        if e.kind == 'play' and (e.side, e.slug) in flagged:
            plays_flagged['evo' if e.form == 'evo' else 'hero' if e.form == 'hero' else 'approx'] += 1
            first_bad = min(first_bad, e.tick)
        if e.kind == 'ability' and not _ability_supported(e, ability_champions):
            first_bad = min(first_bad, e.tick)
    out['flagged_plays'] = dict(plays_flagged)
    out['faithful_prefix_end_tick'] = None if first_bad == math.inf else int(first_bad)
    if out['unsupported_cards']:
        out['tier'] = 'unsupported-card'
    elif out['faithful_prefix_end_tick'] is None and not (out['evo_cards'] or out['hero_cards'] or out['approx_cards']):
        out['tier'] = 'faithful-supported'
    else:
        out['tier'] = 'base-form-substitution'
    return out


def _ability_supported(e: Event, ability_champions) -> bool:
    """A source ability event our engine can execute (exactly one candidate, a base-form Champion whose ability the
    engine implements). Two-candidate events resolve only at run time (one live candidate), so they end the prefix."""
    return len(e.candidates) == 1 and split_form(e.candidates[0])[1] == 'base' and \
        split_form(e.candidates[0])[0] in ability_champions


# -- opening hand / queue ------------------------------------------------------------------------------------------
def infer_cycle(seq, deck) -> list[tuple[tuple, tuple]]:
    """Every (opening hand set, queue front-first) under which each card of `seq` is in hand when played."""
    found = []
    for hand in itertools.combinations(deck, 4):
        rest = [c for c in deck if c not in hand]
        for queue in itertools.permutations(rest):
            held, q = set(hand), deque(queue)
            for card in seq:
                if card not in held:
                    break
                held.remove(card)
                held.add(q.popleft())
                q.append(card)
            else:
                found.append((hand, queue))
    return found


def cycle_summary(cands) -> dict:
    if not cands:
        return dict(n=0)
    hands = {frozenset(h) for h, _ in cands}
    fixed = sum(len({q[i] for _, q in cands}) == 1 for i in range(4))
    return dict(n=len(cands), hand_sets=len(hands), queue_positions_fixed=fixed,
                unique=len(cands) == 1)


def first_use_order(seq, deck) -> tuple[tuple, tuple]:
    order = list(dict.fromkeys(seq)) + [c for c in deck if c not in seq]
    return tuple(order[:4]), tuple(order[4:8])


# -- engine --------------------------------------------------------------------------------------------------------
_ENGINE: dict = {}


def engine():
    """Process-wide engine setup: live16402 crown pin drop (SIMFID_CROWN_FROM_GAMEDATA, as bot.players.runtime) before
    bot.levels.match.install_engine_levels() copies the pins."""
    if not _ENGINE:
        crown = os.environ.get('SIMFID_CROWN_FROM_GAMEDATA', '')
        if crown:
            from clasher.balance import TOURNAMENT_SPELL_OVERRIDES
            for card in crown.split(','):
                TOURNAMENT_SPELL_OVERRIDES.get(card, {}).pop('crown_tower_damage', None)
        from bot.levels.match import install_engine_levels
        install_engine_levels()
        import clasher
        from clasher.data import CardDataLoader
        loader = CardDataLoader()
        names = set(loader.load_card_definitions())
        _ENGINE.update(loader=loader, names=names, clasher_file=str(Path(clasher.__file__).resolve()),
                       root=os.environ.get('CLASHER_ROOT', ''), crown=crown)
        _ENGINE['ability_champions'] = ability_champions()
    return _ENGINE


def ability_champions() -> frozenset:
    """Champions whose ability this engine can activate: deploy each alone at level 11 with 10 elixir and ask
    can_activate_champion_ability after 20 ticks (past every deploy time)."""
    from clasher.arena import Position
    from clasher.battle import BattleState
    from clasher.player import PlayerState
    out = set()
    filler = ['Knight', 'Archer', 'Zap', 'Fireball', 'Cannon', 'Musketeer', 'Giant']
    for slug in sorted(CHAMPIONS):
        name = SLUG_TO_ENGINE[slug]
        deck = [name] + filler
        try:
            ps = [PlayerState(s, deck=list(deck), hand=list(deck[:4]), cycle_queue=deque(deck[4:]),
                              card_levels={c: 11 for c in deck}) for s in (0, 1)]
            b = BattleState(players=ps, rng=random.Random(0))
            b.players[0].elixir = 10.0
            if not b.deploy_card(0, name, Position(9.5, 10.5)):
                continue
            for _ in range(20):
                b.step()
            b.players[0].elixir = 10.0
            if b.can_activate_champion_ability(0):
                out.add(slug)
        except Exception:   # noqa: BLE001 - a champion this engine cannot build has no ability
            continue
    return frozenset(out)


def rarity_of(name):
    c = engine()['loader'].get_card(name) if name else None
    return getattr(c, 'rarity', None)


@dataclass
class Config:
    name: str
    # 'inferred' | 'inferred_last' (diagnostic: last consistent candidate) | 'first_use' |
    # 'deck_order' (no inference: the source deck list's first four in hand, the rest queued in list order)
    hand: str = 'inferred'
    levels: str = 'real'          # 'real' | 'l11'
    offset: int = DEFAULT_OFFSET
    slack: int = 0
    seed: int = 0


CONFIGS = {
    'main': Config('main'),
    'slack40': Config('slack40', slack=40),
    'firstuse': Config('firstuse', hand='first_use'),
    'l11': Config('l11', levels='l11'),
    'lastcand': Config('lastcand', hand='inferred_last'),
    'deckorder': Config('deckorder', hand='deck_order'),
}


def _alive_card(b, seat, name):
    for e in b.entities.values():
        if e.player_id == seat and e.is_alive and getattr(e, 'hitpoints', 0) > 0 and \
                getattr(getattr(e, 'card_stats', None), 'name', None) == name:
            return True
    return False


def _attempt(b, ev: Event, names, ability_champions=frozenset(CHAMPIONS)) -> str:
    """Try one source event now. -> 'ok' or a rejection reason. Never changes hand/elixir on rejection."""
    from clasher.arena import Position
    if b.game_over:
        return 'terminal'
    if ev.kind == 'ability':
        if not ev.candidates:
            return 'ability_unattributed'
        live = [c for c in ev.candidates if _alive_card(b, ev.side, SLUG_TO_ENGINE.get(split_form(c)[0]))]
        if len(ev.candidates) == 1:
            card = ev.candidates[0]
        elif len(live) == 1:
            card = live[0]
        else:
            return 'ability_ambiguous'
        base, form = split_form(card)
        if form != 'base':
            return 'ability_unsupported_form'
        if base not in ability_champions:
            return 'ability_unsupported_engine'
        if not b.can_activate_champion_ability(ev.side):
            return 'ability_unavailable'
        return 'ok' if b.activate_champion_ability(ev.side) else 'ability_unavailable'
    name = names[ev.side][ev.slug]
    p = b.players[ev.side]
    if name not in p.hand:
        if None in p.hand and p.cycle_queue and p.cycle_queue[0] == name:
            return 'refill_pending'
        return 'not_in_hand'
    try:
        resolved = b.resolve_card_play(ev.side, name)
    except Exception:   # noqa: BLE001 - engine refusal by exception (e.g. unreconciled level data)
        return 'engine_error'
    if resolved is None:
        return 'mirror_unresolvable' if name == 'Mirror' else 'unresolvable'
    if p.elixir + 1e-9 < resolved[1].mana_cost:
        return 'elixir'
    try:
        ok = b.deploy_card(ev.side, name, Position(ev.x / 1000.0, ev.y / 1000.0))
    except Exception:   # noqa: BLE001
        return 'engine_error'
    return 'ok' if ok else 'placement'


def _tower_hp(b, seat):
    """(king, sorted princess pair) as ints; a fallen King means every tower is down (source convention)."""
    p = b.players[seat]
    king = max(0, int(round(p.king_tower_hp)))
    if king <= 0:
        return 0, (0, 0)
    pr = sorted(max(0, int(round(v))) for v in (p.left_tower_hp, p.right_tower_hp))
    return king, tuple(pr)


def build_battle(m: Match, cfg: Config, plan, card_levels, tower_levels):
    from bot.levels.match import tower_curve
    from clasher.battle import BattleState
    from clasher.player import PlayerState
    players = []
    for s in (0, 1):
        names = [SLUG_TO_ENGINE[b] for b, _, _ in m.decks[s]]
        hand, queue = plan[s]
        players.append(PlayerState(s, deck=names, hand=[SLUG_TO_ENGINE[c] for c in hand],
                                   cycle_queue=deque(SLUG_TO_ENGINE[c] for c in queue),
                                   card_levels=dict(card_levels[s]), tower_level=int(tower_levels[s])))
    with tower_curve():
        return BattleState(players=players, rng=random.Random(cfg.seed))


def simulate(m: Match, cfg: Config) -> dict:
    """Run one source match in the engine under `cfg`. -> result dict (never raises for a source problem)."""
    eng = engine()
    t0, c0 = time.perf_counter(), time.process_time()
    out = dict(key=m.key, tag=m.tag, config=cfg.name, mode=m.mode, battle_type=m.battle_type,
               offset=cfg.offset, slack=cfg.slack, events=len(m.events),
               plays=sum(e.kind == 'play' for e in m.events), abilities=sum(e.kind == 'ability' for e in m.events))
    out['engine_id'] = dict(clasher=eng['clasher_file'], root=eng['root'], crown=eng['crown'])
    out['classify'] = cls = classify(m, eng['names'], eng['ability_champions'])
    try:
        card_levels, tower_levels = levels(m, rarity_of)
    except Reject as r:
        out['status'] = r.args[0]
        return out
    out['level_map'] = dict(cards=[sorted(set(d.values())) for d in card_levels], towers=tower_levels)
    if cls['tier'] == 'unsupported-card':
        out['status'] = 'unsupported-card'
        return out
    if cfg.levels == 'l11':
        card_levels = [{k: 11 for k in d} for d in card_levels]
        tower_levels = [11, 11]
    plan, cyc = [], []
    for s in (0, 1):
        deck = [b for b, _, _ in m.decks[s]]
        seq = m.plays(s)
        cands = infer_cycle(seq, deck)
        cyc.append(cycle_summary(cands))
        if cfg.hand == 'first_use':
            plan.append(first_use_order(seq, deck))
        elif cfg.hand == 'deck_order':
            plan.append((tuple(deck[:4]), tuple(deck[4:])))
        elif cands:
            plan.append(cands[-1] if cfg.hand == 'inferred_last' else cands[0])
        else:
            plan.append(None)
    out['cycle'] = cyc
    if any(p is None for p in plan):
        out['status'] = 'unsupported-cycle'
        return out
    out['plan'] = [dict(hand=list(h), queue=list(q)) for h, q in plan]
    names = [{b: SLUG_TO_ENGINE[b] for b, _, _ in m.decks[s]} for s in (0, 1)]
    try:
        b = build_battle(m, cfg, plan, card_levels, tower_levels)
    except Exception as ex:   # noqa: BLE001
        out['status'] = 'engine-setup-error'
        out['error'] = f'{type(ex).__name__}: {ex}'[:300]
        return out

    queues = [deque(e for e in m.events if e.side == s) for s in (0, 1)]
    first_try = {}                  # id(event) -> engine tick of first attempt
    log = Counter()
    delays = []
    first_reject = None
    rejects = []
    crashed = None

    def due(e):
        return max(0, e.tick + cfg.offset)

    def process():
        nonlocal first_reject
        waiting = set()             # seats whose head event retries next tick
        while True:
            heads = [q[0] for s, q in enumerate(queues) if s not in waiting and q and due(q[0]) <= b.tick]
            if not heads:
                return
            e = min(heads, key=lambda e: (e.tick, e.order))
            res = _attempt(b, e, names, eng['ability_champions'])
            waited = b.tick - first_try.setdefault(id(e), b.tick)
            if res != 'ok' and res in RETRYABLE and waited < cfg.slack:
                waiting.add(e.side)     # this seat's later events wait behind it
                continue
            queues[e.side].popleft()
            if res == 'ok':
                log['injected'] += 1
                if waited:
                    log['injected_after_wait'] += 1
                    delays.append(waited)
            else:
                log[res] += 1
                if len(rejects) < 200:
                    rejects.append((e.tick, b.tick, e.side, e.slug or ','.join(e.candidates), res))
                if first_reject is None:
                    first_reject = dict(tick=e.tick, engine_tick=b.tick, side=e.side, kind=e.kind, card=e.slug,
                                        reason=res)

    try:
        while not b.game_over and b.tick < TICK_CAP:
            process()
            if b.game_over:
                break
            waiting = any(q and due(q[0]) <= b.tick for q in queues)
            nxt = min((due(q[0]) for q in queues if q), default=TICK_CAP)
            if not waiting and nxt > b.tick + 1:
                if b.fast_forward_idle_ticks(min(nxt, TICK_CAP) - b.tick) > 0:
                    continue
            b.step()
    except Exception as ex:   # noqa: BLE001 - an engine crash mid-match is a failed reconstruction
        crashed = f'{type(ex).__name__}: {ex}'[:300]
    pending = sum(len(q) for q in queues)
    out['commands'] = dict(log) | {'pending_at_terminal': pending}
    out['first_reject'] = first_reject
    out['rejects'] = rejects
    # A usable training prefix ends at the first unsupported mechanic (classify) OR the first rejected source command,
    # whichever is earlier: after a rejection the engine state is no longer the source game's (review r2).
    bounds = [t for t in (cls['faithful_prefix_end_tick'], first_reject and first_reject['tick']) if t is not None]
    out['usable_prefix_end_tick'] = min(bounds) if bounds else None
    if delays:
        out['wait_ticks'] = dict(n=len(delays), max=max(delays), sum=sum(delays))
    out['engine'] = dict(terminal=bool(b.game_over), tick=int(b.tick), winner=b.winner if b.game_over else None,
                         crowns=(b.get_crown_count(0), b.get_crown_count(1)),
                         hp=[_tower_hp(b, s) for s in (0, 1)])
    if crashed:
        out['status'] = 'engine-crash'
        out['error'] = crashed
    else:
        out['status'] = 'ran'
    out['score'] = score(m, out['engine'])
    failed = sum(v for k, v in log.items() if k not in ('injected', 'injected_after_wait'))
    out['clean'] = bool(not crashed and failed == 0 and pending == 0 and b.game_over)
    out['wall_s'] = round(time.perf_counter() - t0, 3)
    out['cpu_s'] = round(time.process_time() - c0, 3)
    return out


def source_hp(m: Match, seat):
    king, left, right = m.final_hp[seat]
    if king <= 0:
        return 0, (0, 0)
    return king, tuple(sorted((left, right)))


def score(m: Match, eng: dict) -> dict:
    errs = []
    six = True
    for s in (0, 1):
        sk, sp = source_hp(m, s)
        ek, ep = eng['hp'][s]
        errs += [abs(sk - ek), abs(sp[0] - ep[0]), abs(sp[1] - ep[1])]
        six &= (sk, tuple(sp)) == (ek, tuple(ep))
    return dict(winner=eng['terminal'] and eng['winner'] == m.winner,
                crowns=eng['terminal'] and tuple(eng['crowns']) == tuple(m.crowns),
                six_hp=bool(eng['terminal'] and six), hp_abs_err=errs,
                source=dict(winner=m.winner, crowns=list(m.crowns), hp=[source_hp(m, s) for s in (0, 1)]))


# -- source access, samples --------------------------------------------------------------------------------------
def shards():
    return sorted(HF_REPLAYS.glob('part-*.parquet'))


def shard_rows():
    import pyarrow.parquet as pq
    return [(p.name, pq.ParquetFile(p).metadata.num_rows) for p in shards()]


def read_rows(shard_name, rows=None):
    """[(row, tag, payload dict)] from one shard (all rows when rows is None)."""
    import pyarrow.parquet as pq
    t = pq.read_table(HF_REPLAYS / shard_name, columns=['replay_tag', 'payload_json'])
    tags, payloads = t.column('replay_tag'), t.column('payload_json')
    idx = range(t.num_rows) if rows is None else sorted(rows)
    return [(i, tags[i].as_py(), json.loads(payloads[i].as_py())) for i in idx]


def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def write_sample(path, refs, meta):
    """refs: [(shard name, row)] -> <path>.jsonl.gz (key, tag, payload) + <path>.json (refs, meta)."""
    by = {}
    for s, r in refs:
        by.setdefault(s, []).append(r)
    rows = {}
    for s, rs in by.items():
        for r, tag, p in read_rows(s, rs):
            rows[(s, r)] = (tag, p)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(str(path) + '.jsonl.gz', 'wt') as f:
        for s, r in refs:
            tag, p = rows[(s, r)]
            f.write(json.dumps(dict(key=f'{s}:{r}', tag=tag, payload=p), separators=(',', ':')) + '\n')
    meta = dict(meta, n=len(refs), refs=[f'{s}:{r}' for s, r in refs],
                tags=[rows[(s, r)][0] for s, r in refs],
                shard_sha256={s: sha256(HF_REPLAYS / s) for s in sorted(by)})
    Path(str(path) + '.json').write_text(json.dumps(meta, indent=1) + '\n')
    return meta


def load_sample(path):
    with gzip.open(str(path) + '.jsonl.gz', 'rt') as f:
        return [json.loads(line) for line in f]


def native50_refs():
    """The Oct 4 native-corpus selection rule (reports/strategy_council_20260928/native-corpus/study.py prepare()),
    reproduced on HF part-000000 (5,000 rows): 20 evenly spaced 1v1 rows + 30 greedy additions maximising new
    form-qualified deck/tower card keys, ties to the earliest row."""
    shard = 'part-000000.parquet'
    pool = []
    for i, _, p in read_rows(shard):
        if any(len(p['battle'][s]['players']) != 1 for s in SIDES):
            continue
        feats = {c['card_key'] for s in SIDES for c in p['battle'][s]['players'][0]['deck']}
        feats |= {p['battle'][s]['players'][0].get('tower_card', {}).get('card_key') for s in SIDES}
        pool.append((i, feats))
    selected = [pool[round(i * (len(pool) - 1) / 19)] for i in range(20)]
    seen = set().union(*(f for _, f in selected))
    used = {i for i, _ in selected}
    for _ in range(30):
        i, f = max((r for r in pool if r[0] not in used), key=lambda r: (len(r[1] - seen), -r[0]))
        selected.append((i, f))
        used.add(i)
        seen |= f
    return [(shard, i) for i, _ in selected], dict(pool=len(pool), features=len(seen))


def random_refs(n, seed, exclude=()):
    sizes = shard_rows()
    total = sum(k for _, k in sizes)
    excl = set(exclude)
    rng = random.Random(seed)
    idx = rng.sample(range(total), n + len(excl))
    starts, acc = [], 0
    for name, k in sizes:
        starts.append((acc, name, k))
        acc += k
    out = []
    for g in idx:
        for a, name, k in starts:
            if a <= g < a + k:
                ref = (name, g - a)
                break
        if ref not in excl:
            out.append(ref)
        if len(out) == n:
            break
    return out, dict(total=total, seed=seed)


# -- worker pool ---------------------------------------------------------------------------------------------------
def _work(args):
    rec, cfg = args
    try:
        m = parse(rec['payload'], key=rec['key'], tag=rec['tag'])
    except Reject as r:
        return dict(key=rec['key'], tag=rec['tag'], config=cfg.name, status=r.args[0])
    return simulate(m, cfg)


def _init():
    try:
        os.nice(0)
    except OSError:
        pass
    engine()


def run(sample, cfg: Config, out_path, workers):
    recs = load_sample(sample)
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    done = set()
    eng = engine()
    signature = dict(config=cfg.name, offset=cfg.offset, slack=cfg.slack,
                     engine_id=dict(clasher=eng['clasher_file'], root=eng['root'], crown=eng['crown']))
    if out_path.exists():
        for line in out_path.open():
            if not line.strip():
                continue
            row = json.loads(line)
            if row.get('status') == 'ran' and any(row.get(k) != signature[k] for k in ('config', 'offset', 'slack')) \
                    or ('engine_id' in row and row['engine_id'] != signature['engine_id']):
                raise SystemExit(f'{out_path}: existing rows were made with a different config/engine '
                                 f'({row.get("config")}, offset {row.get("offset")}, {row.get("engine_id")}); '
                                 'refusing to resume into it')
            done.add(row['key'])
    todo = [(r, cfg) for r in recs if r['key'] not in done]
    t0 = time.time()
    with out_path.open('a') as f:
        if workers <= 1:
            _init()
            results = map(_work, todo)
        else:
            import multiprocessing as mp
            pool = mp.get_context('fork').Pool(workers, initializer=_init, maxtasksperchild=50)
            results = pool.imap_unordered(_work, todo, chunksize=1)
        for i, res in enumerate(results, 1):
            f.write(json.dumps(res, separators=(',', ':'), default=list) + '\n')
            f.flush()
            if i % 50 == 0:
                print(f'{cfg.name} {i}/{len(todo)} {time.time() - t0:.0f}s', flush=True)
        if workers > 1:
            pool.close()
            pool.join()
    print(f'{cfg.name} done {len(todo)} in {time.time() - t0:.0f}s -> {out_path}', flush=True)


# -- corpus scan (levels encoding, forms, supports, modes) ---------------------------------------------------------
def _scan_shard(name):
    C = Counter
    s = dict(matches=0, not1v1=0, modes=C(), battle_types=C(), level_by_slug={}, tower=C(), tower_level=C(),
             evo_matches=0, hero_matches=0, nonprincess_matches=0, level_incomplete=0, kinds=C(), forms_at_play=C(),
             unknown_slugs=C(), mixed_level_matches=0)
    for _, _, p in read_rows(name):
        s['matches'] += 1
        b = p['battle']
        if any(len(b[x]['players']) != 1 for x in SIDES):
            s['not1v1'] += 1
            continue
        s['modes'][b.get('game_mode')] += 1
        s['battle_types'][b.get('battle_type')] += 1
        evo = hero = nonp = inc = False
        lvset = set()
        for x in SIDES:
            pl = b[x]['players'][0]
            for c in pl['deck']:
                base, form = split_form(c['card_key'])
                lv = c.get('level')
                d = s['level_by_slug'].setdefault(base, C())
                d[lv] += 1
                lvset.add(lv)
                evo |= form == 'evo'
                hero |= form == 'hero'
                inc |= not isinstance(lv, int) or lv <= 0
                if base not in SLUG_TO_ENGINE:
                    s['unknown_slugs'][base] += 1
            tc = pl.get('tower_card') or {}
            s['tower'][tc.get('card_key')] += 1
            s['tower_level'][tc.get('level')] += 1
            nonp |= tc.get('card_key') != 'tower-princess'
            inc |= not isinstance(tc.get('level'), int) or tc.get('level') <= 0
        s['evo_matches'] += evo
        s['hero_matches'] += hero
        s['nonprincess_matches'] += nonp
        s['level_incomplete'] += inc
        s['mixed_level_matches'] += len(lvset) > 1
        for e in p['events']:
            s['kinds'][e['kind']] += 1
            if e['kind'] == 'play_card':
                s['forms_at_play'][e.get('form_at_play')] += 1
    return s


def scan(workers):
    import multiprocessing as mp
    with mp.get_context('fork').Pool(workers) as pool:
        parts = pool.map(_scan_shard, [p.name for p in shards()])
    tot = {}
    for s in parts:
        for k, v in s.items():
            if isinstance(v, Counter):
                tot.setdefault(k, Counter()).update(v)
            elif isinstance(v, dict):
                d = tot.setdefault(k, {})
                for kk, vv in v.items():
                    d.setdefault(kk, Counter()).update(vv)
            else:
                tot[k] = tot.get(k, 0) + v
    engine()
    rar = {}
    for slug, c in tot['level_by_slug'].items():
        r = rarity_of(SLUG_TO_ENGINE.get(slug))
        valid = {k: v for k, v in c.items() if isinstance(k, int) and k > 0}
        rr = rar.setdefault(r, dict(min=99, max=0, below_first=0, n=0, slugs=0))
        rr['slugs'] += 1
        rr['n'] += sum(c.values())
        if valid:
            rr['min'] = min(rr['min'], min(valid))
            rr['max'] = max(rr['max'], max(valid))
        rr['below_first'] += sum(v for k, v in valid.items() if k < RARITY_FIRST_LEVEL.get(r, 1))
    tot['level_by_rarity'] = rar
    tot['level_by_slug'] = {k: dict(sorted(((str(a), b) for a, b in v.items()))) for k, v in tot['level_by_slug'].items()}
    return json.loads(json.dumps(tot, default=lambda o: dict(o)))


# -- CLI -----------------------------------------------------------------------------------------------------------
def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    a = sub.add_parser('scan')
    a.add_argument('--out', default=str(RUN_DIR / 'scan.json'))
    a.add_argument('--workers', type=int, default=16)
    a = sub.add_parser('select')
    a.add_argument('which', choices=['native50', 'random', 'discovery'])
    a.add_argument('--n', type=int, default=1000)
    a.add_argument('--seed', type=int, default=20261020)
    a.add_argument('--out', required=True)
    a.add_argument('--exclude', nargs='*', default=[], help='sample .json files whose refs are excluded')
    a = sub.add_parser('run')
    a.add_argument('--sample', required=True)
    a.add_argument('--config', default='main')
    a.add_argument('--offset', type=int)
    a.add_argument('--slack', type=int)
    a.add_argument('--name', help='output config name (default: config name, with offset suffix when given)')
    a.add_argument('--out', required=True)
    a.add_argument('--workers', type=int, default=8)
    args = ap.parse_args(argv)
    if args.cmd == 'scan':
        res = scan(args.workers)
        Path(args.out).write_text(json.dumps(res, indent=1, sort_keys=True) + '\n')
        print(json.dumps({k: res[k] for k in ('matches', 'not1v1', 'level_incomplete', 'evo_matches', 'hero_matches',
                                               'nonprincess_matches', 'level_by_rarity')}, indent=1))
    elif args.cmd == 'select':
        exclude = []
        for path in args.exclude:
            exclude += [tuple(r.split(':')) for r in json.loads(Path(path).read_text())['refs']]
        exclude = [(s, int(r)) for s, r in exclude]
        if args.which == 'native50':
            refs, meta = native50_refs()
            meta['rule'] = 'study.py prepare(): 20 evenly spaced + 30 greedy coverage, part-000000'
        else:
            refs, meta = random_refs(args.n, args.seed, exclude)
            meta['rule'] = f'random.Random({args.seed}).sample over the concatenated shard rows, excluding ' \
                           f'{len(exclude)} refs'
        meta = write_sample(args.out, refs, meta)
        print(json.dumps({k: v for k, v in meta.items() if k not in ('refs', 'tags')}, indent=1))
    elif args.cmd == 'run':
        cfg = CONFIGS[args.config]
        kw = {}
        if args.offset is not None:
            kw['offset'] = args.offset
        if args.slack is not None:
            kw['slack'] = args.slack
        name = args.name or (cfg.name + (f'-off{args.offset:+d}' if args.offset is not None else ''))
        cfg = Config(**{**cfg.__dict__, **kw, 'name': name})
        run(args.sample, cfg, args.out, args.workers)


if __name__ == '__main__':
    sys.exit(main())
