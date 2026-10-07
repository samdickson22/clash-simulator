#!/usr/bin/env bash
set -euo pipefail
cd /mpac/sdicks02/repos/clasher
[[ -f /mpac/sdicks02/jobs/clasher/transfer-ready.json ]]
stage=reports/strategy_council_20260928/engine-speed/stage6
export PYTHONPATH="$PWD/engine-rs:$PWD/src:$PWD/$stage"
case ${1:?suite} in
 stage5-replay) .venv/bin/python -B reports/strategy_council_20260928/fleet/stage5_replay.py ;;
 speed) .venv/bin/python -B engine-rs/differential.py --games 24 --output /mpac/sdicks02/jobs/clasher/differential-linux-20261007.json ;;
 fast) .venv/bin/python -B -m pytest -q tests/test_battle_clone.py tests/test_card_mechanics.py tests/test_scope_engine_cards.py tests/test_elixir_leak_penalty.py ;;
 stage2) .venv/bin/python -B -m unittest -v test_parity test_stage2 test_canonical_data ;;
 stage4) .venv/bin/python -B reports/strategy_council_20260928/fleet/audited_suite.py stage4 ;;
 stage5) .venv/bin/python -B -m unittest -v test_stage3_regressions test_stage5_search test_stage5b_deadline ;;
 stage6) .venv/bin/python -B -m unittest -v test_beam_dash.BeamDash test_chain_stagger.ChainStagger test_mirror_leaf.MirrorLeaf test_hook_planner.HookPlanner test_skeleton_ability.SkeletonAbility test_mirror_public.MirrorPublic test_mirror.Mirror test_clone.Clone test_hook.Hook test_leap.Leap test_dash.Dash test_early.EarlyCards test_ram.RamAndBomb test_early2.Early2 test_arena8.Arena8 test_ranking.Ranking test_ranged.Ranged test_reuse.Reused test_body.Body test_body2.Body2 test_souls.Souls test_placement_cache.PlacementCache test_projectile_extensions.ProjectileExtensions test_golden.Golden test_payloads.Payloads test_graveyard.Graveyard test_haste.Haste test_haste_ramp.HasteRamp test_dragon_chain.DragonChain ;;
 *) exit 2 ;;
esac
