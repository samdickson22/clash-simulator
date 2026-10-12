# Guarded release procedure — candidate, not authorized to run

The verbatim `receipts/END-PRODUCTION-PACKET-REVIEW-r2.md` procedure is binding.
Coordinator 2e275312 authorizes preparation only. No production driver, barrier,
reducer or outcome read has been performed by this change.

1. Obtain independent approval of `release_run.py` and explicit coordinator
   release authorization after the TIERS Mac-summary route. The coordinator
   supplies the release JSON and its SHA. Its prerequisite envelope must equal
   sealed R5 3b7d2295 exactly. The Mac-summary commit must be an ancestor of the
   eventual canonical private HEAD. The driver currently has an **empty explicit
   descendant allowlist in approved r2**: any tracked difference from 9bb349b1
   fails closed. Approved Mac-route r3 adopts only the 18 exact metadata paths assigned
   in COORDINATOR 4eb6c3e5. Unknown classification names are denied.
   The fourteen-day route is not available
   before 2026-10-25T19:31:38Z.
   **Route separation:** the fourteen-day route must use approved r2 SHA
   `42219e57c052ada73a3ca691839fa47166f1d554fa5600dd85553bb68a916a5e`
   with canonical HEAD at 9bb349b1 and an empty descendant diff. Never use r3
   for the fourteen-day route. The Mac-summary route uses reviewed r3 SHA
   `9ffbd2e197e58b5c56b3d58cefe4008d47cb4fdf50764808e841218294408bca`.
2. Only under the later state-change ruling, incorporate the Mac metadata into a
   local-only descendant of private 9bb349b1. Never push that
   checkout or its private ref. At present canonical R stays clean at 9bb349b1;
   the driver is committed in the worker's public checkout, not installed in R.
   Use `prepare_release_descendant.py` only after that ruling: it builds a tree
   from 9bb349b1 with a temporary index, copies regular blobs at exact allowed
   paths, checks `git diff --no-renames --name-only`, and protects the result with
   a local private ref. It preserves the public Mac source as a second parent
   for barrier ancestry, without merging its unrelated public changes into the
   tree. It does not update the working-tree HEAD or its index. Unknown paths
   under the Mac session prefix abort. Do not run this helper on real R now.
3. Run the approved committed driver by absolute path, from canonical
   `R/reports/explore/t1`, using `e4v3-venv/bin/python -B` (3.12.12), environment
   `PYTHONDONTWRITEBYTECODE=1`, nice 19/core 63. Launch the parent with **env -i**:
   preserve only the operator's HOME, PATH=/usr/bin:/bin and
   PYTHONDONTWRITEBYTECODE=1. Launch **detached under setsid**,
   with stdin `/dev/null` and stdout/stderr redirected to an exclusive private log,
   never in a bare SSH foreground. Provide required `--release`,
   `--release-sha256`, `--r5`, `--copy-receipt` and unique `--private-name`.
   The private parent `t1-20261010-r1/release-private/` must be a new/plain 0700
   directory established under that authorization. Never invoke the reducer bare.
   Immediately before launch, confirm the reviewed driver SHA and that its
   directory contains only the committed tree (no extra Python files). Approved
   r2 is 42219e57c052ada73a3ca691839fa47166f1d554fa5600dd85553bb68a916a5e;
   reviewed Mac-route r3 is 9ffbd2e197e58b5c56b3d58cefe4008d47cb4fdf50764808e841218294408bca. Confirm canonical
   e4v3 directory mode is exactly 555 and git status --porcelain --ignored is empty.
4. The driver checks canonical ancestry/ref/cleanliness, exact descendant allowlist,
   remote-ref ancestry exclusion and all 17 executed local modules plus plan.json.
   It requires the actual -B flag, interpreter 3.12.12 and numpy 2.2.6; the reducer
   receives no PYTHON* environment variables and runs in a new process session.
   It imports canonical health code, compares the exact copied-root health ledger
   against PC4 16e1b34f, ignoring only top-level UTC. A mismatch or exception
   prevents both barrier and reducer. The parent also denies game-path opens.
   For `committed_mac_summary`, the release envelope must additionally supply
   `a3p_poll_check` and `mac_receipt_manifest`, each a full `{path,commit,sha256}`
   binding at `D/a3p-poll-check.json` and `D/sealed/receipt-manifest.json`.
   `release.mac_summary_path` must be `D/sealed/tiers-summary.json`.
   Before the health guard, r3 verifies all three committed artifacts, the A3-P
   manifest SHA and summary seal, exact tier coverage and Boolean consistency.
   If any frozen-feasible tier is disqualified by A3-P, it returns failure type
   `A3PRequiresRuling`, creates no output directory and invokes no reducer.
   Return this health-only failure to the coordinator for a selection ruling.
   If every frozen-feasible tier passes A3-P, the frozen reducer stays unchanged.
5. It captures the explicit barrier's stdout/stderr privately, then invokes the
   unchanged aebb2017 reducer with the same root/ledger/receipt, capturing all
   stdout/stderr privately. The reducer runs its own barrier before games.
   Both fresh in-barrier check paths and SHAs are retained in the health receipt;
   scratch diagnostics remain in their original paths.
