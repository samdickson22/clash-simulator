# Imitation data implementation (T0–T3)

Started 2026-10-08 UTC. Code is authored on 127x05; all execution is on 127x01/03.
No commits. Frozen runtime, extractor, roles and evaluation recipe remain read-only.

- T0: PASS. The hub lacked `fleet/gpu_env.sh` and `gpu_check.py`; exact copies
  are staged in the new `imitation/t0/` directory, without replacing fleet files.
- T1: PASS. Deck-free public-event ledger and own cycle qualified against oracles.
- T2: PASS. 82,231 perspectives, 64,140,802 rows; zero violations; copy on 04 verified.
- T3: PASS published 06:42:32 UTC under coordinator's decoupled release decision.
  COMPLETE: all requested copies verified; P16 receipt published 08:17:06 UTC; poll disabled.

T1 PASS published on 127x01 and mirrored to 05. 319,077 exact elixir comparisons,
2,015,370 known facts, zero conflicts. Includes 74,440 development (74,424 plus
16 terminal), 209,575 confirmation, 23,058 srp and 12,004 Collector (12,002 plus
2 terminal) checks. 8 Collector grants and 12 abilities. Five unit tests pass.
The full development suite took 484.77 s wall / 484.57 s CPU; detailed timings
are in `data/receipts/T1-PASS.json`. API is described in `DATA-CONTRACT.md`.

T0 PASS: installer `imitation-t0-env-20261008-r1` PID 3396798, exit 0;
GPU suite `imitation-t0-check-20261008-r1` PID 3397566, exit 0, 82.32 s wall /
91.26 s CPU. All required checks pass; torch.compile is the expected optional
failure on driver 470. Receipt: `fleet/imitation-t0-gpu-check-127x01.json`.

T2 pilot `imitation-t2-pilot-r2`, PID 3401417, exit 0: 48 perspectives, 37,821
rows, 31 non-header arrays logically equal plus exact header/summary equality,
zero elixir/hand/queue/refill/own-cycle violations. 287.02 s unit wall.
Output: `data/c56-sidecars-r2/`. Initial pilot r1 stopped safely on the extra
unsupervised terminal context row: the frozen hook omits it. The adapter now
captures the retained final battle after return; no frozen source changed.
No data deleted. No fallback needed.

T2 production completed with 64 workers each on 01/03 (128 total). Node03 had
only 1,248 original units, so a complete read-only comparison copy is staged
under fresh `imitation/data/c56-input-v1/` on 03 from the hub; no C56 file on 03
is overwritten. Production output is `data/c56-sidecars-v1/`.

Production labels and launcher PIDs:
- 01: `imitation-t2-production-01-v1`, PID 3404410, partition 0/2, exit 0
  at 04:43:33 UTC: 884 units, 41,102 perspectives, 32,080,827 rows, zero
  violations. 1h50m23s wall / 412,308.14 s process CPU (including setup).
- 03: `imitation-t2-production-03-v1`, PID 3398212, partition 1/2, exit 0
  at 04:34:40 UTC: 883 units, 41,129 perspectives, 32,059,975 rows, zero
  violations. 1h40m31s wall / 375,568.63 s process CPU (including setup).
- Input staging/checksum: `imitation-t2-stage-input-v1`, PID 3404417, exit 0.
- 01 continuation: `imitation-data-finish-v1`, PID 3406691. Waits on the exact
  two production exit receipts, then collects 03 outputs, finalizes, checksum
  mirrors to 04, builds the store, computes baselines, copies/verifies to 04/08,
  and writes T2/T3 PASS receipts. Script: `finish_data.py`; resumable by a fresh
  fleet label. Status: `data/operations/continuation-status.json`; failures:
  `data/operations/continuation-blocked.json`.

