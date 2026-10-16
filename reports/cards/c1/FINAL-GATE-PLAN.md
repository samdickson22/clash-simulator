# C1 final gate: schema 2, preparation only

The r1 launcher at `476a747f75569040f9b137d0991691c95e6f1b29` was **REJECTED**. Its recipe and
`ready.json`/`inputs.sha256` protocol are retired. Do not execute it. The six repairs below replace the
bare-wait gate with a reviewed Python driver; no engine/native change, simulation, build, remote command,
merge/rebase, gate or pin switch is part of this repair assignment. Fresh independent approval of the revised
commit is required before any host execution. Comparator normalization remains approved at SHA256
`aad00c4bed5418528db06308513f6edf66b12e0af9ca4c890dd8555bc5f150a8`, with its existing semantic scope.

## Order and authority

1. CARD LEAD accepts B2 and supplies its exact commit plus required integration case IDs. Integrate B2 before
   C1 in the authorized integration checkout; reconcile actual conflicts only. The driver verifies accepted
   B2 ancestry with `git --no-replace-objects merge-base --is-ancestor` against the integrated commit.
2. Build the frozen integrated source on 04 under the existing reviewed `build.sh`, CPU lease ≤8, nice15,
   cargo -j8. Retain command, source/native/inventory hashes, PID/PGID, successful exit and start/end UTC.
   Native631ac focused approval and native2ac historical gate do not cover the combined source.
3. Rerun affected tests on that exact source/native. Required inventory: review-r2=21, snapshot-followup=2,
   c1-cases=72 (36 scripts × both seats), first-update=42, batchA-review=4, c1-scenarios=36,
   named-replays=11 (games22,245,274,323,16,86,336,460,189,415,548), plus the accepted B2 owner's explicit
   integration cases. Every deploy/result/continuation must be inspected; hashes alone do not establish PASS.
   Reconfirm comparator read sites/negative controls if integration changes them. No obsolete B2 gate.
4. Obtain independent approval of the exact launcher/helper commit, inspect actual raw review/test/build
   evidence and authorize the dependency inventory. Then audit liveness/receipts for duplicate jobs. Only
   then stage and launch a fresh full C56 gate on04. This plan provides no B2 acceptance or launch authority.

LIVE LEAD retains active-pin authority. No runtime writes, active pin switch, emulator work, heavy05 compute,
hosts09–18, or unrelated worktrees. Preserve inherited08 PID1042473 artifacts and04 diagnostics4131290/
4132214; this preparation did not poll/restart them. Historical gate/native2ac artifacts remain unchanged.

Strict silence: no routine DMs/status/test/review/commit updates or manual completion duplicates. Questions
requiring owner action go directly to CARD LEAD through `t3_thread_send(mode='auto')`, maximum two sentences
plus one receipt path; never user-input tools. One automatic final delivery for the whole assignment.
Parent: `thread:delegated-task:command%3Amcp%3A7f0bf0df-35b9-48b9-bbf9-8f9cdcc3f584%3Adelegate-task%3Aclasher-card-lead-20261016-r1`.
Future/resumed child briefs repeat these rules. Independent review remains separate from implementation.

## Materialized one-use bundle

After prerequisites, use `/mpac/sdicks02/jobs/clasher/cards/c1/final-<integrated SHA first12>[-rN]` on04.
A failed/interrupted attempt keeps all evidence and its persistent claim. A retry requires a fresh suffix and
job audit. Never reuse the inherited `gate`, `verify`, `out`, `tree-r2`, or `out-r2` directories.

The run must be owned, canonical, real, mode0700, containing exactly `inputs/`, `ready.json`, `manifest.json`.
No old logs, PASS, output, dangling symlink or persistent claim is admitted. Every input is a private
single-link regular file or real directory: **no input symlinks, hardlinks, special files or external input
allowlist**. Dereference permitted read-only source material during separately authorized staging; do not
change permissions on the original. Materialize all roles, including transitive report modules, data and
Python packages. Input directories and controls are frozen without write bits before admission. The run
parent stays0700 so the driver can exclusively create its own `.gate-started/` and `output/`.

