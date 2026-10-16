"""T1 receipts and fresh play_match matches; no heldout root enumeration."""
from unittest.mock import patch

import numpy as np

from .origins import SimOrigins, is_body


def sampled(tick, last):
    """Alternating 2/3 ticks (8 FPS); never fabricate/interpolate T1 frames."""
    return last is None or tick // 5 * 2 + (tick % 5 >= 2) > last // 5 * 2 + (last % 5 >= 2)


def t1_source(rt, guard, episode, split, emit, max_ticks=None):
    match = guard.load(rt, episode, split)
    deployments, main_ids = [], {}
    abilities = []
    for e in match.events:
        if e.get('kind') == 'champion ability':
            abilities.append(e)
            continue
        if max_ticks is not None and e['exec_tick'] > max_ticks:
            continue
        index = len(deployments)
        deployments.append(dict(index=index, owner=int(e['side']), card=e['card'], tick=int(e['exec_tick']),
                                x=float(e['tile'][0]), y=float(e['tile'][1]),
                                is_spell=e.get('kind') == 'spell', event_id=e.get('event_id')))
        for uid in e.get('spawned_native_ids', ()):
            if uid in main_ids and main_ids[uid] != index:
                raise ValueError('native ID belongs to multiple deployment receipts')
            main_ids[uid] = index
    origins, last = {}, None
    # records(1) preserves the recording tick. zip with distinct frames mirrors
    # T1Match.records' duplicate-tick filter, without matching by proximity.
    frames = (fr for i, fr in enumerate(match.frames)
              if i == 0 or fr['tick'] != match.frames[i-1]['tick'])
    for record, raw in zip(match.records(1), frames):
        if max_ticks is not None and record['tick'] > max_ticks:
            break
        units = []
        for obj in raw['objects']:
            if (obj.get('visible_hint') == 'invisible' and obj['owner'] == 1
                    or not obj.get('max_hp') or obj['max_hp'] <= 0 or obj['card_id'] == -1):
                continue
            card = match.card_of(obj['card_id'])
            if card is None:
                continue
            uid = f"t1:{obj['native_id']}"
            if uid not in origins:
                dep = main_ids.get(obj['native_id'])
                kind = 'main' if dep is not None else 'child_unresolved'
                if dep is not None:
                    d = deployments[dep]
                    if d['owner'] != obj['owner'] or d['card'] != card:
                        raise ValueError('receipt/main-body identity disagreement')
                body, _ = match.labels.identity(obj)
                token = emit.bodies.body_token(body)
                origins[uid] = dict(uid=uid, deployment_index=dep, kind=kind, origin=kind,
                                    parent_uid=None, source_card=card, owner=int(obj['owner']),
                                    first_tick=int(raw['tick']), exact=dep is not None,
                                    is_deployment=dep is not None, is_building=bool(token and token[1] == 1),
                                    method='accepted_spawned_native_ids' if dep is not None else 'no_parent_receipt')
            units.append(dict(card=card, cls=card, owner=int(obj['owner']), x=obj['x']/1000., y=obj['y']/1000.,
                              hp_frac=obj['hp']/obj['max_hp'], score=1., true_uid=uid))
        if len(record['units']) != len(units):
            raise ValueError('T1Match/raw unit alignment changed')
        record['units'] = units
        if sampled(record['tick'], last):
            emit(record, origins)
            last = record['tick']
    return dict(decks=match.entry['decks'], truth_deployments=deployments,
                origins=list(origins.values()), abilities=len(abilities),
                limitations=['T1 child parentage is unavailable; child_unresolved is a non-deployment negative.',
                             'T1 native snapshots are irregular; frames are subsampled, never interpolated.',
                             'Accepted bodies absent from all snapshots cannot have per-frame supervision.'])


RARE = ('GoblinHut', 'FirespiritHut', 'ArcherQueen', 'Goblinstein', 'MightyMiner', 'Golem',
        'SkeletonArmy', 'MinionHorde', 'GoblinGang', 'Bats')


def sim_decks(rt, index, seed):
    """Human catalog/X4S base, deterministic rare-class coverage in each hand."""
    from bot.players.ours import x4s_setup
    rng = np.random.default_rng(seed)
    if index % 3:
        decks = [list(rt.PRIOR['decks'][int(rng.integers(len(rt.PRIOR['decks'])))]['cards']) for _ in (0, 1)]
    else:
        decks = x4s_setup(rt, index, seed-index)['decks']
    for seat, deck in enumerate(decks):
        # At most one champion per deck; otherwise engine's champion rules
        # produce very little coverage of the second champion.
        champion = ('ArcherQueen', 'Goblinstein', 'MightyMiner')[(index + seat) % 3]
        anchors = [RARE[(2*index+seat) % 2], champion, 'Golem', RARE[6+(index+seat) % 4]]
        available = [c for c in deck if c in rt.R.costs and c not in ('ArcherQueen', 'Goblinstein', 'MightyMiner')]
        available += ['Knight', 'Archers', 'Fireball', 'Zap', 'Skeletons', 'HogRider']
        unique = list(dict.fromkeys(anchors + available))[:8]
        if len(unique) != 8 or any(c not in rt.R.costs for c in unique):
            raise ValueError('invalid sampled sim deck')
        rng.shuffle(unique)
        decks[seat] = unique
    return decks


