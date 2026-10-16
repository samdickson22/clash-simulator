# C1 fresh final gate — prepared, not launched

2026-10-16. The focused correction `f68e5f80f` / native `631ac18d` has independent r2 **APPROVE**; this is not
the integrated final gate. The historical PASS covers only `2ac024c7`. This plan and the new
`tools/final_gate.sh` require independent host-script review before execution. No engine/native change is
needed for preparation, and no merge, rebase, build or final gate is authorized by this document alone.

Review inputs: [approval/results](RESULTS.md), [exact comparator predicates and continuation receipts](SNAPSHOT-DIAGNOSTICS.md),
and [unexecuted launcher](tools/final_gate.sh). Launcher SHA256
`57c3bd179aac3f9b50b930606b22c5f139ef7b37713202647cd7ebd589faa282`;
tested comparator `aad00c4bed5418528db06308513f6edf66b12e0af9ca4c890dd8555bc5f150a8`.
Review code delta with `git diff 933178477 HEAD -- reports/cards/c1/` in the C1 worktree. These hashes identify
the submissions; independent launcher review and comparator coverage acceptance are still outstanding.

## Required order and immutable identities

1. CARD LEAD supplies **accepted and integrated B2** receipt and exact accepted source SHA. Existing review
   approval of C1 is not a substitute. Keep B2 selectors (including ElectroWizard secondary, ElectroDragon
   hop, Log/Bandit remembered hits) in B2; retain C1 boulder/axe filters. Reconcile actual conflicts only, in
   the lead-authorized integration target; record each resolution and review any substantive change.
2. Record the exact integrated source commit, prove the accepted B2 commit is its ancestor, and freeze the
   source. Rerun affected C1/B2 probes on that combined Python/native; inherited `2ac024c7` diagnostics and
   `631ac18d` focused approval are not receipts for the combined source. Meaningful snapshot-continuation
   findings must be resolved or explicitly bounded by independent review before the integration verdict.
3. Build that exact frozen source on **04 only**, using existing `c1/build.sh` under `cpu_job.sh 8` / nice 15 /
   cargo -j8. Record PID/PGID, input commit, build start/end, binary hash. Do not reuse the old native hash
   by assumption. No heavy 05 work, no hosts 09–18, no emulator work or active-pin/runtime writes.
4. After affected verification passes and launcher review approves the **exact script hash**, audit jobs and
   launch the fresh C56 gate once. Give the lead exact PID/PGID and receipts for passive shepherding.

`B2_ACCEPTED_SHA` and `INTEGRATED_SHA` are intentionally unfilled while B2 is pending. `NATIVE_SHA` is assigned
from the combined build receipt. `PREP_COMMIT` identifies the reviewed tools/plan revision. No placeholder is
a readiness signal. Routine coordination goes directly to CARD LEAD via `t3_thread_send(mode='auto')`,
including evidence, recommendation and whether dependent work waits; no user-input tools. Parent thread:
`thread:delegated-task:command%3Amcp%3A7f0bf0df-35b9-48b9-bbf9-8f9cdcc3f584%3Adelegate-task%3Aclasher-card-lead-20261016-r1`.
No active descendants or pending legacy input requests; future briefs must repeat this coordination rule.
Sam's later strict-silence rule supersedes routine reporting: message only for blocked parent action, urgent live
failure, explicit request or essential dependency handoff, max two sentences plus one receipt path. No routine
status/results/queue/commit acknowledgments or duplicate manual completion; detailed evidence stays in files.

## Fresh bundle on 04

Use `/mpac/sdicks02/jobs/clasher/cards/c1/final-${INTEGRATED_SHA:0:12}`. A failed/interrupted attempt is preserved;
any justified later attempt uses a fresh `-rN` suffix after duplicate/job audit. Never reuse `c1/gate`, `verify`,
`tree`, `out`, `tree-r2`, `out-r2` or either inherited snapshot job directory.

The following is a staging recipe **for review and later use**, not an executed preparation job. Commands
using unresolved SHAs must wait. Supply only verified full hexadecimal commit/hash values.