Resume production after inspecting exit/log/PID (never duplicate a live label):
`bash reports/strategy_council_20260928/fleet/fleet_run.sh NEW-LABEL .venv/bin/python -B reports/strategy_council_20260928/imitation/replay_sidecars.py --out reports/strategy_council_20260928/imitation/data/c56-sidecars-v1 --partition 0 --partitions 2 --workers 64`
For 03 use partition 1 and prefix the Python command with
`env CLASHER_C56_RECON=/mpac/sdicks02/repos/clasher/reports/strategy_council_20260928/imitation/data/c56-input-v1`.
Completed units recheck all file checksums and audit violations on resume.

Header provenance decision ACCEPTED: COORDINATOR.md 2026-10-08 03:40 UTC.
independent `verify_header_contract.py` regenerated the authoritative global
header via the frozen writer and compared all 1,767 original archives. All
common fields match; 270 originals carry the historical v3 runtime SHA
`af205b0bc8614ff8a2ac794c7af0708f8822fe29681fccf6fd8ba7eaebe7ba82`,
while actual replay is required v3b `1ec2c60c254fd9cc5579b163ef994a0e233a942bd97acda864d31d91442d3493`.
The aligned replay retains original headers; actual provenance is in the
sidecar manifest. Evidence: `data/c56-sidecars-v1/header-contract-audit.json`.
The explicit exemptions are `extra.reused_v2_episode_ids`, `extra.v2_sha256`,
and `extra.runtime_sha256` (only the two pinned SHA values above). Every other
header/summary field must match; every array must match dtype, shape and C-order
values. Original headers stay unchanged. Successful v3b reproduction of the
270 v3-era units is additional determinism evidence, recorded in the audit.
The audit passed under fresh label `imitation-t2-header-audit-v3`, PID 3417927,
exit 0 (20 s wall): 1,767 headers checked, all 270 historical unit IDs recorded.
Six negative checks reject an unknown runtime SHA or changes to phase, shard,
part, extraction and an unexpected field. Receipt mirrored to 05 at
`data/receipts/header-contract-audit.json`. Production
and `imitation-data-finish-v1` continue unchanged. The verifier change does not
require their restart. T2 PASS still requires the full replay and checksum gates.

T3 code prepared (`build_store.py`, `packed_store.py`, `baselines.py`). Real
pilot-store smoke round trip passes all 45 retained perspectives/34,545 rows;
3 excluded_leak perspectives omitted. Final smoke: `data/store-smoke-v2`,
`imitation-t3-store-smoke-v3`, PID 3408585, exit 0. `passed=false` deliberately;
only `smoke_passed=true`. Earlier smoke found/fixed a duplicate manifest key.
Balance uses the minimum of the two frozen sqrt caps, not their product.
Four loader/metric/phase/timing-denominator tests pass;
`imitation-t3-tests-v3`, PID 3420408, exit 0, 8.08 s wall / 7.43 s CPU.
Baselines retain the frozen all-row timing metrics and add explicit playable-row
timing/calibration metrics for comparison with the model's DESIGN denominator.
P16 CPU scoring partitions whole units across two workers, preserving each
perspective's recurrent state; CPU receipts include child process time.
Scorer/spawn TRAIN smoke: `imitation-t3-p16-partition-smoke-v1`, PID 3421414.
Passed: one train perspective, 587 supervised/playable rows, 17.42 s scorer
wall. Receipt `data/receipts/t3-p16-partition-smoke.json` mirrored to 05.
P16 upgrade/forward plumbing passes on one TRAIN perspective (589 rows, ten
recurrent chunks), `imitation-t3-p16-smoke-v2`, PID 3412437, exit 0, 25.11 s wall /
24.41 s CPU. Receipt `data/receipts/t3-p16-smoke.json` mirrored to 05.
The initial attempt failed the prescribed upgrader's descriptor guard: five
values across Goblins/IceSpirit/IceSpirits differ between checkpoint gamedata
daa58b28 and extraction gamedata 3d99987c. `p16_upgrade.py` copies checkpoint
descriptor rows into a private builder copy and then calls the unchanged
`contract_v5.upgrade_policy_payload_to_v5`. Every existing checkpoint tensor
(including descriptor buffers) is asserted unchanged after remapping. No
checkpoint or frozen runtime was modified; this smoke used train rows only.

