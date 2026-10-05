"""Resumable Stage 3 differentials. Python reference sources remain read-only."""

import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import random
from types import SimpleNamespace
from clasher.rl.strategy_bots import StrategyBot
from clasher.paths import gamedata_path

import numpy as np
import clasher_core
from clasher.balance import tournament_tower_stat
from clasher.rl.card_semantics import building_target_pressure_score
from clasher.rl.public_observation import project_council_public_observation
from clasher.rl.public_action_mask import PublicActionMaskInput
from clasher.rl.public_scripted_opponent import PublicScriptedOpponent
from differential import ES, config, snapshot, battle_digest, Position
from stage2_matches import PILOT, resources, battle


def metadata(builder):
    bot = PublicScriptedOpponent(builder)
    cards, bodies = {}, {}
    for token, (name, s) in bot.cards.items():
        row = dict(
            token=token,
            radius=float(s.collision_radius or 0.5),
            blocker_radius=float(builder.card_stat_features[token, 12]) * 3,
            cost=float(s.mana_cost),
            count=float(s.summon_count or 1),
            hp=float(s.scaled_hitpoints or 0),
            damage=float(s.scaled_damage or 0),
            range=float(s.range or 0),
            shield=bool(
                s._raw_entry.get("summonCharacterData", {}).get("shieldHitpoints", 0)
            ),
            building=str(s.card_type).lower() == "building",
            spell=name in bot.spells,
            margin=int(s.deploy_w_tile_margin or 0),
            only_buildings=bool(s.targets_only_buildings),
        )
        row["efficiency"] = (
            (max(0.0, float(s.hitpoints or 0)) / 700.0) ** 0.5
            + float(s.damage or 0) / 170.0
            + 0.2 * max(1.0, float(s.summon_count or 1))
        ) / max(1.0, float(s.mana_cost))
        import math

        row["tower_pressure"] = math.log1p(
            building_target_pressure_score(s)
        ) / math.log1p(400.0)
        cards[name] = row
    for token, s in bot.bodies.items():
        name = next(n for n, st in bot.cards.values() if st.name == s.name)
        bodies[s.name] = dict(
            cards[name],
            token=token,
            blocker_radius=float(builder.card_stat_features[token, 12]) * 3,
        )
    for token, name in bot.crowns.items():
        bodies[name] = dict(
            token=token,
            radius=1.0,
            blocker_radius=float(builder.card_stat_features[token, 12]) * 3,
            cost=0.0,
            count=1.0,
            hp=float(
                tournament_tower_stat(
                    "PrincessTower" if name == "Tower" else "KingTower", "hitpoints"
                )
            ),
            damage=0.0,
            range=0.0,
            shield=False,
            building=True,
            spell=False,
            margin=0,
            only_buildings=False,
        )
    return dict(cards=cards, bodies=bodies)


def verify_view(b, r, scripts, builder, mask_builder, actions=False):
    for seat in (0, 1):
        p = project_council_public_observation(builder.build_actor(b, seat))
        expected = mask_builder.build(
            PublicActionMaskInput.from_confidence_observation(p)
        )
        actual = np.asarray(scripts.public_mask(r, seat))
        assert np.array_equal(expected, actual), (
            "mask",
            b.tick,
            seat,
            np.flatnonzero(expected != actual).tolist(),
        )
        v = json.loads(scripts.public_view(r, seat))
        bot = PublicScriptedOpponent(builder)
        ref = bot._bodies(p)
        assert len(v["bodies"]) == len(ref), (b.tick, seat, v["bodies"], ref)
        for got, want in zip(v["bodies"], ref):
            for key in (
                "x",
                "y",
                "enemy",
                "hp",
                "radius",
                "cost",
                "crown",
                "spell_credit",
            ):
                assert got[key] == getattr(want, key), (b.tick, seat, key, got, want)
            assert got["maximum"] == want.max_hp
            assert got["only_buildings"] == want.targets_buildings
        assert v["hand"] == p.observation.hand_ids[:4].tolist()
        assert v["elixir"] == float(p.observation.global_features[5]) * 10
        assert v["towers"] == p.observation.global_features[8:14].astype(float).tolist()
        if actions:
            for style in ("balanced", "pressure", "defense"):
                want = PublicScriptedOpponent(builder, style=style).select_action(p)
                got = scripts.select_action(r, seat, style)
                assert got == want, ("action", b.tick, seat, style, want, got)
            env = SimpleNamespace(battle=b, action_space=resources()[3])
            want = StrategyBot("balanced").select_action(
                env, seat, action_mask=expected
            )
            got = scripts.select_action(r, seat, "sb-balanced")
            assert got == want, ("action", b.tick, seat, "sb-balanced", want, got)


def fingerprint():
    paths = list(Path("engine-rs/src").glob("*.rs")) + [
        Path(__file__),
        Path("engine-rs/clasher_core.abi3.so"),
    ]
    paths += list(Path("src/clasher").rglob("*.py"))
    paths.append(gamedata_path())
    return {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(paths)}


