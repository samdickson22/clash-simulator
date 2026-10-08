# S5: frozen tracker v3 strength confirmation

Written and SHA256-hashed before any S5 game, including pilots. The coordinator's 2026-10-08 06:25 UTC S4 entry explicitly overrides the earlier R-hand-materiality condition. This is the first strength confirmation of S4 tracker v3; no further tracker development or calibration is permitted. A discovered correctness bug stops the study and is reported, never silently repaired.

## Fixed protocol and cells

Exactly S2–S4 Player B: native single-root search, horizon 160, 10-tick search interval, 63 candidate-style rollouts, up to 21 public candidates with C56 balanced/pressure/defense styles. Poll every two ticks from tick 90; one outstanding command; no wall-clock deadline changes actions. S1 immutable runtime is copied from manifest 3ad63c0a7ad1634bac32bf5b031a7a312013497d8863aeaa3b0e2b0e077e5677. No engine/gamedata edits.

128 paired worlds × two seats per cell, 256 games/cell, 1,536 games total. Planning decks use eval/eval_ood roles restricted to train-supported decks and role-frequency weights; opponent decks and inference prior are train-only. Families: 20 Hog 2.6 worlds and 18 each Hog EQ/Firecracker/MM, Royal Hogs/Furnace, X-Bow, bait, Goblinstein, AQ. Schedule deck orders are shuffled; seats swap decks. Script styles cycle balanced/pressure/defense by pair index.

Cell order: T3-N97, ELT-N97, Full-N97, R-derived, T3-N90, Full-N90. All use Full's frozen predecessor board/HP/own-HUD noise and target image latency (four ticks with .98 probability, otherwise eight), zero injected tap failures, unchanged ordinary action rejection. N97/N90 mean recall=precision=.97/.90. R-derived has N97 noisy packets, but its opponent resource/hand/cycle input is exact deduction from public events with prior ambiguity, never hidden identities. Legacy and ELT anchors retain their S3 definitions and sampling streams. Channels are seed-paired, not forced to have identical realizations after action divergence.

T3 uses the final unchanged S4 tracker_v3.py (SHA256 0e6a7c3610c114af3e700c603cf0aa0c9e3a3315286ae43d768289012ae1899f), tracker_v2.py, derived_d1.py, board.py and ELT dependencies. T3 receives public event candidates and detached token/position triples via the S3 adapter. No truth, hidden deck/hand, entity ID or engine RNG enters inference. Frozen S3 resource interval radii are N97 .0682 and N90 .1104. No hand confidence multiplier. Exact implementation hashes are in frozen-s4-inputs.json.

## Fresh seeds and freeze

Confirmation world 9772000001+1009*i and sensor 9872000001+1009*i, i=0..127. Schedule RNG 9771100001; bootstrap RNG 9771100003. Pilot/equivalence worlds 9770800001+1009*i and sensors 9870800001+1009*i, i=0,1,2. Planner world+100000+seat, sampling +1, legacy +2; conservatively audit offsets through +4. Channel SeedSequence([sensor+seat,channel_index]) uses board/HP/HUD/events indices 0..3. Latency sensor+500+seat and taps sensor+700+seat.

Before games, scan all retained historical report text, receipts, seed fields and NPZ metadata on 04 and collector 01, including S1–S4 and earlier. Record unavailable paths and audit failures; any detected collision blocks launch. Missing historical archives limit absolute disjointness claims and are reported. PREREG.sha256 is immutable. The final evaluation manifest freezes execution/analysis sources, copied runtime, schedule, execution map, tests, source hashes and preflight evidence before confirmation. Read-only frozen-file audits cover S1–S4 and S5 on 01/04/08; S4 development hashes are checked separately because v3 was outside its confirmation manifest.

## Preflight, complete-only inference and diagnostics

Run inherited S4 v3/T2/recovery/mass tests unchanged, plus S5 integration checks. Six terminal timing pilots (one per cell) suppress and do not retain outcomes. Three development worlds test terminal action hash/count/tick equivalence of all four anchors (ELT-N97, Full-N97, R-derived, Full-N90) against S3's controller. One additional matched T3 development game verifies tracing does not change terminal actions. S4's 24 exact P16 replays remain existing frozen evidence; no tracker modifications require repeating them.

Outcome-blind until all 1,536 identity-valid immutable terminal receipts, all 152 partition successes and both supervisor successes exist. Score win=1/draw=.5/loss=0; average both seats per world. NumPy default_rng(9771100003), 10,000 shared paired-matchup percentile bootstrap resamples of 128 worlds, retaining both seats and every cell. Report all six scores and 95% CIs.

Primary: T3-N97 − Full-N97, PASS iff 95% lower bound strictly >0. Secondary: T3-N97 − ELT-N97 and T3-N90 − Full-N90, each with the same strict rule. Descriptive ceiling gap: R-derived − T3-N97, with CI. No multiplicity adjustment, outcome exclusions, optional stopping, retuning or outcome-dependent reruns. Independent receipt aggregation rechecks identities, counts, score means, aggregate hash and paired contrasts after the complete barrier.

Per-cell diagnostics use the S3/S4 tick-modulo-20-equals-10 decision samples: elixir coverage, width, MAE, coverage within 1,200 ticks after missed/spurious/confused events, ≥90%-mass hand rate and conditional accuracy, and old unanimity. V3's `hand` field denotes ≥90% mass, so the scoring-only snapshot computes old S3 unanimity independently across all projected cycle branches; it does not alter inference or the sampler. Truth is scoring-only. Report actual event rates, decision timing, action rejections, game CPU and operational CPU separately. These correlated decision diagnostics are descriptive, not independent Bernoulli trials.

## Operations and S1–S4 technical-rerun rule

Detached fleet/fleet_run.sh supervisors on 127x04/08, nice 10, one native/BLAS thread. 152 fixed indexed partitions, even indices on 04, odd on 08, 76 each. Requested concurrency up to 76, dynamically reduced by host-wide capacity: ≤96 of our worker processes, ≤16 with a console user. Reserve supervisor/other-worker headroom and recheck `who` and process counts before launches. Currently both hosts have console users. Collector 127x01 is light; 127x05 code/docs/small results only. No heavy local execution. No borrowed hosts are planned.

Valid terminal receipts match manifest, job, seeds, pair, cell and seat; remain immutable and are skipped on resume. Restart identical incomplete inputs only after verified technical failure, retaining logs/current-state and exit receipts with a fresh attempt label. Wrong identity or changed frozen hashes are hard failures, never overwritten. A correctness bug requires stopping and reporting; any new confirmation would require a separately authorized preregistration and fresh seeds. No retries for outcomes, timing or surprising diagnostics.

If a host disappears, stop collection without a retry loop, write PROGRESS.md/RESUME.md and report. Never assume workers died or restart/migrate them. Never delete data, broadly signal processes, touch tailscale/csc-tailscale/crontab, use 127x02/07, edit sealed S1–S4 files or commit. Copy only S5-owned files with rsync -c; raw receipts and runtime stay fleet-side. Mirror S5 code/docs/small evidence/results to the 127x05 checkout.
