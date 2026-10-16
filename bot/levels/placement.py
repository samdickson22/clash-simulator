"""Experimental common simulator mask intersection; no native/rollout physics changes.

Only actual commands entering RoyaleSim use this adapter. Ordinary buildings keep
existing own-frame rows 0..14. Water-sensitive cards exclude tile centres touching
WATER half-cells in the pinned static arena, including air troops and bridge edges.
Installation requires an exact-binary placement_probe receipt, not a calibration hypothesis.
No class/global monkeypatches; standard factories and other Runtime instances stay unchanged.
"""
from __future__ import annotations

import hashlib
import json
import os
from functools import lru_cache
from pathlib import Path

import numpy as np

VERSION = 'rsim-static-water-intersection-v3'
PROOF_ENV = 'CLASHER_LEVELS_PLACEMENT_PROOF'
ARENA_SHA256 = '7fbe4b0dce373d49ec69f1cdaeb65047b1602ea58dd6ce3a79dfe9be03fe7169'
CARDS_SHA256 = 'c68d6c011e0130649aa2647b21e293c8bf7141e32262bdfd8cc7592704229fdc'
WATER_KINDS = frozenset({'troop', 'ordinary', 'tunnel', 'rolling', 'water_spell'})


def water_tiles(arena):
    """Pure fixed geometry: a tile centre touches its four surrounding half-cells.

    This is only a WATER intersection, not a new territory/occupancy/footprint oracle.
    The exact-binary probe must establish closed edges and card classes before use.
    """
    if (arena.get('tiles') != [18, 32] or arena.get('half_grid') != [36, 64]
            or arena.get('half_tiles_per_tile') != 2 or arena.get('bits', {}).get('WATER') != 32):
        raise ValueError('unsupported static arena geometry')
    grid = np.asarray(arena['grid'], dtype=np.int64)
    if grid.shape != (64, 36):
        raise ValueError('unexpected static arena half-cell grid shape')
    water = (grid & 32) != 0
    tiles = water.reshape(32, 2, 18, 2).any(axis=(1, 3))
    if not np.array_equal(tiles, tiles[::-1, ::-1]):
        raise ValueError('pinned static WATER geometry is not seat-rotation invariant')
    result = tiles.reshape(576)
    result.flags.writeable = False
    return result


def card_kind(row, cards=None, _seen=frozenset()):
    """Static shipped card metadata only; no levels, state, battle or deploy checks.

    SpellAsDeploy carries troop territory only without enemy-side permission.
    Variant rows inherit their forms' class; projectile-spawn spells refuse water.
    Tunnelling buildings retain enemy-side eligibility and their existing occupancy.
    """
    if row.get('name') == 'Mirror':
        return 'mirror'  # Public history must resolve this before an actor can authorize a tap.
    name = row.get('name')
    if name in _seen:
        return 'unknown'
    variant = (row.get('spell') or {}).get('variant')
    if variant is not None:
        options = variant.get('options') if isinstance(variant, dict) else None
        if not isinstance(cards, dict) or not isinstance(options, list) or not options:
            return 'unknown'
        kinds = []
        for option in options:
            target = option.get('card') if isinstance(option, dict) else None
            form = cards.get(target)
            if not isinstance(form, dict):
                return 'unknown'
            kinds.append(card_kind(form, cards, _seen | {name}))
        # Native kind_code takes the first form; the loader requires uniform body
        # kinds. Refuse unresolved/mixed placement classes rather than guessing.
        return kinds[0] if kinds[0] in ('troop', 'ordinary', 'tunnel') and len(set(kinds)) == 1 else 'unknown'
    kind = row.get('kind')
    if kind in ('troop', 'building'):
        if row.get('spawn_pathfind'):
            return 'tunnel' if row.get('can_deploy_on_enemy_side') is True else 'unknown'
        if kind == 'troop':
            return 'troop'  # Flying does not waive the shipped deployment WATER test.
        return 'ordinary' if not row.get('can_deploy_on_enemy_side') else 'unknown'
    if kind == 'spell':
        spell = row.get('spell')
        if not isinstance(spell, dict) or type(spell.get('spell_as_deploy')) is not bool:
            return 'unknown'
        if spell['spell_as_deploy'] and not spell.get('can_deploy_on_enemy_side', False):
            return 'rolling'
        if (row.get('projectile') or {}).get('spawn_character'):
            return 'water_spell'
        return 'unrestricted'
    return 'unknown'