```bash
# In the authorized local integration checkout, after B2 acceptance/integration:
git rev-parse "$INTEGRATED_SHA^{commit}"
git merge-base --is-ancestor "$B2_ACCEPTED_SHA" "$INTEGRATED_SHA"
RUN=/mpac/sdicks02/jobs/clasher/cards/c1/final-${INTEGRATED_SHA:0:12}
ssh 127x04 "test ! -e '$RUN' && mkdir -p '$RUN/tree' '$RUN/rt' '$RUN/tools' '$RUN/gate-tools' '$RUN/batchA-tools' '$RUN/c1-tools' '$RUN/verify' '$RUN/receipts'"
git archive "$INTEGRATED_SHA" engine-cards | ssh 127x04 "tar -x -C '$RUN/tree' --strip-components=1"
```

Populate `c1-tools` / `batchA-tools` from the reviewed `PREP_COMMIT`, not a mutable checkout; retain their source
commit/hash manifest. Copy the unchanged gate and helper tools from the historical C1 bundle on 04:

```bash
cp -a /mpac/sdicks02/jobs/clasher/cards/c1/tools/gate.sh "$RUN/tools/gate.sh"
cp -a /mpac/sdicks02/jobs/clasher/cards/c1/gate-tools/. "$RUN/gate-tools/"
cp -a /mpac/sdicks02/jobs/clasher/cards/c1/rt/. "$RUN/rt/"
ln -sfn "$RUN/tree" "$RUN/rt/engine-rs"
ln -sfn "$RUN/tree/py/src" "$RUN/rt/src"
ln -sfn "$RUN/tree/py/gamedata.json" "$RUN/rt/gamedata.json"
ln -s /mpac/sdicks02/jobs/clasher/cards/batchA/roots "$RUN/roots"
/mpac/sdicks02/repos/clasher-bot/bot/exit/cpu_job.sh 8 bash /mpac/sdicks02/jobs/clasher/cards/c1/build.sh "$RUN/tree" "$RUN/out"
```

These commands are confined to the new bundle; `rt` is a mirror of symlinks to read-only r1 metadata, with
three local source/data overrides. Do not edit the referenced runtime. Confirm all three resolved targets
and the pinned native before use. Keep the committed gamedata **without overlay** for C56. Optional C1
overlay checks use a separate scratch root with the four documented stat rows, never the final gate root.

Read-only source hashes of the reused reviewed gate helpers (confirmed 09:34Z on 04):

- `tools/gate.sh`: `21bbecaf168be4c5b5ff44f96208025b58424b62efdf80ecf9179db37353e170`.
- `gate-tools/parity_fixtures.py`: `057bd386f022d3770baf0a47d19b7eac2b8e9fc978a0464746ae4a6fc7afe976`.
- `gate-tools/parity_roots.py`: `2d721a49d003abfaadd0e5f532749f700addfd733c493e7acf2b6abe225063eb`.
- `gate-tools/compare.py`: `dce90963be2d46b6a0af8ba418d7c661b2d16a95f1d17202207c0c147eff9e6e`.

## Affected verification before readiness

Use isolated logs/JSON under `$RUN/verify`, check every child exit and parse its result; do not infer PASS from
bare `wait` or a done marker. Run independent groups sequentially under leases ≤8. Exact Python environment:

```bash
PY=/mpac/sdicks02/repos/clasher-bot/.venv/bin/python
ES=/mpac/sdicks02/repos/clasher-bot-runtime/r1/reports/strategy_council_20260928/engine-speed
export PYTHONPATH=$RUN/out:$RUN/rt/engine-rs:$RUN/rt/src:$ES:$RUN/batchA-tools:$RUN/c1-tools
export CARDS_GAMEDATA=$RUN/rt/gamedata.json PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
# Each payload below runs through cpu_job.sh N nice -n 15, with its own output log and JSON.
"$PY" -B "$RUN/c1-tools/probe_review_r2.py" "$RUN/verify/review-r2.json"
"$PY" -B "$RUN/c1-tools/probe_snapshot_followup.py" "$RUN/verify/snapshot-followup.json"
"$PY" -B "$RUN/c1-tools/probe_c1_cases.py" "$RUN/verify/c1-cases.json"
"$PY" -B "$RUN/batchA-tools/probe_first_update_paths.py" "$RUN/verify/first-update.json"
"$PY" -B "$RUN/batchA-tools/probe_native_scen.py" "$RUN/verify/batchA-review.json" --cases
"$PY" -B "$RUN/batchA-tools/probe_native_scen.py" "$RUN/verify/c1-scenarios.json" Bowler Assassin ZapMachine ElectroWizard IceWizard InfernoDragon MegaKnight Fisherman AxeMan ElectroDragon BossBandit Ronin
```

