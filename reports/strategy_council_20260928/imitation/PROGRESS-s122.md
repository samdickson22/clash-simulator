# S122 data track — T9 / T10

Current status: **T9 PASS; T10 QA PASS; production running on 127x01 and 127x03.**
T1 receipt received and verified. Details and operational history below.
Code/docs authored on 127x05; all data parsing, downloading and extraction on 127x03/01.
Frozen C56 runtime/extractor and gamedata are read-only. No commits, deletions, or broad tree copies.

Source: `VanguardX101/IL_Replay`, revision `059d43a02138a34b1b3009cc2acc7630fb99a638`.
Download-only directory on 03: `/mpac/sdicks02/repos/clasher-local-data/il_replay/`.
Only pinned parquet files are downloaded; dataset content is never executed.
Output root: `reports/strategy_council_20260928/imitation/data/` on fleet.
Scope: 121 cards (Three Musketeers excluded on either side); Battle Healer and Mirror flagged.
C56 assignments remain frozen. Cross-version match leaks must be excluded on the new side.

Predeclared T10 gates: 400 perspectives covering each of the 65 admitted new own cards at least 3 times;
placement acceptance >=0.99 overall, 0 illegal labels, determinism on 6 perspectives,
per-card acceptance/retention reporting, exclude any new own card with acceptance <0.95;
zero truth-audit violations; production errors zero or isolated per-perspective errors <0.5%.
Workers plus other Clasher workers <=80 per host, <=16 with console user. Hosts 01/03 only.

Fetch launch label: `imitation-s122-fetch-20261008-r1` on 127x03.
Resume (new label after nonzero exit; existing files verified and reused):
`bash reports/strategy_council_20260928/fleet/fleet_run.sh imitation-s122-fetch-20261008-r2 .venv/bin/python reports/strategy_council_20260928/imitation/s122/fetch_source.py`

Operational records (2026-10-08 UTC):
- Fetch: PID 3393344, label `imitation-s122-fetch-20261008-r1`, exit 0. 104 pinned parquet files verified.
- C56 refilter: PID 3393699 on 03, label `imitation-s122-c56-refilter-20261008-r1`.
  Original filter executed with source-path bindings redirected to the freshly fetched pinned parquet.
  Gzip metadata is reproduced from the original archive; raw JSONL and compressed archive comparisons are independent.
- D1 waiter: PID 3399855 on 01, label `imitation-s122-wait-d1-20261008-r1`.
  Status: `data/receipts/s122-d1-wait.json`. It polls every 300 seconds for <=24 h.
  Receipt appearance does not itself release extraction: API/pins and QA still must pass.
- Role extension retains old families and salt `c56-roles-v1:`. New held-out sides opposite frozen C56 train
  become excluded_leak; new train opposite old held-out/excluded roles is also excluded. No v1 assignment changes.
- QA selection: salted hash, rare-card-first minimum 3 perspectives with actual recorded plays of each of 65 new cards,
  hash-fill to 400. Six separate hash-selected cases for determinism. No outcome-based sample replacement.

## T9 PASS (2026-10-08 02:55 UTC)

- All 104 pinned parquet files / 1,888,381,137 bytes verified. Fetch 31.04 s wall on 03.
- C56 equality: **52/52 raw JSONL payloads and compressed gzip archives byte-identical**.
- New S122 payloads: **333,934 perspectives**, 198,907 matches. Pre-exclusion 355,585
  exactly reproduces design count; 21,651 new perspectives excluded for Three Musketeers.
- Flags among new perspectives: Battle Healer 4,090; Mirror 1,950.
- Per-card counts: `S122-CARD-COUNTS.tsv` and `data/receipts/T9-payloads.json`.
- Roles v2: 416,165 total entries; all 82,231 v1 assignments unchanged. Counts:
  train 320,768; dev 16,772; eval 16,134; eval_ood 15,052; excluded_leak 47,439.
  New-only: train 251,388; dev 13,226; eval 12,369; eval_ood 11,281; excluded_leak 45,670.
  29 new S122-only OOD families; zero train/held-out match leaks.
