"""Resumable C56 controller, human matches, imports, and public placement gates.

Every mode pins all non-vision reference code, native code, data and the
prospective human-deck plan. Reference source files are never changed.
"""

import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import pickle
import random
import time

import clasher_core
import cloudpickle
import numpy as np
from clasher.rl.action_space import DiscreteTileActionSpace
from clasher.rl.public_action_mask import PublicActionMaskInput
from c56_controller import CARDS, resources, verify
from diagnostics import detail
from differential import ROOT, Position, battle_digest, config, snapshot
from stage2 import fingerprint
from stage2_matches import battle

FOLDER = ROOT / "reports/strategy_council_20260928/engine-speed/stage4"
PLAN = FOLDER / "c56_human64_plan.json"


def same(b, r):
    words, index = r.rng_state()
    return battle_digest(b) == r.digest() and b.rng.getstate()[1] == tuple(words) + (
        index,
    )


def failure(b, r, **fields):
    return dict(ok=False, tick=b.tick, **fields, **detail(b, r))


def play(b, r, seat, action, space):
    decoded = space.decode_action(int(action), seat)
    if decoded.is_no_op:
        return None
    card = b.players[seat].hand[decoded.slot]
    pos = decoded.position
    pa = b.deploy_card(seat, card, pos)
    ra = r.apply_action(seat, card, pos.x, pos.y) if r is not None else pa
    row = [b.tick, seat, int(action), card, pos.x, pos.y, pa]
    assert pa == ra, ("accept", row, ra)
    return row


def recorded(b, rows, r=None):
    for a in rows:
        pa = b.deploy_card(a[1], a[3], Position(a[4], a[5]))
        assert pa == a[6], ("recorded accept", a)
        if r is not None:
            assert r.apply_action(a[1], a[3], a[4], a[5]) == pa
            assert same(b, r), ("recorded action", a)


def schedule(record):
    out = defaultdict(list)
    for a in record["actions"]:
        out[a[0]].append(a)
    return out


def run_game(ep, cfg, res, *, roots=False):
    builder, _, scripts, bots = res
    b = battle(ep, builder.loader)
    r = clasher_core.BattleState(snapshot(b, cfg))
    space = DiscreteTileActionSpace()
    actions = []
    checked = []
    decisions = 0
    pcpu = rcpu = 0.0
    limit = 1601 if roots else 6001
    for t in range(limit):
        if b.game_over:
            break
        if roots and t >= 100 and t % 100 == 0:
            for seat in (0, 1):
                result = verify(b, r, builder, scripts, bots, seat)
                if not result["ok"]:
                    return result, b, r
            checked.append(dict(tick=t, digest=battle_digest(b), seats=2, styles=3))
        if t >= 90 and t % 5 == 0:
            packets = [builder.build_public(b, seat) for seat in (0, 1)]
            expected = [
                bots[ep["styles"][seat]].select_action(packets[seat]) for seat in (0, 1)
            ]
            if roots:
                choices = expected
            else:
                choices = [
                    scripts.select_action(r, seat, ep["styles"][seat])
                    for seat in (0, 1)
                ]
                if choices != expected:
                    for seat in (0, 1):
                        if choices[seat] != expected[seat]:
                            result = verify(b, r, builder, scripts, bots, seat)
                            return (
                                dict(
                                    result,
                                    ok=False,
                                    kind="controller_action",
                                    expected_choices=expected,
                                    actual_choices=choices,
                                ),
                                b,
                                r,
                            )
                decisions += 2
            for seat, action in enumerate(choices):
                mask = bots[ep["styles"][seat]].mask_builder.build(
                    PublicActionMaskInput.from_confidence_observation(packets[seat])
                )
                assert action != 2305 and mask[action]
                row = play(b, r, seat, action, space)
                if row is not None:
                    actions.append(row)
                if not same(b, r):
                    return failure(b, r, kind="action"), b, r
        start = time.process_time()
        b.step()
        pcpu += time.process_time() - start
        start = time.process_time()
        r.step()
        rcpu += time.process_time() - start
        if not same(b, r):
            return failure(b, r, kind="tick"), b, r
    return (
        dict(
            ok=True,
            episode=ep,
            ticks=b.tick,
            terminal=b.game_over,
            actions=actions,
            accepted=sum(a[6] for a in actions),
            decisions=decisions,
            roots=checked,
            accepted_by_card={
                c: sum(a[6] for a in actions if a[3] == c)
                for c in sorted({a[3] for a in actions})
            },
            python_cpu=pcpu,
            rust_cpu=rcpu,
            digest=battle_digest(b),
        ),
        b,
        r,
    )