def sim_source(rt, index, seed, emit, max_ticks=6001, players=('v1', 'scripted-pressure'), abilities=True):
    from bot.live.synth import SynthPerception
    from bot.live.player import make_live_player
    from bot.players.ours import play_match
    from bot.players.base import PublicView
    from fair_player import observe
    import stage2_matches
    from clasher.analysis.loss_review import delay_fixes

    decks = sim_decks(rt, index, seed)
    # play_match's per-seat command queues (created in seat order): an ability must not spend elixir the bot has
    # reserved for a pending card command (own_packet raises 'reservations exceed physical elixir')
    queues = []

    class Queue(delay_fixes.CommandQueue):
        def __init__(self, *args, **kw):
            super().__init__(*args, **kw)
            queues.append(self)
    original_battle = stage2_matches.battle
    captured = {}
    synth = SynthPerception(rt)

    def make_battle(*args, **kw):
        b = original_battle(*args, **kw)
        ledger = SimOrigins(b)
        captured['ledger'] = ledger
        step, last = b.step, [None]

        def capture():
            if not sampled(b.tick, last[0]):
                return
            info = observe(b, rt.R.builder, 0, [])
            events = [dict(kind='card', seat=d['owner'], name=d['card'], tick=d['tick'], x=d['x'], y=d['y'])
                      for d in ledger.deployments]
            record = synth.record(PublicView(b.tick, 0, info, info, events, (), True))
            # SynthPerception's nearest-body label heuristic has no exact IDs.
            # Keep its HUD/towers, replace units with exact engine entities and
            # source cards captured at creation (also avoids entity-mask caps).
            record['units'] = []
            for e in b.entities.values():
                if not is_body(e) or not e.is_alive:
                    continue
                if e.player_id == 1 and ledger.hidden(e, b.tick):
                    continue
                o = ledger.origins[e.id]
                if not o['exact']:
                    raise RuntimeError(f"unresolved sim origin at entity {e.id}")
                events = [(i, ev) for i, ev in enumerate(ledger.ability_events)
                          if ev['uid'] == o['uid'] and 0 <= b.tick-ev['tick'] <= 5]
                record['units'].append(dict(card=o['source_card'], cls=o['source_card'], owner=int(e.player_id),
                                            x=float(e.position.x), y=float(e.position.y),
                                            hp_frac=float(e.hitpoints/e.max_hitpoints), score=1., true_uid=o['uid'],
                                            origin_kind='ability' if events else o['kind'],
                                            origin_event_index=events[-1][0] if events else None))
            origins = {o['uid']: dict(o, is_building=ledger.entities[eid].entity_kind == 1)
                       for eid, o in ledger.origins.items() if o['_body']}
            emit(record, origins)
            last[0] = b.tick

        def step_and_capture(*args, **kw):
            if abilities and b.tick >= 90 and b.tick % 20 == 0:
                ledger.activate_abilities(idle=lambda owner: len(queues) == 2 and not queues[owner].pending)
            result = step(*args, **kw)
            ledger.observe_abilities()
            capture()
            return result

        b.step = step_and_capture
        capture()
        return b

    with patch.object(stage2_matches, 'battle', make_battle), patch.object(delay_fixes, 'CommandQueue', Queue):
        result = play_match(rt, {s: make_live_player(rt, players[s]) for s in (0, 1)},
                            seed=seed, decks=decks, max_ticks=max_ticks)
    if len(queues) != 2:
        raise RuntimeError(f'expected play_match to create 2 command queues, saw {len(queues)}')
    ledger = captured['ledger']
    # Wall/CPU timings belong in the job manifest, never in deterministic data.
    result = {k: v for k, v in result.items() if k not in ('timing', 'cpu_seconds')}
    return dict(decks=decks, truth_deployments=ledger.deployments, origins=ledger.body_origins(),
                result=result, players=list(players), abilities=len(ledger.ability_commands),
                ability_commands=ledger.ability_commands, origin_events=ledger.ability_events,
                limitations=['Ability effects follow the pinned engine; this does not certify native-client fidelity.',
                             'Same-UID ability returns have per-frame origin_kind=ability; birth origin stays main.'])
