# C56 human-data track: PROGRESS

Current v3b status at 2026-10-04T19:57:03.471495+00:00: repair and all gates passed; detached extraction is running. Driver 15128; workers 15631/15632/15633, nice 10. First three new units verified: 144 perspectives / 117,776 rows, zero errors or illegal labels. Original 270 units unchanged. ETA 2026-10-05T09:03:56.019235-07:00, load dependent. Full extraction is not complete.

Owner: c56-data agent. Started 2026-10-02 ~21:20 local. Resumable: read this file first.

Rules: never git reset/clean/stash/commit; never edit m0/runtime-snapshots/ or pilot/ kits; do not edit
engine mechanics (battle.py, entities.py, cards/*), public_scripted_opponent.py or the Tier A root
generator (engine agent owns them); kill only own PIDs; <=3 worker processes, `nice -n 10`; no rented
compute; v4 behaviour byte-identical when v5 flags are off. Disk: only ~29 GiB free at start -> keep
total c56/data under ~8 GiB.

PY=/Users/sam/Desktop/code/clasher/.venv/bin/python ; D=reports/strategy_council_20260928/c56/data

## Current v3 status 2026-10-03T23:05Z
V3 launch BLOCKED by GoblinsteinTether.on_attach on entities without card_stats. No mechanics edits authorized; requested engine-owner fix or explicit narrow-fix authorization. Runtime-engine-v3 is frozen; P16 identity and 202 reuse comparisons passed. Six default replay outputs are unchanged; six clamped perspectives repeat byte-for-byte. Full matched QA is collecting error evidence. The temporary QA pause has been lifted: old v2 parent 29832/driver 29835 and its workers are running again. QA has finished; see the final v3 handoff below. No v2 output has been deleted.

## Historical v2 status 2026-10-03T05:54:29.127552+00:00
QA gates and launch task COMPLETE. Full extraction RUNNING, not finished.
- Runtime: runtime-engine-v2, final source SHA b542e3bfa4fad2ff316fe7a33d85f19d72524f44477962dd97ae5a29628d4271.
- Parent PID 29832, active S117 driver 29835, current workers 30229/30230/30231, nice 10. Worker PIDs recycle after eight units.
- Full scope 82,231 = S117 62,766 then disjoint S122 19,465. Output recon/engine-v2b; log logs/full-engine-v2b.log.
- New-engine QA: 32 tests pass, one historical checkpoint-gamedata skip; original engine 27 pass. Placement 99.8236% matched / 99.6525% S122; zero illegal labels. Matched retention 65.1839% -> 72.9248%. Opponent contradiction loss 0 points, so all hard-cut policies remain.
- Determinism: six perspectives twice per new phase, byte-identical; complete hashes in QA_SUMMARY.md.
- First THREE newly extracted units pass persisted-row validators. Together with the three reused S117 units: 288 perspectives, 211,770 validated rows, zero errors/illegal labels, 99.8378% placement acceptance.
- Estimate at launch: 50.60 hours remaining, finish 2026-10-05T08:21:49Z (Oct 5 01:22 PDT), 4.517 GiB output / 4.913 GiB total data. Estimates depend on host load and sample mix.
- Resume with the exact detach command below; do not launch a second driver while PID 29832 or its child is active. Completion receipt will be recon/engine-v2b/completion.json. No BC fitting.

## Status (handover 2026-10-02 ~22:10 to the next agent)
- [x] 0. Payload fetch DONE (52/52 SHA-verified; 74,236 matches, 82,231 C56 perspectives, 62,766 with S117-simulable
  opponent ("s117"), 6,338 tower-troop matches excluded). payloads/ 347 MB.
- [x] 1. Contract v5 code + tests done (see Files). 27/27 pass under runtime/ incl. bit-identical upgraded P16 logits;
  workspace run of v5 + human-replay + council contract tests: 96 pass, 1 skip (upgrade test skips: workspace gamedata
  differs). Not yet done: audit of masks for X-Bow/spawner footprints, deploy-anywhere, Mirror/Clone, Tornado pulls (PLAN 3).
- [~] 2. Pipeline: index built, role file FROZEN, replayer + driver written and smoke-tested (6 perspectives OK).
  RUNNING: cost measurement (3 units x 48 perspectives, shards 0/26/39) -> qa/cost100-a/. NOT yet done: determinism
  rerun, QA summary, full extraction launch.
- [x] 3. Held-out eval spec frozen: eval/heldout_eval_spec_v1.json (sha256 d9f978f7...a7ae) bound to role file.
- [ ] 4. BC fit (natural) + offline eval: not started (later session).

## Files (created/changed this track)
- src/clasher/rl/contract_v5.py (new; builder, public projection, mask w/ 3x3 tower fix + ability, cached mask,
  descriptors, upgrade_policy_payload_to_v5), src/clasher/rl/contract_v5_tokens.json (pinned 360 tokens, sha 35db1a76...)
- src/clasher/rl/human_replay_v5.py (new; v5 replayer, cuts per PLAN 4.3, ability labels, compact deterministic shards)
- edited (v4 byte-identical; diff vs pilot-runtime-v5 = v5 hooks only): src/clasher/rl/model.py (semantics v5 input,
  champion globals kept for contract 5), structured_obs.py (_actor_visible hook), public_action_mask.py (_footprint_size)
- tests/test_contract_v5.py (new; copy also in runtime/tests/)
- c56/data/runtime/ = frozen extraction runtime (pilot-runtime-v5 + overlay of the files above; c56_bootstrap.OVERLAY).
  After ANY edit of an overlay file in src/, re-copy it into runtime/src/clasher/rl/ and use a NEW extraction --out
  (extract.py refuses a changed runtime manifest).
- scripts/: c56_bootstrap.py, extract.py (resumable per (shard, part) unit), build_index.py, make_roles.py,
  fetch_payloads_c56.py, build_token_list.py
- index/perspectives.jsonl.gz (sha f368af12...), roles/c56_roles_v1.json (sha 7e357f64...cdfe; train 69,380, dev 3,546,
  eval 3,765, eval_ood 3,771 in 8 families, excluded_leak 1,769), eval/heldout_eval_spec_v1.json

## Decisions / findings
- Extraction engine = frozen copy of m0/runtime-snapshots/pilot-runtime-v5 engine + gamedata (identical to the
  workspace engine on 2026-10-02 21:20; the engine agent is about to edit the workspace engine), plus my v5 rl
  modules overlaid. This keeps the C56 extraction byte-deterministic while the engine agent works.
- S122 token list from all 122 corpus cards = 360 tokens; the 36 pilot tokens are a subset and their 36 card-stat
  columns are identical to v4.

## Requests for engine agent
- [engine reply 22:45] Workspace engine now has the S122 fixes (Vines, Void, Goblin Curse, Heal Spirit as kamikaze troop, Elixir Collector, Goblin Drill deploy-anywhere) plus Berserker/Fire Spirit/mass repairs; identity check clean. Card kind changes: Heal spell->troop; GoblinDrill can deploy on enemy side. Furnace-as-troop is planned but NOT landed (handover item a in engine/PROGRESS.md).
- Modern Furnace as a troop; the 5 S122 card fixes (needed for phase s122). Extraction never follows the workspace engine.

## Log
- 2026-10-02 ~22:00 RESUMED after teardown (fetch had finished). Found contract_v5.py + model/obs/mask hooks written
  by the previous instance at 21:27-21:29 (not logged). Created runtime/ = rsync of m0/runtime-snapshots/pilot-runtime-v5
  (engine + gamedata sha daa58b..., identical to workspace engine files at copy time; workspace gamedata.json differs:
  3d99...) with v5 rl files overlaid (copy list: contract_v5.py contract_v5_tokens.json structured_obs.py
  public_action_mask.py model.py human_replay_demonstrations.py human_replay_bc.py + new modules). Run tests there:
  `cd runtime && CLASHER_ROOT=$PWD $PY -m pytest -q -p no:cacheprovider tests/test_contract_v5.py` (copy test in first).
- Fixes: Goblinstein ability lives on summonCharacterSecondData; model forward (contract>=4 zeroing) now keeps the
  champion globals for v5; v5 mask rounds blocker centres (float32 3.5000002 made the 3x3 tower block 4 wide on one
  side). Added upgrade_policy_payload_to_v5 (token rows by name, new rows zero).
- 21:20 read CLAUDE/AGENTS, PLAN 1/3/4/5, amendment, P16 README/PROGRESS/code. Fetch started.
- ~21:45-22:10 v5 replayer human_replay_v5.py + scripts; index built; roles frozen; eval spec frozen; cost run launched
  (PID 89091). Smoke on shard 14: 6 perspectives 0.5-7.8 s each under heavy load. HANDOVER requested by coordinator.

## Coordinator handover 2026-10-03T04:56:06Z
- Opus agent stopped at a clean point. Track handed to GPT-6-Astra (high) via T3 delegate_task, clientRequestId c56-data-astra-20261003-1 (scope: QA summary, opponent-side contradiction repair rule (>3 pt retention -> repair+flag), determinism, full extraction launch; no BC).

## QA takeover 2026-10-02 21:57 PDT
- Read requested guidance and PLAN section 4. Cost PID 89091 verified alive with workers 89226/89227/89228, nice 10. No other jobs touched.
- First cost unit (shard 39) completed, 48 perspectives. Added scripts/qa_extract.py for persisted-shard contract validation and aggregate metrics. Awaiting the other two units before contradiction decision.
- Reconstructed exact inherited cost launch command from live argv and runtime binding:
  `/Users/sam/Desktop/code/clasher/reports/strategy_council_20260928/pilot/detach.sh /Users/sam/Desktop/code/clasher/reports/strategy_council_20260928/c56/data/logs/cost100-a.log env CLASHER_ROOT=/Users/sam/Desktop/code/clasher/reports/strategy_council_20260928/c56/data/runtime PYTHONPATH=/Users/sam/Desktop/code/clasher/reports/strategy_council_20260928/c56/data/runtime/src OMP_NUM_THREADS=1 nice -n 10 /Users/sam/Desktop/code/clasher/.venv/bin/python /Users/sam/Desktop/code/clasher/reports/strategy_council_20260928/c56/data/scripts/extract.py --workers 3 --shards 0 26 39 --max-parts 1 --out /Users/sam/Desktop/code/clasher/reports/strategy_council_20260928/c56/data/qa/cost100-a`

## Cost QA complete
- 144/144 perspectives, zero extraction errors; all 90,134 stored rows pass contract validators. QA_SUMMARY.md and cost100-a-metrics.json contain measured rates and projections.
- Placement 99.6365%; illegal supervised labels 0/89,976; retention 65.1839%. Opponent hand/elixir cuts cost 0 points, so retain hard cuts unchanged. Projected 44.21 h / 3.141 GiB output, within disk cap.
- Frozen role and eval hashes verified. No runtime or replayer changes. Next: six-perspective independent-process determinism and contract-v5 test rerun.

## Detached QA gates
- Started PID 2555, one sequential worker, nice 10. Log: logs/qa-gates.log. Exact command:
  `/Users/sam/Desktop/code/clasher/reports/strategy_council_20260928/pilot/detach.sh /Users/sam/Desktop/code/clasher/reports/strategy_council_20260928/c56/data/logs/qa-gates.log env CLASHER_ROOT=/Users/sam/Desktop/code/clasher/reports/strategy_council_20260928/c56/data/runtime PYTHONPATH=/Users/sam/Desktop/code/clasher/reports/strategy_council_20260928/c56/data/runtime/src OMP_NUM_THREADS=1 nice -n 10 /bin/sh /Users/sam/Desktop/code/clasher/reports/strategy_council_20260928/c56/data/qa/run_gates.sh`
- qa/run_gates.sh runs the frozen-runtime contract tests, then two fresh-process identical six-perspective replays, then cmp. ALL_GATES_PASS is emitted only if all commands exit zero.
- Contract-v5 rerun PASSED: 27 tests in 42.61 seconds. First six-perspective determinism output sha256 96ffe6a8d8695ca760f5d00e4eabd3114a13b71bd8bd763599778791ca1d22cf; second run pending.
- 2026-10-03T05:03:34Z coordinator steer: do NOT extract on the pre-fix engine copy; wait for c56/engine/ENGINE_FREEZE_READY, take a new frozen copy, re-check v5 vs card kinds, short QA rerun, then full extraction. Give up after 4 h wait and report.

## Tasks 1–3 complete; coordinator engine override
- Six-perspective fresh-process outputs match byte-for-byte. Both SHA-256: 96ffe6a8d8695ca760f5d00e4eabd3114a13b71bd8bd763599778791ca1d22cf. 27 tests pass. PID 2555 completed, ALL_GATES_PASS.
- No full launch on the old copy. Waiting for c56/engine/ENGINE_FREEZE_READY; absent as of 2026-10-03T05:04:56.190618+00:00. Four-hour wait deadline: 2026-10-03T09:04:56.190618+00:00.
- On readiness: new immutable snapshot, receipt appended to marker, card-kind/mask verification, contract tests and >=40-perspective QA with before/after retention, then launch only if new gates pass. Keep old snapshot and QA intact; never reuse old NPZ shards in the new output.
- Known limitations added to QA_SUMMARY.md: champion abilities, Tornado King activation, Spirit Empress.
- Prepared qa/test_engine_contract.py for the replacement snapshot only: Heal and Furnace troop descriptors, Goblin Drill building/deploy-anywhere descriptor, cached-mask parity, and mask-versus-engine placements for both seats around towers, borders and both territories. No engine edits. These tests intentionally are not run against the old engine.
- Bootstrap now accepts either the original runtime or the planned runtime-engine-v2 via CLASHER_ROOT. The new copy must contain an extraction_freeze.json receipt with its pinned gamedata_sha256. No snapshot exists yet; original QA commands continue to bind the original runtime. Runtime manifests still prevent resuming output with changed source.
- Added qa/cost-sample-card-coverage.json and sample-coverage limits to QA_SUMMARY.md. Planned new-engine QA uses the same 144 inputs for a paired retention comparison; dedicated tests cover absent Goblin Drill.

## Replacement snapshot taken 2026-10-03T05:23:43Z
- Read ENGINE_FREEZE_READY, verified all 10 listed source hashes, copied workspace src/clasher plus gamedata, checked source stability before/after copy, overlaid the original eight v5 files. Old runtime unchanged.
- New runtime: runtime-engine-v2. Runtime SHA-256: 30b579dc5a1ba406daef8fa1e600c7062746b20badd6733899ea7523d8d81be8. Gamedata SHA-256: 3d99987c19cb94a0c8a6795e943829771078e564859e34c1411e221e5d57486a. Full source/copy hash receipt: runtime-engine-v2/extraction_freeze.json.
- Ready marker SHA before acknowledgement: 0e9d4c91f410d1ee8bd50c2eeab6d2310b96eb9bc9bcf73ff51abd4a92051265. Appending acknowledgement releases the engine agent; future workspace edits do not enter this snapshot.

## Replacement-engine gates running
- PID 19149, detached nice 10. Serial stages: original 27 tests + six card-kind/mask cases; matched 144-perspective cost with <=3 workers; all-row validators; two fresh-process six-perspective deterministic shards plus cmp. Log: logs/qa-engine-v2.log.
- Exact command:
  `/Users/sam/Desktop/code/clasher/reports/strategy_council_20260928/pilot/detach.sh /Users/sam/Desktop/code/clasher/reports/strategy_council_20260928/c56/data/logs/qa-engine-v2.log env CLASHER_ROOT=/Users/sam/Desktop/code/clasher/reports/strategy_council_20260928/c56/data/runtime-engine-v2 PYTHONPATH=/Users/sam/Desktop/code/clasher/reports/strategy_council_20260928/c56/data/runtime-engine-v2/src OMP_NUM_THREADS=1 nice -n 10 /bin/sh /Users/sam/Desktop/code/clasher/reports/strategy_council_20260928/c56/data/qa/run_engine_v2_gates.sh`
- ENGINE_V2_TESTS_AND_DETERMINISM_PASS is a receipt for tests/cmp only; inspect placement, errors, retention/contradiction rule and disk projection before full launch.
- Initial launch PID 19149 exited before startup, empty log and no matching process. Retried identical detach command while keeping the invoking Python process alive for two seconds. Active replacement PID 19493. No job was killed.

## Replacement contract correction
- First replacement suite: 30 passed, 1 skipped, 2 Goblin Drill placement failures. Cost did not run. Skip is the historical P16 checkpoint upgrade test, whose gamedata hash differs from the new engine; it passed on the original snapshot.
- Root cause: generic public mask tests building commands at tile centres with localization padding, while new deploy-anywhere Drill uses an even footprint snapped in world coordinates. Added a default-preserving placement hook to public_action_mask.py and a v5-only override for deploy-anywhere buildings. Uses only public tower/building observations plus immutable placement geometry. No engine changes, no changes to normal buildings or v4 behavior.
- Copied these two owned RL overlays into runtime-engine-v2; original runtime unchanged. Revised runtime SHA-256: b542e3bfa4fad2ff316fe7a33d85f19d72524f44477962dd97ae5a29628d4271. Revision recorded in extraction_freeze.json. Fresh cost output will be qa/cost100-engine-v2b.
- Replacement gate rerun PID 22073, two-second startup hold. Exact command: `/Users/sam/Desktop/code/clasher/reports/strategy_council_20260928/pilot/detach.sh /Users/sam/Desktop/code/clasher/reports/strategy_council_20260928/c56/data/logs/qa-engine-v2b.log env CLASHER_ROOT=/Users/sam/Desktop/code/clasher/reports/strategy_council_20260928/c56/data/runtime-engine-v2 PYTHONPATH=/Users/sam/Desktop/code/clasher/reports/strategy_council_20260928/c56/data/runtime-engine-v2/src OMP_NUM_THREADS=1 nice -n 10 /bin/sh /Users/sam/Desktop/code/clasher/reports/strategy_council_20260928/c56/data/qa/run_engine_v2b_gates.sh`.
- Corrected replacement tests: 32 passed, 1 expected checkpoint-gamedata skip in 23.98 s. Matched 144-perspective cost is running. All six new kind/mask cases passed.
- Asked coordinator whether new-engine full scope includes all 82,231 C56 perspectives now that the five former S117 exclusions are repaired, or retains 62,766 S117. Existing s122 phase is the disjoint 19,465-perspective remainder. Continue matched QA while awaiting scope answer.
- No scope answer yet after >60 seconds. Stated assumption: full C56 means all 82,231 on the repaired engine. Will QA newly eligible s122 opponents before launch; coordinator can still steer back to original subset. Added --total-perspectives to the QA projection script and --phase to deterministic QA, without changing the extractor.

## Matched replacement cost complete; S122 QA running
- 144/144, zero errors, 100,849 rows validated. Retention 100,661/138,034 = 72.9248%, up 7.7408 points from 65.1839%. Placement 8,490/8,505 = 99.8236%. Illegal supervised labels 0; opponent hand/elixir cuts 0 points. Hard-cut branch unchanged.
- New matched timing median 6.1465 s, p90 12.9498 s; S117 projection 41.77 h / 3.563 GiB. New-runtime S117 byte determinism runs are finishing.
- S122 48-perspective sample includes all five previously excluded opponent cards: Void 11, Collector 12, Vines 11, Drill 13, Curse 3 deck occurrences. Added a detached single-worker sample plus independent six-perspective byte repeat, PID 25726; <=3 workers including the other gate runner.
- Exact command (two-second startup hold): `/Users/sam/Desktop/code/clasher/reports/strategy_council_20260928/pilot/detach.sh /Users/sam/Desktop/code/clasher/reports/strategy_council_20260928/c56/data/logs/qa-s122-engine-v2b.log env CLASHER_ROOT=/Users/sam/Desktop/code/clasher/reports/strategy_council_20260928/c56/data/runtime-engine-v2 PYTHONPATH=/Users/sam/Desktop/code/clasher/reports/strategy_council_20260928/c56/data/runtime-engine-v2/src OMP_NUM_THREADS=1 nice -n 10 /bin/sh /Users/sam/Desktop/code/clasher/reports/strategy_council_20260928/c56/data/qa/run_s122_gates.sh`.
- Replacement S117 determinism PASSED: both six-perspective NPZ SHA-256 dfcc8db70ce570ed891eb8005ff563e2cf88e5b15d23f4ad933942f5426fe507, cmp zero. Gate runner PID 22073 completed. Matched before/after metrics and per-side rates appended to QA_SUMMARY.md. Only PID 25726 / its single S122 worker remains active for data QA.
- S122 cost complete: 48/48 with zero errors, all 28,612 rows validated. Placement 2,294/2,302 = 99.6525%; illegal labels 0; retention 28,552/45,828 = 62.3025%. Two OWN hard elixir cuts, zero opponent hand/elixir cuts. Own cuts remain hard; opponent policy unchanged. S122 median 4.119 s / p90 9.7125 s. Combined 82,231-perspective projection: 50.72 h on three workers, 4.517 GiB output plus ~0.40 GiB existing data. Awaiting S122 determinism before full launch.

## FULL EXTRACTION LAUNCHED 2026-10-03T05:45:31.581134+00:00
- All gates pass on revised replacement runtime. S122 six-perspective repeats match SHA-256 17e9e66c3db100012b76acc0c5e9e95537ee9607c9feb0996512a136e3750af9. Gate PID 25726 finished.
- Full 82,231 C56 perspectives: sequential S117 62,766 then disjoint S122 19,465. No coordinator scope reply arrived; proceeded with stated full-C56 assumption after the new-opponent QA passed.
- Detached parent PID 29832, nice 10, at most three extraction workers. Exact launch/resume command (keep invoking process alive two seconds after detach): `/Users/sam/Desktop/code/clasher/reports/strategy_council_20260928/pilot/detach.sh /Users/sam/Desktop/code/clasher/reports/strategy_council_20260928/c56/data/logs/full-engine-v2b.log env CLASHER_ROOT=/Users/sam/Desktop/code/clasher/reports/strategy_council_20260928/c56/data/runtime-engine-v2 PYTHONPATH=/Users/sam/Desktop/code/clasher/reports/strategy_council_20260928/c56/data/runtime-engine-v2/src OMP_NUM_THREADS=1 nice -n 10 /bin/sh /Users/sam/Desktop/code/clasher/reports/strategy_council_20260928/c56/data/scripts/run_full.sh`.
- Driver scripts/run_full.sh runs the phases sequentially and writes recon/engine-v2b/completion.json with counts/errors at the end. Completed unit sidecars are skipped on resume.
- Reused four validated same-runtime cost units, 192 perspectives; no old-engine shards reused. Runtime source hash, frozen role/eval hashes and seeded shard hashes verified again before launch.
- Projection: 4.517 GiB output; 4.913 GiB total data; 50.60 hours remaining at launch, ETA 2026-10-05T08:21:49.378356+00:00. Free-space gate retains >18 GiB after projection. launch.json records exact values.
- Next: inspect worker PIDs and validate newly finished full-run units.
- Live process check: detached parent 29832 -> S117 driver 29835 -> workers 30229, 30230, 30231; all nice 10. Resource tracker 30228 is not an extraction worker. Startup log reports 1,331 pending S117 units, confirming the three completed seed units were skipped. All completion receipts, hashes and limitations consolidated into qa/QA_SUMMARY.md. Awaiting three newly generated units for final persisted-shard validation.

## Final verification 2026-10-03T05:54:29.127552+00:00
- Three new full units (shard-000-part-01/02/03) finished: 48 perspectives each, zero errors; walls 359.0 / 310.5 / 292.9 s. All persisted rows pass validators.
- Full-run source/role/eval hashes and startup resume behavior verified. No further coordinator decision is required to continue the stated all-C56 run; known fidelity gaps remain in QA_SUMMARY.md.
- Files changed this takeover: src/clasher/rl/contract_v5.py and public_action_mask.py; data/PROGRESS.md; data/scripts/c56_bootstrap.py, qa_extract.py, qa_determinism.py, run_full.sh; data/qa/QA_SUMMARY.md, test_engine_contract.py, gate runner scripts and QA evidence; new data/runtime-engine-v2 snapshot and overlay revision receipt; data/recon/engine-v2b launch/output evidence; engine/ENGINE_FREEZE_READY acknowledgement only. Original role/eval files and old runtime unchanged.
- 2026-10-03T06:53:34Z coordinator decision (champion repairs landed after the 05:23Z freeze: Mighty Miner lane switch/bomb, Goblinstein tether; abilities masked in the C56 scripts; Tornado King activation still unconfirmed): do NOT restart the full extraction. After it completes, re-extract only perspectives where either deck has a champion (archer-queen, mighty-miner, goblinstein) on a NEW frozen copy of the workspace engine (src/clasher after engine Phase 2, identity-verified), replace those units, and report retention before/after for that subset. BC waits for that refresh.

## v3

Implementation started. Read tower-gap evidence and Stage 0 receipt. Temporarily paused the authorized v2 tree for the three-heavy-process cap during QA; finished units retained. Frozen role/eval untouched. V3 gates pending.

V3 frozen 2026-10-03T22:38:22.123493+00:00. Stage 0 marker present and drivers absent. Workspace copy checked before/after, v2 RL overlays plus opt-in clamp. Runtime SHA256 2e9fc689462669d021fcc3dc51dd0b47149011cb9793c8ea47cb491b224655fc; gamedata 3d99987c19cb94a0c8a6795e943829771078e564859e34c1411e221e5d57486a. Identity and contracts pending.

V3 reuse inventory: 44408 finished v2 perspectives; 10054 conservative reuse candidates; random audit 202 (seed 5603003). Game-over perspectives also excluded. No reuse admitted yet.

V3 contracts: 37 passed, one expected historical checkpoint/gamedata skip. P16 identity: 12 episodes, 15,949 boundaries, zero mismatches. Default flag: six fixed perspectives compared to the prior replayer on the same engine, complete NPZ bytes identical. QA orchestration interrupted by an edit of its running shell file; no data loss, restarting from resumable results. Existing extraction scripts are unchanged; v3 uses separate scripts.

V3 clamp determinism: two independent processes, six perspectives, identical NPZ SHA256 132fbdaa9e8aac583a37d0b0df2faf4212c7c00f847467566a40227c112a6cb4. Detached QA PID 93894 is running 202 reuse comparisons then all 300 tower-gap matched perspectives, at most three nice-10 workers.

V3 reuse audit completed: {"checked": 202, "differences": 0, "rows": 139501}. All existing per-row bytes and legacy summary fields compared; two new fields were zero/false. Full matched QA remains pending.

V3 BLOCKER: matched QA stopped after 26/300 completed pairs. Frozen and workspace c56_champions.py both dereference e.card_stats.summon_character_data without guarding None in GoblinsteinTether.on_attach, line 148. Engine mechanics are outside this task authorization. No full v3 launch; no v2 output deleted. Requested engine-owner repair or explicit authorization for the narrow guard. Continuing QA to record failing perspectives; old v2 remains temporarily paused during bounded QA.

Frozen-runtime contract verification corrected: pytest rerun with -c /dev/null and cwd runtime-engine-v3 to suppress repository pythonpath injection; 37 passed, one historical gamedata skip in 23.84 s. Separate focused Goblinstein regression fails at frozen c56_champions.py:148 in 0.54 s. Logs: v3-contract-tests-frozen.log and v3-goblinstein-regression-frozen.log. Replay QA runtime binding was already verified in each process.

V3 serializer round-trip passed: six clamped perspectives, 4,554 rows; every compact field and perspective summary preserved byte-for-byte, zero illegal labels. Weight API tower_clamp_weights(existing_weights, summary, submitted_ticks) multiplies prior PLAN 4.6 factors by 0.5 at/after first_clamp_tick, even if the tower later leaves the clamped state. Focused tests cover multiplication, strict >1.0 threshold, both owners, King towers, allowed deaths and lane proof. No BC fitting.

Exact Goblinstein reproduction: shard 12/index 967, c2ed6383ed1d483ba291325ac578138e opponent. Both clamp-off and clamp-on fail at tick 5131 before any clamp. A friendly RollingProjectile has card_stats=None and is included by GoblinsteinTether.on_attach. This is a refreshed-engine failure independent of the clamp, not a newly retained tail. Evidence: qa/v3/goblinstein-reproduction.json. Minimal engine-owner repair is to exclude entities with no card_stats before the summon_character_data lookup; no mechanics file was edited here.

V3 300-perspective diagnostic complete: {"admitted": false, "attempted": 300, "caveat": "Diagnostic statistics exclude one failed perspective; full sample admission is blocked.", "errors": [{"error": "AttributeError(\"'NoneType' object has no attribute 'summon_character_data'\")", "item": {"index": 967, "shard": 12, "side": "opponent", "tag": "c2ed6383ed1d483ba291325ac578138e"}, "mode": "matched"}], "failed_pairs": 1, "illegal_labels": 0, "projected_output_gib": 6.887291805049324, "projected_total_data_gib": 7.326093647790993, "successful_pairs": 299, "v2_matched_retention": 0.7649351752851792, "v3_clamp": {"attempts": 20988, "clamped": 113, "cuts": {"opponent_placement_rejected": 5, "own_insufficient_elixir": 4, "own_masked_tile": 20, "own_placement_rejected": 5, "pocket_play_but_sim_tower_alive": 18, "recorded_end": 87, "sim_game_over": 129, "sim_kill_of_tower_standing_in_real": 31}, "perspectives": 299, "placement_acceptance": 0.9977129788450543, "possible": 282454, "rejected": 48, "retention": 0.8533955971591834, "supervised_rows": 241045}, "v3_no_clamp": {"attempts": 18405, "clamped": 0, "cuts": {"opponent_placement_rejected": 4, "own_insufficient_elixir": 3, "own_masked_tile": 16, "own_placement_rejected": 4, "pocket_play_but_sim_tower_alive": 16, "recorded_end": 68, "sim_game_over": 75, "sim_kill_of_tower_standing_in_real": 113}, "perspectives": 299, "placement_acceptance": 0.997826677533279, "possible": 282454, "rejected": 40, "retention": 0.7708086980534884, "supervised_rows": 217718}, "validated_rows": 241461}

V3 S122 remainder QA: {"perspectives": 48, "retention": 0.735052806144715, "supervised_rows": 33686, "possible": 45828, "placement_acceptance": 0.9972027972027973, "attempts": 2860, "rejected": 8, "clamped": 24, "cuts": {"sim_game_over": 17, "recorded_end": 10, "own_insufficient_elixir": 3, "own_placement_rejected": 2, "sim_kill_of_tower_standing_in_real": 8, "pocket_play_but_sim_tower_alive": 2, "opponent_placement_rejected": 1, "opponent_insufficient_elixir": 2, "own_masked_tile": 3}, "illegal_labels": 0, "validated_rows": 33743, "v2_before": 0.6230252247534258}

V3 handoff BLOCKED. No v3 full extraction or replacement deletion. Engine-owner fix required at src/clasher/cards/c56_champions.py:148; exact reproduction fails with clamp off/on at tick 5131. Restored v2 parent 29832 / driver 29835 and workers 71463,79327,81457 from this task's temporary pause; resource tracker 30228 restored too. All QA jobs have exited. Reuse verification 202/202 passed over 139,501 rows; 10,054 conservative candidates, none copied yet. Matched diagnostic 299/300 pairs completed; one engine exception, zero illegal labels. V2 matched retention 76.4935%, v3 no-clamp 77.0809%, v3 clamp 85.3396%; placement 99.7713%. S122 48/48 passed: retention 62.3025% -> 73.5053%; placement 99.7203%; zero illegal labels. Six clamped perspectives repeat exactly; default six NPZ outputs unchanged. Frozen contract tests 37 pass/1 skip; separate engine regression fails. Projected total data 7.326 GiB based on successful sample, current data about 3.0 GiB; host free about 14.3 GiB. ETA unavailable until engine repair/readmission. Resume path after engine repair: preserve the blocked snapshot and qa/v3 evidence under separate names, take a new freeze, rerun identity/contracts including the regression and all QA, then admit_v3.py, stop_v2.py, and detach extract_v3.py with three nice-10 workers. Existing v2 extraction scripts, role/eval files, engine mechanics and protected directories were not modified.

## Tether repair takeover 2026-10-03T23:25:46.118479+00:00
Authorized narrow engine fix and v3 refresh. V2 tree temporarily SIGSTOP for QA capacity: [29832, 29835, 15555, 30228, 79327, 81457]. Finished units and previous QA retained. Initial free disk 14.29 GiB; data 3.05 GiB.

Tether root cause verified: spells.py RollingProjectile construction intentionally sets card_stats=None; on_attach scans all friendly live entities, not only troops. One predicate now excludes statless entities before reading summon_character_data. Pre-fix focused regression fails at line 148 as expected. Scope/regression suite and workspace P16/C56 identities running; equivalent C56 command logs only to c56/engine, leaving engine-speed untouched.

V3 frozen 2026-10-03T23:28:40.300392+00:00. Stage 0 marker present and drivers absent. Workspace copy checked before/after, v2 RL overlays plus opt-in clamp. Runtime SHA256 af205b0bc8614ff8a2ac794c7af0708f8822fe29681fccf6fd8ba7eaebe7ba82; gamedata 3d99987c19cb94a0c8a6795e943829771078e564859e34c1411e221e5d57486a. Identity and contracts pending.

Refreshed v3 snapshot with original freeze_v3.py workflow. Preserved blocked snapshot as runtime-engine-v3-blocked-tether and all QA as qa/v3-blocked-tether. Source checked stable before/after copy. Only runtime delta is c56_champions.py; new hash af205b0bc8614ff8a2ac794c7af0708f8822fe29681fccf6fd8ba7eaebe7ba82. Expanded statless-entity regression covers both no monster and successful binding; 20 scope/regression tests pass.

Workspace identities PASS: P16 12 episodes / 15,949 boundaries and C56 7 episodes / 2,900 boundaries, zero mismatches. Frozen contracts 37 passed / 1 historical gamedata skip; frozen regression 2 passed. Frozen P16 still running. Fresh repair QA launched with two nice-10 workers: 40 paired perspectives including the exact crash, independently repeated, then six default comparisons and 48 S122 perspectives. Prior 202/202 reuse proof remains applicable because the only runtime delta is the Goblinstein attachment guard, and reuse excludes every champion deck; this is carried evidence, not claimed as a fresh audit.

Frozen P16 identity PASS: 12 episodes / 15,949 boundaries / zero mismatches. Exact formerly crashing perspective now completes in both clamp modes with 1,202 rows each and zero illegal labels. Fresh 40-case double replay remains running; six-perspective whole-shard determinism launched separately after frozen identity exited, keeping at most three heavy processes.

Fresh six-perspective whole-NPZ determinism PASS: both SHA256 132fbdaa9e8aac583a37d0b0df2faf4212c7c00f847467566a40227c112a6cb4, identical to the blocked snapshot for these unaffected cases. First 40-case pass still running without errors. A separate exact clamp-off/on reproduction launched after determinism completed, in addition to the 40-case sample. Disk guard implemented in v3 driver: pause own workers and driver below 12 GiB free or at 7.375 GiB data, reserving 128 MiB under the hard cap. Admission cap changed to 7.5 GiB.

Fresh first 40-perspective paired pass complete: retention 74.7288% no-clamp -> 85.5217% clamp; placement 99.6298%; 31,582 stored rows validated, zero illegal labels. Independent second pass running. Fresh output projection 6.9225 GiB; total data approximately 7.3773 GiB including preserved snapshots and QA, just above the driver soft pause point of 7.375 GiB and below the hard 7.5 GiB cap. Forecast uncertainty and disk pauses remain operational risks; no unsupported completion claim.

Fresh 40/40 independent paired repeats PASS: identical clamped NPZ SHA256 values and identical before/after summaries for every perspective. Both clamp modes of exact crash also pass in separate reproduction; old failure evidence remains in qa/v3-blocked-tether. Fresh default and S122 checks finishing before admission. No v2 output deletion or full v3 launch yet.

V3 admission PASS. Reusable 10054; projected total data 7.378 GiB; initial estimate 29.56 hours on three workers, subject to first-unit timing and host load. Gates: qa/v3/gates.json.

V3 repair admission PASS. Fresh 40 cases twice, 63,164 validated rows, zero illegal labels, 99.6298% placement; matched v2 retention 76.3152%, v3 no-clamp 74.7288%, clamp 85.5217%. Fresh S122 48/48, 33,743 rows, 99.7203% placement, 73.5053% retention, zero illegal labels. Six default byte comparisons and six whole-NPZ repeats pass. Reuse allowed: 10,054 candidates under carried 202/202 audit with sole-runtime-delta proof. Projection 7.378133570216596 GiB total; initial QA timing estimate 29.558558019922845 hours on three workers. Admission qa/v3/gates.json. Next clean v2 stop then detached v3 launch.

V2 stop script SIGINT did not exit the detached tree within 30 seconds; no v3 driver started. Added bounded SIGTERM fallback only after verifying process group 29832 contains exactly the recorded authorized v2 tree. Finished units remain untouched; no other process group is signalled.

V2 tree fully exited after verified-group SIGTERM fallback; finished units retained. V3 LAUNCHED detached PID 27633, three nice-10 workers, clamp enabled, resumable replacement/reuse post-pass. Log logs/full-engine-v3-tether.log; exact command/environment in recon/engine-v3/launch.json. Launch free 16.145885467529297 GiB, data 3.060104826465249 GiB. First-unit verification pending.

V3 startup confirmed: driver 27633, worker PIDs 28016/28017/28018, resource tracker 28015, all nice 10. Queue contains 1,767 units across S117 and S122. Runtime manifest pins af205b0bc8614ff8a2ac794c7af0708f8822fe29681fccf6fd8ba7eaebe7ba82 and updated driver/script hashes; reuse inventory pinned. Current data 3.06 GiB, free approximately 15.18 GiB. First units still running.

## Tether fix and v3 verified launch 2026-10-03T23:51:28.399639+00:00
Engine change is exactly one guard in GoblinsteinTether.on_attach, excluding intentionally statless rolling spell projectiles. Focused scope/regression 20 passed; contracts 37 passed / 1 historical skip; frozen regression 2 passed. Workspace P16 0/15,949 mismatches, workspace C56 0/2,900, frozen P16 0/15,949. Runtime SHA256 af205b0bc8614ff8a2ac794c7af0708f8822fe29681fccf6fd8ba7eaebe7ba82. First three persisted v3 units independently revalidated while only this extraction group was temporarily paused; resumed afterward. 144 perspectives / 122,263 rows / zero illegal labels; 15 verified reuse copies, 129 fresh replays. NPZ hashes match sidecars; superseded v2 NPZs removed after verification, old sidecars retained. Exact receipts: recon/engine-v3/first-units-verified.json and verified-launch-status.json. Driver 27633; workers [28016, 28017, 28018]; all nice 10. Measured remaining estimate 34.88 hours, ETA 2026-10-05T10:44:12.946906+00:00. Projected total data 7.378 GiB; launch disk 16.146 GiB free / 3.060 GiB data; current 16.173 GiB free / 3.062 GiB data. Full extraction remains running. Disk guard SIGSTOPs own workers/driver below 12 GiB free or above 7.375 GiB data; 7.5 GiB hard cap. Projection is close to the soft stop, so a disk pause may prevent uninterrupted completion. No other mechanics edits, protected-directory writes, frozen role/eval changes, or unrelated process signals. Reuse audit is explicitly carried 202/202 evidence with one-file delta/champion-exclusion proof.

Changed files for this takeover: src/clasher/cards/c56_champions.py; data/qa/v3/test_goblinstein_regression.py; data/scripts/{extract_v3,admit_v3,stop_v2,qa_tether_v3}.py; engine/run_tether_identity.sh; data/qa/v3/run_tether_{frozen_gates,determinism}.sh; both PROGRESS.md and data/qa/QA_SUMMARY.md; refreshed/archived v3 runtimes, QA logs/receipts and extraction artifacts. Resume using exact command/environment in recon/engine-v3/launch.json only after confirming no active driver; normal resume skips published units.

## V3b crash repair 2026-10-04T10:41:29.218611+00:00
Verified old extraction driver/workers absent; 270 finished units preserved. Authorized work limited to c56_champions.py engine logic, extraction driver/support, focused tests and receipts. Initial data 3.2 GiB, free 20 GiB. Pulse callback can clear next_hit_ms through on_death before the loop increments it. Step 1 regression and identity gates starting. No unrelated processes signalled.

V3b step 1 2026-10-04T10:45:05.723619+00:00: pre-fix focused regression fails twice at original line 187. Fix advances the timer before _pulse so synchronous death callbacks can cancel it. Scope + previous statless-entity regression + new cancellation tests: 22 passed. Four-mode canonical workspace identity PID 29495 still running.
Step 2 sweep plan pins all 27,649 champion perspectives and all 270 finished units, 12,607 perspectives. Seeded 2% finished sample = 253, seed 5604004. Fixed replay workers 31691/31697, nice 10; third CPU slot reserved for identity. Counterfactual timer instrumentation records perspectives that would hit the old None increment; actual exceptions retain full traceback.
Provisional v3b copy made with original freeze workflow and overlays; workspace stability verified. Runtime hash 1ec2c60c254fd9cc5579b163ef994a0e233a942bd97acda864d31d91442d3493. Gamedata copied explicitly from runtime-engine-v3, SHA256 3d99987c19cb94a0c8a6795e943829771078e564859e34c1411e221e5d57486a; canonical workspace gamedata is NOT used. Delta versus v3: champion fix plus existing council_pilot.py and script_rollout_planner.py workspace changes, neither edited by this task. Frozen reuse gate pending.
Step 3 driver catches per-perspective exceptions and durably logs unit/id/traceback to errors.jsonl, records exclusions in the existing sidecar errors field, and counts failures across resumed and new units. It stops new dispatch above 0.5%; output columns unchanged. Tests pending.

V3b step 3 validation 2026-10-04T10:47:02.290684+00:00: injected per-perspective failure tests pass for mixed success and all-failed units, proving later perspectives execute, tracebacks persist, exclusions match receipts, and resume skips both unit types. Real Golem death-damage regression also reproduces the old crash. Original frozen runtime: all 3 new tests fail at line 187. Fixed frozen runtime: 23 scope/Goblinstein tests pass. Driver + new workspace regressions: 5 pass. P16 identity 0/15,949 and C56 identity 0/2,900; recorded/random identity still running. Slot-2 supervisor PID 34603 waits for identity exit and success marker, runs 253 reuse checks on one worker, then starts the third sweep partition. Sweep PIDs 31691/31697 remain live. Full sweep is mandatory and pending; no extraction resume yet.

V3b continuation 2026-10-04T10:50:06.905041+00:00: all implementation work is prepared. Final combined workspace tests: 25 passed. Detached finish supervisor PID 37878 waits for owned sweep workers 31691/31697 and slot-2 supervisor 34603 to exit, confirms every cancellation witness on original v3, requires full sweep/reuse/identity gates plus unchanged finished-file hashes, then launches extraction via pilot/detach.sh and verifies three new units. No gate may be skipped. Exact commands: qa/v3b/slot2.sh and qa/v3b/finish.sh; logs in qa/v3b. At handoff within this active session these gates remain pending, and extraction has NOT resumed. Current conservative projected data 7.401 GiB; estimate from 12,607 actual finished perspectives 6.090 GiB. Disk guard remains 7.375 GiB soft / 7.5 GiB hard.

V3b step 1 COMPLETE 2026-10-04T11:17:05.159502+00:00: check_identity.sh c56_v3b passed all four modes. P16 12 episodes / 15,949 boundaries, C56 7 / 2,900, recorded 8 confirmations, random 24 episodes / 7,198 boundaries; all zero mismatches. Identity PID 29495 exited.
Reuse QA found a comparison-container issue: all logical array bytes, dtypes, shapes and summaries matched, but part() makes C-order copies while compact replay features can be Fortran-order. NPY headers and entry bytes proved the layout difference. Preserved initial evidence under qa/v3b/reuse-serialization-layout. Comparator now restores the original persisted storage order before comparing single-perspective NPZ bytes, with original provenance. No engine or driver change for this QA issue. Stopped only owned slot-2 group 34603 and owned finish supervisor 37878 after checking group ownership. Restarted slot-2 supervisor as PID 64317; it runs the full 253 sample then sweep partition 2. Sweep workers 31691/31697 continue, with no engine exceptions so far.

V3b step 4 reuse gate PASS 2026-10-04T11:32:06.182723+00:00: 253/253 seeded finished perspectives re-extracted successfully. Every dtype, shape, logical array byte, and perspective summary matches. Single-perspective NPZ bytes also match after using the original persisted storage order and provenance. All 270 original finished units remain in place. Receipt qa/v3b/reuse-summary.json; per-perspective SHA256 values in reuse-???.jsonl. Runtime 1ec2c60c254fd9cc5579b163ef994a0e233a942bd97acda864d31d91442d3493; champions c670df5510503c0b8d78d45d53da9cd201bd63943fe2c6c91e7856b332d91181; original v3 gamedata 3d99987c19cb94a0c8a6795e943829771078e564859e34c1411e221e5d57486a retained. Canonical workspace gamedata is not used for extraction. Step 2 exhaustive sweep remains pending; all three workers now run sweep partitions, PIDs 31691/31697/64317, nice 10. Restarted finish supervisor is PID 64666, command qa/v3b/finish-restart.sh. Extraction remains gated.

V3b sweep coverage independently checked against index/perspectives.jsonl.gz using normalized own/opponent base decks: exactly 27,649, zero missing or extra perspective IDs. Receipt qa/v3b/sweep-coverage.json pins index SHA256 f368af125b72e423d54826e16c5a75db113dae3cc4a8a2102adb68d0b362bb45. Sweep remains in progress with zero engine exceptions at 3,210 completed.

V3b sweep checkpoint 2026-10-04T13:00:54.823745+00:00: 7047/27649 perspectives complete, 0 engine exceptions, 1 timer-cancellation witnesses so far. Workspace champion source still matches the tested c670df55 hash. All identity suites and 253/253 reuse comparisons passed. Active sweep PIDs 31691/31697/64317; gated finish supervisor 64666. Extraction has not resumed.

V3b real crash confirmation 2026-10-04T13:02:09.513230+00:00: shard 11/index 362/team, episode 1100724, match 5becf104f0bb41f685cf9784088a82e2. Original runtime-engine-v3 reproduces the exact line-187 NoneType += int exception. Fixed v3b completes to recorded_end with 720 rows; doctor 291 dies during the pulse at tick 3204 and its cancelled timer stays None. Evidence: qa/v3b/crash-first-before.log, crashes-before.json and sweep-011.jsonl. Only owned sweep PID 64317 was paused briefly for this reproduction to keep at most three heavy processes, then resumed in finally. No further engine edit needed. Remaining sweep still required before extraction resume.

V3b driver follow-up 2026-10-04T13:56:36.702540+00:00: an all-failed unit now removes any unreceipted final NPZ left by an interrupted attempt before publishing its exclusion receipt. Published units still return through the unchanged skip/verify branch first. Both driver regression variants now begin with an orphan NPZ and prove successful replacement or exclusion cleanup, followed by resume skipping. Combined scope/previous Goblinstein/new death/driver suite rerun: 25 passed. Engine source unchanged, so previous four-mode identity and reuse gates remain applicable. Only owned sweep PID 64317 was briefly paused for CPU capacity during this test run and restored in finally.

V3b launch-helper check 2026-10-04T14:06:30.289585+00:00: supervisor already has nice 10, so launch computes the relative nice adjustment to land exactly at nice 10 instead of adding another 10. A real parent/child probe returned nice 10 for both. Launch receipt will record caller/target priority, the actual command, and the portable command for a normal nice-0 shell. Driver/engine unchanged by this helper correction.

V3b sweep checkpoint 2026-10-04T15:04:29.633395+00:00: 13971/27649 complete, 0 engine exceptions, 1 timer-cancellation witnesses. Original v3 crash 1100724 confirmed; fixed engine completes it. Workspace champion hash unchanged. All identity and 253 reuse gates passed. Owned sweep PIDs 31691/31697/64317, finish supervisor 64666. No extraction resume before the full sweep passes.

V3b sweep checkpoint 2026-10-04T17:01:16.845917+00:00: 20218/27649 complete, 0 repaired-engine exceptions, 1 timer-cancellation cases. One original-v3 crash has already been confirmed independently. Workspace champion hash remains c670df55. Identity, frozen tests and 253 reuse comparisons passed. Workers 31691/31697/64317 and gated supervisor 64666 remain owned by this task. No extraction resume until full coverage.

V3b sweep checkpoint 2026-10-04T18:40:22.006878+00:00: 25608/27649 complete, zero repaired-engine exceptions. Partition counts {2: 7955, 0: 9030, 1: 8623}; targets {0:10178,1:8623,2:8848}. Original crash count confirmed so far: 1. Remaining partitions continue before admission and resume.

V3b steps 1-4 PASS: {"checks": {"reuse": {"attempted": 253, "failures": 0, "old_timer_would_crash": 0, "results_sha256": "f20f32ed6c8129e3f89f1cc8fcd5e767e287a5bd399ea2bfb0cb07838e5f96fa"}, "sweep": {"attempted": 27649, "confirmed_original_crashes": 1, "failures": 0, "old_timer_would_crash": 1, "results_sha256": "2c5f28f686c744fd8f6368a9223e0689bd534fe65a98d880b661fa82ee91e153"}}, "data_gib": 3.221434206701815, "driver_sha256": "8e95786c1dede45e9fd8d02f8c85cd86331667d3dbc5c8a6713808f0520ac9c7", "finished_files_verified": 540, "finished_perspectives": 12607, "free_gib": 16.419513702392578, "gamedata_note": "Original v3 gamedata retained; canonical workspace gamedata is NOT used.", "gamedata_sha256": "3d99987c19cb94a0c8a6795e943829771078e564859e34c1411e221e5d57486a", "gamedata_source": "/Users/sam/Desktop/code/clasher/reports/strategy_council_20260928/c56/data/runtime-engine-v3/gamedata.json", "identity": {"C56": 2900, "P16": 15949, "mismatches": 0, "random_episodes": 24, "recorded": 8}, "previous_manifest_sha256": "fd23698acb2ffe4d45aa61b605d13b88f3b6faa699ca7c1a040e5844618c1d91", "projected_data_gib_conservative": 7.408130060322582, "runtime": {"files": 366, "overlay": {"contract_v5.py": "02e00388080bd94da2da2d58e64127ef9d9defc3e0139e26ec6e563bf38cbe86", "contract_v5_tokens.json": "5e20ce085662869fb4f0b56fee7851007b4c146d32e56b97da05a3058cf1b4f0", "human_replay_bc.py": "60f6de6970739a8946918eb5ba89ba6232b6a46b32d8ad9ad51af0100976a5fd", "human_replay_demonstrations.py": "703f25c447c119bf1bd7d31b2ffc9980efee445a0a871c86e470be46a204af4b", "human_replay_v5.py": "8d457b9975404f6503ce722fee98efa126c2a7f2337e095f621f10b3eac0e03a", "model.py": "e513b0c661fab21e35ad6f2ffc64d6cfd01d7dc7b4fc480435e38e33a285d989", "public_action_mask.py": "e6e94abae45b0988dbcc087970a11cc0b2f07fc1cc335decec75b5714798d107", "structured_obs.py": "e74b97e5f5dc8f97442fee98a113dadc480126b51ed997868a11a318db5f127a"}, "runtime": "/Users/sam/Desktop/code/clasher/reports/strategy_council_20260928/c56/data/runtime-engine-v3b", "sha256": "1ec2c60c254fd9cc5579b163ef994a0e233a942bd97acda864d31d91442d3493"}, "tests": {"frozen": 23, "workspace": 25}, "utc": "2026-10-04T19:50:03.902353+00:00"}

V3b step 5 detached resume launched: {"pid": 15128, "finished_units_skipped": 270, "log": "logs/full-engine-v3b.log"}

V3b first new units verified; extraction running: {"complete": false, "conservative_projection_gib": 7.408130060322582, "data_gib": 3.2234126338735223, "driver": 15128, "eta_basis": "new unit replay cost; remaining eligible v2 copies excluded; three workers; load dependent", "eta_utc": "2026-10-05T16:03:56.019235+00:00", "finished_original_files_unchanged": 540, "finished_perspectives": 12751, "finished_units": 273, "historical_remaining_hours": 23.73883854861057, "nice": 10, "pending_reuse": 7160, "projected_data_gib": 6.101461892169103, "remaining_hours": 20.17706172839506, "running": true, "seconds_per_fresh_replay": 3.4966666666666666, "utc": "2026-10-04T19:53:18.596996+00:00", "verified_units": [{"illegal": 0, "perspectives": 48, "rows": 40024, "sha256": "d041144eba83d09cf262863c924ead5b01b391796e5ff79112f9dcc6ce5dcce8", "unit": "s117/shard-011-part-04.json", "wall_seconds": 141.15}, {"illegal": 0, "perspectives": 48, "rows": 38908, "sha256": "b85de1a571a62df40656ce5eedffc3454fed8e08a655e99082cb89448ee45c64", "unit": "s117/shard-011-part-05.json", "wall_seconds": 120.23}, {"illegal": 0, "perspectives": 48, "rows": 38844, "sha256": "04d337c240a13ec281635c790279ed810f12e4b118d2f5861706f702c1e57955", "unit": "s117/shard-011-part-06.json", "wall_seconds": 126.75}], "workers": [15631, 15632, 15633]}

## V3b verified resume 2026-10-04T19:57:03.471495+00:00
Goblinstein's pulse can invoke the doctor's death callback, clearing next_hit_ms before the old increment. Advancing the timer before the pulse preserves cancellation. Only c56_champions.py engine logic changed; the previous statless-entity guard remains intact.

Final tests: 25 workspace and 23 frozen passed. Four workspace canonical-data identities passed with zero mismatches: P16 12 episodes / 15,949 boundaries; C56 7 / 2,900; recorded 8 confirmations; random 24 / 7,198. Full champion sweep: 27,649 perspectives, zero exceptions. One original-v3 crash was reproduced; no further champion fix was needed. Episode 1100724 now has 720 valid persisted rows in s117/shard-011-part-05.npz.

Reuse audit: 253/253 seeded random finished perspectives match every dtype, shape, logical array byte and summary. Per-perspective NPZ bytes match using original storage order and provenance. All 540 original finished files remain byte-identical, covering 270 units / 12,607 perspectives.

Runtime SHA256: 1ec2c60c254fd9cc5579b163ef994a0e233a942bd97acda864d31d91442d3493.
Champion SHA256: c670df5510503c0b8d78d45d53da9cd201bd63943fe2c6c91e7856b332d91181.
Gamedata SHA256: 3d99987c19cb94a0c8a6795e943829771078e564859e34c1411e221e5d57486a. Original v3 gamedata is retained; canonical workspace gamedata is NOT used for extraction. The original freeze method and eight overlays were retained. The snapshot also copies existing workspace council_pilot.py and script_rollout_planner.py changes, neither edited by this task.

Driver logs each failed perspective with unit/id/full traceback to errors.jsonl and the existing sidecar errors field. Failed perspectives are excluded. Dispatch stops above 0.5% cumulative published attempts; active units finish before exit. Dataset columns and deterministic serialization are unchanged. Completed receipts skip replay; all-failed units discard unreceipted final NPZs from interrupted attempts.

Resumed via pilot/detach.sh. Current v3b status at 2026-10-04T19:57:03.471495+00:00: repair and all gates passed; detached extraction is running. Driver 15128; workers 15631/15632/15633, nice 10. First three new units verified: 144 perspectives / 117,776 rows, zero errors or illegal labels. Original 270 units unchanged. ETA 2026-10-05T09:03:56.019235-07:00, load dependent. Full extraction is not complete.
The first three units contain 33 eligible v2 copies and 111 fresh replays. Their hashes and validation are in recon/engine-v3/verified-launch-v3b.json. Only the newly launched session was briefly paused for independent verification, then resumed. No unrelated process was signalled.

Estimated remaining time: 20.18 hours. ETA uses fresh unit replay cost, excludes 7160 remaining eligible v2 copies, and assumes three workers. Projected final data: 6.101 GiB; conservative prior-QA projection: 7.408 GiB. Current data: 3.223 GiB. Existing guards pause at 7.375 GiB data or below 12 GiB free, protecting the 7.5 GiB hard cap. The conservative forecast may reach the soft pause. Full extraction remains running.

Evidence: qa/v3b/gates.json, reuse-summary.json, sweep-coverage.json, crashes-before.json, crash-case-persisted.json, tests-final.log, frozen-tests.log; engine-speed/logs/*_c56_v3b.*; recon/engine-v3/launch-v3b.json and verified-launch-v3b.json. Changed-file inventory: qa/v3b/CHANGED_FILES.txt. No other engine logic, gamedata, protected directories, Git state, or unrelated processes were modified.


V3 extraction PAUSED: {"utc": "2026-10-04T21:31:10.384998+00:00", "driver": 15128, "workers": [15375, 16099, 19380], "free_gib": 11.966854095458984, "data_gib": 3.2823390532284975, "reason": "disk limit; workers and driver SIGSTOP; manual resume required"}

V3 extraction PAUSED: {"utc": "2026-10-05T04:01:07.159524+00:00", "driver": 15128, "workers": [75880, 78820, 80416], "free_gib": 11.973094940185547, "data_gib": 3.5046241292729974, "reason": "disk limit; workers and driver SIGSTOP; manual resume required"}
2026-10-05T07:27:43Z coordinator: after T3 restart, SIGCONT extraction pgid 15128 (free disk 18 GiB, data 3.5 GiB < guard limits).

V3 extraction PAUSED: {"utc": "2026-10-05T17:38:27.848568+00:00", "driver": 15128, "workers": [72288, 72289, 72290], "free_gib": 11.997325897216797, "data_gib": 3.5123116075992584, "reason": "disk limit; workers and driver SIGSTOP; manual resume required"}

2026-10-05T20:46Z coordinator agent (f35, via ssh), observation only, no signal sent: driver 15128 and pool workers 72288-72290 are in state S (not stopped), and no process on the host is in state T. recon/engine-v3 has had no new output since about 07:25Z, apart from disk-paused.json written by the 17:38Z guard trip; who later SIGCONTed it is not recorded. The workers have about 1 s of CPU since they spawned at about 07:26Z, while the driver polls. Likely cause: the 07:2xZ T3 restart killed the previous pool workers, and their pending apply_async tasks can never complete, so the driver waits on them indefinitely. Left untouched as instructed (resume only if state T). A fix needs a decision: SIGTERM alone will not unblock it, because pending results never become ready. It needs a kill and relaunch of extract_v3.py with its verified-unit reuse, and only once free disk is comfortably above the 12 GiB guard (currently about 13 GiB), or the remainder should move to f35 as the handoff plans. 811/1767 units as previously recorded.

## f35 migration 2026-10-05
Mac extraction PGID 15128 stopped after verifying exact driver/group, unchanged idle worker CPU and 811 finished units. All 1,622 finished NPZ/sidecar files match f35 by size and SHA256. Signals: SIGTERM, SIGKILL. No other process group touched. f35 output is canonical; Linux frozen-runtime gates must pass before resuming. Receipt: recon/engine-v3/stopped-migration-f35-20261005.json.