`inputs/` roles (all required, no other top-level entries):

| Role | Exact content / binding |
|---|---|
| engine | Entire tracked `engine-cards/` Git archive at integrated commit, including Python/gamedata/glue; no build products |
| native | Only `clasher_core.abi3.so` from the successful integrated build, matching receipt SHA and ELF magic |
| pinned-native | Only `clasher_core.abi3.so`, pinned681b5f2c866ba3df1aa9903d1bf40d565e21feb6f541319bef84ee493c72066b |
| r1 | Full materialized historical r1 runtime, including engine glue, src, models, report modules and data; inventory approved by owning lead |
| total-runtime | Byte-identical r1 files except engine-rs replaced by entire engine role, src replaced by engine/py/src, gamedata from engine/py/gamedata.json |
| bot | Entire tracked bot repository Git archive at declared bot_commit, including bot package and transitive tracked report modules/data |
| python | Standalone Python3.12.12 prefix with regular executable bin/python3.12, stdlib, lib-dynload, complete venv site-packages and native dependency libraries; full inventory approved by owner |
| fixtures | Frozen t1-split.json plus t1-trainval fixture inputs; all 577 train/validation IDs derive from split and existing fixture dirs |
| roots | Frozen roots-*.jsonl.gz and config-*.json inputs; sample is sorted Random(20261015).sample(range(total),300) |
| tools | Exactly final_gate.sh, final_gate.py, final_gate_contract.py, gate_worker.py, gate_fixtures.py, gate_roots.py, gate_compare.py from independently approved tools commit |
| evidence | Typed receipts plus raw review/build/tests/platform/input provenance under raw/ |

The driver authenticates source/tool/bot Git objects from an explicit local repository allowlist (C1, CARD
LEAD, main, bot checkouts); does not trust current checkout files or a claimed archive SHA. Engine and bot
file inventories must exactly equal their declared Git archives. Staging a bot revision with tracked symlinks
or submodules is rejected; an explicit reviewed materialization contract would be needed, not an ignore.
All r1/Python/fixture/root content is hashed recursively and bound to owner-approved platform/input evidence.
This is an owner attestation with checked identities, **not cryptographic proof that a human approved it**.
The lead must inspect/authenticate the actual evidence and approve that inventory before launch. The driver
cannot discover an omitted optional dependency by magic; isolated worker paths prevent imports falling back
to an unlisted checkout/site package. Missing dependencies fail the gate. The host OS/dynamic loader and fixed
control interpreter are trusted platform components; record their platform provenance in the raw evidence.
The worker verifies its actual sys.base_prefix is the frozen capsule and its version is3.12.12.

`manifest.json` is a JSON object keyed by canonical paths relative to inputs (including role dirs and empty
dirs). Each directory record is `{ "kind":"dir", "mode":320 }` (0500 example); file record adds
`"kind":"file", "mode":256, "size":N, "sha256":"<64hex>"` (0400 example; executable0555).
Inventory records must exactly equal recursive actual lstat/hash results. Duplicate JSON keys, traversal,
absolute/noncanonical/control-character paths, extra/missing files, write bits, links and unlisted roles fail.
Controls, evidence and helpers are included in repeated checks; output/control paths cannot masquerade as inputs.

`ready.json` has exactly these fields (angle-bracket values are deliberately unfilled):

