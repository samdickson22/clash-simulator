# Missing-template worker UTC audit

## 2026-10-16T09:12Z — routing hold and preserved jobs

Branch `cards/lead`, worktree `/mpac/sdicks02/repos/clasher-cards`; lead HEAD at check
`2883465a81705058a7a81ca82f74d20e0ff3a4ab`. This worker has made no commit/push yet.
Do not stage lead `reports/cards/PROGRESS.md` or unrelated `reports/cards/nulls/*`.
Publication and active/runtime pin switches HOLD. No r3 roots published on 03/04/08;
existing immutable r2 roots and generation remain unchanged. No B2/C1 gate/merge touched.

Exact accepted receipts, retained separately from incomplete class evidence:
- `receipts/missing-templates-k4l.json`: K4L HEADLINE exact command hashes **12/12 PASS**;
  command on 04: `CARD_TEMPLATE_JOB=/mpac/sdicks02/jobs/clasher/cards/missing-templates-r3 bash source/reports/cards/runtime/tools/gate_k4l.sh`
  under existing `cpu_job.sh 4`, nice 15. Both arms ran fresh.
- `receipts/missing-templates-assembler-tests.txt`: **11/11 PASS**, command on 05 (light, 0.289s):
  `PYTHONDONTWRITEBYTECODE=1 nice -n 15 python3 -B -m unittest bot.cards.test_build_runtime`.

Read-only liveness commands at 09:07–09:09Z:
`ssh 127x04 'ps -eo pid,pgid,stat,etime,args | grep -E "(none_stats_probe|gate_object_templates)" | grep -v grep; tail -n 3 /mpac/sdicks02/jobs/clasher/cards/missing-templates-r3/none-stats-dev.log'`
and equivalent 08 filter `(class-final-dev|object_templates_probe|replay_missing_templates)`.
Remote `rg` unavailable; corrected to grep. An initial `tail -3` over expanded paths failed;
corrected to `for f in .../class-final-dev-?.log; do tail -n 2 "$f"; done`.

Preserve running jobs; no duplicate launched:
- 04 wrapper **793005**, worker **793749**, PGID **793000**:
  `cpu_job.sh 1 env PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1 NUMPY_MADVISE_HUGEPAGE=0 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 RAYON_NUM_THREADS=1 CLASHER_BOT_RUNTIME=/mpac/sdicks02/jobs/clasher/cards/missing-templates-r3/dev-live CLASHER_BOT_RUNTIME_PINS=live16402b-r3 nice -n 15 /mpac/sdicks02/repos/clasher-bot/.venv/bin/python -B /mpac/sdicks02/jobs/clasher/cards/missing-templates-r3/source/reports/cards/runtime/tools/none_stats_probe.py --baseline-script /mpac/sdicks02/jobs/clasher/cards/missing-templates-r3/baseline_c56_scripted.py --out /mpac/sdicks02/jobs/clasher/cards/missing-templates-r3/none-stats-dev.json`.
  Last read: 37,274 checks, zero failures; final 55,834/8,496 ranking comparison denominators pending.
- 08 wrapper **707421**, worker **1804205**, PGID **707255**:
  `cpu_job.sh 1 env PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1 NUMPY_MADVISE_HUGEPAGE=0 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 RAYON_NUM_THREADS=1 CLASHER_BOT_RUNTIME=/mpac/sdicks02/repos/clasher-bot-runtime/live16402b-r2 CLASHER_BOT_RUNTIME_PINS=live16402b-r2 nice -n 15 /mpac/sdicks02/repos/clasher-bot/.venv/bin/python -B /mpac/sdicks02/jobs/clasher/cards/missing-templates-r3/source/reports/cards/runtime/tools/replay_missing_templates.py --repo /mpac/sdicks02/jobs/clasher/cards/missing-templates-r3/replay-repo --expect-error --out /mpac/sdicks02/jobs/clasher/cards/missing-templates-r3/replay-5000110-r2.json`.
  Original r2 replay; no sealing. Fresh receipt pending.
