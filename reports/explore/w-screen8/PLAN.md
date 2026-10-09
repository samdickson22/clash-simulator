# Frozen W-screen8 outcome plan

Config SHA256: `f044f822bc3d13912e19ce61b065d35d8995d94232cd91b94bd04782421ec126`. Commit and push this plan and config before any game, including smoke.

600 fresh paired seeds 4503599677370496–4503599677371095. Three arms on identical seeds: baseline vs baseline (0), full W vs baseline (W), screen8 W vs baseline (S8). Symmetric physical/hypothetical d=27; capacity one; five train decks / all 25 matchups; alternating seats; shuffled decks matched across arms. 1,800 terminal games. No reporting-seed tuning, dropped games, replacement seeds or early outcome stopping. Smoke uses two separate seeds. Audit all prior exploration ranges/inventories and helper offsets before games.

W appends 10/20/40-tick WAITs; nonterminal prior 0.01 × sqrt(wait_ticks/20) × max(0,1-own_elixir/10). Screen8 scans every play with balanced style, fully refines top eight, fully scores all WAITs, exactly reuses original WAIT for 10-tick WAIT. Preserve sequential score accumulation, candidate order and epsilon ties. Horizon 160, interval 10, 16 samples, three styles. Same build48/private native WAIT engine as w-confirm. Fair inputs: public board, own HUD, accepted enemy events, sampled hidden model/RNG independent of physical opponent.

**Pass criterion:** paired 95% CI upper bound for screen8 minus full-W loss change ≤ +3 percentage points. Shared 5,000 paired-seed percentile bootstrap resamples for loss rates, contrasts and pooled loss-review metrics. Report wins/losses/draws, under-4 arrivals, defender availability, cap time/leak, rejected plays, expensive-card affordability/use, full-decision wall/CPU p50/p95/p99 and >200 ms fraction. Loaded idle game timings are descriptive, not live deadline admission.

Production flag `wait_screen8` defaults OFF. OFF delegates unchanged S6. Verify fixed-state score/action parity and exact ON decisions against symmetric w-confirm screen8 on existing 125-state corpus. Build at a fresh versioned path; never replace deployed libraries. Provide exact wiring patch for prohibited files where timed-WAIT suppression requires it.

Compute 127x03 only, CPU, detached setsid, nice 10 / SCHED_IDLE, ≤60 combined Clasher processes. Cache/raw logs under /mpac. Keep PROGRESS current; explicit own-path staging after secret scan.
