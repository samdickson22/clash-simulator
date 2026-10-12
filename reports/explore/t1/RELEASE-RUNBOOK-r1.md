# Guarded release procedure — candidate, not authorized to run

The verbatim `receipts/END-PRODUCTION-PACKET-REVIEW-r2.md` procedure is binding.
Coordinator 2e275312 authorizes preparation only. No production driver, barrier,
reducer or outcome read has been performed by this change.

1. Obtain independent approval of `release_run.py` and explicit coordinator
   release authorization after the TIERS Mac-summary route. The coordinator
   supplies the release JSON and its SHA. Its prerequisite envelope must equal
   sealed R5 3b7d2295 exactly. The Mac-summary commit must be an ancestor of the
   eventual canonical private HEAD. The fourteen-day route is not available
   before 2026-10-25T19:31:38Z.
2. Only under the later state-change ruling, incorporate the public driver and
   Mac summary into a local-only descendant of private 9bb349b1. Never push that
   checkout or its private ref. At present canonical R stays clean at 9bb349b1;
   the driver is committed in the worker's public checkout, not installed in R.
3. Run the approved committed driver by absolute path, from canonical
   `R/reports/explore/t1`, using `e4v3-venv/bin/python -B` (3.12.12), environment
   `PYTHONDONTWRITEBYTECODE=1`, nice 19/core 63. Provide required `--release`,
   `--release-sha256`, `--r5`, `--copy-receipt` and unique `--private-name`.
   The private parent `t1-20261010-r1/release-private/` must be a new/plain 0700
   directory established under that authorization. Never invoke the reducer bare.
4. The driver checks canonical ancestry/ref/cleanliness and receipt/module pins.
   It imports canonical health code, compares the exact copied-root health ledger
   against PC4 16e1b34f, ignoring only top-level UTC. A mismatch or exception
   prevents both barrier and reducer. The parent also denies game-path opens.
5. It captures the explicit barrier's stdout/stderr privately, then invokes the
   unchanged aebb2017 reducer with the same root/ledger/receipt, capturing all
   stdout/stderr privately. The reducer runs its own barrier before games.
   Both fresh in-barrier check paths and SHAs are retained in the health receipt;
   scratch diagnostics remain in their original paths.
6. It checks the emitted ledger against PC4 except UTC, and checks all three
   sensitivity sections' ledger SHA bindings. Any barrier/reducer/post-check or
   final-record failure quarantines the owned output directory with mode 000.
   The visible failure record contains stage/type only, never exception text,
   stdout, selection or result values. Preserve quarantine and stop; no retry.
7. Only after the health receipt completes may the coordinator read the private
   output. Descriptive sensitivity never chooses a tier. No output handoff is
   permitted while review, the Mac route or explicit release authorization waits.

C2 copied the dereferenced 01 r3 hub chain into `release-blocks-0108-r3` on 05.
The receipt pins 3,072 proofs (set d0f01069), 24,576 streaming game hashes and
1,100 ACK hashes. The file inventory is private. No game data was parsed.

The later CPU ruling releases 01 CPUs only. Its four job directories, all A5
host/release roots on 01/08, end-received, private R and bundles remain frozen.
The hub mirror remains paused. C2 does not authorize deletion or relocation.