T2 PASS published at approximately 04:46:49 UTC. All 1,767 units / 82,231
perspectives / 64,140,802 rows reproduce; all five truth-violation counts zero.
Completed-unit CPU time: 786,942.55 s (218.60 h). Process CPU including setup:
787,876.77 s. Replay wall 1h50m23s. Copy on 04 verifies 7,068 artifacts,
9,198,923,857 bytes; manifest SHA 1a18b263bd0d2d44aee75491e82aa89e152c8a8474cca6d664128c0fc2790cb6.
Coverage and T2 PASS receipts mirrored to 05. The original continuation PID
3406691 has advanced to T3 store building; no restart or blocked receipt.
At 04:48 UTC, S122 has expanded to 78 configured hub workers. Before baseline
preregistration/fitting, P16 scoring was reduced from eight workers to two to
respect the shared 80-worker cap. No metric or statistical recipe changed.
T3 PASS remains absent. The accepted-header audit passed under fresh label
`imitation-t2-header-audit-v4`, PID 3443852, exit 0 at 04:47:48 UTC: all 270
historical units' completed replay receipts now verify. Updated audit copied
with checksum equality to 04 and mirrored to 05.
The 270-header provenance decision is accepted as recorded above.
Other workers must still wait for the actual verified `data/receipts/T3-PASS.json`.

T3 checkpoint 05:16:59 UTC: store manifest PASS, 1,767 units written, all 805
sampled perspectives pass exact round trip. Independently checked role counts
against the frozen role file: train 69,380 / dev 3,546 / eval 3,765 / eval_ood
3,771 perspectives. Rows respectively 53,989,262 / 2,759,722 / 2,943,085 /
2,885,746. Build 1,205.49 s wall / 781.14 s CPU; root manifest SHA
1acf6b5875091e009c18e598a71714016b9833b6cc626032e0fa676ccdac5c2f.
Frequency scoring complete: 46.75 s wall / 45.87 s CPU. Joint NLL dev/eval/OOD:
0.438199 / 0.436319 / 0.425070; card NLL 1.424337 / 1.404350 / 1.599666;
tile NLL 4.017820 / 4.029418 / 4.048951. Small baseline JSON and store manifest
mirrored to 05 receipts. P16 scoring runs with two workers, original continuation
PID 3406691 still live; no blocked receipt. Baseline source is now frozen by
prereg.json (recipe SHA 45c14463ee57798cef59d5c9d33a5caeccedfc11353c41b35445f0769ea74a84).
No console users; 78 busy Clasher processes on each host. No restarts.

P16 checkpoint 06:37:19 UTC: dev scoring completed at 06:36:37 UTC,
648/648 perspectives, 505,669 supervised rows and 26,328 plays. Joint NLL
0.4187397683; when NLL 0.1789347266 (playable 0.1846920516); card NLL
1.0333683455, top1 0.5372607110, top3 0.9299604983; tile NLL 3.5724496296,
median tile error 3; ECE 0.0086816557. Receipt mirrored to 05 at
`data/receipts/baselines-v1/p16-bc-dev.json`. Original dev workers exited;
the same parent 3449355 automatically launched eval workers 3510500 / 3510503,
each at 41 s elapsed / 41 s CPU. Eval target remains 705 perspectives.
Supervisor 3406704 live; no blocked receipt, source SHA matches preregistration.
Copies and T3 PASS remain pending. No manual restart or source change.

