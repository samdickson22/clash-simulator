import json, sys, math
from pathlib import Path
from bot.fidelity import run as R
from bot.fidelity.fixture import load_fixture, load_split
from bot.fidelity.score import pair_units
D = Path("/mpac/sdicks02/repos/clasher-bot-data")
R.C56_IDS.update(json.loads(Path("bot/fidelity/c56_native_ids.json").read_text()))
idn = {v: k for k, v in R.C56_IDS.items()}
fix = load_fixture(D / "t1-trainval" / sys.argv[1], load_split(D / "t1-split.json"))
want = sys.argv[2].split(",")
res = {}
for kind in ("clasher", "rsim15535"):
    eng = R.make_engine(kind, -1)
    sim, _ = R.replay(fix, eng)
    res[kind] = (sim, pair_units(fix.units, sim))
shown = 0
for tk, u in sorted(fix.units.items(), key=lambda kv: kv[1].first_tick):
    if u.tower_slot is not None or idn.get(u.root) not in want:
        continue
    print(f"--- truth {tk} {idn.get(u.root)} side {u.side} first {u.first_tick}")
    ticks = sorted(u.rows)[:: max(1, len(u.rows) // 14)][:14]
    for kind, (sim, pairs) in res.items():
        sk = next((s for t, s in pairs if t == tk), None)
        line = []
        for t in ticks:
            a = u.rows[t]; b = sim[sk].rows.get(t) if sk is not None else None
            line.append(f"{t}:{'-' if b is None else int(math.dist(a[:2], b[:2]))}/{a[2]-(b[2] if b else 0)}")
        print(f"  {kind:10s} sim_first {sim[sk].first_tick if sk is not None else None}  " + " ".join(line))
    print("  truth xy  " + " ".join(f"{t}:{u.rows[t][0]},{u.rows[t][1]}" for t in ticks[:6]))
    for kind, (sim, pairs) in res.items():
        sk = next((s for t, s in pairs if t == tk), None)
        if sk is not None:
            print(f"  {kind:10s}" + " ".join(f"{t}:{sim[sk].rows[t][0]},{sim[sk].rows[t][1]}" if t in sim[sk].rows else f"{t}:-" for t in ticks[:6]))
    shown += 1
    if shown >= int(sys.argv[3]):
        break
