"""Exhaustive public-mask tile placements from fresh and real pocket roots."""

import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path

import numpy as np
import clasher_core
from differential import ROOT, ES, config, snapshot, battle_digest
from diagnostics import detail
from stage2 import fingerprint
from stage2_matches import (
    PILOT,
    resources,
    battle,
    PublicActionMaskInput,
    reference_public_observation,
)

GAMES = ES / "results/stage2_matches_r11.json"


def mask_for(b, seat, res):
    _, builder, mask_builder, space = res
    view = reference_public_observation(builder.build_actor(b, seat))
    return mask_builder.build(
        PublicActionMaskInput.from_confidence_observation(view)
    ), space


def pocket_roots(cfg, res, games_path=GAMES):
    games = json.loads(games_path.read_text())["results"]
    found = set()
    for case in range(64):
        record = games[str(case)]
        b = battle(record["episode"], res[0])
        r = clasher_core.BattleState(snapshot(b, cfg))
        schedule = defaultdict(list)
        for a in record["actions"]:
            schedule[a[0]].append(a)
        for t in range(record["ticks"]):
            for a in schedule[t]:
                from differential import Position

                pa = b.deploy_card(a[1], a[3], Position(a[4], a[5]))
                ra = r.apply_action(a[1], a[3], a[4], a[5])
                assert pa == ra == a[6]
            b.step()
            r.step()
            assert battle_digest(b) == r.digest(), (case, b.tick)
            if b.game_over:
                break
            if b.tick % 50:
                continue
            for seat in (0, 1):
                if seat in found or b.get_crown_count(seat) == 0:
                    continue
                mask, space = mask_for(b, seat, res)
                pockets = 0
                for a in np.flatnonzero(mask[:2304]):
                    c = space.decode_action(int(a), seat)
                    name = b.players[seat].hand[c.slot]
                    spell = cfg["cards"][name].get("spell")
                    if spell:
                        continue
                    if (seat == 0 and c.position.y >= 15) or (
                        seat == 1 and c.position.y < 17
                    ):
                        pockets += 1
                if pockets:
                    found.add(seat)
                    yield (
                        f"pocket-game{case}-tick{b.tick}-seat{seat}",
                        b.clone(),
                        r.clone(),
                        (seat,),
                    )
            if len(found) == 2:
                return
    raise AssertionError("real games did not supply both-seat pocket roots")


def roots(cfg, res, games_path=GAMES):
    for group in range(4):
        deck = list(PILOT[group * 4 : group * 4 + 4]) + list(
            PILOT[((group + 1) % 4) * 4 : ((group + 1) % 4) * 4 + 4]
        )
        ep = dict(seed=91000 + group, decks=[deck, deck])
        b = battle(ep, res[0])
        for p in b.players:
            p.elixir = 10
        yield f"fresh-{group}", b, clasher_core.BattleState(snapshot(b, cfg)), (0, 1)
    yield from pocket_roots(cfg, res, games_path)


def check_card(b, r, seat, slot, cfg, res, ticks):
    mask, space = mask_for(b, seat, res)
    parent = battle_digest(b)
    assert parent == r.digest()
    accepted = rejected = boundaries = pockets = 0
    tiles = []
    for action in np.flatnonzero(mask[slot * 576 : (slot + 1) * 576]) + slot * 576:
        action = int(action)
        c = space.decode_action(action, seat)
        name = b.players[seat].hand[slot]
        pb, rb = b.clone(), r.clone()
        pos = c.position
        pa = pb.deploy_card(seat, name, pos)
        ra = rb.apply_action(seat, name, pos.x, pos.y)
        attempt = dict(
            seat=seat,
            card=name,
            action=action,
            x=pos.x,
            y=pos.y,
            python_accept=pa,
            rust_accept=ra,
        )
        if pa != ra or battle_digest(pb) != rb.digest():
            return dict(ok=False, kind="action", attempt=attempt, **detail(pb, rb))
        accepted += pa
        rejected += not pa
        tiles.append([pos.x, pos.y])
        spell = cfg["cards"][name].get("spell")
        if (
            pa
            and (not spell or spell.get("requires_territory"))
            and ((seat == 0 and pos.y >= 15) or (seat == 1 and pos.y < 17))
        ):
            pockets += 1
        if not pa:
            continue
        for _ in range(ticks):
            if pb.game_over:
                break
            pb.step()
            rb.step()
            boundaries += 1
            words, index = rb.rng_state()
            if (
                battle_digest(pb) != rb.digest()
                or tuple(words) + (index,) != pb.rng.getstate()[1]
            ):
                return dict(
                    ok=False,
                    kind="tick",
                    tick=pb.tick,
                    attempt=attempt,
                    **detail(pb, rb),
                )
    assert battle_digest(b) == r.digest() == parent, "clone changed parent"
    return dict(
        ok=True,
        card=b.players[seat].hand[slot],
        seat=seat,
        accepted=accepted,
        rejected=rejected,
        tiles=tiles,
        boundaries=boundaries,
        pocket_accepted=pockets,
    )


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--games-receipt", type=Path, default=GAMES)
    p.add_argument(
        "--full-gate", type=Path, default=ES / "results/stage2_full_gate_r11.json"
    )
    p.add_argument("--only-pockets", action="store_true")
    p.add_argument("--ticks", type=int, default=64)
    args = p.parse_args()
    gate = json.loads(args.full_gate.read_text())
    for f in (
        "engine-rs/src/lib.rs",
        "engine-rs/clasher_core.abi3.so",
        "engine-rs/differential.py",
    ):
        assert (
            hashlib.sha256((ROOT / f).read_bytes()).hexdigest() == gate["files"][f]
        ), f"full-game gate source changed: {f}"
    cfg = config(PILOT)
    res = resources()
    identity = fingerprint()
    out = dict(fingerprint=identity, ticks=args.ticks, results={})
    if args.output.exists():
        old = json.loads(args.output.read_text())
        if old.get("fingerprint") == identity and old.get("ticks") == args.ticks:
            out = old
    for label, b, r, seats in roots(cfg, res, args.games_receipt):
        if args.only_pockets and label.startswith("fresh"):
            continue
        for seat in seats:
            for slot in range(4):
                if b.players[seat].hand[slot] is None:
                    continue
                key = f"{label}-{seat}-{slot}"
                if out["results"].get(key, {}).get("ok"):
                    continue
                result = check_card(b, r, seat, slot, cfg, res, args.ticks)
                out["results"][key] = result
                tmp = args.output.with_suffix(".tmp")
                tmp.write_text(json.dumps(out, indent=2) + "\n")
                tmp.replace(args.output)
                print(
                    key,
                    {
                        k: v
                        for k, v in result.items()
                        if k not in ("python", "rust", "field_diff", "tiles")
                    },
                    flush=True,
                )
                if not result["ok"]:
                    raise SystemExit(1)
    print("PASS", len(out["results"]), "card/seat/root groups", flush=True)


if __name__ == "__main__":
    main()
