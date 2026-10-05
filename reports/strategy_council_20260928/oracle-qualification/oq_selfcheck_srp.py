"""Self-checks for ScriptRolloutPlanner (srp / srp_xm). Run inside the frozen runtime env.

Checks (each prints PASS/FAIL; exit code 1 on any FAIL):
 1. phi_antisymmetry: _phi(b, 0) == -_phi(b, 1) on real states; terminal values +-2 / 0 by seat.
 2. phi_direction: lowering the opponent's princess-tower HP raises the planning seat's _phi.
 3. no_mutation: select_action leaves the real battle untouched (tick, time, elixir, hands,
    cycle, every entity's id/position/HP, engine RNG state) and leaves env.battle in place.
 4. determinism: same state + same planner seed -> same action (the decision is a function of
    the state and the planner's own RNG only; it never sees the real opponent's move).
 5. legality_and_side: the chosen action is engine-legal AND in the public mask (or no-op), and a
    troop/building placement by seat 1 lands on seat 1's half (catches perspective mix-ups).
 6. purity_xm: srp_xm plans at every playable decision then plays no-op; the game must equal the
    never-play control (games/noop/...g001.json).
"""

from __future__ import annotations

import json
import sys

import numpy as np

import oq_cost
import oq_lib
from clasher.rl.train_recurrent import maybe_silence_stdio

FAILS: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"{'PASS' if ok else 'FAIL'} {name} {detail}", flush=True)
    if not ok:
        FAILS.append(name)


def fingerprint(b) -> tuple:
    ents = tuple(
        sorted(
            (int(k), type(e).__name__, int(e.player_id), round(float(e.position.x), 6),
             round(float(e.position.y), 6), round(float(e.hitpoints), 6), bool(e.is_alive))
            for k, e in b.entities.items()
        )
    )
    players = tuple(
        (round(float(p.elixir), 6), tuple(p.hand), tuple(getattr(p, "cycle", ()) or ()),
         float(p.left_tower_hp), float(p.right_tower_hp), float(p.king_tower_hp))
        for p in b.players
    )
    return (int(b.tick), round(float(b.time), 6), players, ents, b.rng.getstate())


def main() -> None:
    players = json.loads((oq_lib.OQ_DIR / "batches.json").read_text())["players"]
    ctx = oq_lib.Context()
    snaps, _, _ = oq_cost.collect_snapshots(ctx, "holdout", "balanced", 0, every_ticks=300)
    snaps2, _, _ = oq_cost.collect_snapshots(ctx, "holdout", "defense", 1, every_ticks=300)
    snaps += snaps2
    env = ctx.envs("holdout", 0)[0]
    space = env.action_space
    no_op = space.no_op_action

    def planner(name: str, seed: int):
        cfg = players[name]
        return oq_lib.ScriptRolloutPlanner(
            env, ctx.bot(cfg.get("style", "balanced")), samples=cfg["samples"],
            script_top=cfg["script_top"], horizon=cfg["horizon"],
            rollout_interval=cfg["rollout_interval"], seed=seed,
            opponent_model=(ctx.strategy_bot(cfg["opponent_model"][3:])
                            if str(cfg.get("opponent_model", "")).startswith("sb-") else None),
        )

    # 1 + 2
    p = planner("srp_xm", 1)
    anti = all(abs(p._phi(b, 0) + p._phi(b, 1)) < 1e-12 for b in snaps)
    t = snaps[0].clone(); t.game_over = True; t.winner = 1
    term = p._phi(t, 1) == 2.0 and p._phi(t, 0) == -2.0
    t.winner = None
    term = term and p._phi(t, 0) == 0.0 and p._phi(t, 1) == 0.0
    check("phi_antisymmetry", anti and term, f"states={len(snaps)}")
    direction = True
    for b in snaps[:6]:
        for seat in (0, 1):
            c = b.clone()
            before = p._phi(c, seat)
            opp = c.players[1 - seat]
            opp.left_tower_hp = max(1.0, opp.left_tower_hp * 0.5)
            direction &= p._phi(c, seat) > before
    check("phi_direction", direction)

    # 3, 4, 5 on playable states, both seats, both variants
    mutated = nondet = illegal = wrong_side = 0
    tested = 0
    for name in ("srp_xm", "srp"):
        for b in snaps:
            for seat in (0, 1):
                exact = space.legal_action_mask(b, seat)
                real_env_battle = env.battle
                env.battle = b
                obs = env.get_structured_observation(seat)
                pub = env.get_action_mask(seat, structured_observation=obs)
                env.battle = real_env_battle
                mask = exact & pub
                mask[no_op] = True
                legal = np.flatnonzero(mask).astype(np.int64)
                if not np.any(legal != no_op):
                    continue
                tested += 1
                fp = fingerprint(b)
                with maybe_silence_stdio(True):
                    a1 = planner(name, 7).select_action(b, seat, legal)
                    a2 = planner(name, 7).select_action(b.clone(), seat, legal)
                mutated += int(fingerprint(b) != fp or env.battle is not real_env_battle)
                nondet += int(a1 != a2)
                illegal += int(a1 != no_op and not mask[a1])
                if a1 != no_op and a1 < space.no_op_action:
                    hand = b.players[seat].hand
                    card = hand[a1 // 576]
                    sel = space.decode_action(a1, seat)
                    stats = b.card_loader.get_card(card) if hasattr(b, "card_loader") else None
                    is_spell = stats is not None and str(stats.card_type).lower() == "spell"
                    if not is_spell:
                        own_half = sel.position.y < 16 if seat == 0 else sel.position.y > 16
                        # Pocket placements after a princess tower falls are legal on the
                        # enemy half; count only if no enemy princess tower is down.
                        opp = b.players[1 - seat]
                        pocket = opp.left_tower_hp <= 0 or opp.right_tower_hp <= 0
                        wrong_side += int(not own_half and not pocket)
    check("no_mutation", mutated == 0, f"decisions={tested} mutated={mutated}")
    check("determinism", nondet == 0, f"nondeterministic={nondet}")
    check("legality_and_side", illegal == 0 and wrong_side == 0,
          f"illegal={illegal} wrong_side={wrong_side}")

    # 6 purity for srp_xm
    spec = {"role": "holdout", "opponent": "balanced",
            "seed": oq_lib.PILOT_CELL_SEEDS[("holdout", "balanced")], "game": 1,
            "player": {"name": "srp_xm_shadow", **players["srp_xm"], "shadow": True}}
    out = oq_lib.play_game(ctx, spec)
    ref = json.loads((oq_lib.OQ_DIR / "games/noop/noop__holdout__balanced__s12009449__g001.json").read_text())
    same = all(out[k] == ref[k] for k in ("ticks", "outcome", "candidate_tower_hp", "opponent_tower_hp", "decisions"))
    check("purity_xm", same and out["planner_calls"] > 0, f"planner_calls={out['planner_calls']}")

    print("SELFCHECK", "PASS" if not FAILS else f"FAIL {FAILS}")
    sys.exit(1 if FAILS else 0)


if __name__ == "__main__":
    main()