@lru_cache(maxsize=1)
def static_rules():
    """Read public immutable installed data; never instantiate/query a simulator battle."""
    import royalesim as rs
    data = Path(rs.data_dir())
    parsed = []
    for relative, expected in (('derived/arena.json', ARENA_SHA256), ('derived/cards.json', CARDS_SHA256)):
        raw = (data/relative).read_bytes()
        if hashlib.sha256(raw).hexdigest() != expected:
            raise ValueError(f'placement static data pin mismatch: {relative}')
        parsed.append(json.loads(raw))
    arena, catalogue = parsed
    rows = catalogue['cards']
    cards = {row['name']: row for row in rows}
    if len(cards) != len(rows):
        raise ValueError('duplicate static simulator card identity')
    return water_tiles(arena), cards


class PlacementMask:
    def __init__(self, base):
        from clasher.rl.contract_v5 import ContractV5ActionMaskBuilder
        if type(base) is not ContractV5ActionMaskBuilder or base.mask_version != 1:
            raise TypeError(f'unsupported placement mask builder: {type(base)}')
        self.base, self.builder = base, base.builder
        if not self.builder.canonical_perspective:
            raise ValueError('placement adapter requires canonical own-frame tiles')
        self.calls = self.removed = self.unknown_slots = self.mirror_slots = 0
        self.water_removed = 0
        self.water, self.cards = static_rules()
        self._kinds = {}

    def __getattr__(self, name):
        return getattr(self.base, name)

    def _kind(self, name, history):
        from clasher.card_aliases import resolve_card_name
        loader = self.builder.loader
        definitions = loader.load_card_definitions()
        name = resolve_card_name(name, definitions)
        if name == 'Mirror':
            self.mirror_slots += 1
            if history is None:
                return 'unknown'
            name = resolve_card_name(history.card_name, definitions)
            if name == 'Mirror':
                return 'unknown'
        if name not in definitions:
            return 'unknown'
        if name in self._kinds:
            return self._kinds[name]
        from bot.players.royalesim_adapter import royalesim_card
        kind = card_kind(self.cards.get(royalesim_card(name), {}), self.cards)
        self._kinds[name] = kind
        return kind

    def build(self, request):
        from clasher.rl.public_action_mask import PublicActionMaskInput
        if not isinstance(request, PublicActionMaskInput):
            raise TypeError('placement adapter accepts public mask input only')
        original = np.asarray(self.base.build(request))
        if original.shape != (2306,) or original.dtype != np.bool_:
            raise ValueError('unexpected public action mask shape/type')
        mask = original.copy()  # Never mutate a base mask or a shared cached array.
        for slot in range(4):
            token = int(request.hand_ids[slot])
            name = self.builder.card_name_for_token_id(token) if token > 0 else None
            if name is None:
                kind = 'unknown'
            else:
                kind = self._kind(name, request.own_last_play)
            if kind == 'ordinary':
                mask[slot*576 + 15*18:(slot+1)*576] = False
            if kind in WATER_KINDS:
                part = mask[slot*576:(slot+1)*576]
                self.water_removed += int(np.count_nonzero(part & self.water))
                part[self.water] = False
            elif kind == 'unknown':
                # Unidentified or unclassified cards cannot authorize any deployment.
                self.unknown_slots += 1
                mask[slot*576:(slot+1)*576] = False
        if np.any(mask & ~original) or not np.array_equal(mask[2304:], original[2304:]):
            raise AssertionError('compatibility mask unmasked an action or changed WAIT/ability')
        self.calls += 1
        self.removed += int(np.count_nonzero(original & ~mask))
        return mask

    def diagnostics(self):
        return dict(version=VERSION, calls=self.calls, removed=self.removed,
                    unknown_slots=self.unknown_slots, mirror_slots=self.mirror_slots, water_removed=self.water_removed,
                    base_type=f'{type(self.base).__module__}.{type(self.base).__qualname__}')


def proof():
    """Bind the supplied passing microprobe to the currently installed binary/data and this source."""
    from .placement_probe import installed_identity, validate_receipt
    path = os.environ.get(PROOF_ENV)
    if not path:
        raise ValueError(f'{PROOF_ENV} must name a passing exact-binary microprobe receipt')
    raw = Path(path).read_bytes()
    receipt = json.loads(raw)
    validate_receipt(receipt, installed_identity())
    return dict(version=VERSION, path=str(Path(path).resolve()), sha256=hashlib.sha256(raw).hexdigest(),
                installed=receipt['identity'])


def _wrap(owner, builder):
    current = owner.mask_builder
    if isinstance(current, PlacementMask):
        if current.builder is not builder or current.base.builder is not builder:
            raise ValueError('placement wrapper belongs to a different observation builder')
        return current
    wrapped = PlacementMask(current)
    if wrapped.builder is not builder:
        raise ValueError('unexpected mask-builder observation instance')
    owner.mask_builder = wrapped
    return wrapped


