"""Resumable, fail-fast Stage 2 differential. Never modifies the Python oracle."""

import argparse
from collections import deque
import hashlib
import json
from pathlib import Path
import time
import sys

import clasher_core
from clasher.paths import gamedata_path
from differential import (
    CARDS,
    ES,
    ROOT,
    Position,
    battle_digest,
    config,
    initial,
    snapshot,
)
from diagnostics import detail, phase_step


def fingerprint():
    # Vision is an independent concurrent task, outside this engine/controller
    # dependency graph. Fail closed if a future gate starts importing it.
    assert not any(
        name == "clasher.vision" or name.startswith("clasher.vision.")
        for name in sys.modules
    ), "vision dependency requires fingerprint requalification"
    reference = [
        p
        for p in ROOT.joinpath("src/clasher").rglob("*.py")
        if "vision" not in p.relative_to(ROOT / "src/clasher").parts[:1]
    ]
    paths = [
        *reference,
        *ROOT.joinpath("engine-rs/src").glob("*.rs"),
        *ROOT.joinpath("engine-rs").glob("*.py"),
        ROOT / "engine-rs/clasher_core.abi3.so",
    ]
    return hashlib.sha256(
        gamedata_path().read_bytes()
        + b"".join(
            str(p.relative_to(ROOT)).encode() + p.read_bytes() for p in sorted(paths)
        )
    ).hexdigest()


def focused_case(focus, case, cfg, ticks=2200, trace_tick=None):
    cards = (focus,) + tuple(c for c in CARDS if c != focus)
    b = initial(21000 + case, cards=cards)
    for p in b.players:
        # High-cost focused cards must actually enter play in this fixture.
        # Real-game gates retain the reference's ordinary starting elixir.
        p.elixir = max(p.elixir, cfg["cards"][focus]["cost"])
        p.deck = (list(cards) * 2)[:8]
        p.hand = list(cards[:4])
        p.cycle_queue = deque((list(cards) * 2)[4:8])
    r = clasher_core.BattleState(snapshot(b, cfg))
    actions = []
    coverage = dict(jump_ticks=0, stun_ticks=0, push_ticks=0, hidden_ticks=0)
    pcpu = rcpu = 0.0
    for t in range(trace_tick or ticks):
        if b.game_over:
            break
        if t % 80 == 0:
            for seat in (0, 1):
                p = b.players[seat]
                card = next(
                    (
                        c
                        for c in cards
                        if c in p.hand and p.elixir + 1e-9 >= cfg["cards"][c]["cost"]
                    ),
                    None,
                )
                if card:
                    x = (4.5, 13.5)[(t // 80 + seat + case) % 2]
                    if case >= 6:
                        x = (8.5, 9.5)[(t // 80 + seat + case) % 2]
                    # Keep troop fixtures unchanged; building footprints need deeper forward anchors.
                    y = (
                        (10.5 - case % 3 if seat == 0 else 21.5 + case % 3)
                        if cfg["cards"][focus]["footprint"] == 0
                        else (10.5 + case % 3 if seat == 0 else 21.5 - case % 3)
                    )
                    if cfg["cards"][card].get("spell") and not cfg["cards"][card][
                        "spell"
                    ].get("requires_territory"):
                        targets = [
                            e
                            for e in b.entities.values()
                            if e.player_id != seat
                            and e.is_alive
                            and type(e).__name__ == "Troop"
                        ]
                        if targets:
                            target = targets[(case + t // 80) % len(targets)]
                            x, y = target.position.x, target.position.y
                        else:
                            x, y = 3.5, 25.5 if seat == 0 else 6.5
                    pa = b.deploy_card(seat, card, Position(x, y))
                    ra = r.apply_action(seat, card, x, y)
                    actions.append([t, seat, card, x, y, pa, ra])
                    if pa != ra or battle_digest(b) != r.digest():
                        return dict(
                            ok=False,
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
        for field, attr in [
            ("jump_ticks", "_river_jump_active"),
            ("stun_ticks", "stun_timer"),
            ("push_ticks", "_knockback_target"),
            ("hidden_ticks", "_hidden_building"),
        ]:
            coverage[field] += any(
                bool(getattr(e, attr, False)) for e in b.entities.values()
            )
        words, index = r.rng_state()
        if (
            battle_digest(b) != r.digest()
            or tuple(words) + (index,) != b.rng.getstate()[1]
        ):
            return dict(
                ok=False, kind="tick", tick=b.tick, actions=actions, **detail(b, r)
            )
    return dict(
        ok=any(a[2] == focus and a[-1] for a in actions),
        focal_accepted=sum(a[2] == focus and a[-1] for a in actions),
        ticks=b.tick,
        game_over=b.game_over,
        python_cpu=pcpu,
        rust_cpu=rcpu,
        digest=battle_digest(b),
        coverage=coverage,
        actions=len(actions),
        accepted=sum(a[-1] for a in actions),
    )


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--cards", nargs="+", default=["Skeletons", "Goblins"])
    p.add_argument("--cases", type=int, default=6)
    p.add_argument("--case", type=int)
    p.add_argument("--ticks", type=int, default=2200)
    p.add_argument("--trace-tick", type=int)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    identity = fingerprint()
    cfg = config(tuple(dict.fromkeys((*CARDS, *args.cards))))
    out = dict(
        fingerprint=identity,
        cards=args.cards,
        ticks=args.ticks,
        cases=args.cases,
        results={},
    )
    if args.output.exists():
        old = json.loads(args.output.read_text())
        if all(
            old.get(k) == out[k] for k in ("fingerprint", "cards", "ticks", "cases")
        ):
            out = old
    for card in args.cards:
        for case in [args.case] if args.case is not None else range(args.cases):
            key = f"{card}-{case}"
            if out["results"].get(key, {}).get("ok") and not args.trace_tick:
                continue
            result = focused_case(card, case, cfg, args.ticks, args.trace_tick)
            out["results"][key] = result
            tmp = args.output.with_suffix(".tmp")
            tmp.write_text(json.dumps(out, indent=2) + "\n")
            tmp.replace(args.output)
            print(
                key,
                "phase trace saved"
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
    print("PASS", len(out["results"]), "focused cases", flush=True)


if __name__ == "__main__":
    main()