Coordinator hang investigation 05:44–05:54 UTC: no deadlock observed. P16 parent
3449355 waits in futex for two **spawned** workers, 3449692 and 3449695. Both
are single-threaded and CPU-active. Over 93.9 s they consumed 93.31 / 93.27 s
CPU, read 7,108,478 / 10,879,765 additional bytes and made 522 / 816 reads.
At 05:52 each had 43m30 CPU over 43m50 elapsed. Parent CPU staying at 11 s is
expected: ProcessPoolExecutor returns partition results only after each whole
partition. There is no intermediate per-perspective heartbeat. Torch is already
single-threaded and workers use spawn, not a post-Torch fork. py-spy stack dumps
were denied by ptrace policy; noninteractive sudo requires a password. No signals,
source changes to the preregistered baseline, restarts or lost work. Evidence on
01: `data/diagnostics/p16-liveness-{a,b}.json`, `p16-diagnosis.json` (the latter
mirrored as `data/receipts/p16-diagnosis.json`). Supervisor 3406704 remains live.

The coordinator now explicitly authorizes certified store copies to leased
127x11/13/14/16/18. Read `fleet/LEASED-HOSTS.md` and
`/mpac/sdicks02/cc/FLEET-SHARING.md`; all five live leases validated at 05:54,
no console users, at least 1.69 TB free, and lease-host SSH reads from 01 work.
Only these five newly authorized targets are contacted. T3 certificate still
absent: no leased store transfer launched. The unchanged original supervisor
will first complete P16, copy/verify 04/08, then publish T3-PASS.

Prepared `copy_leased_store.py`: receiver validates actual T3 certificate and
its 04/08 manifest hashes, copies an explicit manifest-derived list with rsync -c,
requires an empty checksum dry run, verifies every artifact SHA and retains the
certificate. SIGTERM stops its verified active child and exits; wrapper enforces
lease/resource caps. Only stdlib, bounded memory, one transfer at a time.
Hub syntax check `imitation-lease-copy-syntax-v1`, launcher 3481955, exit 0,
0.05 s wall / 0.04 s CPU. No bulk data or tests run on 05.

Leased-copy continuation (after actual T3-PASS): re-read target lease and hub
`/mpac/sdicks02/jobs/clasher/lease-ready-HOST.json`, inspect owned wrapper state
and console users. Stage only owned `copy_leased_store.py` and
`verify_artifacts.py` with rsync -c from 01 into a fresh/owned
`/mpac/sdicks02/repos/clasher-lease/data/imitation-copy-v1/`. Launch each host
sequentially, with fresh label `imitation-store-copy-HOST-v1`, using only:
`source /mpac/sdicks02/repos/clasher-lease/env.sh; bash /mpac/sdicks02/repos/clasher-lease/run.sh LABEL /mpac/sdicks02/repos/clasher-lease/repo/.venv/bin/python -B /mpac/sdicks02/repos/clasher-lease/data/imitation-copy-v1/copy_leased_store.py`.
Never source the shared env or use fleet_run on leased hosts. Check wrapper
`.exit.json` status pass, helper `data/imitation-copy-v1/receipt.json`, checksum
dry-run empty and certificate SHA against 01. Preserve each hub readiness
receipt in our operations directory before updating ONLY its data fields with
verified evidence (`data_copied`, `ready_for_gpu_training_on_c56_store`,
`data_note`, store path and copy receipt). Mirror small copy receipts to 05.
On failure preserve logs/data and inspect before a fresh-label resume; never
duplicate a live wrapper. No training is launched by this worker.

Temporary data-worker continuation poll: every 10 minutes in this same T3 thread,
first run 2026-10-08 03:36:34 UTC; disable after verified copies to 04/08 and
11/13/14 plus separate P16 baseline receipt, or an unresolved
external blocker (deadline 2026-10-09 03:30 UTC). Scheduler ID:
`scheduled-task:command:mcp:b1656a57-211a-4456-ab5e-d0075b77ded5:schedule-task:clasher-imitation-data-finish-poll-20261008-v1`.
No active fleet job was restarted. Header audit v4 is complete, with all 270
historical unit IDs and completed replay receipts verified; copies on 01/04/05.

Jobs use `fleet/fleet_run.sh`; labels, PIDs and resume commands will be recorded
here when launched. Logs and exit receipts: `/mpac/sdicks02/jobs/clasher/`.

