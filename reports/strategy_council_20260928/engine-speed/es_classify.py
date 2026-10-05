"""Classify collapsed stacks ("dir/file.py:func;..." outermost first) into subsystems."""

from __future__ import annotations

import collections

# (category, function names or None, file substring or None). Deepest matching frame wins.
ENGINE_RULES: list[tuple[str, set[str] | None, str | None]] = [
    ("clone", {"clone", "deepcopy", "_deepcopy_dict", "_reconstruct", "_deepcopy_list", "clone_lazy"}, None),
    ("legal_mask", {"legal_action_mask", "_legal_action_mask_legacy", "_legal_action_mask_fast",
                    "random_legal_action"}, None),
    ("deploy", {"deploy_card", "apply_action", "resolve_card_play"}, None),
    ("elixir_cards", {"regenerate_elixir", "tick_card_refill", "_next_card_refill_cooldown_ms"}, None),
    ("phase_clock", {"_update_battle_phases"}, None),
    ("tick_grids", {"native_building_cost_cells"}, None),
    ("tick_grids", None, "native_spatial.py"),
    ("spell_resolve", {"_resolve_pending_spell_casts"}, None),
    ("combat", {"update_combat_component", "_update_active_combat", "advance_attack_clock"}, None),
    ("targeting", {"get_nearest_target", "_get_nearest_target_vectorized", "_select_nearest_target",
                   "_select_first_nearest_target", "_select_spatial_character_tie", "_is_valid_target",
                   "is_targetable_by", "is_within_sight", "_retain_or_acquire_target",
                   "_preferred_fallback_crown_targets", "_should_switch_target", "can_attack_target",
                   "native_target_distance_from", "native_target_distance_to", "iter_entities_in_radius",
                   "_rebuild_target_cache", "get_fast_target_cache", "is_expected_to_die_from_projectiles",
                   "is_within_attack_reach", "is_within_target_keep_reach", "is_within_attack_clock_reach",
                   "is_within_attack_engagement_reach", "_sync_fast_target_entity"}, None),
    ("damage_effects", {"take_damage", "_deal_attack_damage", "_resolve_attack_damage",
                        "_snapshot_attack_damage_targets", "_snapshot_attack_area_targets_at",
                        "apply_stun", "apply_slow", "apply_periodic_damage"}, None),
    ("damage_effects", None, "effects/"),
    ("projectile_spawn", {"_create_projectile"}, None),
    ("movement", {"update_movement_component", "begin_movement_tick", "finish_movement_tick",
                  "_move_towards_target", "_update_knockback_movement", "_advance_native_charge",
                  "_update_river_jump", "_try_start_river_jump"}, None),
    ("pathfinding", {"_get_pathfind_target", "_native_movement_waypoint", "_choose_crossing_bridge_x"}, None),
    ("pathfinding", None, "pathfinding.py"),
    ("avoidance", {"_update_native_avoidance", "_apply_native_avoidance", "_decay_native_avoidance"}, None),
    ("collision", {"_accumulate_troop_collision_for", "_collision_vector_units", "_resolve_troop_collisions"}, None),
    ("status_buff_hp", {"update_buff_component", "update_status_effects", "update_hitpoint_component",
                        "_update_periodic_damage_effects", "_update_intrinsic_lifetime"}, None),
    ("object_phase", {"_run_object_phase", "tick_character_object_phase"}, None),
    ("projectiles", {"_update_homing_for_logic_tick", "_move_towards", "_resolve_impact",
                     "_collect_splash_targets", "_deal_splash_damage", "_damage_target",
                     "_update_piercing", "_update_piercing_tick", "_reaches_target_this_update"}, None),
    ("spells_areas", {"_apply_continuous_effects", "_apply_damage_tick", "_apply_tornado_pull",
                      "_deal_rolling_damage", "_apply_freeze_snapshot"}, None),
    ("spells_areas", None, "clasher/spells.py"),
    ("spells_areas", None, "dynamic_spells.py"),
    ("card_mechanics", None, "mechanics/"),
    ("card_mechanics", None, "shared/"),
    ("card_mechanics", None, "champion/"),
    ("card_mechanics", None, "cards/"),
    ("spawn", {"_spawn_entity", "_spawn_troop", "_spawn_single_troop", "_spawn_swarm_troops",
               "_spawn_unit_at_position", "_spawn_unit_at_angle", "_attach_card_mechanics",
               "_create_card_stats_from_data", "_snap_to_valid_position"}, None),
    ("cleanup_death", {"_cleanup_dead_entities", "_spawn_death_units", "on_death"}, None),
    ("win_check", {"_check_win_conditions", "_update_tower_hp"}, None),
    ("quantize", {"quantize_logic_position"}, None),
    ("rewards", {"_compute_dense_rewards", "reward_potential_p0"}, None),
    ("idle_fast_forward", {"fast_forward_idle_ticks", "can_fast_forward_idle"}, None),
]


