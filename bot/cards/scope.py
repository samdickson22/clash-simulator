"""Opt-in card scope for the frozen search runtime (pin set `card_scope`, bot/players/runtime.py).

The runtime's Resources (fair_player, wrapped by quickwin_resources.cached_resources) is built for the 56 C56 cards:
`config(CARDS)`, `metadata(builder)` (default action_cards=CARDS bound at def time; the scripted bot's scope is
`SUPPORTED_CARDS | C56_ADDED_CARDS`, read at call time), the start-up demos (`for name in CARDS`) and the templates.
`extend(R, 'full')` keeps that build untouched and runs a second Resources build with those four scope sites
widened to C56 + EXTRA_CARDS, then merges into R, base first:

- config: every C56 entry (cards and side tables) is the base object, in base order; new keys follow. config(card)
  is per-card, so the C56 entries of the full build are identical (asserted).
- meta (native scripted-opponent tables): base cards/bodies first, new ones after (overlap asserted equal);
  R.native is rebuilt from the merged meta.
- costs: from the merged config (C56 keys/values unchanged).
- templates: the base dict, plus full-build keys it lacks. Templates are registered with setdefault in config
  order, so a single full build could pick a different template for a shared token; the base-first merge cannot.
R.builder and R.bots (the Python scripted bots: our own candidates / Python-side scripts) stay the base C56 ones.
No frozen runtime file is modified; module globals are patched only during the second build and restored.
"""
from __future__ import annotations

from contextlib import contextmanager
import json
import sys

# Ladder cards outside C56 that the full scope adds (runtime / Python-engine names, 2026-10-16 pool of 122 minus
# the 56 minus the 3 pool aliases of C56 cards: Archer=Archers, IceSpirits=IceSpirit, IceGolemite=IceGolem).
# Trim here: drop a name to keep it out of config/meta/costs/templates (EXCLUDED records why).
EXTRA_CARDS = (
    'Assassin', 'AxeMan', 'BarbarianHut', 'Barbarians', 'BattleHealer', 'BattleRam', 'Bomber', 'BossBandit',
    'Bowler', 'Clone', 'DarkMagic', 'DarkWitch', 'DartBarrell', 'ElectroDragon', 'ElectroGiant', 'ElectroWizard',
    'EliteArcher', 'Elixir Collector', 'ElixirGolem', 'Fisherman', 'Freeze', 'GiantBuffer', 'GiantSkeleton',
    'GoblinCage', 'GoblinCurse', 'GoblinDemolisher', 'GoblinDrill', 'GoblinGiant', 'GoblinMachine', 'GoldenKnight',
    'Graveyard', 'Heal', 'Hunter', 'IceWizard', 'InfernoDragon', 'LavaHound', 'LittlePrince', 'MegaKnight',
    'MegaMinion', 'MiniSparkys', 'Mirror', 'Monk', 'Mortar', 'MovingCannon', 'Pekka', 'Phoenix', 'Rage',
    'RageBarbarian', 'RamRider', 'Ronin', 'RoyalGiant', 'RoyalRecruits', 'SkeletonBalloon', 'SkeletonDragons',
    'SkeletonKing', 'SkeletonWarriors', 'Snowball', 'SpearGoblins', 'SuspiciousBush', 'ThreeMusketeers',
    'Tombstone', 'Vines', 'Witch', 'WitchMother', 'ZapMachine',
)
EXCLUDED = {
    'MergeMaiden': 'Spirit Empress: no card_vocab entry (card_action token 1 = UNK); the v5 observation cannot name it',
}
SCOPES = ('c56', 'full')
# meta.cards tokens of the three C56 cards with two vocab tokens. c56_scripted.initialize registers both aliases
# from a set ({declared, canonical}), so which token metadata() keeps depends on PYTHONHASHSEED (seeds 0/1/2 give
# three different metas on r1-total). These are the PYTHONHASHSEED=0 values, which are also the tokens the learned
# rollout opponents were trained on (bot-lopp-models pool/R3a/v1.npz meta_vocab holds 20, 77, 114 and not
# 24, 38, 289). Sorting can't reproduce them (BarbLog keeps its own token, BlowdartGoblin the vocab name's).
# r1-cards1 pins them, so its meta no longer depends on the hash seed. The new cards with two tokens (Assassin,
# EliteArcher, RageBarbarian, SkeletonBalloon, SkeletonWarriors, Snowball; seed-dependent too) get the token of their
# own runtime name, builder.token_id(name, 'card_action'), which is what the v5 packet carries for that card in hand.
META_CARD_TOKENS = {'BarbLog': 20, 'BlowdartGoblin': 77, 'Ghost': 114}   # other tokens: BarbarianBarrel 24, BlowdartGoblin 38, RoyalGhost 289
# meta.bodies rows where the full build's value replaces the base one. RamRider: the Ram entity's stats name is
# 'RamRider' (token 271 Ram); the base (C56) build only saw the rider payload under that name (token 272, range 5.5,
# hp 593); the full build adds the card's own stats (token 271, buildings-only, hp 1766), which is what the native
# reads for the Ram (scripts.rs body view, leaf.rs cost). No C56 card puts a 'RamRider' body on the board.
FULL_WINS_BODIES = frozenset({'RamRider'})