def run_imports(ep, record, cfg, res):
    builder, _, _, _ = res
    b = battle(ep, builder.loader)
    rows = schedule(record)
    times = set(
        random.Random(ep["seed"] ^ 610024).sample(range(90, record["ticks"]), 16)
    )
    results = []
    while not b.game_over:
        if b.tick in times:
            native = clasher_core.BattleState(snapshot(b, cfg))
            parent = battle_digest(b)
            if not same(b, native):
                return failure(b, native, kind="import"), b, native
            copy = b.clone()
            child = native.clone()
            start = time.process_time()
            for _ in range(100):
                clone = native.clone()
            clone_us = (time.process_time() - start) * 1e4
            del clone
            for _ in range(200):
                recorded(copy, rows[copy.tick], child)
                copy.step()
                child.step()
                if not same(copy, child):
                    return (
                        failure(
                            copy, child, kind="import_continuation", root_tick=b.tick
                        ),
                        copy,
                        child,
                    )
            assert parent == battle_digest(b) == native.digest(), "clone parent mutated"
            results.append(
                dict(
                    root_tick=b.tick,
                    ticks=200,
                    entities=len(b.entities),
                    clone_us=clone_us,
                    root_digest=parent,
                    end_digest=child.digest(),
                )
            )
        recorded(b, rows[b.tick])
        b.step()
    assert len(results) == 16 and battle_digest(b) == record["digest"]
    return dict(ok=True, roots=results), b, None


def placements_at(b, cfg, res, seat, *, pocket=False):
    builder, _, scripts, bots = res
    space = DiscreteTileActionSpace()
    native = clasher_core.BattleState(snapshot(b, cfg))
    result = verify(b, native, builder, scripts, bots, seat, actions=False)
    if not result["ok"]:
        return result, b, native
    packet = builder.build_public(b, seat)
    mask = bots["balanced"].mask_builder.build(
        PublicActionMaskInput.from_confidence_observation(packet)
    )
    parent = battle_digest(b)
    rng = random.Random(620056 + b.tick + seat)
    checks = []
    for slot, card in enumerate(b.players[seat].hand[:4]):
        if card is None:
            continue
        candidates = []
        for action in np.flatnonzero(mask[slot * 576 : (slot + 1) * 576]) + slot * 576:
            action = int(action)
            pos = space.decode_action(action, seat).position
            enemy_side = pos.y >= 15 if seat == 0 else pos.y < 17
            if pocket and (
                not enemy_side
                or cfg["cards"][card].get("spell")
                or cfg["cards"][card].get("anywhere")
            ):
                continue
            candidates.append(action)
        if not candidates:
            continue
        if pocket:
            chosen = rng.sample(candidates, min(40, len(candidates)))
        elif cfg["cards"][card].get("anywhere") or card == "GoblinBarrel":
            enemy = [
                a
                for a in candidates
                if (
                    (space.decode_action(a, seat).position.y >= 17)
                    if seat == 0
                    else (space.decode_action(a, seat).position.y < 15)
                )
            ]
            own = [a for a in candidates if a not in enemy]
            chosen = rng.sample(enemy, min(20, len(enemy))) + rng.sample(
                own, min(20, len(own))
            )
        else:
            chosen = rng.sample(candidates, min(40, len(candidates)))
        for action in chosen:
            copy = b.clone()
            child = native.clone()
            row = play(copy, child, seat, action, space)
            if not same(copy, child):
                return (
                    failure(copy, child, kind="placement_action", action=row),
                    copy,
                    child,
                )
            for _ in range(80):
                copy.step()
                child.step()
                if not same(copy, child):
                    return (
                        failure(copy, child, kind="placement_continuation", action=row),
                        copy,
                        child,
                    )
            assert parent == battle_digest(b) == native.digest()
            checks.append(
                dict(
                    action=action,
                    card=card,
                    seat=seat,
                    x=row[4],
                    y=row[5],
                    accepted=row[6],
                    pocket=pocket,
                    enemy_side=(row[5] >= 15 if seat == 0 else row[5] < 17),
                    end_digest=child.digest(),
                )
            )
    return dict(ok=True, placements=checks), b, native