def gate1(args):
    loader, builder, mask_builder, space = resources()
    cfg = config(PILOT)
    meta = metadata(builder)
    scripts = clasher_core.NativeScripts(json.dumps(meta))
    games = json.loads((ES / "results/stage2_matches_final3.json").read_text())[
        "results"
    ]
    out = {"fingerprint": fingerprint(), "results": {}}
    if args.output.exists():
        prev = json.loads(args.output.read_text())
        if prev["fingerprint"] == out["fingerprint"]:
            out = prev
    for case in range(args.games):
        if str(case) in out["results"]:
            continue
        record = games[str(case)]
        b = battle(record["episode"], loader)
        schedule = defaultdict(list)
        for a in record["actions"]:
            schedule[a[0]].append(a)
        ticks = set(
            random.Random(103000 + case).sample(range(90, record["ticks"]), args.roots)
        )
        rows = []
        while not b.game_over:
            if b.tick in ticks:
                r = clasher_core.BattleState(snapshot(b, cfg))
                verify_view(b, r, scripts, builder, mask_builder, args.actions)
                rows.append(dict(tick=b.tick, digest=battle_digest(b)))
            for a in schedule[b.tick]:
                assert b.deploy_card(a[1], a[3], Position(a[4], a[5])) == a[6]
            b.step()
        assert len(rows) == args.roots
        out["results"][str(case)] = rows
        tmp = args.output.with_suffix(".tmp")
        tmp.write_text(json.dumps(out, indent=2) + "\n")
        tmp.replace(args.output)
        print("roots", case, len(rows), "PASS", flush=True)
    print("PASS roots", sum(map(len, out["results"].values())), flush=True)


def gate_games(args):
    from stage2_matches import episode

    loader, builder, mask_builder, space = resources()
    cfg = config(PILOT)
    scripts = clasher_core.NativeScripts(json.dumps(metadata(builder)))
    out = {"fingerprint": fingerprint(), "results": {}}
    if args.output.exists():
        prev = json.loads(args.output.read_text())
        if prev["fingerprint"] == out["fingerprint"]:
            out = prev
    for case in range(args.start, args.games):
        if str(case) in out["results"]:
            continue
        ep = episode(case + 100)
        b = battle(ep, loader)
        r = clasher_core.BattleState(snapshot(b, cfg))
        styles = ep["styles"]
        if case % 4 == 3:
            styles[case % 2] = "sb-balanced"
        actions = 0
        while not b.game_over:
            if b.tick >= 90 and b.tick % 5 == 0:
                choices = []
                for seat, style in enumerate(styles):
                    p = project_council_public_observation(builder.build_actor(b, seat))
                    if style == "sb-balanced":
                        mask = mask_builder.build(
                            PublicActionMaskInput.from_confidence_observation(p)
                        )
                        want = StrategyBot("balanced").select_action(
                            SimpleNamespace(battle=b, action_space=space),
                            seat,
                            action_mask=mask,
                        )
                    else:
                        want = PublicScriptedOpponent(
                            builder, style=style
                        ).select_action(p)
                    got = scripts.select_action(r, seat, style)
                    if got != want:
                        import cloudpickle

                        Path(
                            "engine-rs/evidence-stage3/action_failure.pkl"
                        ).write_bytes(cloudpickle.dumps(b))
                        Path(
                            "engine-rs/evidence-stage3/action_failure_native.json"
                        ).write_text(r.snapshot())
                        verify_view(b, r, scripts, builder, mask_builder)
                        print(
                            "hands",
                            b.players[seat].hand,
                            "elixir",
                            b.players[seat].elixir,
                            flush=True,
                        )
                        print(
                            "ranked",
                            PublicScriptedOpponent(
                                builder, style=style
                            )._ranked_actions(p)
                            if style != "sb-balanced"
                            else None,
                            flush=True,
                        )
                    assert got == want, (
                        "game action",
                        case,
                        b.tick,
                        seat,
                        style,
                        want,
                        got,
                    )
                    choices.append(got)
                    actions += 1
                for seat, move in enumerate(choices):
                    pa = space.apply_action(b, seat, move)
                    ra = scripts.apply_discrete(r, seat, move)
                    # No-op return conventions differ; state is the contract.
                    assert battle_digest(b) == r.digest(), (
                        "apply",
                        case,
                        b.tick,
                        seat,
                        move,
                        pa,
                        ra,
                    )
            if args.trace_tick and b.tick == args.trace_tick - 1:
                from diagnostics import phase_step

                result = phase_step(b, r)
                Path("engine-rs/evidence-stage3/phase.json").write_text(
                    json.dumps(result, indent=2)
                )
                print({k: v["field_diff"] for k, v in result.items()}, flush=True)
                return
            b.step()
            r.step()
            assert battle_digest(b) == r.digest(), ("step", case, b.tick)
            words, index = r.rng_state()
            assert tuple(words) + (index,) == b.rng.getstate()[1]
        out["results"][str(case)] = dict(
            ticks=b.tick,
            actions=actions,
            styles=styles,
            digest=battle_digest(b),
            winner=b.winner,
        )
        tmp = args.output.with_suffix(".tmp")
        tmp.write_text(json.dumps(out, indent=2) + "\n")
        tmp.replace(args.output)
        print("game", case, b.tick, styles, "PASS", flush=True)
    print("PASS games", len(out["results"]), flush=True)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--games", type=int, default=8)
    p.add_argument("--roots", type=int, default=32)
    p.add_argument("--trace-tick", type=int)
    p.add_argument("--actions", action="store_true")
    p.add_argument("--full-games", action="store_true")
    p.add_argument("--start", type=int, default=0)
    p.add_argument("--output", type=Path, default=ES / "results/stage3_gate1.json")
    args = p.parse_args()
    (gate_games if args.full_games else gate1)(args)