- **T11 consumer requirement:** `index/c56-v2-metadata.json` and the roles-v2
  `v2_actor_ineligible_frozen_c56_keys` exclude 2,361 old C56 perspectives with a Three Musketeers
  opponent from the v2 actor corpus. Their historical v1 roles remain unchanged. Old C56
  Battle Healer/Mirror metadata is provided separately in that index metadata file.
- QA sample fixed: 400 perspectives, all 65 admitted new own cards played in >=3 selected
  perspectives; six fixed determinism cases. Sample SHA `718a17d96dd2984facc6304fc2446181cb2d24e349fe6e62ab98556777393b58`.
- T9 prepare label `imitation-s122-prepare-20261008-r1`, PID 3395388, exit 0.
- Packing/copy label `imitation-s122-pack-mirror-20261008-r1`, PID 3397683 on 03; running.
  Copies only explicit product files to 01/04, then verifies every destination SHA256.
- Independent QA input packaging: `imitation-s122-pack-qa-20261008-r1`, PID 3399483 on 03.
- T1-PASS arrived; receipt hashes verified against hub sources. It reports 319,077 exact
  elixir checks and 2,015,370 known-fact checks, zero conflicts. D1 wait exit 0 at 02:53:34Z.

T10 source: `s122/extract_s122.py`, `qa_s122.py`, `finalize_s122.py`.
Each unit invokes the unchanged frozen replay with T2's observer; sidecar truth is separate.
Terminal context rows use the same observer on the retained final battle. Six cases compare
full NPZ bytes with an independent no-observer run and an observer repeat; sidecars/audits/events
also repeat exactly. Pre-registered QA bars unchanged. T10 has not started yet.
Production reserves 64 processes for the C56 pass until its complete manifest exists, checks
actual same-user Python/Clasher process counts, and grows only into available capacity.

## T10 running QA (2026-10-08 03:01 UTC)

- QA input fast-pack complete, exit 0, 400 fixed inputs copied to 01.
- QA r1 (`imitation-s122-qa-20261008-r1`, PID 3407338) refused before extraction:
  the initial resource counter included shell/time/rsync wrappers. Fixed the operational
  counter to actual compute executables; no sample, bars, engine, or observer changes.
- QA r2: label `imitation-s122-qa-20261008-r2`, launcher PID 3407872, driver PID 3407885
  on 01, eight workers. Status `data/qa/s122-qa/status-127x01-0.json`.
- QA follow-on: `imitation-s122-qa-finish-20261008-r1`, PID 3408380 on 01. Waits for r2 exit 0,
  runs six repeats and six no-observer baselines (two workers), then checks every fixed bar.
- Temporary production job packing r1 was stopped via verified Python PID 3398907 with
  SIGTERM (receipt `data/receipts/pack-r1-stop.json`). Only job-input gzip compression is
  reduced from 9 to 1. Existing packed inputs are reused after decompressed byte equality;
  any interrupted file is renamed and retained, never deleted. Canonical T9 payload archives,
  frozen runtime and recipe are unchanged.
- Packing/copy resume: `imitation-s122-pack-mirror-20261008-r2`, PID 3400505 on 03.
  It will copy the explicit T9+input file list and independently verify SHA256 on 01/04.

Prepared production launch (after QA-PASS and pack/mirror exit 0):
`bash reports/strategy_council_20260928/fleet/fleet_run.sh imitation-s122-production-20261008-r1 bash reports/strategy_council_20260928/imitation/s122/start_production.sh`
Run once on 01 and once on 03. Partition 0 is 03; partition 1 is 01. Up to 78 pool workers,
with initial dispatch reserving 64 for C56, and accounting for other compute processes.
Unchanged successful unit receipts are hash-verified and reused. Resume with a fresh fleet label.

Prepared collection/verification/copy (01 only):
`bash reports/strategy_council_20260928/fleet/fleet_run.sh imitation-s122-finalize-20261008-r1 .venv/bin/python reports/strategy_council_20260928/imitation/s122/finalize_s122.py`

Production supervisors launched, **waiting on gates**, not yet extracting:
- 01 launcher PID 3413029, 03 launcher PID 3403323.
- Both use `imitation-s122-production-20261008-r1`; node-local logs and `.exit` under jobs/clasher.
- They require T10-QA-PASS and successful checked T9 packing/copy before invoking extraction.
- Final collector will mirror only small T10 receipts to 05 and append completion to this progress file.