```json
{
  "schema": 2,
  "integrated_commit": "<40hex>",
  "b2_accepted_commit": "<40hex>",
  "tools_commit": "<independently reviewed 40hex>",
  "bot_commit": "<40hex>",
  "native_sha256": "<64hex>",
  "source_repo": "/mpac/sdicks02/repos/clasher-cards-c1",
  "bot_repo": "/mpac/sdicks02/repos/clasher-bot",
  "manifest_sha256": "<hash of exact manifest.json bytes>",
  "receipts": {
    "b2": {"path":"evidence/b2.json", "sha256":"<64hex>"},
    "integration": {"path":"evidence/integration.json", "sha256":"<64hex>"},
    "build": {"path":"evidence/build.json", "sha256":"<64hex>"},
    "tests": {"path":"evidence/tests.json", "sha256":"<64hex>"},
    "launcher_review": {"path":"evidence/launcher-review.json", "sha256":"<64hex>"},
    "platform": {"path":"evidence/platform.json", "sha256":"<64hex>"}
  }
}
```

Every typed receipt requires matching `kind`, nonempty `authority` and `evidence_id`, and nonempty
`raw_evidence` mapping of evidence/raw paths to SHA256, all present in the manifest. Additional required fields:

- b2: `verdict=ACCEPTED`, matching `commit`, unique `required_integration_cases` list.
- integration/build/tests: `source_commit`, `native_sha256`, `engine_inventory_sha256`, `verdict=PASS`, integer
  `exit_code=0`. Integration adds matching `b2_commit` and `required_tests`: exact group-to-case-ID arrays,
  with counts above and B2 IDs matching accepted B2. A case-count total alone is insufficient.
- build: nonempty command argv, positive pid/pgid, ordered started_utc/ended_utc endingZ.
- tests: `groups` mapping all required groups to actual unique case rows `{case,verdict:"PASS",exit_code:0,
  artifact:"evidence/raw/...",artifact_sha256:"..."}`. Case IDs must match integration.required_tests and
  each actual artifact must be inventoried/hashed. Lead authenticates the artifacts' contents and exit receipts.
- launcher_review: `verdict=APPROVE`, `reviewed_commit=tools_commit`, `code_hashes` exactly seven tools basenames
  to hashes matching both Git and materialized files. Raw independent review must actually approve this revision.
- platform: `verdict=APPROVED`, `dependency_closure=materialized-no-symlinks`, `python_version=3.12.12`,
  and `python_inventory_sha256`, `r1_inventory_sha256`, `fixtures_inventory_sha256`, `roots_inventory_sha256`.

Inventory-binding hashes in these typed receipts use SHA256 over Python
`json.dumps(content_map, sort_keys=True).encode()` (default separators/ensure_ascii), where content_map maps
all role-relative file names to SHA256, excluding directories; the outer manifest independently binds modes,
sizes and empty dirs. Keep exact raw evidence alongside each typed translation; never replace a rejected report
or failed artifact with a later PASS. The tests module supplies synthetic schema examples; none authorize a run.

## Driver/result contract

The shell must be entered with `/bin/bash -p`; env-i is also applied **before cpu_job.sh** so neither wrapper
nor child can reload inherited BASH_ENV. The driver uses a fixed isolated control interpreter, checks04 host
and its direct parent's existing8-slot lease/PGID, and exclusively claims before control validation. It keeps
the exact originally read ready/manifest bytes; validates without generating a new trusted baseline; rechecks
those bytes and the full frozen inventory before fixtures, before roots, before comparator, and at completion.
No environment from the caller reaches workers. Logs record the effective minimal environment/per-arm roots.
Workers fix r1 policy, remove stale EVAL root, isolate sys.path, disable site/.pth processing and bytecode,
use nice15 and single-thread BLAS/OMP/Rayon. No ambient overlays, Python optimization, pin policy or loader preload.
Workers use -P -s -S -B under the explicit clean environment, keeping PYTHONHASHSEED=0; bootstrap requires
hash_randomization=0, safe_path, no_site and no_user_site. The control interpreter alone uses-I (no engine
operations): -I would ignore PYTHONHASHSEED and is intentionally not used for gate workers.