Resource incident 06:07 UTC: hub `who` now shows sdicks02 pts/0 from
127.0.0.1. Read-only process metadata counts 82 Clasher Python processes,
64 running; aggregate is above the 16-process console-user cap. Our P16
uses two CPU workers. No new workload launched and no other worker touched.
Coordinator adjustment of other hub workloads is required while this session
remains. Original healthy P16/supervisor preserved; T3 PASS still pending.

06:27 UTC resource recheck: console session persists, 81 Clasher Python
processes (75 running). No new workload launched; the two P16 workers each
advanced another 600 CPU seconds. No failure receipt or completed P16 role yet.

06:37 UTC resource recheck: console remains. 82 Clasher Python processes
observed (11 running, 71 sleeping); other-worker outputs were not inspected.
Our new eval pool has the same two-worker cap. No new manual workload launched.

Coordinator decision 06:41 UTC supersedes the coupled completion path and prior
console alarm: P16 is gate A2 only, not a training-store prerequisite. Our own
fleet-monitor pts sessions were not console users. Use
`~/.local/bin/fleet-console-users` from now on; count zero on 01/04/08 at launch.
No other worker was changed. This closes the previously reported cap incident.
Latest requested lease-copy targets are 11/13/14; 16/18 are no longer queued.

T3-PASS published 2026-10-08T06:42:32.432848Z by `release_t3.py publish`, label
`imitation-t3-release-v1`, launcher 3514669, exit 0, 6.99 s wall / 6.97 s CPU.
Certificate SHA 6b335ec4470215922c1ff346da18535fe3f8e3eb9e88dfe109d16d1f86b9472c.
Independent check re-read all plan identities against frozen roles, complete
unit receipts with exactly 805 sampled perspectives, role manifests and
frequency/prereg/count-file hashes. Rows/counts equal the previously reported
store totals. Source/store/recipe remain unchanged. Certificate and updated
contract mirrored to 05. It records `p16_baseline: pending`, original label/PID,
estimated completion 08:30 UTC (not a deadline) and separate future
`T3-P16-BASELINE.json`. Destination-copy receipts are separate and certificate
SHA is stable; do not overwrite T3-PASS to add copies or P16 numbers.

Handoff 06:42:42 UTC: verified old `finish_data.py` PID 3406704 received SIGTERM
only to that PID, never the process group, to prevent its old in-memory path
from recopying destinations and overwriting the new certificate. Original label
`imitation-data-finish-v1` exit 143 is intentional, with logs preserved. The P16
parent 3449355 (now PPID 1), eval workers 3510500/3510503 and their output/log
remain running untouched. Evidence `data/operations/supervisor-handoff.json`.
Do not resume the obsolete `finish_data.py` path.

Replacement detached labels on 01, all with source env/.venv/fleet_run:
- `imitation-t3-copies-v2`, launcher 3515177, `release_t3.py copies`: sequential
  home copies 04 then 08, SHA verification, output `data/receipts/T3-COPIES.json`.
  At 06:44, transferring to 04. Inspect exact PID/log/exit before fresh-label resume.
- `imitation-t3-p16-receipt-v1`, launcher 3515185, `release_t3.py p16`: waits for
  existing scorer completion then validates 648 dev/705 eval/0 OOD and publishes
  `T3-P16-BASELINE.json`. No second scoring run. Deadline remains 03:30 UTC Oct 9.
- `imitation-t3-leased-copies-v1`, launcher 3515754,
  `finish_leased_copies.py`: sequential 11/13/14 via existing lease-local wrappers,
  live lease/qualification/resource checks, checksums and readiness data-field
  updates with originals backed up under `data/operations/`.
  Host11 label `imitation-store-copy-127x11-v1`, launcher 894677, running transfer.
  Status `data/operations/leased-copies-status.json`, failures
  `leased-copies-blocked.json`. No duplicate launch if host label already exists.
  Leased helper now pins the source certificate's manifest SHA; home-copy completion
  is independent under the new coordinator decision. Total copy RSS is bounded;
  existing lease wrapper enforces the 64 GB limit and reclaim termination.

