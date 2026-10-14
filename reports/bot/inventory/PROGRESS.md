# Bot inventory: progress (resumable)

Owner: the bot-lead research sub-agent. Writable scope: `bot/players/` and `reports/bot/inventory/` only. No commits and no pushes.

## 2026-10-13 (127x05)

### Research
I read the X4S/X4S2/X4S3/X4S3b, K-anytime, K-v2, K2, S1, W-screen8 and exit-r3 results. I traced the harness (`x4s/run.py`) and the full planner class stack down to the native `rollout_e1`.

### Runtime
I found a complete runtime on 05: R = `/mpac/sdicks02/jobs/clasher/e4v3-20261010-r1`, read-only. Its native, v1 and R3a SHAs match the X4S pins. The untracked loss_review modules there are byte-identical to the main checkout's.

### Environment
- `uv sync` in `clasher-bot` gave `.venv` with Python 3.12.12, torch 2.10.0+cu128 and numpy 2.3.5.
- **Caveat:** the base interpreter lives under the `e4-guard-race-fix-20261012` job directory.

### Checkpoints
- **127x01:** `x4s3b-fitseed-20261013/inputs` holds main02, R3a, R3a-rep/-rep2/-rep3 and R4-D. I computed their SHA-256s with read-only `ssh` + `sha256sum` under nice.
- **127x04:** `clasher-checkpoints/v2` has no main-2026100802.

### Implemented `bot/players/`
| File | Contents |
|---|---|
| `runtime.py` | Bootstrap and pin checks |
| `base.py` | Interface |
| `policy.py` | v1 and R3a players |
| `search.py` | K4/K4S/KU/budget search |
| `ours.py` | Match loop and `x4s_setup` |
| `smoke.py`, `run.sh` | Smoke test and launcher |
| `royalesim_adapter.py` | Sketch: card map and action→command conversion verified |

### Smoke
- One 1,200-tick match, K4S-b48 vs v1: rc 0, 29 s CPU.
- Equivalence 3/3: the budget run reproduced the unbounded choice.
- A repeat gave the identical command hash `b6e0d3e0…`, so the run is deterministic.
- Receipts: `smoke-b48-1200.json`, `smoke-b48-1200-repeat.json`.
- Total CPU used on 05 is about 80 s, including a 200-tick wiring test.

### RoyaleSim
- I installed royalesim 0.1.34 in a scratch venv at `/mpac/sdicks02/cache/botinv-royalesim-venv`.
- All 25 X4S matchups construct.
- 53 of 56 C56 names are identical; 3 are renamed.

### Deliverable
[INVENTORY.md](INVENTORY.md), sections 1–5.

## Next (for the lead)
1. Copy R into a bot-owned runtime (rsync command in INVENTORY §5 caveats) and set `CLASHER_BOT_RUNTIME`.
2. Re-create `.venv` on a managed interpreter.
3. Calibrate budget N against the X4S cutoff rates (INVENTORY §2). Then run a ~200-seed paired check of `unbounded` vs v1 on a fresh seed bank, on a fleet host (03/04) rather than 05.
4. Write the RoyaleSim public-view translator, work item R2 in INVENTORY §4. Then do the R4 validation: v1-vs-v1 and KU-vs-v1 in RoyaleSim, paired with our engine.
