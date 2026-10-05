"""Real public-script trajectory gate. Atomic per-game resume receipts."""

import argparse
from collections import deque
import hashlib
import json
from pathlib import Path
import random
import time

import clasher_core
from clasher.data import CardDataLoader
from clasher.player import PlayerState
from clasher.rl.action_space import DiscreteTileActionSpace
from clasher.rl.native_public_observation import (
    NativeProjectileCatalog,
    public_reference_builder,
)
from clasher.rl.public_observation import reference_public_observation
from clasher.rl.public_scripted_opponent import PublicScriptedOpponent
from clasher.rl.public_action_mask import PublicActionMaskBuilder, PublicActionMaskInput
from differential import ROOT, ES, BattleState, config, snapshot, battle_digest
from diagnostics import detail, phase_step
from stage2 import fingerprint

ROLES = ES.parent / "m0/data/roles_v2"
PILOT = tuple(json.loads((ROLES / "training.json").read_text())["cards"])
STYLES = ("balanced", "pressure", "defense")


def resources():
    loader = CardDataLoader()
    catalog = NativeProjectileCatalog.from_csv(
        Path.home()
        / ".cache/clasher-native-reference/decoded-logic-1e505767/projectiles.csv",
        expected_sha256="c59ef74273b721b861e6a499bc8869a6fc29ad07919884b79ebe859455d6eac5",
    )
    builder = public_reference_builder(loader, catalog, public_contract_version=4)
    return loader, builder, PublicActionMaskBuilder(builder), DiscreteTileActionSpace()


def episode(case):
    decks = []
    for role in ("training", "development"):
        decks.extend(json.loads((ROLES / f"{role}.json").read_text())["decks"])
    decks.extend(
        json.loads((ES.parent / "pilot/hog26-deployment.json").read_text())["decks"]
    )
    decks = list({tuple(d["cards"]): d for d in decks}.values())
    rng = random.Random(72000 + case)
    selected = [decks[case % len(decks)], decks[(case * 7 + 11) % len(decks)]]
    hands = [list(d["cards"]) for d in selected]
    for deck in hands:
        rng.shuffle(deck)
    return dict(
        case=case,
        seed=82000 + case,
        names=[d["name"] for d in selected],
        decks=hands,
        styles=[STYLES[case % 3], STYLES[(case // 3) % 3]],
    )


def battle(ep, loader):
    return BattleState(
        players=[
            PlayerState(
                owner, deck=list(deck), hand=list(deck[:4]), cycle_queue=deque(deck[4:])
            )
            for owner, deck in enumerate(ep["decks"])
        ],
        rng=random.Random(ep["seed"]),
        card_loader=loader,
    )


def match(case, cfg, res, trace_tick=None, until=6001):
    ep = episode(case)
    loader, builder, mask_builder, space = res
    b = battle(ep, loader)
    r = clasher_core.BattleState(snapshot(b, cfg))
    controllers = [PublicScriptedOpponent(builder, style=s) for s in ep["styles"]]
    actions = []
    pcpu = rcpu = 0.0
    boundary_count = 0
    for t in range(trace_tick or until):
        if b.game_over:
            break
        if t >= 90 and t % 5 == 0:
            views = [
                reference_public_observation(builder.build_actor(b, o)) for o in (0, 1)
            ]
            choices = [int(c.select_action(v)) for c, v in zip(controllers, views)]
            for owner, action in enumerate(choices):
                mask = mask_builder.build(
                    PublicActionMaskInput.from_confidence_observation(views[owner])
                )
                assert mask[action], (case, t, owner, action)
                choice = space.decode_action(action, owner)
                if choice.is_no_op:
                    continue
                name = builder.card_name_for_token_id(
                    int(views[owner].observation.hand_ids[choice.slot])
                )
                pos = choice.position
                pa = b.deploy_card(owner, name, pos)
                ra = r.apply_action(owner, name, pos.x, pos.y)
                actions.append([t, owner, action, name, pos.x, pos.y, pa, ra])
                if pa != ra or battle_digest(b) != r.digest():
                    return dict(
                        ok=False,
                        episode=ep,
                        kind="action",
                        tick=t,
                        actions=actions,
                        **detail(b, r),
                    )
        if trace_tick and t == trace_tick - 1:
            return phase_step(b, r)
        start = time.process_time()
        b.step()
        pcpu += time.process_time() - start
        start = time.process_time()
        r.step()
        rcpu += time.process_time() - start
        boundary_count += 1
        words, index = r.rng_state()
        if (
            battle_digest(b) != r.digest()
            or tuple(words) + (index,) != b.rng.getstate()[1]
        ):
            return dict(
                ok=False,
                episode=ep,
                kind="tick",
                tick=b.tick,
                actions=actions,
                **detail(b, r),
            )
    assert until < 6001 or b.game_over, "full match did not terminate"
    return dict(
        ok=True,
        episode=ep,
        ticks=b.tick,
        boundaries=boundary_count,
        python_cpu=pcpu,
        rust_cpu=rcpu,
        speed_ratio=pcpu / rcpu,
        digest=battle_digest(b),
        winner=b.winner,
        actions=actions,
    )


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--games", type=int, default=64)
    p.add_argument("--case", type=int)
    p.add_argument("--start-case", type=int, default=0)
    p.add_argument("--trace-tick", type=int)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    identity = fingerprint()
    cfg = config(PILOT)
    res = resources()
    out = dict(fingerprint=identity, results={})
    if args.output.exists():
        prior = json.loads(args.output.read_text())
        if prior.get("fingerprint") == identity:
            out = prior
    for case in (
        [args.case] if args.case is not None else range(args.start_case, args.games)
    ):
        if out["results"].get(str(case), {}).get("ok") and not args.trace_tick:
            continue
        result = match(case, cfg, res, args.trace_tick)
        out["results"][str(case)] = result
        tmp = args.output.with_suffix(".tmp")
        tmp.write_text(json.dumps(out, indent=2) + "\n")
        tmp.replace(args.output)
        print(
            "match",
            case,
            "trace saved"
            if args.trace_tick
            else {
                k: v
                for k, v in result.items()
                if k not in ("python", "rust", "field_diff", "actions")
            },
            flush=True,
        )
        if not result.get("ok"):
            raise SystemExit(1)
    print("PASS", len(out["results"]), "full matches", flush=True)


if __name__ == "__main__":
    main()