## T10 QA PASS; production active (2026-10-08 03:15 UTC)

QA: 400/400 perspectives, 277,822 rows (277,281 supervised), zero extraction errors,
zero illegal labels, zero truth-audit violations in all five columns. Placement acceptance
**0.9958936562** (78 rejections / 18,995 attempts); retention **0.8077588618**.
Each of 65 new cards had placement attempts. Lowest new-card acceptance: Phoenix **0.9714285714**.
**No additional actor cards excluded.** Six independent repeats and six no-observer replays
produce identical NPZ bytes; repeated sidecars/audits/events also identical.
QA on 01: 490.12 s wall, 3,786.70 worker CPU-s (additional six+six checks recorded separately).
Golden Knight: 82 own ability events, all rejected by the frozen oracle (64 masked, 18
unattributable), zero labelled ability actions. This is reported, not patched.
Receipt: `data/receipts/T10-QA-PASS.json`, including per-card acceptance and retention.

T9 copy: 7,953 explicit products / 3,087,264,038 bytes on both 01 and 04,
independent SHA256 verification with zero mismatches. 6,984 production units, 48 perspectives
per full unit. Full role JSON (76 MiB) stays on fleet; small summaries mirrored to 05.

Active launches:
- **01 production:** `imitation-s122-production-20261008-r1`, launcher PID **3413029**,
  driver PID **3413053**, partition 1/2, initially 11 workers (dispatch now respects lower
  available capacity as collector processes start). Status:
  `data/recon/engine-v3-s122/status-127x01-1.json`.
- **03 production:** `imitation-s122-production-20261008-r3`, launcher PID **3405970**,
  driver PID **3405983**, partition 0/2, initially 13 workers. Status:
  `data/recon/engine-v3-s122/status-127x03-0.json`.
  r1 was only a waiter; self-SSH was unavailable. Its verified shell PID 3403336 was stopped
  with SIGTERM and the waiter switched to local receipt reads. r2 stopped before replay
  because the T1 test-source file was missing on 03. Copied only the absent T1 test/verification
  files from hub with `rsync -c --ignore-existing`, and verified the complete source pins
  equal QA before r3. No extractor, runtime, observer, or QA threshold change.
- **01 collector:** `imitation-s122-finalize-20261008-r2`, launcher PID **3416606**.
  r1 exited safely when the 03 startup failed. Current collector tracks remote r3/local r1.
- **01 capacity propagation:** `imitation-s122-capacity-release-20261008-r1`, PID **3415942**.
  Copies only the authoritative completed C56 manifest to 03 with `--ignore-existing`, verifies
  its checksum, and never overwrites it. Both S122 supervisors then see the same C56 completion
  gate and can expand within actual process limits. No bulk C56 outputs copied by this helper.

Resume a stopped production partition on its original host with a new fleet label and:
`bash reports/strategy_council_20260928/imitation/s122/start_production.sh`
All successful unit receipts are checksum-verified and reused. Never change the pinned driver,
D1 modules, runtime or recipe during a run. Inspect the recorded failure first.
Resume collection on 01 with a fresh fleet label and:
`.venv/bin/python reports/strategy_council_20260928/imitation/s122/finalize_s122.py --remote-label imitation-s122-production-20261008-r3 --local-label imitation-s122-production-20261008-r1`
Set those labels to the actual resumed launches if they differ.

Production estimated CPU work from fixed QA: about 878 CPU-h. With C56 finishing in roughly
1–2 h and the reserved capacity then released, estimated completion about **7–9 h from 03:15 UTC**.
This is an estimate, not a completed extraction claim. Completed-unit rows, errors, wall/CPU
and file sizes will be reported by the final receipts. The collector validates all file hashes,
rows, isolated-error fraction <0.5%, zero illegal labels, and zero audit violations, then
checksum-copies to 04 and mirrors small receipts to 05. Production copy is pending.

## Published production snapshot (03:18:44 UTC)