Fixtures: two parents, three pool workers each. Individually wait both, record exit statuses, then audit exact
577 IDs/schema/chain hashes/ticks/action counts/results, native import path and cross-arm bytes before roots.
Preserve historical Python/native lockstep residuals: no requirement that every start/first mismatch agrees
with Python. Roots: eight individually waited workers, four shards per arm; deterministic300 IDs, full/cut
pairing and assignment; all header fields, source identities, action sampling and checks validated. Required
per-root checks: actions×3 rollouts, seven evaluation parts, evaluate, two views/masks, three selections, three
cumulative steps (1,50,200), snapshot hash, and apply+step40 when sampled plays exist. Cross-arm bodies must
be byte-identical. The descriptive unchanged comparator is separately waited; a nonzero exit also rejects.

All generated paths are exclusively created with nofollow; no inherited gate.sh/bare wait. Helpers only
reopen reserved regular output files in an owned nonwritable directory. Phase receipts include every PID/PGID,
command, exit/signal and UTC. Interrupted children are stopped by exact owned child PGIDs and waited, never
pgrep/pkill. Failure leaves claim, raw logs, per-phase and all-child exits and FAIL.json; roots never start after
failed fixture exits/audit. Success is written to exclusive .PASS.tmp, atomically linked without clobbering to
PASS.json, then temp removed; any publication exception removes PASS. Accept only PASS with outer launcher
exit0 and matching launch/baseline/phase receipts, no FAIL. A SIGKILL/power loss cannot supply a valid outer exit.
Each observed child status is stored by unique label before its live entry is removed. If a later wait raises,
phase-exits.json preserves the partial observations; cleanup retains them and publishes phase-final-exits.json
and all-child-exits.json with the complete union, without duplicates or overwritten statuses. Cleanup blocks
TERM/INT/HUP until children and receipts finish, then restores the signal mask so pending cancellation prevents
PASS. SIGKILL/power loss remain detectable through missing outer exit/complete receipts, not catchable cleanup.
Phases are registered before any spawn. Spawn/PID registration and phase-receipt writes also defer these
signals; workers immediately reset their inherited mask before gate dispatch. A stop at spawn completion
therefore leaves a tracked PID and final phase/all-child receipts even if the phase wait was never entered.

After review/prerequisites/job audit, the **later owner-approved** invocation is (not run here):

```bash
setsid /usr/bin/env -i PATH=/usr/bin:/bin LANG=C.UTF-8 LC_ALL=C.UTF-8 USER="$(/usr/bin/id -un)" \
  /mpac/sdicks02/repos/clasher-bot/bot/exit/cpu_job.sh 8 \
  /bin/bash -p "$RUN/inputs/tools/final_gate.sh" \
  "$RUN" "$INTEGRATED_SHA" "$NATIVE_SHA" "$B2_ACCEPTED_SHA" "$TOOLS_COMMIT" \
  </dev/null >/dev/null 2>&1 &
```

Capture $! and its actual PGID plus final outer status in an independently approved owner/shepherd receipt;
do not infer successful launcher exit from PASS alone. No new watcher or staging/host script is provided by
this plan. Any new/changed host-touching script requires separate independent review before execution.
The outer wrapper requires USER for its two ps user selectors; derive it from actual identity as above,
never drop it or restore the caller's arbitrary environment. The inner driver/worker environments stay clean.

## Review/rollback

r1 findings and failed scratch artifacts remain at CARD LEAD `reports/cards/reviews/C1-final-tools-r1.md`
and `/mpac/sdicks02/jobs/clasher/cards/c1-final-tools-review-local/`. Revised local checks import only pure
validators and AST-extracted wait/filesystem functions with fake processes. No native/engine/host driver runs.
See scoped `reviews/` for candidate-bound fresh independent verdict, exact hashes and local command receipts.

Rollback this tools repair by reverting its scoped commit(s), **without executing the rejected old launcher**.
For engine fallback retain f68e5f80f and unchanged native631ac artifacts, plus historical native2ac gate artifacts;
no runtime/live-pin rollback is necessary because none was changed. Combined-source/B2 gates remain pending.
