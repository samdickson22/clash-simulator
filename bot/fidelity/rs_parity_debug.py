"""Step a fixture in Python and Rust to TICK and print entities near (X, Y) on both sides.

    PYTHONPATH=engine-rs:src:. python -m bot.fidelity.rs_parity_debug EP TICK X Y [R]
"""
import json, sys
from bot.fidelity import rs_parity as P


def main():
    import clasher_core
    from differential import battle_digest, config, snapshot
    from bot.fidelity.fixture import load_fixture, load_split
    from clasher.arena import Position
    ep, tick, x, y = sys.argv[1], int(sys.argv[2]), float(sys.argv[3]), float(sys.argv[4])
    rad = float(sys.argv[5]) if len(sys.argv) > 5 else 3.0
    fix = load_fixture(P.D / "t1-trainval" / ep, load_split(P.D / "t1-split.json"))
    b = P._py_battle(fix)
    cards = tuple(sorted({P._name(P.ID2N[i]) for s in (0, 1) for i in fix.initial_order[s]}))
    r = clasher_core.BattleState(snapshot(b, config(cards)))
    plays = sorted((p for p in fix.plays if p.kind != "champion ability"), key=lambda p: (p.exec_tick, p.side, p.slot))
    pi = 0
    while b.tick < tick:
        t = b.tick
        while pi < len(plays) and plays[pi].exec_tick - 1 <= t:
            p = plays[pi]
            b.deploy_card(p.side, P._name(p.card), Position(*p.tile))
            r.apply_action(p.side, P._name(p.card), p.tile[0], p.tile[1])
            if t >= tick - 40:
                print("play", t, p.side, p.card, p.tile)
            pi += 1
        b.step(); r.step()
        if b.tick >= tick - 3:
            print("tick", b.tick, "digest equal", battle_digest(b) == r.digest())
            print("  PY:", sorted((k, v) for k, v in P._py_entities(b).items() if abs(v[1] - x) < rad and abs(v[2] - y) < rad))
            rs = json.loads(r.snapshot())["entities"]
            print("  RS:", sorted((e["id"], e["owner"], round(e["x"], 3), round(e["y"], 3), e["hp"], e["class"], e.get("target"))
                                  for e in rs if abs(e["x"] - x) < rad and abs(e["y"] - y) < rad))


if __name__ == "__main__":
    main()