- 08 class-final-dev wrapper **446854**, PGID **446850**, runner **509024**, workers **509026/509028**
  (other two finished earlier) completed by 09:08Z. Original command `cpu_job.sh 4 bash /mpac/sdicks02/jobs/clasher/cards/missing-templates-r3/class-final-dev.sh`.
  Four shard receipts copied using `scp '127x08:/mpac/sdicks02/jobs/clasher/cards/missing-templates-r3/class-final-dev-?.json' reports/cards/runtime/receipts/`.
  **Development evidence only**: 122/122 definitions, 366/366 combat/death/lifetime scenarios,
  56,354 checks, zero exceptions, 187 public (token,kind) pairs (95 troop/14 building/51 projectile/27 area),
  355 templates, 142 config identities. Native admitted actions 121/122; MergeMaiden excluded by frozen v5 scope.
  Aggregate `receipts/missing-templates-class-dev.json` does not claim exhaustive class PASS.

Independent read-only review task `/root/host_script_review` (native Sol high;
backing thread `thread:provider:codex:native-thread:01a143f7-2e9a-7943-b700-4a9c715a4c72`),
verdict **REQUIRES CORRECTION** before class gate / altered launch:
1. Native-only identities checked but omitted from inventory (`get` vs `setdefault`); retain all provenance.
2. Native objects omitted translator/meta/script-body checks; make checks equivalent to Python.
3. Translator `_row` checks bypass actual `_rows` mapping/drop path; test source mappings and exact carrier registry.
   External source-card/motion can alias multiple internal child objects; do not claim lossless external identity.
4. Add roots from native public full-board rows, beyond Python boards and native one-row roots.
5. `totality_object_templates.sh` hardcodes published r3 and can leave child alive after failed wait;
   use explicit scratch-root override and reap all children before failure.
6. `release_objects.py create` publishes runtime roots and is HOLD; ancestor-symlink / output-overlap
   checks required before any eventual publication. It has not executed.
7. Assembler review permits scratch `--native` only; do not invoke existing cargo `--build-dir` (-j16).

Reviewed hashes (first round): gate helper f4bde78ae6bcf889d1ed757d1d2817b74822cbdf77b36ad79649c5621d62a051;
replay 0ff48331e0f7b693264eafec5b2c1c51b92761421df853faabe8d4575e432fdd;
probe development 4792d14f1c7dbf5d57f0fb1f69134f3989d778289cf70c4478254a94a3b38878;
assembler 056986a72cd523595ba8371f2a15ca5291b90a49a4330ac79b789ed1d4544e06.
Coverage correction is in progress; fresh independent review required before altered probe/launcher executes.
Lead notified via T3 request `template-status-20261016-0909`; response started lead run 13.

Scoped source changes: differential.py exports exact public identity/static fields; fair_player.py recursively
completes nested templates preserving old entries; royalesim_translate.py/royalesim_vocab.py complete missing rows;
build_runtime.py/test_build_runtime.py explicitly export/overlay fair_player; gate_k4l.sh optional class helper.
Candidate PIN_SETS r3 entries exist only in uncommitted working code and isolated test source; no active/default switch.
New probe/replay/release/totality/gate helpers and LIVE patch are under this runtime report tree.
LIVE worktree remains read-only; `git -C /mpac/sdicks02/repos/clasher-live apply --check .../patches/live-template-vocab.patch` passed.

Rollbacks: none to released source/runtime. Earlier development probe attempts retained in scratch and superseded
(fixture placement, spell None-stat probe assumption, native deployment/death callback fixture corrections).
One own queued cpu_job4 replay wrapper PGID532773 was replaced before routing hold by the actual cpu_job1
single-process replay above; no other jobs touched. No resumption of completed/superseded gates.
Deferred: release/pin promotion; receipts on 03/04/08; accepted full-class claim until corrected independent review.

## 2026-10-16T09:13Z — preserved jobs finished, coverage corrections await review

Read-only `ps -p 793005,793749` (04) and `ps -p 707421,1804205` (08) now show no live processes.
No replacements/duplicates launched. Copied receipts with scoped `scp`:
- 04 `none-stats-dev.json` → `receipts/missing-templates-none-stats-dev.json`:
  **PASS 55,834/55,834 checks, zero failures; 8,496/8,496 C56 ranking comparisons identical**.
