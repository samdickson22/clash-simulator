# Next-run receipt copy owner

This separate 05 owner fills the two receipt directories required by
[NEXT-EVAL-EXPANSION.md](NEXT-EVAL-EXPANSION.md). It copies completed `run.json` and
`summary.json` from 08 to `ROOT/next-run-receipts/{S100,M}`. ROOT is
`/mpac/sdicks02/scratch/pretrain-v1-dev/followup-20261022`. Each size can publish
independently. No code in either reviewed expansion script changes. The separate
expansion worktree must remain at its exact GO `ef8b9395e3ba5faf4d340f754adee3f627e2d982`.

The source is the immutable 01/02 allocation's existing 08 publication at
`/mpac/sdicks02/jobs/clasher/pretrain-v1/followup-20261022/{next-S100,next-M100}`
and matching `select-next-*` directories. Controller revision `962244600d` has
script SHA256 `bc703a4072634ccccedb90f03e34ef9d3cebad25046bcce3cae14922607b4218`.
The helper reads only fixed paths with standard Python on 08. Every attempt uses
one SSH connection for both sizes, a 90-second deadline and a 2 MiB stdout bound.
It returns just three small raw receipts per size plus digests. It streams the
selected anchor hash without transferring its contents. Allocation, claim, bundle
and published receipt digests bind the transfer, with bundle and published hashes
checked against the bytes read. The unchanged waiter's `validate_run()` checks the
registered run and scientific provenance locally before any publication.

Missing source files or absent publication metadata wait for another 60-second
poll. Provisional, smoke or unadmitted selections wait. Once those files are all
present, malformed JSON, scientific mismatch, source symlinks and hash conflicts
fail closed. SSH nonzero exits and connection deadlines retry and preserve the last transport
failure in `ROOT/next-run-receipts-owner.json` and stdout. Local publication errors
including local SSH setup errors, and oversized or malformed SSH responses fail closed. No retry chooses other data.

Raw encoding and newlines survive transport. Both run and summary, plus a durable
`copy-receipt.json` binding manifest, are fsynced in a hidden directory, which is
then renamed with Linux `RENAME_NOREPLACE` and its parent fsynced. The public size
directory never appears with only one receipt. Existing destinations must contain
exactly the two regular receipt files and the matching binding manifest, with no
symlinks. Conflicts stop without overwriting. A crash after rename can reuse the
exact bytes on restart after fsyncing the files, destination and publication parent again; a hidden interrupted copy is never a READY publication.
There are no workload children or process recovery actions. This addresses the R22
partial READY and duplicate orphan hazards and the R13 stale-result/path-binding
principles without adding another fleet supervisor.

## Parent launch after exact review GO

The parent owns landing and launch. Preserve this dedicated checkout clean at the
exact reviewed commit while it runs. The owner checks reviewed HEAD and clean
status at startup and each poll, requires host 127x05 and nice >=10, and refuses
MemAvailable below 29 GiB or one-minute load above 90. The existing host guard
should wrap this one receipt job. No GPU or scientific job is part of this owner.
It takes `ROOT/next-run-receipts-owner.lock` with nonblocking singleton flock before
writing its launch state or connecting. The lock stays held for the entire run.

Staged command only, not executed during implementation or review. Set
`REVIEWED_SHA` to the exact reviewed commit of this receipt-owner checkout. Check
for an existing owner immediately before the eventual launch. The expansion owner
has its own reviewed checkout and can be launched independently by the parent.

```bash
RECEIPT_CODE=/mpac/sdicks02/repos/clasher-pv1-next-receipts-20261022
RECEIPT_ROOT=/mpac/sdicks02/scratch/pretrain-v1-dev/followup-20261022
R2=/mpac/sdicks02/scratch/rl-search-prior-20261020-r2
GPU= CUDA_VISIBLE_DEVICES= nohup bash "$RECEIPT_CODE/bot/pretrain_v1/run_guarded.sh" \
  "$RECEIPT_ROOT/next-run-receipts-owner.log" -- \
  "$R2/run.sh" "$RECEIPT_CODE/reports/bot/pretrain-v1/sweep/copy_next_receipts_05.py" \
  --reviewed-revision "$REVIEWED_SHA" \
  </dev/null >"$RECEIPT_ROOT/next-run-receipts-launcher.out" 2>&1 &
```

The atomic owner state records PID, process start tick, boot ID, script SHA256,
reviewed revision, status, wait reason, last network failure and completed bindings.
Success is `status=done` with both size manifests. Failure requires parent
inspection; never delete conflicting public directories to force a retry. The
existing expansion waiter still performs all its own gates. No completion ETA is
asserted here and no live selection status was read.

Local verification uses temporary fixtures, the actual fixed remote helper run
locally, and mocked SSH processes. Run without contacting any host:

```bash
python3 -B -m unittest discover -s reports/bot/pretrain-v1/sweep -p test_copy_next_receipts_05.py -v
```


## Operational state

Fresh independent Sol high GO is exact source `aa10b891e1154f931382339312837aed2f53b9ba`.
The parent landed identical source blobs and launched the dedicated immutable checkout at 10:53:49Z
on 2026-10-22. Guard PID 2197122, owner PID 2197130. Its state reports S100 published and M pending
atomic publication, no network failure. The expansion waiter remains independently gated.
Launch receipt: `ROOT/next-run-receipts-launch-receipt.json`. Runtime state: `ROOT/next-run-receipts-owner.json`.