6. It compares canonical JSON, masking only top-level UTC, and checks all three
   sensitivity sections' ledger SHA bindings. Any barrier/reducer/post-check or
   final-record failure quarantines the owned output directory with mode 000.
   The visible failure record contains stage/type only, never exception text,
   stdout, selection or result values. SIGTERM, SIGHUP and SIGINT raise into the
   BaseException quarantine path. The reducer's new session keeps terminal
   hangups isolated; on termination the driver SIGKILLs and reaps the owned
   reducer session, including its E4 grandchildren. Failure handlers block
   TERM/HUP/INT until quarantine; output ownership is registered at mkdir under
   a signal mask, before the guarded call can return.
   SIGKILL cannot be handled. Any exit without a completed health record means:
   treat the output as locked, chmod 000 the owned private directory, and report
   failure only. Preserve quarantine and stop; no retry.
7. Only after the health receipt completes may the coordinator read the private
   output. Descriptive sensitivity never chooses a tier. No output handoff is
   permitted while review, the Mac route or explicit release authorization waits.

Do not run another barrier concurrently. The driver requires exactly its parent
and reducer's two new recheck receipts; a third concurrent run fails closed and
quarantines outputs. Keep their original health scratch and diagnostics intact.
Parent reads under the block root are limited to complete/interference health
proofs, neither symlinked. The early audit hook rejects operator game paths before
even hashing them. C2's ACK hashes remain the binding; the frozen health function
checks ACK existence only. This informational S6 behaviour is unchanged.

C2 copied the dereferenced 01 r3 hub chain into `release-blocks-0108-r3` on 05.
The receipt pins 3,072 proofs (set d0f01069), 24,576 streaming game hashes and
1,100 ACK hashes. The file inventory is private. No game data was parsed.

The later CPU ruling releases 01 CPUs only. Its four job directories, all A5
host/release roots on 01/08, end-received, private R and bundles remain frozen.
The hub mirror remains paused. C2 does not authorize deletion or relocation.

## Exact builder and HEAD activation steps — documentation only, not authorized now

The builder is awaiting its narrow independent review. Neither this section nor
driver approval authorizes running the builder or moving canonical R. Execute
only after builder approval, Mac outputs/A3-P and explicit coordinator state-change
and release GO. Any failed check stops; preserve evidence and request a ruling.

Use the coordinator's full public Mac metadata source SHA and a fresh unused ref.
The target must start with `refs/private/` and must never be
`refs/private/t1-registration-20261012`. Candidate builder SHA (pending review):
`dd644cdcde6c9a6d6994aac891ecd4cf20d8b810873b8cef3fab56ef21647259`.
The builder directory's `release_run.py` must be the reviewed Mac-route r3 SHA
above, and the directory must contain only its committed tree. Before and after
building, the protection ref must still resolve to
`9bb349b1d4f467866f802a859c142c4adc7c0402`.

Launch the builder with a clean environment, no GIT_* variables, and -B. Here
`release_source_sha` is the full coordinator-bound source SHA, and
`release_fresh_ref` is the new ref name. Preserve the builder's JSON receipt:

```bash
env -i HOME="$HOME" PATH=/usr/bin:/bin PYTHONDONTWRITEBYTECODE=1 \
  nice -n 19 taskset -c 63 \
  /mpac/sdicks02/jobs/clasher/e4v3-venv/bin/python -B \
  /mpac/sdicks02/jobs/clasher/t1-health-stop-reconcile-20261010/reports/explore/t1/prepare_release_descendant.py \
  --source-commit "$release_source_sha" --private-ref "$release_fresh_ref"
```

The builder creates the target only with a zero old-value compare-and-swap; an
existing ref is never overwritten. It checks the protection ref on both sides.
Set `release_descendant_sha` from that preserved receipt. The exact HEAD move is:

```bash
git -C /mpac/sdicks02/jobs/clasher/t1-20261010-r1/end-a5-release-r1/source \
  switch --detach "$release_descendant_sha"
cd /mpac/sdicks02/jobs/clasher/t1-20261010-r1/end-a5-release-r1/source
```

Immediately afterwards, under the same clean environment and -B interpreter,
verify **all** of the following using the preserved builder receipt:
All Git queries below run from that canonical directory; they must never query
the public worker checkout by accident.

- `git rev-parse HEAD` equals its `commit`, and `git rev-list --parents -n 1 HEAD`
  has exactly three SHA tokens: descendant, private base9bb349b1, and the receipt's
  full `source_commit`, in that order. Both parent commits must be ancestors.
- `git --no-optional-locks status --porcelain --ignored` is empty.
- `git rev-parse refs/private/t1-registration-20261012` is still exactly9bb349b1.
- `git diff --no-renames --name-only 9bb349b1 HEAD` is a subset of the reviewed
  driver's exact 18-path allowlist, with neither failure path present.
- `stat -c %a <R>/reports/strategy_council_20260928/live-loop/v4/mac-e4-package/e4v3`
  is exactly `555`. All 18 execution pins still equal the reviewed values.
- Neither the private base nor descendant occurs in remote-tracking ancestry.
  Never push canonical R, either private ref or any commit descending from them.

Record the observed HEAD, both parents, empty status, protection SHA and directory
mode before launching the route-specific driver. This turn executes none of these
activation commands; canonical R remains frozen at9bb349b1.