@contextmanager
def _widened(cards):
    """Widen the four C56 scope sites for one Resources build; always restored."""
    import c56_controller
    import fair_player
    c56s = sys.modules['clasher.rl.c56_scripted']
    kw = c56_controller.metadata.__kwdefaults__
    saved = (c56_controller.CARDS, kw['action_cards'], fair_player.CARDS, c56s.C56_ADDED_CARDS)
    try:
        c56_controller.CARDS = kw['action_cards'] = fair_player.CARDS = cards
        c56s.C56_ADDED_CARDS = saved[3] | frozenset(cards)
        yield
    finally:
        c56_controller.CARDS, kw['action_cards'], fair_player.CARDS, c56s.C56_ADDED_CARDS = saved


def _same(a, b):
    return json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)


def _merge(base, full, what, keep_base=None, conflicts=None):
    """base entries (same objects, same order) then full-only entries; overlapping entries must be equal, except in
    the tables named in keep_base {table: names where full wins}: there the base value wins unless named, and every
    differing pair is recorded in `conflicts`."""
    keep_base = keep_base or {}
    out = dict(base)
    for key, value in full.items():
        if key not in base:
            out[key] = value
        elif isinstance(base[key], dict) and isinstance(value, dict):
            bad = [k for k in base[key] if k not in value or not _same(base[key][k], value[k])]
            if bad and key in keep_base:
                conflicts.update({f'{what}.{key}.{k}': dict(base=base[key][k], full=value.get(k),
                                                            kept='full' if k in keep_base[key] else 'base') for k in bad})
            elif bad:
                raise AssertionError(f'{what}.{key}: full build differs on base entries {bad[:5]}')
            wins = keep_base.get(key, ())
            out[key] = {**{k: value[k] if k in wins and k in value else v for k, v in base[key].items()},
                        **{k: v for k, v in value.items() if k not in base[key]}}
        elif not _same(base[key], value):
            raise AssertionError(f'{what}.{key}: full build differs')
    return out


def full_cards(base_cards):
    extra = tuple(c for c in EXTRA_CARDS if c not in EXCLUDED)
    assert not set(extra) & set(base_cards)
    return tuple(sorted(set(base_cards) | set(extra)))


def extend(R, scope):
    """Widen a built Resources R in place to `scope`; 'c56' is a no-op. Returns R."""
    if scope not in SCOPES:
        raise ValueError(f'card_scope={scope!r}; known: {SCOPES}')
    if scope == 'c56':
        return R
    import clasher_core
    import fair_player
    from quickwin_resources import cached_resources
    base_cards = tuple(R.config['cards'])
    cards = full_cards(base_cards)
    with _widened(cards):
        F = cached_resources(fair_player.Resources)()   # class built inside the patch: its globals see `cards`
    # config also holds Mirror's 'level12:<card>' payloads (mirror_snapshot.extend) next to the playable cards.
    for what, got in (('config', [c for c in F.config['cards'] if not c.startswith('level12:')]), ('meta', F.meta['cards'])):
        if set(got) != set(cards):
            raise AssertionError(f'{what} scope: missing {sorted(set(cards) - set(got))} extra {sorted(set(got) - set(cards))}')
    R.config = _merge(R.config, F.config, 'config')
    # meta.bodies is keyed by stats name; the full build's extra card stats can re-key a name the base resolved from a
    # payload (RamRider). Base wins (C56 states keep today's rows) except FULL_WINS_BODIES.
    R.scope_conflicts = {}
    R.meta = _merge(R.meta, F.meta, 'meta', keep_base=dict(bodies=FULL_WINS_BODIES), conflicts=R.scope_conflicts)
    R.meta_token_pins = {}
    pins = dict(META_CARD_TOKENS)
    for name in R.meta['cards']:
        if name not in base_cards and name not in pins:
            pins[name] = int(R.builder.token_id(name, namespace='card_action'))
    for name, token in pins.items():
        row = R.meta['cards'].get(name)
        if row is not None and row['token'] != token:
            R.meta_token_pins[name] = (row['token'], token)
            R.meta['cards'][name] = dict(row, token=token)
    R.native = clasher_core.NativeScripts(json.dumps(R.meta))
    R.costs = {n: c['cost'] for n, c in R.config['cards'].items()}
    R.templates = {**R.templates, **{k: v for k, v in F.templates.items() if k not in R.templates}}
    R.template_count = len(R.templates)
    R.card_scope = scope
    R.scope_cards = tuple(R.meta['cards'])     # playable names (config['cards'] adds Mirror's level12: payloads)
    return R
