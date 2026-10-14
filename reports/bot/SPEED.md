# Engine speed, single core, same workload (exploration)

Run 2026-10-14 ~03:20Z on 127x03 (Threadripper 3990X, 2.2–2.9 GHz). The host was idle: 0 console users and nothing
else of ours running. Each engine ran alone, pinned to core 100 (`taskset -c 100`, nice 5).

**Workload.** The same 24 T1 train fixtures for every engine: episodes 1975100723…752, the 20th–43rd train episodes.
- Each run uses the fixture's decks, initial hands and elixir.
- Every recorded card play is issued at its execution tick − 1. Abilities are skipped.
- The engine then steps one tick at a time to the recording's end or its own game end. Game end is checked every 50
  ticks, untimed.
- That is about 33–34k ticks per engine, 1,380–1,430 per fixture, since the recordings are windows of the battle.
- Timed: the stepping loop including deploy calls.
- For RoyaleSim each deploy also reads the hand from `state_json()`, as a bot would. That is 5–6% of its time.

**Clone cost.** Sampled at ticks 1000, 2000 and 3000, 50 repetitions each, reported as the median.
- Ours: the native `clone()`.
- RoyaleSim has no in-memory clone, so `save()` plus `load()` into a second Battle, its branching primitive.

| engine | ticks/s, 1 core [95% CI over fixtures] | step only | clone / branch | notes |
|---|---:|---:|---:|---|
| **Clasher Rust core** (`engine-rs`, built from origin/main dbf31faf) | **34,344** [30,086, 39,634] | 34,683 | **5.0 µs** (`clone()`) | C56 scope; 25 of 941 plays refused |
| Clasher Python reference | 521 [442, 631] | 529 | 1,776 µs (`BattleState.clone()`) | |
| RoyaleSim 0.1.34, default 16.402 rules | 30,804 [27,107, 35,702] | 32,750 | 5,184 µs (save 2,370 + load 2,821; 47 KB blob) | `state_json` + parse 45 µs |
| RoyaleSim 0.1.34, 15.535.29 rules (the faithful arm, see FIDELITY.md) | 14,203 [12,236, 16,761] | 14,941 | 4,986 µs (save 2,369 + load 2,611) | `state_json` + parse 93 µs |

## Reading

- **Raw stepping:** our Rust core and RoyaleSim's default rules are about equal (34k vs 31k ticks/s). RoyaleSim's
  15.535 rule set, the one that matched the native recordings best, runs at less than half that (14k). RoyaleSim
  publishes 16–20k on one loaded laptop core.
- **Branching:** search needs it, and here the gap is about 1,000×. Our Rust `clone()` costs 5 µs. RoyaleSim needs
  about 5 ms per save+load.
  - A search player that clones about 1,000 times per decision would spend about 5 s per decision on RoyaleSim
    clones alone, against about 5 ms on ours.
  - So RoyaleSim is fine for rollouts or self-play that step forward, but impractical as the *internal* model of a
    clone-heavy search unless we add a native clone. It's MIT-licensed, so adding one is possible.
- **Our Python reference** is ~520 ticks/s on this C56 workload, below the 1.3k measured earlier on P16. It's 66× slower
  than the Rust core.

## Caveats

- **Rust vs Python parity is not exact on C56.** On 1 of 24 fixtures (1975100725) the Rust core's game ended at a
  different tick (1000 vs 750). The Rust core's C56 parity gates (STAGE4) are still in progress for champions.
- One host, one core, one run. The CIs cover fixture-to-fixture variation, not machine noise.
- Throughput depends on board density; these windows mix early, double-elixir and overtime phases identically for all
  engines.

## Reproduce (127x03)

```
cd /mpac/sdicks02/repos/clasher-bot   # Rust core: /mpac/sdicks02/jobs/clasher/bot-speed/build.sh
for e in rsim15535 rsim16402 rs py; do
  PYTHONPATH=engine-rs:src:. taskset -c 100 nice -n 5 .venv/bin/python -B -m bot.speed.bench --engine $e \
    --episodes <24 episodes> --out OUT/bench-$e.json
done
.venv/bin/python -m bot.speed.summarize OUT
```

Raw results are in `/mpac/sdicks02/jobs/clasher/bot-speed/` on 03.
