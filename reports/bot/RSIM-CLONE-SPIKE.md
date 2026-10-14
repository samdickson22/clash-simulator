# Spike: in-memory clone for RoyaleSim (exploration)

2026-10-14, about 1 h, BOT LEAD. The coordinator asked whether a faithful engine can serve as the search model.

## Result

**Yes, cloning is feasible at about 10 µs, and it's exact.**

| | median | max | n |
|---|---:|---:|---:|
| `restore_from(other)`: copy a battle's state into an existing Battle | **9.8 µs** | — | 24 states |
| `clone()`: new Python Battle object | 38.7 µs | 42.3 µs | 24 states |
| stock `save()` + `load()` (for comparison) | 4,778 µs | — | 24 states |
| our Rust core `clone()` (SPEED.md) | 5.0 µs | — | — |

- **States tested:** 24 mid-battle states, at 1/3 and 2/3 through 12 train fixtures of ≥3,000 ticks, on the 15.535.29
  arm. Measured on 127x04, idle and pinned to one core.
- **Determinism:** a clone stepped with the same remaining script matched the original's `state_hash()` on **14,400
  of 14,400 ticks** (24 × 600). It also matched a fresh replay from scratch (24/24). Stepping a clone left the
  original untouched (24/24).
- **No physics change:** the fork reproduces the PyPI 0.1.34 wheel's fidelity results **byte-for-byte on all 577
  fixtures** (15.535 arm; only the timing field excluded).
- **Why `clone()` costs 39 µs:** it also copies the wrapper's per-object tables (the unit-type name list and the
  calibration). Moving those behind an `Arc` would bring it to about `restore_from`'s 10 µs. For search,
  `restore_from` into a reusable scratch battle is the natural primitive anyway.

## What the patch is

`bot/rsim_fork/patch_clone.py` applies 20 lines to `crates/royalesim/src/py.rs` of RoyaleGym/RoyaleSim at
`ffe0d27` (the 0.1.34 release, MIT):
- `#[derive(Clone)]` on the PyO3 `Battle` wrapper;
- `clone()`;
- `restore_from(other)`.

No unsafe code was needed. `BattleState` already derives `Clone`, the card table is shared through an `Arc`, the RNG
lives in the state, and the only `RefCell`s are function-local or thread-local profiling.

**Build caveat:** the derived data tables are gitignored upstream.
- I staged them locally from the installed 0.1.34 wheel's `royalesim/data/`, on 03 and 04 only. They are not
  committed and not redistributed.
- The wheel carries no JSON for the 16.402 card table, so the fork's `cards-160402017` include was pointed at the
  15.535 table. **The fork's 16.402 mode is therefore not valid.** Use PyPI 0.1.34 for 16.402, or obtain that table
  properly.

Attribution: RoyaleSim © its authors, MIT license. Any fork we keep retains `LICENSE` and the upstream history.

## What it doesn't solve

Our search player's internal model is more than clone+step. Per `reports/bot/inventory/INVENTORY.md` §3, each
rollout calls `NativeScripts.rollout_e1`, which runs **both sides' scripted rollout policies and the leaf scorer
inside our Rust engine**. Planning on RoyaleSim therefore also needs those policies and the scorer on RoyaleSim.
There are two ways:
- port them to Python driving RoyaleSim, which is simple but costs Python per decision point (`state_json` + parse
  45–93 µs);
- implement them in Rust inside the fork, which is fast but takes days.

RoyaleSim's 15.535 arm also steps at 14k ticks/s against our core's 34k. So a RoyaleSim-native planner would be
roughly 3–10× slower per decision until it's optimized.

## Reproduce

```
# 127x03: fork + build
git clone https://github.com/RoyaleGym/RoyaleSim.git fork && git -C fork checkout ffe0d27
python bot/rsim_fork/patch_clone.py fork
#   stage data/derived/*.json, data/raw/retroroyale-2018/csv_logic/*.csv from the 0.1.34 wheel; point card.rs:88 at cards-15.535.json
maturin build --release --no-default-features    # /mpac/sdicks02/jobs/clasher/bot-speed/build_rsimfork.sh
# 127x04
PYTHONPATH=REPO forkvenv/bin/python -m bot.rsim_fork.clone_test --episodes <12 episodes>
```

The wheel and venv are at `/mpac/sdicks02/repos/clasher-bot-rsim/{dist,forkvenv}` on 04 (dist also on 03). Results
are in `/mpac/sdicks02/jobs/clasher/bot-rsimfork/` on 04.
