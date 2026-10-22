# Next-bank 05 expansion

This component waits for the existing CODE93 follow-up owner to start its registered next-snapshot S100 evaluator,
then its M evaluator. It expands each existing 24-worker pool to 64 workers on 05. It does not start an evaluator,
select weights, train, build cases, publish a comparison, or replace that owner. The comparison and all scientific
accounting remain CODE93-owned. The power-bank R28 command remains valid without the new optional
`--expected-arm`; the next-bank controller always supplies that argument.

No jobs were launched and no live processes were signalled during implementation or local tests. No remote
commands or bank/checkpoint changes were made. Operational launch and landing belong to the parent agent after
review. This component does not depend on a lease watcher. Hosts 01/02 continue their training; 04/HP1 and all
other hosts are outside this component.

## Frozen inputs and owners

- Original source is `/mpac/sdicks02/repos/clasher-pv1-followup-owners-20261022`, revision
  `93baf3a5bcff9670a0b8ddbcf437638172e84fbd`. `sweep/next_eval_original.json` freezes its complete evaluator
  package, owner script and host guard hashes, original boot ID, PID/start identities 2013400/244214526 and
  guard 2013392/244214525. These were read locally, without changing either process.
- Root is `/mpac/sdicks02/scratch/pretrain-v1-dev/followup-20261022`. Bank is `next-snapshot-bank.json`,
  SHA256 `10c24cd429416344d6ee69342bc6317a2c90387bb73a97eb38c9dbf4cf30a276`, exactly 1,600 assigned cases.
- Snapshot ready receipt is `/mpac/sdicks02/datasets/pretrain-v1/snapshot-20261022-b083/STORE-READY.json`.
  The snapshot has 83 batches, 41,328 usable matches and 8,143,577 rows. Store
  `f-ce6e509ee43a-b-1005dbb4/MANIFEST.jsonl` has SHA256
  `f52562891584db3dffef6c45ced1106a41b712456e67a1cd87ccc084b23dc59a`. The input receipt hash and 83-entry
  inventory are checked too.
- CODE93 itself atomically mirrors selections from 08 into `ROOT/next-anchors/{S100,M}`. Both must be
  `anchor.pt`, hash-verified, admitted, eligible, non-smoke selections with the registered seed. A provisional
  selection blocks this component. The waiter never picks a checkpoint.
- `ROOT/scaling-read.json` must report all six S/M 25/50/100 runs complete. The local receipt read during
  implementation reports all six complete. This says nothing about later runtime readiness.

The original 08 publisher exposes run receipts before exposing its selection. Its source directories on 08 are
`/mpac/sdicks02/jobs/clasher/pretrain-v1/followup-20261022/next-S100/` and `next-M100/`. Before each expansion,
the parent must provide byte-identical copies of their completed `run.json` and `summary.json` on 05 at
`ROOT/next-run-receipts/S100/` and `ROOT/next-run-receipts/M/`, respectively. These local copies do not currently
exist as part of this implementation. The waiter waits for them. It checks the snapshot path and row count,
full-data seed/fraction, complete registered architecture and argument set, frozen training-source and feature hashes, exact registered output and
selected checkpoint source path/zero-based epoch 0–7/seed, and finite completed summary values;
it records the selection/run/summary hashes in its phase binding. It does not copy data or contact another host.

## Launch only after parent GO

From this dedicated worktree, the parent first confirms the final reviewed SHA and clean status. Preserve this
worktree at that SHA while the waiter or either controller runs. The waiter verifies HEAD and clean status on
every polling cycle and hashes its own script, the expansion helper and original-source inventory into receipts.
Do not substitute the main checkout, CODE93 checkout, or a mutable published helper.

Staged entry command, with `REVIEWED_SHA` set by the parent to the exact reviewed commit, not executed here:

```bash
NEXT_CODE=/mpac/sdicks02/repos/clasher-pv1-next-eval-expansion-20261022
NEXT_ROOT=/mpac/sdicks02/scratch/pretrain-v1-dev/followup-20261022
R2=/mpac/sdicks02/scratch/rl-search-prior-20261020-r2
nohup bash "$NEXT_CODE/bot/pretrain_v1/run_guarded.sh" \
  "$NEXT_ROOT/next-expansion-waiter.log" -- \
  "$R2/run.sh" "$NEXT_CODE/reports/bot/pretrain-v1/sweep/next_eval_expand_05.py" \
  --reviewed-revision "$REVIEWED_SHA" \
  </dev/null >"$NEXT_ROOT/next-expansion-launcher.out" 2>&1 &
```