Resume commands (new label only after verifying the corresponding job stopped):
`bash reports/strategy_council_20260928/fleet/fleet_run.sh NEW-LABEL .venv/bin/python -B reports/strategy_council_20260928/imitation/release_t3.py copies`
`bash reports/strategy_council_20260928/fleet/fleet_run.sh NEW-LABEL .venv/bin/python -B reports/strategy_council_20260928/imitation/release_t3.py p16`
`bash reports/strategy_council_20260928/fleet/fleet_run.sh NEW-LABEL .venv/bin/python -B reports/strategy_council_20260928/imitation/finish_leased_copies.py`
All authoring on 05; only explicitly owned source/docs copied to 01.

06:47 UTC checkpoint: T3 certificate SHA unchanged. Home transfer to 04 and
leased transfer to 11 remain live; 08 and 13/14 queued in their respective
supervisors. No failure receipts. P16 eval workers each 10m36 elapsed / 10m32
CPU; no duplicate scoring or copies. Physical console count on hub is zero.

06:57 UTC checkpoint: 04 transfer has reached checksum dry verification
(rsync PID 3520064); observed destination 86,075,428,725 bytes. Host11 transfer
has 81,692,210,905 destination bytes; wrapper reports five processes, 0.85 GB
RSS, no stop reason. Home 08 and leased 13/14 remain queued. P16 eval workers
each at 20m22 elapsed, 20m13/20m14 CPU. No failures; certificate SHA unchanged.

07:07 UTC checkpoint: 04 copy PASS, 254 artifacts / 86,075,227,942 bytes,
manifest SHA matches source 1acf6b58...; checksum dry run empty. Independently
read destination manifest SHA and verifier receipt; mirrored small receipts to
05 and copied immutable T3-PASS into the finished destination store. Home copy
supervisor advanced to 08. Host11 now at SHA verification (200/254 progress),
two processes / 1.45 GB RSS, no stop reason. Eval P16 workers at 30m25 elapsed
and 30m13 CPU each. Certificate unchanged; no failures or restarts.

07:17 UTC checkpoint: host11 copy PASS at 07:07:47 UTC, 254 artifacts /
86,075,227,942 bytes; total 1,417.35 s wall, SHA check 99.53 s. Independently
checked destination manifest/certificate hashes, empty checksum dry run and
wrapper exit pass; hub readiness data_copied and training-ready are true.
Small T3-COPY-127x11 receipt mirrored to 05. Leased supervisor advanced to
13 (`imitation-store-copy-127x13-v1`, launcher 3430926); 14 queued. Home 08
transfer continues. P16 eval workers each 40m23 elapsed / 40m07 CPU. No failures.

07:27 UTC checkpoint: 08/13 copy jobs and original P16 scorer remain live,
no exit/failure receipts. 04/11 are verified; 14 remains queued. P16 eval
workers each at 50m23 elapsed / 50m03 CPU. Certificate hash unchanged and
physical console count zero. No new jobs or restarts.

07:37 UTC checkpoint: home copies both PASS; `imitation-t3-copies-v2` exited
0 at 07:28:24 UTC, 45m18.64 wall / 2,565.16 s local process CPU. Both copies
verify 254 artifacts / 86,075,227,942 bytes and matching manifest SHA. 08 SHA
verification 69.39 s; independent receipt/hash and empty checksum dry-run checks
pass. Certificate copied into finished 08 store; home copy receipts mirrored05.
Host13 copy PASS 07:28:53 UTC, 1,257.44 s total wall, 56.39 s SHA verification;
wrapper exit0, peak five processes / 1.47 GB RSS. Destination manifest and
certificate SHA independently match; dry run empty, hub readiness true, receipt
mirrored05. Host14 transfer started07:29:01 under label
`imitation-store-copy-127x14-v1`, launcher3406643, child3406647; five processes
/0.86 GB RSS, no stop reason. P16 eval at1h00m31 elapsed/1h00m06 CPU each.
No failures or restarts; certificate immutable.