Require 21 focused correction cases, the two bounded continuation cases, 72 C1 cases (36 scripts × both seats), 42 first-update paths,
four Batch A review cases, 36 C1 scenarios; every scripted deploy must be valid. Repeat overlay scenarios if
merge resolutions touch their config. Replay the eleven named mixed games via `replay_games.py` with the
frozen `nd-plan.json` and IDs `22 245 274 323 16 86 336 460 189 415 548`. Rerun only relevant B2 final-owner
selector/continuation controls against the integrated native (accepted B2 receipts define their exact CLI;
do not run obsolete B2 gate launchers). In particular, carry over attacks.rs secondary and c56.rs chain guards,
and explicitly cover Log remembered hits plus C1 boulder/axe filters. Account for all meaningful differences;
selected-field comparator equality is not complete snapshot byte equivalence. Keep negative controls live.

## Readiness binding and gate invocation

Create `inputs.sha256` **relative to `$RUN`** over the immutable tree, native, reviewed tools/launcher, copied
review/test/build receipts, and root/fixture input files. It must exclude output directories and readiness
controls to avoid self-reference. Hash both the manifest itself and each referenced receipt. Preserve input
source manifests and the exact commands in the lead's audit. Freeze the bundle before declaring readiness.

`ready.json` is the lead's explicit assertion backed by copied evidence, not a tool-generated approval:

```json
{
  "integrated_commit": "<full integrated SHA>",
  "native_sha256": "<fresh combined build SHA256>",
  "b2_accepted_commit": "<full accepted B2 SHA>",
  "launcher_sha256": "<independently approved final_gate.sh SHA256>",
  "inputs_sha256": "<SHA256 of inputs.sha256>",
  "prerequisites": {"b2_accepted": true, "b2_integrated": true, "affected_probes_pass": true, "launcher_reviewed": true},
  "receipts": {"receipts/b2-acceptance.json": "<hash>", "receipts/integration.json": "<hash>", "receipts/launcher-review.md": "<hash>"}
}
```

Immediately before launch, check `ps -p 1042473` on 08 and `ps -p 4131290,4132214` on 04 plus their receipts;
inspect `ps -u sdicks02 -o pid,ppid,pgid,etime,args` for any existing final bundle job/lease. Do not terminate
or duplicate the inherited jobs. After prerequisites and script review pass, launch **once**, on 04:

```bash
setsid nohup /mpac/sdicks02/repos/clasher-bot/bot/exit/cpu_job.sh 8 bash "$RUN/c1-tools/final_gate.sh" "$RUN" "$INTEGRATED_SHA" "$NATIVE_SHA" "$B2_ACCEPTED_SHA" > "$RUN/launcher.log" 2>&1 < /dev/null &
taskpid=$!; printf '%s\n' "$taskpid"
ps -p "$taskpid" -o pid,ppid,pgid,lstart,etime,args
```

The wrapper restricts host/path, requires its parent's eight-CPU lease, checks readiness/script/native/input
hashes, reserves an atomic one-use marker, runs the **unchanged** historical gate, and independently audits
all raw records/bytes/IDs/native headers before `PASS.utc`. It sanitizes inherited root/overlay variables.
Two fixture pools have three workers each (eight processes with their parents), followed by eight root shards.
Keep `launch.receipt`, UTC start/end, `exit-code.txt`, `gate/compare.json`, raw JSONLs/logs, pre/post hashes and
`PASS.utc`. An empty done file or descriptive compare output is insufficient.

Required result: **577/577 fixture records byte-identical; 577/577 Rust-only chains, zero errors; 300/300 full
+ 300/300 cut roots with exact bodies**, unique/matching IDs and all eight expected native headers. Pinned
native remains `681b5f2c866ba3df1aa9903d1bf40d565e21feb6f541319bef84ee493c72066b`. Record every discrepancy and
bound/triage it rather than broadening comparison. Lead audits receipts independently before acceptance.

## Preservation and rollback

No active live pin switch. Failed verification/gate leaves the isolated bundle and reviewed baseline intact;
record status/PID and end passive waits with lead shepherding. No automatic retry. Revert an unaccepted
integration through its recorded merge parent/commit in the lead-authorized checkout, not a destructive reset.
Focused correction rollback remains `git revert f68e5f80f1b23f5d5245e3c6c856e5ec6fceac4e`; historical native
`2ac024c7` and `c1/gate` artifacts stay intact. No production/runtime restoration is needed for this preparation.