def pocket_root(seat, episodes, games, builder, cfg, res):
    space = DiscreteTileActionSpace()
    masker = res[3]["balanced"].mask_builder
    for index, ep in enumerate(episodes):
        b = battle(ep, builder.loader)
        rows = schedule(games[str(index)])
        while not b.game_over:
            if b.tick >= 90 and b.tick % 5 == 0 and b.get_crown_count(seat) > 0:
                packet = builder.build_public(b, seat)
                mask = masker.build(
                    PublicActionMaskInput.from_confidence_observation(packet)
                )
                for a in np.flatnonzero(mask[:2304]):
                    choice = space.decode_action(int(a), seat)
                    card = b.players[seat].hand[choice.slot]
                    enemy_side = (
                        choice.position.y >= 15 if seat == 0 else choice.position.y < 17
                    )
                    if (
                        enemy_side
                        and not cfg["cards"][card].get("spell")
                        and not cfg["cards"][card].get("anywhere")
                    ):
                        return b, index
            recorded(b, rows[b.tick])
            b.step()
    raise AssertionError(f"no real pocket root for seat {seat}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("roots", "games", "imports", "placements"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--games-receipt", type=Path)
    parser.add_argument("--case", type=int)
    args = parser.parse_args()
    plan = json.loads(PLAN.read_text())
    episodes = plan["episodes"]
    for name, digest in plan["sources"].items():
        assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == digest
    identity = fingerprint()
    plan_sha = hashlib.sha256(PLAN.read_bytes()).hexdigest()
    out = dict(mode=args.mode, fingerprint=identity, plan_sha256=plan_sha, results={})
    if args.output.exists():
        previous = json.loads(args.output.read_text())
        assert all(
            previous.get(k) == out[k] for k in ("mode", "fingerprint", "plan_sha256")
        ), "use a new output for changed inputs"
        out = previous
    res = resources()
    cfg = config(CARDS)
    games = None
    if args.mode in ("imports", "placements"):
        assert args.games_receipt is not None
        source = json.loads(args.games_receipt.read_text())
        assert source["fingerprint"] == identity and source["plan_sha256"] == plan_sha
        games = source["results"]
        assert len(games) == 64 and all(
            r["ok"] and r["terminal"] for r in games.values()
        )
    indices = (
        range(0, 64, 4)
        if args.mode == "roots"
        else range(16)
        if args.mode == "placements"
        else range(64)
    )
    if args.case is not None:
        indices = [args.case]
    for index in indices:
        key = str(index)
        if out["results"].get(key, {}).get("ok"):
            continue
        if args.mode in ("roots", "games"):
            result, b, native = run_game(
                episodes[index], cfg, res, roots=args.mode == "roots"
            )
        elif args.mode == "imports":
            result, b, native = run_imports(episodes[index], games[key], cfg, res)
        else:
            if index < 14:
                deck = list(CARDS[index * 4 : index * 4 + 4]) + list(
                    CARDS[((index + 1) % 14) * 4 : ((index + 1) % 14) * 4 + 4]
                )
                b = battle(dict(seed=630056 + index, decks=[deck, deck]), res[0].loader)
                for player in b.players:
                    player.elixir = 10
                result = dict(ok=True, placements=[])
                native = None
                for seat in (0, 1):
                    r, p, n = placements_at(b, cfg, res, seat)
                    if not r["ok"]:
                        result, b, native = r, p, n
                        break
                    result["placements"] += r["placements"]
            else:
                seat = index - 14
                b, source_case = pocket_root(seat, episodes, games, res[0], cfg, res)
                result, b, native = placements_at(b, cfg, res, seat, pocket=True)
                result["source_case"] = source_case
                if result["ok"]:
                    assert result["placements"]
        assert (
            fingerprint() == identity
            and hashlib.sha256(PLAN.read_bytes()).hexdigest() == plan_sha
        ), "input drift during gate"
        if not result["ok"]:
            path = args.output.with_name(
                args.output.stem + f".case{index}.tick{b.tick}.pkl"
            )
            path.write_bytes(cloudpickle.dumps(b, protocol=pickle.HIGHEST_PROTOCOL))
            result["root_pickle"] = str(path)
            if native is not None:
                result["native"] = json.loads(native.snapshot())
        out["results"][key] = result
        tmp = args.output.with_suffix(".tmp")
        tmp.write_text(json.dumps(out, indent=2) + "\n")
        tmp.replace(args.output)
        print(
            index,
            {
                k: v
                for k, v in result.items()
                if k
                not in (
                    "actions",
                    "roots",
                    "placements",
                    "python",
                    "rust",
                    "native",
                    "field_diff",
                    "episode",
                )
            },
            flush=True,
        )
        if not result["ok"]:
            raise SystemExit(1)
    rows = list(out["results"].values())
    if args.case is None:
        if args.mode == "roots":
            assert sum(len(r["roots"]) for r in rows) >= 200
        if args.mode == "games":
            assert len(rows) == 64 and all(r["terminal"] for r in rows)
        if args.mode == "imports":
            assert sum(len(r["roots"]) for r in rows) >= 1000
        if args.mode == "placements":
            placements = [p for r in rows for p in r["placements"]]
            assert sum(p["accepted"] for p in placements) >= 4000
            assert all(
                any(
                    p["accepted"] and p["pocket"] and p["seat"] == seat
                    for p in placements
                )
                for seat in (0, 1)
            )
            assert all(
                any(
                    p["accepted"] and p["enemy_side"] and p["card"] == card
                    for p in placements
                )
                for card in ("Miner", "GoblinBarrel")
            )
    print("PASS", args.mode, len(rows), "cases", flush=True)


if __name__ == "__main__":
    main()