- 127x01: 11 units / 528 perspectives / 386,240 rows; 53,880,254 published bytes; 524.3 s wall; 5614.66 CPU-s including active workers. Zero published errors/illegal labels/audit violations.
- 127x03: 0 units / 0 perspectives / 0 rows; 0 published bytes; 284.5 s wall; 3732.79 CPU-s including active workers. Zero published errors/illegal labels/audit violations.

01 retention 80.5754%, placement acceptance 99.6805% so far. 03 is still inside its first 48-perspective units; no published rows yet. QA products occupy 80,946,889 bytes on 01. Production copy to 04 remains pending, handled by the collector. These running snapshots are not final QA receipts.

## Stable handoff snapshot (both hosts have verified production units)

- 127x01, 2026-10-08T03:21:53.229114+00:00: 11 units; 528 perspectives; 386,240 rows; 53,880,254 bytes; retention 80.575437%; placement acceptance 99.680489%; 712.77 wall-s; 7505.67 live worker+driver CPU-s. Zero errors/illegal labels/audit violations.
- 127x03, 2026-10-08T03:21:53.746886+00:00: 11 units; 528 perspectives; 393,937 rows; 55,481,097 bytes; retention 80.934182%; placement acceptance 99.680674%; 474.41 wall-s; 6191.79 live worker+driver CPU-s. Zero errors/illegal labels/audit violations.

Total published: 1,056 perspectives, 780,177 rows, 109,361,351 bytes. Both partitions are stably running, collectors active. Final production QA/copy remains pending; no T10-PASS claim yet. Snapshot: data/receipts/T10-running.json. No commits made.

## Fleet expansion preflight blocked (2026-10-08 05:20 UTC)

Requested addition of 127x04/08 stopped under the explicit safe-repartition rule.
No new partition receipt, production labels or PIDs were created. Evidence:
`data/receipts/T10-fleet-expansion-blocked-20261008-r1.json` (hub and 05).

The checksum-matched live driver (`s122/extract_s122.py`, SHA256
`48b86d893836940393ff6dff374a863719e9512a25a6481edffb7cd56ab4eb63`)
loads the full production plan once, slices `units[partition::partitions]`, and retains
`todo=iter(units)` in memory. No unit ownership handoff, plan reload, or per-unit claim
lock exists. Both 01/03 already own all 6,984 units between them; assigning their
unstarted suffixes elsewhere would leave the originals scheduled and risk duplicate work.
The driver and start script reject 04/08, and the driver is itself part of frozen QA pins.
The live finalizer only collects 03 parity 0 and 01 parity 1. Safe expansion would require
stopping/repartitioning the existing jobs or an orchestration change; neither is authorized.

At 05:19:48 UTC neither S3 label (`s3-confirm-node-127x04-r1`,
`s3-confirm-node-127x08-r1`) had an exit receipt. Both hosts had zero console users and
1-minute loads about 76. Polling stopped at this independent preflight blocker;
S3 jobs were untouched. 04/08 input/pin verification and transfers were not attempted.

Existing verified jobs continue unchanged:
- 01 `imitation-s122-production-20261008-r1`: launcher 3413029, driver 3413053,
  partition 1/2; snapshot 488 completed units, 23,344 attempted perspectives,
  16,272,527 rows, zero errors, 72 in flight.
- 03 `imitation-s122-production-20261008-r3`: launcher 3405970, driver 3405983,
  partition 0/2; snapshot 615 completed units, 29,424 attempted perspectives,
  20,430,644 rows, zero errors, 77 in flight.
- 01 collector `imitation-s122-finalize-20261008-r2`: launcher 3416606, still waiting
  for partition 0. Its existing checksum validation and final copy to 04 remain active.

Before-expansion throughput measured from published receipt mtimes over the preceding
15 minutes: 01 152 units / 7,296 perspectives (29,184 perspectives/h),
03 195 units / 9,309 perspectives (37,236 perspectives/h), total **66,420 perspectives/h**.
No after-expansion measurement exists because no expansion launched.
Per-host remaining-unit estimates account for the static partition imbalance:
01 about 4.94 h remaining, 03 about 3.69 h. Updated extraction ETA approximately
**2026-10-08 10:20 UTC**, assuming these rates and similar remaining unit costs;
collector validation and checksum mirror take additional time. This is an estimate,
not a final T10-PASS claim. No commits, deletions, process stops, or pinned source edits.
