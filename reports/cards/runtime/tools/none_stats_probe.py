"""Exercise optional stats with the selected immutable Runtime (one process per root).

CLASHER_BOT_RUNTIME=<root> CLASHER_BOT_RUNTIME_PINS=live16402b-r2 python -B \
  reports/cards/runtime/tools/none_stats_probe.py --out result.json
Uses all runtime actions plus every ladder spelling, all four hand slots and both seats.
The existing excluded UNK card is checked as masked, never admitted to the action scope.
"""
import argparse
import json
from pathlib import Path
import sys
import traceback

TREE = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(TREE))
sys.path.insert(0, str(TREE / 'reports/cards/tools'))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', required=True)
    ap.add_argument('--baseline-script', help='original c56_scripted.py; require identical C56 ranks/candidates')
    args = ap.parse_args()
    from bot.players.runtime import Runtime
    rt = Runtime(verify=True)
    import numpy as np
    import clasher_core
    import c56_controller
    from pool import ladder_pool
    from stage2_matches import battle
    from differential import snapshot
    from clasher.arena import Position
    from clasher.card_aliases import resolve_card_name
    from clasher.rl.c56_rollout_planner import C56RolloutPlanner
    from clasher.rl.public_action_mask import PublicActionMaskInput
    from clasher.rl import c56_scripted
    from bot.cards.scope import EXCLUDED
    R = rt.R
    baseline = None
    if args.baseline_script:
        import types
        baseline = types.ModuleType('clasher.rl._none_stats_baseline')
        baseline.__package__ = 'clasher.rl'
        exec(compile(Path(args.baseline_script).read_text(), args.baseline_script, 'exec'), baseline.__dict__)
    canonical = {resolve_card_name(n): n for n in R.meta['cards']}
    pool = [c['name'] for c in ladder_pool(rt.root / 'gamedata.json')]
    names = sorted(set(pool) | set(R.meta['cards']))
    out = dict(root=str(rt.root), pins=rt.pins, ladder_cards=len(pool), runtime_cards=len(R.meta['cards']),
               names=names, none_stats={}, spell_stats={}, failures=[], checks=0, c56_identical_checks=0, excluded={}, boards={})
    def check(label, fn):
        out['checks'] += 1
        try:
            return fn()
        except BaseException as ex:
            out['failures'].append(dict(site=label, error=f'{type(ex).__name__}: {ex}', traceback=traceback.format_exc()))
    def equal(a, b):
        assert a == b, 'C56 ranks changed'
    fields = ('mana_cost', 'summon_count', 'scaled_hitpoints', 'hitpoints', 'scaled_damage', 'range',
              'collision_radius', 'deploy_w_tile_margin', 'attacks_air', 'targets_only_buildings', 'target_type')
    for name in names:
        stats = R.builder.loader.get_card(name)
        assert stats is not None, name
        out['none_stats'][name] = [f for f in fields if getattr(stats, f, None) is None]
    out['body_none_stats'] = {}
    out['body_hp_fallbacks'] = {}
    for token, stats in R.bots['balanced'].bodies.items():
        out['body_none_stats'][f'{token}/{stats.name}'] = [f for f in fields if getattr(stats, f, None) is None]
        if stats.scaled_hitpoints is None:
            out['body_hp_fallbacks'][f'{token}/{stats.name}'] = 100
            template = R.templates[token, 'Troop']
            assert template['stats']['max_hp'] == 100, (token, template['stats'])
        check(f'body-stats/{token}', lambda stats=stats: (
            float(100 if stats.scaled_hitpoints is None else stats.scaled_hitpoints), float(stats.mana_cost),
            float((stats._raw_entry.get('summonCharacterData', {}).get('shieldHitpoints', 0)) or 0)))
    out['spell_missing_fields'] = {}
    for name, spell in R.bots['balanced'].spells.items():
        spell_fields = ('damage', 'building_damage', 'crown_tower_damage', 'radius', 'duration', 'projectile_range', 'hits_air')
        out['spell_stats'][name] = {f: getattr(spell, f, None) for f in spell_fields}
        out['spell_missing_fields'][name] = [f for f in spell_fields if not hasattr(spell, f)]
    Path(args.out + '.inventory.json').write_text(json.dumps(out, indent=2, sort_keys=True) + '\n')
    for style, bot in R.bots.items():
        check(f'metadata/{style}', lambda bot=bot: c56_controller.metadata(R.builder, bot=bot, action_cards=tuple(R.meta['cards'])))
    # Enemy threats are real engine entities; towers are present in every board.
    fixtures = [('tower', None), ('building', 'Cannon'), ('troop', 'Knight'), ('air', 'Minions'), ('mixed', 'Cannon'), ('missing-hp', 'ThreeMusketeers')]
    for seat in (0, 1):
        for board, threat in fixtures:
            decks = [list(rt.x4s_decks()[0]), ['Cannon', 'Knight', 'Minions', 'HogRider', 'Archers', 'Fireball', 'Zap', 'Skeletons']]
            if seat:
                decks.reverse()
            b = battle(dict(seed=2000024, decks=decks), R.builder.loader)
            for card in ([threat] if threat and board != 'mixed' else ['Cannon', 'Knight', 'Minions'] if board == 'mixed' else []):
                b.players[1-seat].elixir = 10.
                if card not in b.players[1-seat].hand:
                    b.players[1-seat].hand[0] = card
                assert b.deploy_card(1-seat, card, Position(4.5 if card == 'Cannon' else 13.5, 21.5 if seat == 0 else 10.5)), card
            for _ in range(40):
                b.step()
            out['boards'][f'{seat}/{board}'] = [e.card_stats.name for e in b.entities.values() if getattr(e, 'card_stats', None)]
            mine = b.clone()  # stat/mask/ranking calls do not advance the Python battle
            for name in names:
                resolved = canonical.get(resolve_card_name(name))
                if resolved is None:
                    assert name in EXCLUDED, name
                    token = R.builder.token_id(name, namespace='card_action')
                    assert token <= 1, (name, token)
                    out['excluded'][name] = EXCLUDED[name]
                    continue
                for slot in range(4):
                    hand = [c for c in decks[seat] if c != resolved][:4]
                    hand[slot] = resolved
                    mine.players[seat].hand = hand
                    mine.players[seat].elixir = 10.
                    packet = R.builder.build_public(mine, seat)
                    assert int(packet.observation.hand_ids[slot]) == R.builder.token_id(resolved, namespace='card_action')
                    bodies = R.bots['balanced']._bodies(packet)
                    if board == 'missing-hp':
                        assert any(b.enemy and not b.crown and b.max_hp == 100 for b in bodies)
                    if board in ('building', 'mixed'):
                        assert any(b.enemy and not b.crown and b.cost > 0 for b in bodies)
                    label = f'{name}/{seat}/{board}/{slot}'
                    check(label + '/mask', lambda: R.bots['balanced'].mask_builder.build(PublicActionMaskInput.from_confidence_observation(packet)))
                    for style, bot in R.bots.items():
                        ranks = check(label + '/rank/' + style, lambda bot=bot: bot._ranked_actions(packet, all_plays=True))
                        if baseline is not None and resolved in R.base_bots['balanced'].spells.keys() | {n for n, _ in R.base_bots['balanced'].cards.values()}:
                            old = check(label + '/old/' + style, lambda bot=bot: baseline.ranked_actions(bot, packet, all_plays=True))
                            if old is not None and ranks is not None:
                                check(label + '/identical/' + style, lambda: equal(ranks, old))
                                out['c56_identical_checks'] += 1
                    planner = C56RolloutPlanner(R.builder, R.bots, seed=0)
                    check(label + '/candidates', lambda: planner.candidates(packet, (2304,)))
                    # Test the immutable native against all optional spell/stats metadata as well.
                    if slot == 0:
                        native = check(label + '/native-build', lambda: clasher_core.BattleState(snapshot(mine, R.config)))
                        if native is not None:
                            check(label + '/native-mask', lambda: R.native.public_mask(native, seat))
                            check(label + '/native-evaluate', lambda: R.native.evaluate(native, seat, 1.))
                            for style in R.bots:
                                check(label + '/native-rank/' + style, lambda style=style: R.native.select_action(native.clone(), seat, style))
            print('done', seat, board, 'checks', out['checks'], 'failures', len(out['failures']), flush=True)
    out['result'] = 'PASS' if not out['failures'] else 'FAIL'
    Path(args.out).write_text(json.dumps(out, indent=2, sort_keys=True) + '\n')
    print(out['result'], out['checks'], 'checks', len(out['failures']), 'failures', flush=True)
    return bool(out['failures'])


if __name__ == '__main__':
    sys.exit(main())