def install_runtime(rt):
    """Wrap actual script instances, before construction of any experimental actor."""
    from clasher.rl.public_scripted_opponent import PublicScriptedOpponent
    if set(rt.R.bots) != {'balanced', 'pressure', 'defense'}:
        raise ValueError(f'unexpected actual script paths: {sorted(rt.R.bots)}')
    if not hasattr(rt, '_placement'):
        observed = proof()
        scripts = {}
        for style, bot in rt.R.bots.items():
            if not isinstance(bot, PublicScriptedOpponent):
                raise TypeError(f'unexpected actual script instance: {type(bot)}')
            # Full scope supplies separate script-builder instances with the same public vocabulary/data.
            builder = bot.builder
            if (builder.token_names != rt.R.builder.token_names or builder.public_contract_version != 5 or
                    Path(builder.loader.data_file).resolve() != Path(rt.R.builder.loader.data_file).resolve()):
                raise ValueError(f'script builder vocabulary/data differs at {style}')
            scripts[style] = _wrap(bot, builder)
        rt._placement = dict(proof=observed, scripts=scripts)
    if set(rt._placement['scripts']) != set(rt.R.bots):
        raise ValueError('incomplete placement installation paths')
    for style, wrapper in rt._placement['scripts'].items():
        if rt.R.bots[style].mask_builder is not wrapper or wrapper.builder is not rt.R.bots[style].builder:
            raise ValueError(f'placement wrapper replaced at R.bots[{style}].mask_builder')
    return rt._placement


def validate_player(player, *, require_calls=False):
    state = player._placement_actor
    rt = player.rt
    install_runtime(rt)
    wrapper = state['poller']
    if wrapper is None or player.poller.player.mask_builder is not wrapper or wrapper.builder is not rt.R.builder:
        raise ValueError('actual poller.player.mask_builder placement path missing/replaced')
    if state['kind'] == 'search':
        if player.p.core.bots is not rt.R.bots or player.p.core.bots['balanced'].mask_builder is not rt._placement['scripts']['balanced']:
            raise ValueError('actual core.bots[balanced].mask_builder placement path missing/replaced')
        if require_calls and rt._placement['scripts']['balanced'].calls <= state['script_calls_at_start']:
            raise ValueError('actual root candidate mask was never exercised')
    if require_calls and wrapper.calls == 0:
        raise ValueError('actual policy fallback/opponent mask was never exercised')


def install_player(player, *, kind):
    """Explicit instance wrappers: pollers are created by start(), before any select/act."""
    from bot.players.policy import PolicyPlayer
    from bot.search.players import MultiSearchPlayer
    if kind not in ('search', 'policy') or not isinstance(player, MultiSearchPlayer if kind == 'search' else PolicyPlayer):
        raise TypeError(f'unsupported actual {kind} actor: {type(player)}')
    install_runtime(player.rt)
    if hasattr(player, '_placement_actor'):
        if player._placement_actor['kind'] != kind:
            raise ValueError('placement actor installed with conflicting kind')
        return player
    state = player._placement_actor = dict(kind=kind, poller=None, script_calls_at_start=0)
    start, act = player.start, player.act

    def start_with_placement(ctx):
        start(ctx)
        state['poller'] = _wrap(player.poller.player, player.rt.R.builder)
        state['script_calls_at_start'] = player.rt._placement['scripts']['balanced'].calls
        validate_player(player)

    def act_with_placement(view):
        validate_player(player)
        decision = act(view)
        validate_player(player)
        if decision.action < 2304 and (player.poller.mask is None or not player.poller.mask[decision.action]):
            raise ValueError(f'actual selected action bypassed common public mask: {decision.action}')
        return decision

    player.start, player.act = start_with_placement, act_with_placement
    return player


def diagnostics(rt, players, *, require_calls):
    state = install_runtime(rt)
    actors = {}
    for seat, player in players.items():
        validate_player(player, require_calls=require_calls)
        actors[str(seat)] = dict(kind=player._placement_actor['kind'],
                                path='poller.player.mask_builder',
                                candidate_path='p.core.bots[balanced].mask_builder' if player._placement_actor['kind'] == 'search' else None,
                                actor_type=f'{type(player).__module__}.{type(player).__qualname__}',
                                mask=player._placement_actor['poller'].diagnostics())
    return dict(version=VERSION, proof=state['proof'], actors=actors,
                scripts={f'R.bots[{style}].mask_builder': wrapper.diagnostics()
                         for style, wrapper in state['scripts'].items()})
