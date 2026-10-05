# Ten-hour Clasher campaign — GH200

## Funding and machine

Prime CLI availability on 2026-08-26 lists:

- GH200 96 GB, 64 vCPU, 432 GB RAM, 4 TB disk: **$2.29/hour**;
- H100 80 GB, 26 vCPU: $4.29/hour;
- H200 141 GB, 16 vCPU: $4.50/hour.

Use the GH200. The workload is CPU-heavy and the repository already contains a
matched six-worker GH200 saturation result: six semantic games in 150.545
seconds, approximately 143.48 aggregate games/hour. The current Prime wallet is
-$0.39. Add **$30**. Ten full hours cost $22.90 at the currently listed rate;
the remaining balance is safety margin, not permission to leave an idle pod.

Hard rules:

1. re-query availability and price immediately before creation;
2. refuse a price above $2.50/hour without a new decision;
3. use one GH200 and no paid detached disk;
4. publish hash-valid completion markers continuously;
5. copy completed artifacts off during the run, not only at the end;
6. terminate immediately on completion, fatal gate failure, or the ten-hour
   wall deadline;
7. never keep the pod alive merely because prepaid balance remains.

## Schedule

### 00:00–00:20 — provision and smoke

- Create the one-GH200 pod and verify 64 vCPU, 96 GB CUDA memory, free disk,
  pinned repository state, model-weight hashes, ffmpeg, yt-dlp, and clock tool.
- Run one untouched replay through acquisition, semantic extraction, deck-sheet
  generation, portable clock, public mask, and strict verifier.
- Require exact completion/hash contracts and no regression against the pinned
  detector digest. Fail closed and terminate if the smoke fails twice for the
  same reason.

### 00:20–01:50 — 128-replay production wave

- Two conservative acquisition workers; six semantic workers on the one GPU.
- Current scripts use `CLASHER_GPU_COUNT=1`, preventing the old two-GPU modulo
  bug, and generate 32-cluster galleries, lossless eight-card sheets, candidate
  classifications, and raw event streams.
- Stop scaling if the first 12 completed replays fall below 100 aggregate
  games/hour, detector utilization is low without a prepared-frame queue, or
  acquisition failures exceed 25%.

### 01:50–03:00 — close decks and calibrate identity

- Use the existing 29 video-bound exact decks as replay-disjoint calibration.
- Benchmark a lightweight HUD/deck identity adapter with abstention; require at
  least 99% accepted-label precision and zero cross-replay leakage.
- Review generated eight-card sheets directly. Ambiguous hero/evolution art is
  quarantined; deck family or cost consistency never substitutes for exact
  identity.
- If automation fails its precision gate, continue with high-confidence/manual
  closure rather than weakening thresholds.

### 03:00–04:30 — causal packaging

- Reconstruct hand/Next cycle events under exact reviewed decks.
- Apply authoritative public cost, portable current-frame clock, canonical
  actor coordinates, and label-independent public mask v2.
- Keep targets in separate inference-ineligible sidecars. Never repair an
  expert action into the mask.
- Run the strict per-replay verifier and stratified visual action audit.

### 04:30–05:00 — corpus decision

- Combine only current-client, permission-cleared YouTube replay groups.
- Require at least 1,000 legal+clocked actions, 250 complete-HUD actions, 20
  replay groups, and three full verifier passes. Current baseline is
  711/220/33/24.
- Build replay-, deck-, chronology-, and archetype-disjoint splits and verify
  zero group leakage.

### 05:00–06:30 — fresh causal BC screen

Only if the corpus gate passes:

- train the fresh canonical-lane, current-client 494-token family from scratch;
- compare the bounded hierarchical gate/pointer variants, not the contaminated
  historical checkpoint lineage;
- one epoch first, with public Next/confidence corruption and no exact-state
  fallback;
- retain only candidates that improve held-out action type/card/tile metrics
  without collapsing card or win-condition usage.

If the corpus gate does not pass, spend this block on another bounded data wave
and deck closure—not on underpowered policy training.

### 06:30–08:00 — held-out behavioral evaluation

- Run replay-disjoint offline metrics, hand permutation/equivariance,
  corruption sensitivity, confidence calibration, and unknown-card behavior.
- Run matched simulator games against all strategy bots and held-out decks.
- Reject first-to-three-crown rush, no-defense behavior, Hog/other win-condition
  non-use, target-label leakage, illegal-action dependence, or material seed
  instability.

### 08:00–09:30 — short PFSP PPO only after promotion

- If one BC candidate passes every earlier gate, run a short stratified PFSP PPO
  pilot with historical/strategy opponents and held-out archetypes.
- Checkpoint frequently. Evaluate against the BC parent and stable opponents.
- Roll back on broad regression; do not preserve the candidate because compute
  was spent.

If no candidate qualifies, use this time for classifier/deck closure, data
audits, and additional held-out labels.

### 09:30–10:00 — copy-off and teardown

- Copy manifests, compact causal artifacts, checkpoints, raw logs, and visual
  audits to the Mac while verifying SHA-256.
- Produce a single decision report with costs, rates, gates, failures, and exact
  continuation command.
- Terminate the pod and verify `prime pods list` is empty.

## Expected outcome

At the observed 29/37 deck-closure rate and 20.90 legal+clocked actions per
closed match, a 128-video wave projects roughly 100 exact closures and about
2,100 additional usable action targets. This is an extrapolation, not a promise;
the campaign gates use observed outputs only. The wave should comfortably clear
the current 289-action and 30-complete-action deficits while materially
improving deck and matchup diversity.
