# S/M follow-up registration

Registered before generating or playing follow-up cases and before training M25/M50 or the next-snapshot models.
Sam's latest scope is S100 versus M. S100 remains the default; the original result is inconclusive, not an M loss.
L remains cancelled by decision. There is no deployment or outcome-RL launch in this follow-up.

## Power extension

- Freeze 1,600 new HOG26-acct cases, 800 per controller, with 400 per seat within each controller.
  Use the original r2 generator's 40% corpus / 30% frequency / 30% uniform opponent distribution, exclusion list,
  level table, own account levels, deck shuffling and calibrated runtime. Use seed base 2026102201000000.
  All seeds and case IDs must be disjoint from the original 1,200-case bank, including its 400 Hog cases.
- Evaluate the already selected v3 checkpoints, S100 `e9366c55503f3d826fa6add0beb9880883be9274158e728f03f932dcd19acbc7`
  and M `caa5f58ff250fdd689734ad80eb426e654ab4828ff4b08e655df7265e8486f7e`.
  Both see identical cases, seeds, deck order, levels, seat and controller. This is a direct M-minus-S100 comparison;
  it does not require replaying the search control. Original search-control results remain separately reported.
- Use the existing 20,000-draw PCG64 controller-stratified bootstrap, equal controller weights, score win=1,
  draw=0.5, loss=0, complete pairs and all-assigned conservative bounds. Missing, interrupted, invalid and errored
  games stay assigned. Never retry a started case. Report assigned, attempted and valid-pair counts for each arm.
- Fixed horizon, no interim selection or optional stopping. The new 1,600 cases alone determine this readout;
  the original 400 cases remain context and are not pooled into its decision. The approximate CI half-width of
  three percentage points is a power estimate, not a guaranteed width or a reason to add cases after inspection.
- Prefer M only if the complete-pair 95% lower confidence bound of M-minus-S100 is above zero AND the
  all-assigned conservative point estimate is above zero. Otherwise S100 remains the default. An inconclusive
  interval is not evidence of an M loss. This registration does not change the existing decision threshold.
- Run on 05 CPU, initially 24 single-thread workers, guarded with MemAvailable above 28 GiB and load at most 90.
  08 CPU is optional only within those guards and without interfering with GPU training. 04 stays RL.

## Data scaling

- Complete M25/M50/M100 alongside the already completed S25/S50/S100 on exactly the frozen 19,410-match v3 store.
  M100 reuses its trained run and selected checkpoint. M25/M50 use the same nested donor permutation as S,
  seed 2026102001, architecture d320/L6/H8/ff1280, dropout 0.1, AdamW LR 2e-4, decay 0.01, batch 512 and bf16.
  Keep the R7 consumed-future release. No effective-batch or optimizer change.
- As in the S fractions, M50 uses 16 passes with evaluation every two passes; M25 uses 32 passes with evaluation
  every four. Both retain the 6,102-step warmup and patience of two evaluation rounds. This preserves approximately
  eight full-data passes and approximately one full-data pass between evaluations. Actual row/donor counts and
  step counts are reported because nested donor fractions are not exact row fractions.
- Use unchanged full-DEV admission/calibration/checkpoint selection. Report joint NLL, action accuracy, ECE,
  gate and value Brier, Hog metrics and train/DEV sample sizes for all six fraction/size runs. These are DEV reads.
  Do not infer a game win from imitation loss. Run fractions serially on 08 GPU through the existing admission
  and host guards, with the reviewed measured M allocator cap. No new GPU job may bypass those guards.

## Next larger snapshot

- Freeze the first 83 acknowledged batches currently synced on 05, rather than chasing a moving corpus.
  The input receipt lists every batch and receipt hash. Reuse the first 39 byte-identical v3 shards and build
  the additional sealed batches with the unchanged builder and featurizer into a separate store. Never mutate v3.
  Freeze the resulting manifest before copying to 08. Preserve donor-based split, quality-tier rules and labels.
- After the v3 M scaling runs, train S100 and M100 once each on that identical larger snapshot with seed
  2026102001, their original size-specific hyperparameters, batch 512, at most eight passes and patience two.
  Warmup is one full new-data pass, matching the original full-data schedule. DEV selection is unchanged.
- Re-run the same game selection rule on a second 1,600-case bank generated before training, with base
  2026102202000000, disjoint from the original bank and the power-extension bank. Same mix, seat balance,
  pairing, failure accounting and fixed horizon. Report both snapshot comparisons with their sample sizes.
  This avoids treating a bank already used for the first comparison as fresh evidence for the larger snapshot.
- Full training remains on 08 only, serial phases, measured allocator admission and existing host guards.
  If the larger snapshot exceeds the host guard, report the blocker; do not silently change the experiment.

## Artifacts and review

Frozen banks, receipts, row outputs, comparison JSON, scaling results and ownership records live under
`/mpac/sdicks02/scratch/pretrain-v1-dev/followup-20261022/`. Next-snapshot tensors live under
`/mpac/sdicks02/datasets/pretrain-v1/snapshot-20261022-b083/`. GPU outputs live under
`/mpac/sdicks02/jobs/clasher/pretrain-v1/followup-20261022/` on 08.
Sol high reviews the bank extension and launch configuration before execution. Record the exact GO revision,
owner PIDs, output locations and failures in PROGRESS. Jobs must survive the agent turn and refuse duplicate owners.

### Resource amendment, 2026-10-22 08:00Z

Sam adds 01 and 02 for the registered BC fraction and 41,328-match snapshot runs, and 09/12/17 under the
explicit reclaimable fleet leases. 05 and spare CPU on those hosts may evaluate the same frozen banks with
exclusive case claims. 07 is CPU only, at most 32 processes and nice >=10. Hosts 13–16 belong to another
owner; 04 HP1 is untouched. Reallocation changes host ownership only. It does not change the cases,
accounting, seeds, data split, effective batch, optimizer schedule, selection rule or cancelled L decision.
No reallocated phase starts until its original owner is prevented from launching the same phase.
