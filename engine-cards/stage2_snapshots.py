"""Random live imports, clone isolation and 200-tick recorded-action continuations."""

import argparse
from collections import defaultdict, Counter
import json
from pathlib import Path
import random
import time

import clasher_core
from differential import ES, Position, config, snapshot, battle_digest
from diagnostics import detail
from stage2 import fingerprint
from stage2_matches import PILOT, battle
from clasher.data import CardDataLoader

GAMES = ES / "results/stage2_matches_r11.json"


def apply_recorded(b, r, actions):
    for a in actions:
        pa = b.deploy_card(a[1], a[3], Position(a[4], a[5]))
        ra = r.apply_action(a[1], a[3], a[4], a[5])
        if pa != ra or pa != a[6] or battle_digest(b) != r.digest():
            return a
    return None


def verify(root, cfg, schedule, after_actions):
    encoded = snapshot(root, cfg)
    r = clasher_core.BattleState(encoded)
    parent = battle_digest(root)
    if r.digest() != parent:
        return dict(
            ok=False, kind="import", input=json.loads(encoded), **detail(root, r)
        )
    pb, rb = root.clone(), r.clone()
    start = time.process_time()
    for _ in range(100):
        clone = r.clone()
    clone_us = (time.process_time() - start) * 10000
    count = 0
    for offset in range(200):
        t = root.tick + offset
        actions = [] if offset == 0 and after_actions else schedule[t]
        bad = apply_recorded(pb, rb, actions)
        count += len(actions)
        if bad:
            return dict(
                ok=False,
                kind="action",
                tick=t,
                action=bad,
                input=json.loads(encoded),
                **detail(pb, rb),
            )
        pb.step()
        rb.step()
        words, index = rb.rng_state()
        if (
            battle_digest(pb) != rb.digest()
            or tuple(words) + (index,) != pb.rng.getstate()[1]
        ):
            return dict(
                ok=False,
                kind="tick",
                tick=pb.tick,
                offset=offset + 1,
                input=json.loads(encoded),
                **detail(pb, rb),
            )
    assert battle_digest(root) == r.digest() == parent, "clone changed its parent"
    return dict(
        ok=True,
        ticks=200,
        root_tick=root.tick,
        after_actions=after_actions,
        actions=count,
        root_digest=parent,
        end_digest=battle_digest(pb),
        entities=len(root.entities),
        classes=dict(Counter(type(e).__name__ for e in root.entities.values())),
        clone_us=clone_us,
    )


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--games-receipt", type=Path, default=GAMES)
    p.add_argument("--games", type=int, default=64)
    p.add_argument("--roots-per-game", type=int, default=32)
    p.add_argument("--case", type=int)
    p.add_argument("--root-tick", type=int)
    args = p.parse_args()
    games = json.loads(args.games_receipt.read_text())["results"]
    cfg = config(PILOT)
    loader = CardDataLoader()
    identity = fingerprint()
    out = dict(fingerprint=identity, roots_per_game=args.roots_per_game, results={})
    if args.output.exists():
        old = json.loads(args.output.read_text())
        if (
            old.get("fingerprint") == identity
            and old.get("roots_per_game") == args.roots_per_game
        ):
            out = old
    for case in [args.case] if args.case is not None else range(args.games):
        record = games[str(case)]
        b = battle(record["episode"], loader)
        schedule = defaultdict(list)
        for a in record["actions"]:
            schedule[a[0]].append(a)
        randomizer = random.Random(94000 + case)
        selected = sorted(
            randomizer.sample(range(90, record["ticks"] - 200), args.roots_per_game)
        )
        if args.root_tick is not None:
            selected = [args.root_tick]
        phases = {
            t: bool(random.Random(95000 + case * 6001 + t).getrandbits(1))
            for t in selected
        }
        checked = 0
        for t in range(record["ticks"]):
            if t in phases and not phases[t]:
                root = b.clone()
            for a in schedule[t]:
                assert b.deploy_card(a[1], a[3], Position(a[4], a[5])) == a[6], (
                    case,
                    t,
                    a,
                )
            if t in phases:
                if phases[t]:
                    root = b.clone()
                key = f"{case}-{t}"
                if not out["results"].get(key, {}).get("ok"):
                    result = verify(root, cfg, schedule, phases[t])
                    result.update(root_tick=t, after_actions=phases[t])
                    out["results"][key] = result
                    temp = args.output.with_suffix(".tmp")
                    temp.write_text(json.dumps(out, indent=2) + "\n")
                    temp.replace(args.output)
                    if not result["ok"]:
                        print(
                            "FAIL",
                            key,
                            {
                                k: v
                                for k, v in result.items()
                                if k not in ("python", "rust", "field_diff", "input")
                            },
                            flush=True,
                        )
                        raise SystemExit(1)
                checked += 1
            b.step()
        assert battle_digest(b) == record["digest"], (
            f"Python replay changed: game{case}"
        )
        print("PASS game", case, "roots", checked, flush=True)
    values = list(out["results"].values())
    out["summary"] = dict(
        imports=len(values),
        ticks=sum(v["ticks"] for v in values),
        max_clone_us=max(v["clone_us"] for v in values),
        clone_gate=all(v["clone_us"] < 20 for v in values),
    )
    temp = args.output.with_suffix(".tmp")
    temp.write_text(json.dumps(out, indent=2) + "\n")
    temp.replace(args.output)
    assert out["summary"]["clone_gate"], "clone speed gate failed"
    print(
        "PASS",
        len(values),
        "imports",
        sum(v["ticks"] for v in values),
        "ticks",
        "max clone us",
        max(v["clone_us"] for v in values),
        flush=True,
    )


if __name__ == "__main__":
    main()