def _match(rules, file, func):
    for name, funcs, fsub in rules:
        if (funcs is not None and func in funcs) or (fsub is not None and fsub in file):
            return name
    return None


def classify_engine_stack(frames: list[str]) -> str:
    cat = None
    in_step = False
    in_env = False
    for fr in frames:
        file, _, func = fr.rpartition(":")
        if func == "_step_logic_tick":
            in_step = True
        if "selfplay_env.py" in file:
            in_env = True
        m = _match(ENGINE_RULES, file, func)
        if m is not None:
            cat = m
    if cat is not None:
        return cat
    if in_step:
        return "step_glue"
    if in_env:
        return "env_glue"
    return "harness_other"


def classify_engine_stacks(stacks: dict[str, int]) -> dict[str, float]:
    counts = collections.Counter()
    total = 0
    for stack, n in stacks.items():
        counts[classify_engine_stack(stack.split(";"))] += n
        total += n
    return {k: v / total for k, v in counts.most_common()}


# Rollout / training top level: OUTERMOST matching frame wins.
TOP_RULES: list[tuple[str, set[str] | None, str | None]] = [
    ("ppo_update", {"ppo_update"}, None),
    ("recurrent_reconstruction", {"reconstruct_recurrent_state"}, None),
    ("opponent", {"select_action"}, "council_opponents.py"),
    ("opponent", {"select_action"}, "strategy_bots.py"),
    ("opponent", {"select_action"}, "public_scripted_opponent.py"),
    ("opponent_mask", None, None),  # placeholder (filled by special case below)
    ("env_step", {"step"}, "selfplay_env.py"),
    ("learner_obs", {"get_structured_observation"}, "selfplay_env.py"),
    ("learner_mask", {"get_action_mask"}, "selfplay_env.py"),
    ("env_reset", {"reset"}, "selfplay_env.py"),
    ("learner_forward", {"act", "forward"}, "rl/model.py"),
]


def classify_top(frames: list[str]) -> str:
    in_step_slots = False
    for fr in frames:
        file, _, func = fr.rpartition(":")
        if func == "step_slots":
            in_step_slots = True
        for name, funcs, fsub in TOP_RULES:
            if funcs is None:
                continue
            if func in funcs and (fsub is None or fsub in file):
                if name == "learner_mask" and in_step_slots and "observe_slots" not in ";".join(frames):
                    return "opponent_mask"
                return name
    if any("torch" in fr for fr in frames):
        return "torch_other"
    if any("train_recurrent.py" in fr for fr in frames):
        return "collector_glue"
    return "other"


def classify_sub(frames: list[str]) -> str:
    """Within a top-level bucket: engine vs observation vs mask vs model vs other."""
    joined = ";".join(frames)
    if "battle.py:" in joined or "entities.py:" in joined:
        if "structured_obs.py" not in joined and "public_observation.py" not in joined and "action_space.py" not in joined:
            return "engine:" + classify_engine_stack(frames)
    if "rl/model.py" in joined or "torch/nn" in joined:
        return "model"
    if "structured_obs.py" in joined or "public_observation.py" in joined or "card_semantics" in joined:
        return "observation"
    if "action_space.py" in joined or "public_action_mask.py" in joined:
        return "mask"
    return "other"


def classify_rollout_stacks(stacks: dict[str, int]) -> dict:
    top = collections.Counter()
    sub = collections.defaultdict(collections.Counter)
    total = 0
    for stack, n in stacks.items():
        frames = stack.split(";")
        t = classify_top(frames)
        top[t] += n
        sub[t][classify_sub(frames)] += n
        total += n
    return {
        "total_samples": total,
        "top": {k: v / total for k, v in top.most_common()},
        "sub": {t: {k: v / total for k, v in c.most_common(25)} for t, c in sub.items()},
    }