- 08 `replay-5000110-r2.json` → `receipts/missing-templates-replay-5000110-r2.json`:
  exact expected ValueError reproduced with original seed2613058996490974, v1 opponent, no sealing.
Original350 templates compared to development355 identify five exact missing area keys:
27 BarbarianRageDamage (RageBarbarian), 269 RageDamage (Rage), 147 GoblinDrillDamage (GoblinDrill),
200 IceWizardCold (IceWizard), 88 ElectroWizardZap (ElectroWizard).

Corrections prepared locally, NOT executed on compute hosts yet:
- Probe native inventory setdefault+full provenance; equal native static/registry/meta/script-body checks;
  real translator `_rows` mapping checks for all finite unit/spell/projectile/tower mappings, both seats;
  exact object carriers traverse shared production `_resolved_rows` final registry/drop/format path;
  native full public-entity boards at same eight checkpoints/seat; complete/expected scenario flags.
  Native board roots use native public positions/HP/facing/identity with Python HUD/global scaffold;
  this is lookup/root totality evidence, not a native-vs-Python observation-equivalence claim.
- Translator final formatting factored into `_resolved_rows` with exact object-registry validation.
  Source-card/motion aliases remain explicit schema limitations; no new external visibility claim.
- New `tools/run_object_templates.sh`: four nice15 children, unique scratch output, all waits reaped.
- Totality helper: explicit scratch runtime required, preserve old output, reap every child on failure.
Fresh read-only review round2 sent to `/root/host_script_review`; no altered probe/launcher executed.
Review input hashes: probe3bcc93244f39dcecb657a3a7149b7e27447771fc4b2091b92119aae6dd3f19fa;
runner53e2682d44782833f5954c9fad3ad3bec5a40e2307f9b25cced8ba8fdc30164f;
totality4ef1cf2c00ab4a2f3e2c5059cfc84d868a117a801ec57100d36159fe913a8e2a;
translator381138734b2fcdd45434685b3b764f30c70583c51f8cc9fc4052d9b55df29fa6.
Light local checks: `python3 -B -m py_compile ...object_templates_probe.py bot/players/royalesim_translate.py`
and `git diff --check` PASS. Accepted K4L/assembler receipts remain separately retained.

## 2026-10-16T09:17Z — fresh independent approval, targeted corrected pilot only

Fresh review task `/root/host_script_review`, same backing Sol-high child thread above, round2 final verdict
**APPROVE scratch pilot/full run** for final exact probe hash
`b8fcce8ea1ed26300dcacbfc88b92e55fa0ef0448f63a6e5ccc09f60fe09c476` and runner
`53e2682d44782833f5954c9fad3ad3bec5a40e2307f9b25cced8ba8fdc30164f`.
Reviewer read final changes, did not execute/modify/touch hosts. Final corrections add actual v5 projection,
public-position clipping, translator/vocab/scope/runtime source hashes, native constructor materialization
assertions and five-target denominators. Each target has actual exact-carrier translator and projected
synthetic full-board R.root/LIVE-level root paths for both seats. `_rows` source-motion outputs are recorded
separately; parent aliases do not claim exact child identity. Native gameplay emission is separate from
constructor materialization (three spawn effects can disappear within a native step).