07:47 UTC checkpoint: host14 has advanced to checksum dry verification,
four processes /0.85 GB RSS, no stop reason. Home04/08 and leased11/13 remain
verified. P16 eval workers at1h10m31 elapsed/1h10m01 and1h10m02 CPU. No failure
receipts, no new jobs; certificate SHA unchanged, physical console count zero.

07:57 UTC checkpoint: ALL requested copies verified (04/08/11/13/14). Host14
finished 07:50:25 UTC, 1,283.59 s total wall, peak five processes /1.66 GB RSS;
wrapper exit0. Independent manifest/certificate SHA and empty checksum dry run
verified; all three leased hub readiness receipts show data_copied/training-ready.
Home certificate hashes also independently match. Leased-copy supervisor exited
0 at07:50:34, 1h06m27 wall /6.36 s local orchestration CPU (remote copy CPU not
included). Aggregate and host14 receipt mirrored05. Only P16 remains: eval
workers at1h20m28 elapsed/1h19m54 CPU each, healthy; no baseline receipt yet.
Certificate unchanged. Poll continues solely for baseline completion and final
report; no transfer should be restarted.

08:07 UTC checkpoint: only P16 eval remains. Both workers progressed to
1h30m25 elapsed /1h29m47 CPU, parent and receipt watcher live, no completion
receipt yet. Both copy supervisors exited0; all copies already independently
verified. Certificate SHA unchanged; no new jobs or restarts.

FINAL 2026-10-08 08:18 UTC: T0/T1/T2/T3 complete, no remaining data work.
P16 receipt published at08:17:06.358829 UTC; receipt watcher
`imitation-t3-p16-receipt-v1` exited0, scorer/worker PIDs are gone. Recipe and
upgrade-source hashes still equal preregistration; checkpoint SHA is pinned,
learned tensors unchanged, and P16 supervised row counts match the frequency
baseline slice exactly. 648 dev /705 eval /0 OOD perspectives; 505,669 dev and
542,680 eval rows. OOD P16 metrics are null, not a scored zero.

P16 dev/eval metrics respectively:
- Joint NLL 0.4187397683 /0.4144627705.
- Timing NLL (all supervised rows) 0.1789347266 /0.1782971218;
  playable-row timing NLL 0.1846920516 /0.1847381754.
- Card NLL 1.0333683455 /1.0098453448, top1 0.5372607110 /0.5484732009,
  top3 0.9299604983 /0.9345149121.
- Tile NLL 3.5724496296 /3.5514178798; median tile error 3 /3.
- ECE 0.0086816557 /0.0091610227; playable ECE 0.0089609929 /0.0094919683.
- Matched P16-slice frequency joint NLL 0.4743211278 /0.4715358467.
P16 total 11,311.674 s wall (3h08m31.67) /22,120.438 s CPU (6h08m40.44).
No rerun or recipe change. This is the descriptive baseline, not a model gate result.

`data/receipts/T3-P16-BASELINE.json` SHA
7c7019b3dbe530ca40dd77af71b5b49e876fbddc192775569cd70c3722cca4cf.
Its per-role source hashes independently verified after mirroring small JSON05.
T3-PASS remains byte-unchanged at SHA
6b335ec4470215922c1ff346da18535fe3f8e3eb9e88dfe109d16d1f86b9472c.
All five destination manifests/certificates, copy receipts and empty checksum
dry runs were independently checked, with leased readiness updated. Home and
leased-copy aggregate receipts also bind this same certificate SHA.
Final audit summary: `data/receipts/T0-T3-FINAL.json`.

Temporary schedule disabled successfully (enabled=false, nextRunAt=null).
No data-worker jobs need resuming. All original logs and data remain. Incidents:
pilot terminal-hook fix and checkpoint descriptor adaptation documented above;
historical-header exception accepted; apparent P16 deadlock disproved; console
alarm resolved as monitor sessions; old supervisor intentionally handed off
with exit143 for coordinator-authorized release decoupling. No frozen source,
role, eval spec, recipe, baseline scorer or original header was changed.
