"""Per-tick native replay of a recorded reference branch on emulator-5582 (port 26790) only.
Replays the recorded prefix and the recorded branch command stream; no controllers, no ledger."""
import gzip, json, sys, socket, hashlib
from pathlib import Path
PORT = int(sys.argv.pop(1)); V = int(sys.argv.pop(1))
assert PORT in range(26791, 26797)
SNAP = Path("/Users/sam/Desktop/code/clasher/reports/strategy_council_20260928/m0/runtime-snapshots/native-final-v6")
sys.path[:0] = [str(SNAP / "src"), str(SNAP / "scripts")]
from clasher.rl.readiness_execution import ExecutionPlan, canonical_sha
ATT = Path(f"/Users/sam/Desktop/code/clasher/reports/strategy_council_20260928/m0/readiness/tier-a-fresh-v{V}")
def call(cmd):
    assert PORT in range(26791, 26797)
    with socket.create_connection(("127.0.0.1", PORT), timeout=60) as c:
        c.sendall((cmd + "\n").encode()); buf = bytearray()
        while ch := c.recv(1 << 16): buf.extend(ch)
    r = json.loads(buf)
    if not r.get("ok"): raise ValueError(r)
    return r
job_dir = Path(sys.argv[1]); out = Path(sys.argv[2]); t_from = int(sys.argv[3]); t_to = int(sys.argv[4])
rich_ticks = set()
if len(sys.argv) > 5:
    for part in sys.argv[5].split(","):
        a, b = part.split("-"); rich_ticks |= set(range(int(a), int(b) + 1))
plan = ExecutionPlan.model_validate_json((ATT / "branch-plan.json").read_text())
claim = json.loads((job_dir / "claim.json").read_text())
binding = next(c for c in plan.captures if c.family_id == claim["family_id"])
capture = Path(binding.capture_path)
assert canonical_sha(call("attest")) == plan.native_attestation_sha256, "attestation mismatch"
st = call("status"); assert st["paused"] and st["ready"]
config = json.loads((capture / "plan.json").read_text())["config"]
initial = json.loads((capture / "initial.json").read_text())
source = json.loads((capture / "result.json").read_text())
call("configure " + json.dumps(config, separators=(",", ":")))
cur = call("observe")
assert all(cur[k] == initial[k] for k in ("objects", "players", "tick"))
cards = {}
from clasher.data import CardDataLoader
loader = CardDataLoader(capture / "gamedata.json")
def step_to(t):
    cur = call("observe")
    if t > cur["tick"] and not cur["ended"]:
        call(f"step {t - cur['tick']}")
prefix = [c for c in source["commands"] if c["submitted_tick"] < binding.root_tick]
for c in prefix:
    step_to(c["submitted_tick"])
    call(f"replay-schedule-card {c['owner']} {loader.get_card(c['name'])._raw_entry['id']} {round(c['xy'][0]*1000)} {round(c['xy'][1]*1000)} {c['submitted_tick']+1}")
step_to(binding.root_tick)
branch = [json.loads(l) for l in gzip.open(job_dir / "transport.jsonl.gz")]
sched = {}
for rec in branch:
    if rec["commands"]: sched[rec["tick"]] = rec["commands"]
recorded = {json.loads(l)["tick"]: json.loads(l) for l in gzip.open(job_dir / "decisions.jsonl.gz")}
out.mkdir(parents=True, exist_ok=True)
mism = []
with gzip.open(out / "native_ticks.jsonl.gz", "wt") as f:
    tick = binding.root_tick
    while tick <= t_to:
        obs = call("observe")
        assert obs["tick"] == tick
        if tick in recorded:
            ro = recorded[tick]["native_frame"]["ordinary"]
            if ro["objects"] != obs["objects"]:
                mism.append(tick)
        if tick >= t_from:
            rec = {"tick": tick, "ordinary": obs}
            if tick in rich_ticks:
                rec["rich"] = call("observe-rich")
            f.write(json.dumps(rec) + "\n")
        for cmd in sched.get(tick, []):
            call(cmd)
        call("step 1"); tick += 1
print(json.dumps({"mismatched_recorded_frames": mism[:20], "n_mismatch": len(mism)}))