Preflight 08 at 09:16:45Z: old class/replay processes absent; original r2 negative-control receipt exists;
`readlink -f J` equals `/mpac/sdicks02/jobs/clasher/cards/missing-templates-r3`; new source/pilot/full paths absent.
Commands (J abbreviates that exact owned scratch path):
- `ssh 127x08 'cp -a J/source J/class-reviewed-source'` (ordinary copies, no hardlinks).
- `rsync -a --relative bot/players/royalesim_translate.py bot/players/royalesim_vocab.py bot/players/runtime.py reports/cards/runtime/tools/object_templates_probe.py reports/cards/runtime/tools/run_object_templates.sh 127x08:J/class-reviewed-source/`.
- Remote `sha256sum` of probe/runner/translator matched reviewed source hashes exactly.
- `ssh 127x08 'nohup setsid /mpac/sdicks02/repos/clasher-bot/bot/exit/cpu_job.sh 1 env PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1 NUMPY_MADVISE_HUGEPAGE=0 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 RAYON_NUM_THREADS=1 CLASHER_BOT_RUNTIME=J/dev-live CLASHER_BOT_RUNTIME_PINS=live16402b-r3 nice -n 15 /mpac/sdicks02/repos/clasher-bot/.venv/bin/python -B J/class-reviewed-source/reports/cards/runtime/tools/object_templates_probe.py --cards RageBarbarian Rage GoblinDrill IceWizard ElectroWizard --out J/class-reviewed-pilot.json > J/class-reviewed-pilot.log 2>&1 < /dev/null & echo $!'`.
  Wrapper **2432076**; only corrected scoped probe launched after review, no old jobs restarted.
  Pilot denominator5 definitions ×3 scenarios=15, both seats; full denominator122/366 remains pending.
No totality/replay/publishing job launched after latest 'only corrected scoped probe' direction.

Stable accepted receipt hashes (separate gates):
K4L `c1d2799a7d0953bca6e8418bd1edbb2a41bae01756cbeeee4246ccfa0b7c1c62`;
assembler `46b8e3ada4e69c85e80f1775520d6292b59bbf35b29ca592cd9e78e5fa93776f`;
None/ranking `3655db48924ca8af206b55a19d4e80f2e52b46aec2b4a585f8d854bb2356f6db`;
r2 negative control `8c7e4e5ac2afe8e6be318777b19729986d8211cc63008506eacf1da51b93da37`.
Translator source `381138734b2fcdd45434685b3b764f30c70583c51f8cc9fc4052d9b55df29fa6`.

## 2026-10-16T09:19Z — revised authority, candidate checkpoint

Sam explicitly superseded the blanket Opus/promotion HOLD: routine confident reviewed opt-in r3 release
is authorized after actual corrected coverage, independent implementation review and required gates pass,
with exact immutable provenance and rollback to untouched r2. Active LIVE pins remain LIVE-owner authority.
Earlier HOLD statements above are history, not current blanket blockers. No publication has occurred.
Updated direction propagated to active `/root/host_script_review`; it is now independently reviewing the
production implementation, separately from its completed host-script approval. No Claude descendants.
B2→C1 dependency order and host/CPU restrictions unchanged; consequential uncertain choices still defer.

Lead requested an immediate scoped source/probe/audit checkpoint so its fresh implementation review can
start while existing pilot2432076 finishes. This checkpoint includes only this worker's source/probe/audit
and exact receipts; excludes unrelated Null's, lead PROGRESS and the not-yet-safe release draft.
Commands: explicit `git add` / `git add -f` paths; `/mpac/sdicks02/cc/tools/bin/clasher-secret-scan`;
`git diff --cached --check`; `git commit -m 'Cards: complete exact public object template identities'`;
`git push origin cards/lead`. Exact checkpoint SHA/file list will follow immediately after commit.
No running source snapshot is modified; changes later require digest review and affected reruns.

## 2026-10-16T09:21Z — full review findings corrected before checkpoint

Independent implementation review `/root/host_script_review` found one blocking new-input safety omission:
assembler main --rev protected engine-cards but not newly exported fair_player against target/backup overlap.
Added fair-player source input before mutation; regression covers target/backup with engine source aliased
outside so only the new guard catches the overlap. First regression draft failed its expected-message check
because the earlier engine-source guard fired; fixed fixture to isolate the new guard. Final light command
`PYTHONDONTWRITEBYTECODE=1 nice -n 15 python3 -B -m unittest bot.cards.test_build_runtime`
now **12/12 PASS**, new receipt `receipts/missing-templates-assembler-review-tests.txt`; original11 PASS retained.

Review also found a probe assumption defect: frozen synthetic Projectile templates retain troop/building
entity_kind0/1 while class='Projectile'; constructor preserves this historical representation. Current
running pilot snapshot b8fcce8 remains immutable. Corrected candidate probe compares actual materialized
class/stats/spell signature with selected template, inventories historical kind aliases, and keeps strict
kind3 assertions for the five repaired areas. C56 templates remain unchanged. Old pilot may fail this invalid
assertion; it will finish and remain negative development evidence, not be accepted or duplicated.
New probe digest will be bound to checkpoint and re-reviewed before any affected rerun.

