import json, sys
from pathlib import Path
from bot.fidelity import run as R
from bot.fidelity.fixture import load_fixture, load_split
D = Path("/mpac/sdicks02/repos/clasher-bot-data")
R.C56_IDS.update(json.loads(Path("bot/fidelity/c56_native_ids.json").read_text()))
fix = load_fixture(D / "t1-trainval" / sys.argv[2], load_split(D / "t1-split.json"))
eng = R.make_engine(sys.argv[1], 0)
sim, dlog = R.replay(fix, eng)
print("end tick", eng.tick, "fixture end", fix.end_tick, "plays", len(fix.plays), dlog)
b = getattr(eng, "b", None)
if hasattr(b, "game_over"):
    print("game_over", b.game_over, "winner", getattr(b, "winner", None), [ (p.king_tower_hp, p.left_tower_hp, p.right_tower_hp) for p in b.players])
# truth tower hp at end
tw = {(u.side,u.tower_slot): u for u in fix.units.values() if u.tower_slot is not None}
for k,u in sorted(tw.items()): print("truth tower", k, "last tick", max(u.rows), u.rows[max(u.rows)])
from collections import Counter
cut = int(sys.argv[3]) if len(sys.argv) > 3 else 3900
idn = {v: k for k, v in R.C56_IDS.items()}
tc = Counter((u.side, idn.get(u.root, u.root)) for u in fix.units.values() if u.tower_slot is None and u.first_tick < cut)
sc = Counter((u.side, idn.get(u.root, u.root)) for u in sim.values() if u.tower_slot is None and u.first_tick < cut)
for k in sorted(set(tc) | set(sc), key=str): print(k, "truth", tc[k], "sim", sc[k])
pc = Counter((p.side, p.card) for p in fix.plays if p.exec_tick < cut)
print("plays", sorted(pc.items()))
