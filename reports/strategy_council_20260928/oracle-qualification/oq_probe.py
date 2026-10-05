"""Debug probe: play the first N ticks of one game with a planner and print its actions."""
import json, sys
import oq_lib
from clasher.rl.common import NUM_TILES

name, role, style, game, max_tick = sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4]), int(sys.argv[5])
cfg = json.loads((oq_lib.OQ_DIR / "batches.json").read_text())["players"][name]
ctx = oq_lib.Context()
ctx.max_ticks = max_tick
for envs in (ctx.envs(role, 0),):
    for env in envs.values():
        env.max_ticks = max_tick
spec = {"role": role, "opponent": style, "seed": oq_lib.PILOT_CELL_SEEDS[(role, style)], "game": game, "player": {"name": name, **cfg}}
orig = oq_lib.SelfPlayBattleEnv.step
def step(self, actions, **kw):
    b = self.battle; cp = game % 2
    for pid, a in actions.items():
        if a != self.action_space.no_op_action:
            sel = self.action_space.decode_action(a, pid)
            hand = b.players[pid].hand
            print(file=sys.__stdout__, end="", flush=True) or print(file=sys.__stdout__, *[f"t={b.tick:5d} {'ME ' if pid == cp else 'opp'} {hand[sel.slot]:10s} at ({sel.position.x:.1f},{sel.position.y:.1f}) elixir={b.players[pid].elixir:.1f}"])
    return orig(self, actions, **kw)
oq_lib.SelfPlayBattleEnv.step = step
try:
    out = oq_lib.play_game(ctx, spec)
except RuntimeError as e:
    print("stopped:", e)
env = ctx.envs(role, 0)[game % 2]
b = env.battle
print("towers p0", b.players[0].left_tower_hp, b.players[0].right_tower_hp, b.players[0].king_tower_hp, "p1", b.players[1].left_tower_hp, b.players[1].right_tower_hp, b.players[1].king_tower_hp, "candidate seat", game % 2)