Sam coordination rule recorded: routine questions go directly to exact parent via t3_thread_send(mode=auto),
never request_user_input/AskUserQuestion. Parent thread is
`thread:delegated-task:command%3Amcp%3A7f0bf0df-35b9-48b9-bbf9-8f9cdcc3f584%3Adelegate-task%3Aclasher-card-lead-20261016-r1`.
No input request is pending. Rule propagated to active native reviewer and future briefs.

## 2026-10-16T09:25Z — checkpoint, implementation acceptance and superseded queued pilot

Checkpoint **1802e899cea14807f659ee234dcd67839b392f46** committed/pushed cards/lead (30 scoped files),
after staged secret scan and cached diff check PASS. Stored LIVE patch context whitespace normalized;
`git -C /mpac/sdicks02/repos/clasher-live apply --check .../live-template-vocab.patch` still PASS.
Full file list sent immediately to lead via request `template-checkpoint-1802e899c-20261016`.
Independent full production-code review `/root/host_script_review` **APPROVE exact checkpoint**;
brief, resolved findings, reviewed file hashes, stable native task/backing-thread ID and prerequisites are
in `receipts/missing-templates-implementation-review-1802e899c.json`.
This is independent implementation acceptance, separate from host-script review and pending coverage acceptance.
Lead notified via `template-impl-approve-1802e899c`. Coordination rule propagated; no legacy input requests.

Per explicit lead instruction, superseded old known-invalid queued pilot rather than waiting indefinitely.
08 preflight09:23:52–09:24:37Z verified wrapper2432076, PGID2432076, owner sdicks02, exact start
`Fri Oct 16 02:17:06 2026`, full expected class-reviewed-source command, group only wrapper2432076,
cpu_room2432083 and sleep2903998; no Python child, no lease-2432076, no pilot JSON.
Initial read-only awk quoting failed and was corrected to literal `$3`; no action in failed command.
Exact mutation guard: check ps user/pgid/lstart/expected argv, absence lease, and group comm only bash|sleep;
then `kill -TERM -- -2432076`. No broad kill/pkill/rm; all frozen source/logs preserved.
Postcheck09:24:37Z group absent and no lease or JSON: **superseded-not-evidence**, never admitted.

Created fresh ordinary copy `J/class-checkpoint-1802e899c-source` from preserved `J/class-reviewed-source`;
rsync --relative only changed assembler/test/probe files. Remote probe digest exactly
2dceefc5cf28ad052c780e1ba0bb84025ef4793384e3eb4d3aecc1e18aa82140 (approved checkpoint).
After terminal/no-lease/fresh-output checks queued ONLY corrected five-target pilot wrapper **2967873**,
using same reviewed cpu_job.sh1/nice15/thread1/env as09:17 command, but source
`J/class-checkpoint-1802e899c-source`, output `J/class-1802e899c-pilot.json`, log
`J/class-1802e899c-pilot.log`; targets RageBarbarian,Rage,GoblinDrill,IceWizard,ElectroWizard.
No duplicate running probe. Denominator5 definitions/15 scenarios; subsequent full122/366 waits actual pilot result.
No root publication or active pin switch. Rollback unchanged r2 remains retained.

## 2026-10-16T09:32Z — immutable publication script readiness (no execution)

Repaired draft release helper independently reviewed and approved by `/root/host_script_review`:
final `tools/release_objects.py` SHA6ef8f571c337c643911ef26c0bf454e0c3e7691f79a1b01096393775ac650d3e;
`tools/test_release_objects.py` SHAdd2ef6f007d9a3002e3998dc676c59e11d69a6efc6b20b31823c075f534e4d34.
Independent verdict APPROVE, read-only review/no host actions; reviewed create/verify command protocol is
`cpu_job.sh 1 env PYTHONDONTWRITEBYTECODE=1 ...thread1 nice -n 15 <venv-python> -B <accepted-source>/reports/cards/runtime/tools/release_objects.py create|verify --name live16402b-r3|r1-cards2-r3 --source <accepted-source> --commit <accepted-source-SHA> --out <fresh-owned-J-output>`.
Prerequisites remain accepted corrected coverage/gates, main integration/source archive+manifest verification,
host absence/parent/liveness preflight. No release script execution yet. Active LIVE pins remain LIVE-owner only.