The parent must recheck 05 for existing waiters/controllers/pools immediately before this eventual launch.
The waiter also takes `ROOT/next-expansion/waiter.lock` and refuses any live expansion pool or other waiter.
It requires host 127x05 and nice >=10. R2 supplies its frozen environment and nice increment. The usual host guard
remains in place; the helper keeps the existing admission reserve of `28 + 1.1*64` GiB and projected load <=90
before forking. Unchanged workers admit games only at MemAvailable >28 GiB and load <=90. Only one size expands
at a time.

## Completion and crash behavior

The target is a unique exact-argv CODE93 evaluator parent, directly owned by PID 2013400, with all 24 matching
live children. Shells, helpers, partial forks, another bank/checkpoint/arm and another source are never targets.
The outer owner durably creates an exclusive phase intent before spawning the controller. It then records the
controller PID/start/boot identity. The controller uses the R28 drain: freeze the exact evaluator parent, stop and
inspect each worker, let active attempts finish, retire idle workers by PID/start, and keep the parent stopped.
Exclusive per-case kernel claims span the entire unchanged worker game/seal. Stale attempts become unchanged
infrastructure-failure rows and are never retried. The R27 marker race still catches only FileNotFoundError;
malformed markers and other I/O errors stop execution.

The controller resumes the original evaluator parent only after every assigned row validates and no attempt
marker remains. The outer owner writes its complete receipt only after controller exit zero, source/checkpoint/
bank/assignment/runtime/row validation and evidence that the legacy parent is no longer stopped. An existing
unexpanded completed bank is skipped only after those same integrity checks and absence of expansion artifacts.
A completed expanded phase additionally needs its matching outer completion receipt, original intent digest,
no surviving controller/pool and a resumed or exited parent. Completed-phase reuse also works after CODE93
exits normally; its live identity is required whenever further original work is needed. Runtime and control pins are checked against the
frozen R2 environment before either path is accepted. Both checks run again after the controller exits before
the outer completion receipt is written.

A restart with an unfinished intent refuses to spawn anything, even if every row has since appeared. A surviving
controller, inherited pool, stopped parent, torn receipt, or crash between intent and child receipt requires manual
inspection by the parent. There is no automatic signal recovery. Do not delete intent files or issue SIGCONT as
routine restart steps. The parent must first prove controller/child death, inspect the recorded PID/start/boot
identities and attempt markers, and obtain a concrete recovery plan. Host-guard termination can leave the original
evaluator parent stopped; this is a fail-closed condition, not successful completion.

## Timing and verification

At handoff, the supplied selection estimate was 11:30–13:00Z on October 22. It is an input estimate, not a live
observation. The waiter polls missing gates every 30 seconds and waits for CODE93 to publish/start each evaluator.
The ideal pool throughput multiplier is 64/24 = 2.67, before drain time and admission holds. No completion ETA is
claimed until the selected anchors, local receipts, host admission and observed next-bank throughput are known.

Local mock tests exercise both arms, exact parent matching, atomic publication, checkpoint/bank mismatch, sealed
row provenance, durable intent before spawn, restart with surviving work, singleton collision, claims spanning
yield/game/seal, the R28 marker race and original-parent resume only after success. No test calls the live waiter
or signals experiment PIDs.

## Operational status, 2026-10-22

Parent landed the reviewed component through `366c7d542` and verified that the resulting source blobs match
reviewed revision `ef8b9395e3ba5faf4d340f754adee3f627e2d982`. Runtime still uses its original immutable reviewed
worktree. Before launch a fresh process scan found no existing waiter, expansion controller or pool.

The waiter launched at 2026-10-22T10:32:52.108306+00:00 on 05, guard PID
4017232 and owner PID 4017239. Its log currently reports `WAIT ready/selection/run/scaling publication`.
No expansion controller or additional game pool has launched. Singleton owner receipt and lock are under
`ROOT/next-expansion/`; the launch receipt is `ROOT/next-expansion-launch-receipt.json`.

A dedicated receipt-only copier is being implemented and independently reviewed to close the future local
run-receipt gate. It will read completed immutable publication on 08 and atomically publish both run and
summary bytes on 05 with SHA256 bindings. That copier is not running yet. Until selected anchors and local
completed receipts exist, this waiter cannot signal or expand an evaluator.
