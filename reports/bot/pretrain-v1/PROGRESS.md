# pretrain-v1 progress log

New single-model Clash Royale policy. Input: the live memory record plus causal history. Output: gate / slot /
tile / value, with the gate sampled. There is no decision-time search. Design:
`/mpac/sdicks02/scratch/new-pretrain-20261020/{DESIGN,PREREG-DRAFT,INVENTORY,FIDELITY}.md`. Engineering choices:
[DECISIONS.md](DECISIONS.md). Code: `bot/pretrain_v1/`. Data: `/mpac/sdicks02/datasets/pretrain-v1/` on 127x05
(copied to 127x08).

Constraints in force:
- Only 08's GPU is used.
- RL training on 04/08 keeps running.
- Hosts keep MemAvailable above 28 GiB and load at or below 90.
- No Mac or live changes, and no deployment.
- Code lands on main through fresh worktrees after GPT-6.1 Sol (high) review.

## 2026-10-21

- **12:00 PDT: inputs pinned.**
  - Deployed memory package, read-only from the Mac MEM-MANIFEST: `state.py` 9085e337, `rfextras.py` 513088f2,
    cards-122 289d240f. Local byte-identical copies are vendored.
  - Live runs use `spell_events=False`, so record `events` is always empty live.
  - Re-drive corpus at the time: 15.5k / 252k matches, 34 acked batches. Jobs with source coordinates are at
    `scratch/native-redrive-full-20261021/jobs/`.
- **Label-timing measurement** (300 matches, 19,394 executed plays). At E−27 the card is in hand 99.0% of the
  time and affordable 88.3%. Under DESIGN's strict mask, 12.6% of plays therefore cannot be lag-aligned (see
  DECISIONS item 12).
- **Piece 1, featurizer**, and **piece 2, dataset builder**, written.
  - 13 unit tests pass.
  - Smoke parity audit (6 matches): 9,638 polls where the serving path (`policy.Session`) equals builder bytes,
    and 0 violations in 9,638 private-mutation and 4,369 future-suffix cases.
  - Builder speed: 0.4 s per match per core, about 106k stored rows per 500-match batch.
  - Commit e001cf230 on branch `pretrain-v1/featurizer`; Sol review R1 requested.
- **Model**: 2,102,213 parameters. Untrained, single thread on 05 over a real live game: featurize + network +
  decode p50 4.9 ms, p95 6.1 ms.
- **12:15: v0 store and shakedown.** v0 store (pre-review, f0540f3e): 16,916 matches, 3.60M rows, 847,827 admitted
  plays (79.7% of 1,063,202 executed plays). BC v0 epoch 0 on 08 (4.5k rows/s, 12.5 GB VRAM), DEV:
  - joint NLL 0.350 against the frequency baseline's 0.408; Hog 0.477 against 0.553;
  - card top-1 51%, tile top-1 17%, tile within-one 34%;
  - gate ECE 0.003, plays ratio 1.07;
  - **Hog value NLL 3.05**: a few hundred oversampled Hog games' outcomes were memorised. The value loss is now
    importance-corrected (DECISIONS 23).

  v0 is superseded and was stopped.
- **12:20: Sol R1 = NO-GO** (`scratch/pretrain-v1-dev/review/SOL-R1.md`).
  - Blockers: opening-hand ambiguity, uncertain continuations, Mirror legality, split fingerprint ignoring the
    rotation.
  - Should-fix: live eligibility (tick-90 start, deciding record, stale tower, expiry), opponent cast counts.

  Fixed in f3f11f807 (`RESPONSE-R1.md`). #2 is handled per the coordinator's data rule plus an `unc` flag, recorded
  as a disagreement in DECISIONS 14.

  The stronger suffix mutation (it rewrites future source commands too) exposed a second-order leak: admission
  criteria had been gating `History.submit`. The channel is now emulated only from facts observable at d*. The audit
  is back to 0 violations, and 21 unit tests pass.
- **CPU latency** (05 Threadripper, untrained, batch 1, 20,000 polls of real live records):
  - 1 thread: p50 4.9 ms, p95 6.0 ms, p99 6.8 ms; dense p95 5.9 ms; cold 8.3 ms;
  - 4 threads: p95 4.8 ms, p99 5.2 ms.

  The featurizer is 0.17 ms of that. The Mac measurement is pending (no Mac access in this task).
- **Eval hooks built.**
  - (a) `sim_rsim.py` + `eval_rsim.py`: a RoyaleSim producer through the same FrameBuilder; the policy arm on the
    r2 paired bank (HOG26-acct, account levels) is paired against r2's sealed live-search (f1a2) rows. Smoke with an
    untrained model: 2 games, 42 commands, 0 rejections.
  - (b) `probe_roots.py`: the 453 defense groups and 957 spell opportunities, replayed through `observe` on the frozen
    c17/c18 recordings.
- **RL design** written ([RL-DESIGN.md](RL-DESIGN.md)); not launched.
- **12:35:** Sol R2 (re-review of pieces 1+2) and R3 (model / trainer / eval / RL design) requested in parallel.
  The v1 store `f-e2869e6dbb77-b-dafd672b` is being built (36 acked batches).