Safety corrections: protect source/parent/all parent symlink referents from output/target overlap; require fresh
out and existing output parent; reject symlink destination ancestors; isolated no-hardlink rsync staging;
patch with new inode after checked staging-parent permissions; preserve parent receipt; readonly freeze/full
content manifest/overlay manifest/source hashes; native+data pins/parent invariance; Linux atomic renameat2
NOREPLACE (even an existing empty root is preserved). Verification records canonical R.config SHA as well.
Retain failed staging trees and inspect receipt before any retry; never mutate an existing published root.
Light local temp-only safety tests `PYTHONDONTWRITEBYTECODE=1 nice -n 15 python3 -B -m unittest reports.cards.runtime.tools.test_release_objects`
PASS5/5 (0.007s), receipt `receipts/missing-templates-release-safety-tests.txt`. No runtime/remote host touched.

Concrete rollback: all callers remain opt-in and prior immutable r2 roots are retained. Select
`CLASHER_BOT_RUNTIME=/mpac/sdicks02/repos/clasher-bot-runtime/live16402b-r2 CLASHER_BOT_RUNTIME_PINS=live16402b-r2`
(or corresponding r1-cards2-r2) in the opt-in caller's environment; do not remove r3 or switch any active owner
pin. G1/K1 retain existing pins+r2 retry rules until exact released receipts and host preflights are accepted.

Added local aggregation tool58920a9e73e8a06961572b49ffff590c9a15a56f03c102d685e0f9ef43bf96cd,
checks full122 distinct definitions/366 scenarios/complete flags/four disjoint shards/source+template equality,
allfive exact-carrier translator/native-board both seats, source aliases and native emission separately,
config142 observed and every observed identity natively materialized. Independent evidence review pending.
Current corrected pilot2967873 remained queued/no admitted Python at09:30:30Z; no duplicate/full run launched.

## 2026-10-16T09:34Z — acceptance parser review and CPU wait

Corrected pilot2967873 remains queued; 09:33:30Z no Python/lease/JSON. Read-only admission diagnostics:
`ps -u sdicks02 -o stat=,args= | grep -v '^Z' | grep '[p]ython' | grep -Evc 'train_cr\.py'` →104;
7 claim/lease files total, default cpu_room cap105 (no max-live file). No cap/feeder/generation/job changes.
Group contains only wrapper2967873, cpu_room2967883 and sleep3376249; no duplicate/full class launch.

Local aggregation review found protocol acceptance gaps: require >=1500 run ticks and >=450 combat/death,
>=1500 lifetime, exact source inventory bound to approved checkpoint (not merely cross-shard equality),
and exclusive aggregate output creation. Fixed parser88530263c1df4552e69bf767a36c5682a476933831ee43eb4c32935f8f5045e6;
source manifest71d4e713ebd1eb3c720acca6d7266cf33b0563cf16b8727950969f7d883b1e3c generated by
`git show 1802e899cea14807f659ee234dcd67839b392f46:<each of 7 source files>` +SHA256;
recorded in receipts/missing-templates-approved-source-1802e899c.json. Fresh review confirmation pending.
No queued source modified. Stable release approval attestation stored in receipts/missing-templates-release-review.json.

- 2026-10-16T09:35Z independent aggregation review `/root/host_script_review` APPROVE exact parser
88530263c1df4552e69bf767a36c5682a476933831ee43eb4c32935f8f5045e6 and approved-source manifest
71d4e713ebd1eb3c720acca6d7266cf33b0563cf16b8727950969f7d883b1e3c; reviewer checked all7 hashes
against checkpoint1802 including differential runtime-overlay mapping. No remaining parser blockers,
no host/runtime jobs or edits by reviewer. Actual corrected coverage remains pending CPU admission.
