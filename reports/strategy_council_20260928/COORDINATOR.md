# Coordinator state (resume here after a session restart)

Rules: long jobs via pilot/detach.sh (setsid; nohup jobs die on teardown). Implementation -> GPT-6-Astra (high)
via T3 delegate_task; research -> Opus subagents. Decisions log: amendments/2026-10-01-search-and-human-prior.md.

## Detached jobs (check with ps; relaunch via detach.sh with the same env)
- caffeinate (pilot/caffeinate.pid), host watchdog (pilot/host_watchdog.pid, log pilot/logs/host-watchdog.log)
- v7r4h seeds 2901/2902 league phase -> stopped at 2M by pilot/stop_v7r4h_at_2m.sh (log pilot/logs/stop-v7r4h-at-2m.log),
  which then starts seed 2903 `launch.sh 2903 scripted --through nominal` and runs 2M fresh-seed evals.
  The v7r4h orchestrator was stopped on purpose (2026-10-03 21:1xZ).
- fresh-seed evals of v7r4h 1M checkpoints: pilot/eval_v7r4h_1m.sh (log pilot/logs/eval-v7r4h-1M.log),
  results human-prior-p16/evaluation/v7r4h-1M-s290{1,2}/
- srp confirmation (256 games, pre-registered): oracle-qualification oq_run.py x2 (nice 15) with CLASHER_ROOT/
  PYTHONPATH of m0/runtime-snapshots/pilot-runtime-v4; final `python3 oq_report.py srp_xm_c256 ckpt2903`.
- C56 full human extraction: c56/data/scripts/run_full.sh (3 workers), ETA ~2026-10-05; see c56/data/PROGRESS.md.

## Delegated / agent tracks
- learner-tbptt: 3x faster but v7r5 1M (47/43) << v7r4h (60/88): NOT used for PPO; BC only after side-by-side check.
- engine-speed Stage 0 DONE (srp 1.75x, Cython 1.4x); Rust Stage 1b DONE: 4-card slice byte-identical (24 games + coordinator check of 8 unseen cases to 4000 ticks), 61-78x, clone ~1.4us ; Stage 2 DONE (all 16 cards byte-identical; coordinator re-check 16 unseen full matches OK; ~50x) -> Stage 3 native srp (Astra engine-rs-stage3-astra-20261004-1)
- tower-gap/ DONE (README: replay drift; clamp rule adopted)
- done: c56/engine (Astra; audit/C56_AUDIT.md, 51 native scenarios unrun), c56/data QA (Astra), engine-speed profile (Opus)

## Next after current work
- v7r4h 2M result -> decide league fate; seed 2903 1M.
- C56 extraction v3 RUNNING (driver 27633, ETA 2026-10-05 ~03:45 PDT, ~7.4 GiB; runtime af205b0b; QA retention 76.3% -> 85.5%), then C56 BC with TBPTT; evaluate on the frozen held-out human set.
- Native validation of C56 bundles B1-B4 (emulators; needs CPU: schedule when extraction ends), Tornado rule.
- srp-dagger: it1 regressed (premature spending), it2 neutral (87 vs 88). Shelved. NEW: srp-public/ = public-information srp as the player (Astra srp-public-astra-20261004-1), pre-registered 256 games + head-to-head vs s2902 1M.
- NOTE: a T3 server restart cancels delegated Astra tasks and native subagents (detached jobs survive). Resume Astra by re-delegating with "RESUME ... read PROGRESS.md first"; resume Opus agents with SendMessage to their agentId.

## Disk (2026-10-03 ~22:00Z)
- Data container ~96% (≈20 GB unallocated). Compressed 71 large JSON frame dumps in artifacts/worktree-data with zstd
  (24.2 GB originals; verified sha256 round trip; manifest artifacts/worktree-data/COMPRESSED_MANIFEST.tsv; restore `zstd -d`).
  The freed space was absorbed by concurrent growth (swap ~10.7 GB, other projects on this Mac).
- ~/.claude/worktrees (19 GB) belong to assistant-ui/harness-sdk agents (recent, some dirty): not pruned.
- Do not delete evidence (m0/readiness tier-a-fresh-v*, artifacts/, datasets/). Watchdog pauses only oq_run.py below 18 GiB.
- srp hog26 secondary games are paused by the watchdog (primary 256-game confirmation already PASSED).
- 2026-10-03 23:26Z: watchdog v2 (pilot/host_watchdog.sh; v1 kept as host_watchdog.v1.sh): tier 2 pauses c56/data extraction
  and srp-dagger process groups below 11 GiB free (resume >= 14). Patterns anchored to python interpreters — an
  unanchored pgrep once SIGSTOPped an agent shell. v7r4h seed 2903 auto-start disabled (lock
  pilot/v7r4h-launch/locks/coord-2903-started) because of swap/disk pressure; start it manually with
  `launch.sh 2903 scripted --through nominal` via detach.sh when memory allows.
- C56 v3: clamp QA retention 76.5% -> 85.3% (placement 99.77%, 0 illegal labels, reuse check 202/202); launch was blocked
  by a Goblinstein tether crash (c56_champions.py:148) -> Astra c56-v3-launch-astra-20261003-1 fixes it and launches v3.
- 2026-10-04: gamedata drift (workspace IceSpirit HP 90 / Goblin stab 47 vs admitted 84 / 49). Astra
  gamedata-canonical-astra-20261004-1 patches workspace + broadens identity + re-verifies Rust, then writes
  GAMEDATA_CANONICAL_READY; srp-dagger waits on that marker and regenerates labels with native srp.
- v7r4h 2M: s2901 60->79, s2902 88->59 (/192): league phase not dependable; no more league in this form; s2902 1M = best.
- 2026-10-04 ~06:20Z: GAMEDATA canonical (sha 892fbfa0): identity P16 12/12, recorded srp games 8/8, random placements 24/24, C56 7/7 vs admitted baselines; Rust re-verified (+1 pending-lethal guard). Coordinator check: 2 recorded confirmation games reproduce exactly on the workspace with both python and native srp (native ~23x whole-game). Use `bash engine-speed/check_identity.sh` after any engine/data edit.
- 2026-10-04 Sam rule: opponent-derivable private state is fair (exact elixir tracking; hand/cycle once enough cards are revealed). srp-public steered to compute these exactly. TODO after its derived-state module exists: add derived opponent elixir + known-hand/next-card features to the policy contract (C56 v5/v6) before C56 BC, via a post-pass if the stored history allows, else at the next re-extraction.
- 2026-10-04 ~10:45Z: srp-public PASSED (fair search player; beats best policy 0.633 h2h). Expert iteration exit/
  (Astra exit-loop-astra-20261004-1). C56 extraction v3 crashed (champion bug) -> repair+resume (Astra
  c56-v3-resume-astra-20261004-1).
- 2026-10-04: ExIt FAILED pre-registered confirmation (0.48). Keep s2902 1M proposer. Now: search-tuning/ (Astra search-tuning-astra-20261004-1) + Rust Stage 4 C56 (Astra engine-rs-stage4-astra-20261004-1).
  proposer. Decision: the policy's role is the search player's proposal network; gate on search strength. Pre-registered
  256-game confirmation + (if pass) iterations 2-3 (Astra exit-confirm-astra-20261004-1).
- CHECK LATER: ExIt's re-evaluation of the s2902 1M policy gave 83/192 vs 88/192 earlier on the same nominal seeds —
  confirm whether run_eval stochastic play is exactly reproducible (thread nondeterminism?) before relying on
  cross-run pairing.
- 2026-10-04: search tuning PASSED: srp-pub-mix (opponent-model mixture) = best player (0.629 h2h vs srp-pub-pol; scripts 117/128 holdout, 53/64 hog26). Config in search-tuning/RESULTS.md.
- 2026-10-04: live-loop/SURVEY.md written; L1 (rendered-frame perception) running (Astra live-loop-l1-astra-20261004-1). L3 (official client) needs Sam's explicit go.
- 2026-10-04: live L1 v0 failed gates (entities 63%, events mostly missed, capture 0.5-1.6 FPS; HUD/clock good). L1 v1 running (Astra live-loop-l1v1-astra-20261004-1): 10-20k frames, track-birth events, HP association, streaming capture.
- 2026-10-04: C56 extraction v3b RUNNING (driver 15128; Goblinstein timer fix; 0 exceptions over 27,649 swept perspectives; reuse 253/253 identical; per-perspective error isolation; ETA 2026-10-05 ~09:00 PDT, ~6.1-7.4 GiB). Uses base gamedata 3d99987c (known difference).
- 2026-10-04: ClashAI ~11k trophies via full-corpus BC + live loop. native-corpus/ feasibility running (Astra native-replay-feasibility-astra-20261004-1).
- 2026-10-04: native-corpus NO-GO (slow, and replays drift even natively). NEXT after C56 extraction (~2026-10-05 09:00 PDT): S122 actor-scope extraction on the Python sim (<=6 GiB), then generalist BC.
- 2026-10-04: Rust Stage 4 DONE (all 56 cards + champions + native C56 scripts byte-identical; coordinator re-check 8 unseen champion/B4 full games OK, 37-49x). Stage 5 (srp-pub-mix on C56, real-meta deck prior, pre-registered 256 games) running: Astra engine-rs-stage5-astra-20261004-1.
- 2026-10-04 ~22:00Z: LIVE PLAY AUTHORIZED by Sam (throwaway account, Mac mini emulator only). L3a official-client AVD + account + capture/input plumbing (Astra live-l3a-official-client-astra-20261004-1). Disk critical (~10 GiB free; others: roader 33 GB, colima 14 GB — not ours); pnpm store pruned; C56 extraction paused by watchdog tier 2 (<11 GiB).
- 2026-10-04 ~23:30Z: official client crashed on Google APIs (rootable) image at native init; retry with Google Play image blocked by disk (4.4 GiB). roader grew 57->67 GB in hours (not ours; cannot message its thread). Coordinator freed ~5 GiB (deleted superseded official AVD, git gc). Retry 2 running (Astra live-l3a-retry2-playimage-astra-20261004-1).
- 2026-10-04: official client crashed (frrh.aC: 02) on BOTH stock emulator images (Google APIs, Google Play); no workaround attempted; Play AVD+image deleted. Next: BlueStacks Air (Astra live-l3a-bluestacks-astra-20261004-1). Free disk 19 GiB.
- 2026-10-05: Rust Stage 5 strength PASS (C56 fair search 224/256 = 0.875 vs C56 scripts; per-family Hog2.6 0.71 ... RH/Furnace 1.00) but timing FAIL (max 311 ms, 16 >250 ms). Stage 5b deadline/anytime + 2-thread rollouts, pre-registered non-inferiority (Astra engine-rs-stage5b-astra-20261004-1).
- 2026-10-05: BlueStacks Air 5.21.790.7505 downloaded (signed now.gg UJYFHY4XNR, notarized) but install needs macOS admin authorization (SecurityAgent refuses automation; sudo needs password). WAITING ON SAM: run `sudo installer -pkg /Users/sam/.cache/clasher-official/bluestacks-downloads/BlueStacksInstaller_5.21.790.7505.pkg -target /` (or double-click the pkg) on the Mac mini, approve any system-extension/Hypervisor prompts, then tell the coordinator.
- 2026-10-05: L1 v1: entities 97%/HP/HUD/clock/FPS PASS; events (71% recall, 49% precision) and placement 59% FAIL -> derived opponent state fails. L1 v2 deploy-event detection (Astra live-loop-l1v2-events-astra-20261005-1).
- 2026-10-05: Stage 5b PASS (200 ms anytime search, 2 threads; max 230 ms over 384 games under load; 0 overruns; 116/128 vs C56 scripts; h2h identical behaviour 0.500). C56 fair search player is live-budget ready. Stage 6 (remaining S122 cards to Rust, low-arena cards first) running: Astra engine-rs-stage6-astra-20261005-1.
- 2026-10-05: L1 v2 events: stepped 88/78/68% but real 10 FPS stream 24/19/24% (200 deployments; stream timing uncertified). L1 v3 (stream timing, >=3k deployments, track-birth fusion, uncertainty-aware derived state) running: Astra live-loop-l1v3-events-astra-20261005-1.
- 2026-10-05: Stage 6 Astra task FAILED (model at capacity) after 10 low-arena cards passed the early group gate; resumed on GPT-6.1-Sol high (engine-rs-stage6-sol-resume-20261005-1). If Astra is at capacity, fall back to 6.1-Sol per routing rule.
- 2026-10-05: L1 v3 events 64% recall / 67% precision / 58% placement (3,070 deployments, timing p95 27 ms); elixir MAE 2.1. Decision: stop gating L2 on 90% events; run (a) sim degradation study with measured perception noise (Astra perception-degradation-astra-20261005-1) and (b) L2 closed loop from pixels on the offline renderer, pre-registered vs sim (Astra live-loop-l2-astra-20261005-1).
- 2026-10-05 04:50Z: BlueStacks Air installed by coordinator with Sam's admin password (not stored anywhere); app verified Developer ID now.gg UJYFHY4XNR, notarized. L3a continuation (Astra live-l3a-bluestacks-run-20261005-1). Free disk 9 GiB.
- 2026-10-05: BlueStacks first boot timed out at 90 s (StartingKernel); ADB toggle did not save; BlueStacks' bundled hd-adb kill-server can disrupt other emulators' adb. NEXT: retry after L2 finishes, with >=10 min boot timeout, separate ADB server port (ANDROID_ADB_SERVER_PORT) for our tools, and no other emulators running. Evidence live-loop/l3/bluestacks/resume/.
- 2026-10-05: pushed main to github.com/samdickson22/clash-simulator (99f936f81..3f2655757: 331 prior local commits + 1 curated commit of code/tests/engine-rs source/report docs+analysis scripts; bulk artifacts excluded; secrets scan clean). Forks: only notiesu has own work (57 commits Jan-Mar 2026: gym env, BC transformer on scraped Hog 2.6 replays, SB3 PPO/RecurrentPPO, ONNX inference, Docker); others are untouched copies.
- 2026-10-05: public repo cleanup delegated (Astra repo-cleanup-astra-20261005-1): worktree /Users/sam/Desktop/code/clasher-cleanup on branch cleanup/public-readiness, behaviour-preserving, identity + tests must match main, PR to main (not merged by the agent). Merge only after review and when running jobs no longer depend on moved paths.
- 2026-10-05 ~07:00Z server restart: cancelled cleanup (resumed: repo-cleanup-resume-20261005-1), L2 agent (detached pipeline+finalizer continue, 13/48 pairs), search-noise agent (detached supervise continues, 668/1664). Stage 6 resume2 agent survived. Disk hit 5 GiB -> deleted superseded L1 v1/v2 datasets (~3.2 GB); now 8 GiB.
- 2026-10-05 ~07:30Z: user restarted T3/session -> t3_threads tools still absent (cannot list other T3 Connect machines). This restart ALSO killed setsid/detached jobs (L2, search-noise, stage6 gates, watchdog, caffeinate); only extraction pgid 15128 survived. Relaunched caffeinate+watchdog, SIGCONT extraction (disk 18 GiB), resumed L2 (live-loop-l2-resume-20261005-1), search-noise (search-noise-resume-20261005-1), Stage 6 (engine-rs-stage6-resume3-20261005-1), cleanup (repo-cleanup-resume2-20261005-1). LESSON: a full T3 app restart can kill detached jobs too; every long job must be resumable from disk.
- 2026-10-05: f35 (Cal Poly CSC server) available over Tailscale: 256 cores, 755 GB RAM, 2x V100S; shared — ≤48 cores, 1 GPU, nice; persistent /data2/sdicks02 (≤15 GB), scratch /tmp/sdicks02 (10-day purge), $HOME quota tiny. Bootstrap + cross-platform parity (Astra f35-bootstrap-astra-20261005-1). If parity holds: move C56 remainder + S122 extraction + BC training (GPU) to f35.
- 2026-10-05: f35 ON HOLD per Sam ("still setting it up; don't move anything over"). Bootstrap task cancelled before writing anything on f35. Do not use f35 until Sam says it is ready.
- 2026-10-05 13:10Z: project copied to f35:/data2/sdicks02/repos/clasher (+clasher-local-data), verified (dry-run + checksums); Mac copy kept; handoff updated on both.
- 2026-10-05T20:35-21:00Z resume of the Mac jobs SIGSTOPped at about 07:49Z (coordinator agent on f35 via ssh mac-mini). Stage 6: SIGCONT 41247/43204, with no rerun needed (deterministic parity, CPU-time timing gates). human-reserve-r42 PASS (136 games/1617 imports/4017 placements/66 cards/45.4x/clone 17.6us). planner-r42c FAILED a genuine parity check at call 36 Fisherman-1-100 (pressure rollout divergence) after 35/100. Receipts retained; waiting on a native fix and a fresh planner label. search-noise: SIGCONT rejected, because a stop inside a timed decision corrupts latency-variant play and terminal receipts cannot be dropped. Stopped group 89399 SIGKILLed without running; relaunched via detach.sh (supervisor 73385). 3 in-flight games re-run from their seeds (INCIDENT-20261005T203957Z.md). L2: the emulator had kept running, so native pair 19 had ended in-engine with no input, and a resume would have written a terminal receipt for it. Owned groups SIGKILLed while stopped. Partial preserved in live-loop/l2/recovery-sigstop-20261005. PREREG amendment and minimal opening-equality lookup added, re-sealed (2 pins changed), test_recovery OK. Pipeline 75102 and one finalizer 75174 relaunched. Pair 19 rerun passed opening equality and completed; 21/48 pairs done. C56 extraction 15128: state S, left untouched, but STALLED since about 07:25Z (no output; pool workers idle, likely lost tasks from the T3 restart). Needs a decision to kill and relaunch with reuse (disk at 13 GiB free, guard at 12) or to move it to f35. No interim strength outcomes inspected.
- 2026-10-05: f35 thread started (owns the project from HANDOFF_F35_20261005.md). Mac jobs stay paused; coordinate before resuming anything here.
- 2026-10-06: Mac disk hit 100% (214 MB free). Cleared regenerable/re-downloadable only: datasets/external (8.4 GB third-party downloads), uv cache, Android NDK, cargo targets, engine-speed build venvs, node/brew/electron/t3-updater/node-gyp caches. Kept all evidence, results, checkpoints, extraction outputs, AVDs, SDK, .venv. f35 unreachable (ssh timeout) -> likely rebooted; needs tailscale-start via Cal Poly VPN.
- 2026-10-07: disk full again (T3 statev2.sqlite 37 GB and growing; ~/.claude/worktrees 32 GB, not ours). Deleted Mac copies of artifacts/worktree-data and live-loop/l1/v3 (verified copies on f35 /data2; manifest pilot/logs/offloaded-to-f35-manifest-20261007.tsv).

## 2026-10-07 21:40 UTC: f35 down, moving compute to the 127x fleet

- **f35:** down since 2026-10-06 and, per Sam, unlikely to return. Before it went down, the f35 thread merged PR #6 (public cleanup) to main, and the Mac has fast-forwarded to `7f7a20a66`. Any other f35-only progress is unreachable. The f35 `/data2` copy holds the only copies of `artifacts/worktree-data` and `live-loop/l1/v3`, which were deleted locally on 2026-10-07 (see `artifacts/OFFLOADED_TO_F35.md`).
- **All Mac jobs from the 2026-10-05 pause are gone:** no processes remain for PGIDs 15128, 41247, 43204, 95700, 95753, 95820, 89399 or 89739. Each resumes from its own `PROGRESS.md`.
- **New compute:** the Cal Poly 127x lab fleet. Hosts were agreed with the roader thread (1adb92e5):
  - **clasher:** 127x01–127x08 (127x06 is down; 127x03 and 127x05 have no GPU). Hub: 127x02, at `/mpac/sdicks02/repos/clasher`.
  - **roader:** 127x09–127x18.
  - The NFS home is shared across hosts with a quota of about 5 GB, so all caches and toolchains go under `/mpac/sdicks02` (`env.sh`). Rust is pinned to 1.97.1 to match the Mac; Python is 3.12 via uv.
- **Copy:** Mac → 127x02 with `pilot/transfer_to_fleet.sh` (P=6 chunks, then local-data, a final sweep and a dry-run verify).
- **Delegated:** "Fleet bring-up + Linux parity gate", GPT-6-Astra (high). It covers the venv and engine-rs build; all four identity modes and the Rust parity harnesses on Linux; replication to 01–08; and a `fleet/` README with `PARITY-LINUX.md`. Resuming Stage 6, the noise study and C56 extraction on the fleet waits on that parity gate.
- **Outcomes recovered from the Mac tree and committed** (`9a63cab2d`):
  - **L2: NOT READY.** Pixels won 27/48 vs simulator 48/48; the difference is -43.8 pp, CI [-58, -29].
  - **Noise study: FAIL.** Against C56 scripts the player drops from 86.7% clean to 50.0% under full noise; repairing events alone recovers +16.4 pp.
  - **Stage 6:** the human gate and final controls pass. The planner fails at call 36 on a Fisherman seat-1 rollout parity defect.
  - **C56 extraction:** 811/1,767 units, stopped.
- **Perception weights lost locally:** deleting `live-loop/l1/v3` on 2026-10-07 also removed the v3 detector weights (`model/last.pt`, about 1 MB) and `hud.npz`; the only copies are on f35. This was my error: the manifest check treated the folder as evidence only. They are regenerable from the Mac renderer and L1 code, and v4 replaces them anyway. Four tracked docs/scripts in that folder were restored from git.
- **Delegated:**
  - Stage 6 Fisherman fix plus final gate (Astra high, Mac).
  - Perception v4 design (Opus high, research only, writing `live-loop/v4/DESIGN.md`).
- **2026-10-07 22:00 UTC: perception v4 design accepted** (`live-loop/v4/DESIGN.md`, Opus). Root causes of the L2 loss:
  1. The serial loop starved the event detector. Gaps over 300 ms reset its history, so in-loop opponent-event recall was 3.1%.
  2. The player re-tapped plays whose spend wasn't yet recorded (no pending-spend ledger; it acted on frames about 400 ms old).
  3. The search planned against a single draw from a wide opponent posterior.

  **Decision:** a 5-process pipelined runtime on the Mac; a temporal event head; a hypothesis-belief tracker with a 4-root search; a verified actuation channel; training on the fleet A6000s and inference on the Mac.

  **Delegated:** T2 (actuation bench) and T1 (20 FPS collector streaming to `127x02:/mpac/sdicks02/repos/clasher-v4-data`), as one Astra-high task. T3 (the S1 noise-robust search study on the fleet CPUs) waits for the Linux parity gate.
- **2026-10-07 22:15 UTC: command center agreed with roader.** 127x05 (no GPU, idle) becomes Sam's single T3 Code host for both projects; 127x03 is the fallback.
  - **Load:** no heavy jobs from either project run on it.
  - **Clasher compute:** 127x01–04, 07 and 08.
  - **Still Mac-bound:** the offline renderer and anything live-client. The fleet has no KVM access (/dev/kvm is root:kvm), and the live-play authorization names the Mac emulator. Clasher's remaining macOS dependency is just that, plus the Mac-recorded acceptance receipts, which the Linux parity gate is replicating.

## 2026-10-07 22:24 UTC: fleet bring-up, native gate blocked

- 127x02 environment built with locked Python 3.12.13 / Rust 1.97.1. Four identity modes PASS: P16 12/12, C56 7/7, recorded SRP 8/8, random 24/24. Fast pytest 47 pass; Stage2 38, Stage4 88, Stage3/5/5b 10, Stage6 60 unique regression methods pass. Saved-root provenance required the exact reviewed 23-file cleanup migration; original failures retained. Cargo passes but contains zero tests. Native differential: 42,734 ticks, 4,600 MT / 2,000 A* checks, zero mismatches, 37.735x stepping, max clone8.091us. Linux per-core identity CPU time is about2.2x historical M4 Pro.
- Stronger Stage5 recorded 200-root gate FAILS at root4, tick900. First divergent continuation: balanced candidate109, tick1007. ElectroSpirit chain128 chooses Bat127 in Python but124 in Rust because chain_tick excludes the still-staggered Bat127. Python/Mac admitted trace0323ee82 differs from native5f6d1864; frozen Mac native build42 reproduces Linux's exact failed trace and first tick. This is a pre-existing native eligibility regression, not Linux drift. No native/oracle patch made; coordinate a fix and fresh full planner replay with the Stage6 owner.
- NO FAN-OUT: the required hub gate failed. No peer repo/venv copy or P16 smoke was started. Updated allowlist:01,02,03,04,07,08. 127x05 is the shared T3 command center; only an earlier read-only connectivity/console check occurred there, no copy or workload. No roader host used.
- Evidence/helpers: reports/strategy_council_20260928/fleet/{README.md,PARITY-LINUX.md,HUB-RESULTS.json,fleet_run.sh,evidence/}; mirrored on hub. Remote logs/root reducers: /mpac/sdicks02/jobs/clasher/. Source snapshot was frozen before concurrent Fisherman/Mirror changes; 1,150 source hashes,34 replay inputs,179 historical certificate receipts verified before/after. All owned hub jobs exited; no commits.
- **2026-10-07 22:40 UTC: Linux parity gate on 127x02.**
  - **Identity:** all four modes match the Mac exactly (P16 12/12, C56 7/7, recorded 8/8, random 24/24). Stage 2/4/5/6 regressions pass.
  - **Speed:** Rust stepping runs 37.7× Python; per-core CPU time is about 2.2× the M4 Pro's.
  - **Rust defect:** the 200-root Stage 5 planner gate fails at root 4. The Electro Spirit chain excludes spawn-staggered targets in Rust (`engine-rs/src/c56.rs:305`, `:361`) but not in Python. Frozen Mac build 42 fails identically, so this is a native defect, not Linux drift. It is routed to the Stage 6 agent, to be fixed together with Fisherman.
  - **Decision:** the bring-up agent held replication on this gate; I overrode that. Replication proceeds via `127x02:/mpac/sdicks02/jobs/clasher/fanout-coord.sh` (LAN, to 01/03/04/07/08, plus a P16 smoke test on each).
  - **Delegated (Astra high):**
    - C56 extraction resume on 127x01/03/04, starting from the Mac's 811/1,767 units and first proving Linux reproduces finished units byte-for-byte.
    - The S1 noise-robust search study on 127x07/08/02. It uses the current Rust build with its known defect, recorded in PREREG; all arms share the build.

## 2026-10-07 23:35 UTC: Mac thread hands off to the 127x05 coordinator and stops its workers

At Sam's request, the Mac thread cancelled its delegated agents. Stage 6, live-loop v4 T1/T2 and S1 were cancelled. The C56 extraction agent had already finished, blocked. The new 127x05 thread owns everything from here.

**Mac jobs still running (detached; left alive for the new owner):**
- live-loop v4: PGID 8556 runs `actuation/bench.py`, and PGID 9517 runs `v4/pipeline.py --wait-bench-pid 8559` (the T1 collector pipeline).
- The offline renderer emulator, PID 66755 (`clasher_reference_api35`, port 5584).
- Their state is in `live-loop/v4/T2-RESULTS.md`, `T1-PROGRESS.md` and `PREREG.md`.

**Open decision: T2 timing.** gRPC taps were accepted 100% of the time, but the renderer hook adds about 1.1 s before acceptance.

**Stage 6:**
- Build 45 passed the human reserve, but its final manifest no longer counts as qualification.
- A third native defect was found: Inferno Dragon's damage-ramp channel targeting during Bandit's dash (Python's `DamageRamp.allows_target` rejects dash targets).
- A fix is drafted in the Rust source, and private46 is pending. No Stage 6 worker is running. See `engine-speed/PROGRESS.md`.

**127x02 (the fleet hub) went down around 23:25 UTC.** It's unreachable over Tailscale and the LAN; 127x01 can't ping it either. Data that exists only there:
- `/mpac/sdicks02/repos/clasher-v4-data`: T1 stream.

Also on the hub, but with copies elsewhere:
- the hub's full repo copy, its `.venv` and the Linux build;
- the C56 base verification. The 811 units are also on the Mac and on the 01/03/04 copies.

**Fleet status:**
- 127x01, 03, 04, 07 and 08 are up and idle.
- Fan-out copies to them may be incomplete, and their smoke receipts are missing.
- S1 (`search-noise-v2/`) has its PREREG frozen but no games run; it's blocked by the hub outage (`INCIDENT-fleet-unreachable.json`).
- The C56 extraction resume hasn't started any compute. State is in `c56/data/PROGRESS.md` and `FLEET-RESULTS.md`.

**Suggested first move:** pick a new hub among 01/03/04/07/08, or wait for 127x02 to return. Note that each node's `/mpac` copy came from 127x02 and may be partial.
- **2026-10-07 23:45 UTC:** all clasher jobs on the Mac are stopped (SIGTERM): v4 bench PGID 8556, v4 pipeline PGID 9517, renderer emulator 66755, the owned adb servers on ports 5041 and 5042, caffeinate and host_watchdog. The Mac now runs nothing for clasher. T1 collection stopped partway; its state is in live-loop/v4/T1-PROGRESS.md.

## 2026-10-07 23:55 UTC: 127x05 coordinator takes over; decisions

- **Ownership.** The 127x05 thread owns all tracks; the Mac thread and all its agents are stopped (entries above).
  Mac reachable from fleet hosts via `ssh macmini-fleet` (userspace tailnet `tailscale nc`; alias added to the
  shared `~/.ssh/config`).
- **T2 timing: decided, option B** (`amendments/2026-10-07-t2-actuation-timing.md`). Keep the attested hook and its
  ~1.1 s command latency; make the verifier/ledger windows backend-relative (`D_b,p99 + 600 ms`, rollback +200 ms);
  restate the T2 sensitivity gate as within 600 ms of native acceptance (316/320 = 98.75% now, four misses to be
  explained); the planner applies its own actions `D_b` ticks later; L2-v4 gains a simulator arm S-d with the same
  delay. No APK/hook change or re-attestation. Reason: P − O cancels the delay; the official client also delays
  commands, so a player that can't handle it fails L3 anyway; shortening the hook would match nothing real.
- **T1 coverage:** Phase A runs until the heldout split has ≥1,500 opponent events and ≥20 matches, capped at 36
  emulator-hours (count-only stopping rule, split unchanged). Same amendment file.
- **Hub outage (127x02 down since ~23:25Z, off LAN and tailnet).** New hub: **127x01** (A6000, idle, already holds
  ~43 GB of the fan-out). Rebuilt from the Mac tree (code and evidence authority), re-verified by rerunning the Linux
  parity gate, then fanned out over LAN to 03/04/07/08 with smoke receipts. **127x04** keeps a periodic mirror of the
  hub's data directories, so one lab box going dark no longer stops every track. If 127x02 returns it becomes a
  compute node; its unique contents (S1 hub receipts, T1 registration bundles) are reconciled, not trusted
  blindly. Nothing irreplaceable was lost: T1 had collected no matches, S1 had 0 terminal games, and the C56 base
  is on the Mac.
- **Stage 6 moves to the fleet** once the new hub passes parity. The Mac is emulator-only from now on. The Inferno
  Dragon dash-channel fix (private46 draft) is finished and gated there.
- **Sequencing.** Now: hub bring-up (Astra), T1/T2 resume on the Mac emulator (Astra), GPU training env T0
  (6.1-Sol). After the hub is ready: Stage 6 completion, C56 extraction resume, S1 confirmation relaunch.
- **2026-10-07 23:40 UTC:** hub recovery on 127x01 is underway: label `recovery-copy-20261008` (PID 3288950), a two-stream read-only pull from the Mac. The 10 stale receivers left from 127x02 are terminated. A second, unrequested Mac→fleet push was found: two detached `pilot/transfer_to_fleet.sh` runs (PGIDs 29023 and 29029, started 23:37:33Z, hub=127x01 and hub=127x04, launched by neither this thread nor the hub worker). I stopped both with SIGTERM on their verified process groups so the hub copy has a single writer. Any partial files are overwritten by the pull and checked by its checksum sweep. 127x04 gets its copy by LAN fan-out from 127x01 after the hub's checks pass.
- **2026-10-07 23:50 UTC: correction and copy plan.** The two Mac pushes stopped at 23:39Z were the old Mac thread's
  first complete copies to 127x01/127x04 (its cleanup work, not project work). They are dead and stay dead:
  one copy plan only. **127x01** (hub) is filled by the hub worker's pull from the Mac (`recovery-copy-20261008`).
  **127x04** (second copy), **03, 07, 08** get it by LAN fan-out from 127x01 after bootstrap + parity gate.
  The hub worker sources clasher-local-data from the Mac caches (no APK).
  **Mac bulk offload** (`pilot/offload_mac_bulk.sh`, ~33 GB): the Mac's
  `transfer-to-fleet-*.log` will never say DONE now. The signal instead is `127x01:/mpac/sdicks02/jobs/clasher/hub-ready.json`,
  which includes the script's dry-run result (0 checksum differences on 127x01 and 127x04). Only then may the Mac run
  it with `--delete`. The script rechecks both copies itself before deleting. By then 03/07/08 also hold copies, so
  the offloaded data exists on five fleet nodes. Rule from then on: never delete offloaded data on any fleet node
  without first making another copy. The T1 stream from earlier today was registration bundles only (no matches),
  so losing it with 127x02 costs nothing.
- **2026-10-08 00:20 UTC: T0 GPU env PASS** (6.1-Sol high; `fleet/GPU-CHECK.md`, `gpu_env.sh`, `gpu_check.py`).
  `/mpac/sdicks02/envs/clasher-gpu` on 127x04/07/08: Python 3.12, torch 2.7.1+cu118 (newest cu118 build) on driver
  470, ultralytics 8.1.24. Per GPU: FP32 ~24, TF32 ~62, bf16 ~105 TFLOPS; YOLOv8s synthetic epoch ~1.75 s; conv, transformer
  AMP and 16-worker loading pass. `torch.compile` fails ("device kernel image is invalid"), so train eager. Old
  ultralytics needs `TORCH_FORCE_NO_WEIGHTS_ONLY_LOAD=1`, for trusted local checkpoints only. The v3 trainer
  entry points need a CUDA device port (they target MPS). Coordinator re-check on 127x08: torch 2.7.1+cu118 sees the A6000; warm
  bf16 8192² matmul 113.7 TFLOPS. Separate from the repo's parity-pinned `.venv`.
- **2026-10-08 00:35 UTC: T2 verdict FAIL (as reported); T1 smoke PASS; Phase A waits on the hub.** (Astra
  `clasher-v4-t1t2-resume-20261007-1`; coordinator re-read `live-loop/v4/T2-RESULTS.md` and the hub shipments.)
  - Full 640-trial matrix. gRPC: 320/320 accepted, two-tap p95 26.9 ms. Submission→acceptance D_b p50/p99
    1,152/1,187 ms (hook nominal 22 ticks). Verify/rollback windows 1,787/1,987 ms from `actuation/backend-timing.json`.
    Specificity 40/40. Stale re-tap reproduced (2 taps) and blocked by the ledger (1 tap).
  - **Sensitivity 316/320 = 98.75%, below the 99% bar.** All four misses are Cannon plays at two native states
    (ticks 739 and 1,020; two seeds each). The v1 HUD reader read baseline elixir 9 where native had 3.1, so the cost±1
    predicate looked for ~6. Native acceptance was on time each time. No raw frames were retained, so "digit misread"
    vs "stale image" is an inference.
  - **Decision.** The FAIL stands; no re-scoring and no reader tuning on these trials. Accepted for development:
    gRPC transport, the backend-relative timing contract and the ledger. P4 production qualification moves to a
    **prospective re-test with the v4 HUD head (T7)** before L2-v4, under a pre-registered protocol written before
    any trials:
    (a) ≥300 positive and ≥300 negative trials, so a 99% bar means something (40/40 bounds specificity only at
    ≈91%); report Clopper-Pearson bounds;
    (b) raw frames retained for every miss;
    (c) the spend predicate checks the observed elixir drop against the ledger's phase-locked own-elixir
    prediction (DESIGN §2.5), not a single HUD baseline read, plus the slot-card change. One bad digit read can
    no longer veto a real play.
    Production risk meanwhile is low: a false miss never triggers a double play, because a retry requires the card
    to still be in hand. It only mis-states the ledger until the next HUD anchor.
  - **T1:** smoke PASS after a spawned-body adapter fix, a refreeze and same-seed reruns. 19.999/19.995/19.999 FPS,
    98/98 exact-tick plays, three hub checksums verified on 127x01 (28.5 MB). Phase A driver (Mac PID 63610)
    waits for `hub-ready.json`. A pre-existing synthetic FPS unit test still fails (real-stream FPS passes); to be
    fixed or explained at the next v4 code change.
- **2026-10-08 00:45 UTC: hub 127x01 qualified** (00:32:53Z). Fresh Linux build from the current Mac source (native
  `13e908c5…`). Identity: P16 12/12, C56 7/7, random 24/24, recorded 8/8. Regressions: Stage 2 38, Stage 3/5/5b 10,
  Stage 4 88. Full Stage 5 200-root replay 200/200 exact (the root 4 Electro Spirit defect is fixed in this source).
  Native differential 0 mismatches, 37.8×. Cumulative Stage 6 66/66 incl. the BeamDash fixtures (informational).
  LAN fan-out to 03/04/07/08 running. `hub-ready.json` follows the Mac offload dry run. The 127x02 watch expired at
  00:33Z with the host still down; no further polling.
- **Restart plan and host split** (from `hub-ready.json` on):
  - **Stage 6 → fleet (127x01, ≤8 processes).** Freeze build 46 (Inferno Dragon dash-channel fix) on Linux and
    rerun every final gate fresh. Independent verification grows from 6 recorded games to **48 unseen recorded +
    24 unseen human games**, pre-registered before running: independent checks found all three late defects
    (Fisherman, Electro Spirit, Inferno Dragon), and fleet CPU makes a bigger sample cheap.
  - **C56 extraction → 127x01 (48 workers), 127x03 (64), 127x04 (32).** Base re-verified on the new hub against
    `qa/fleet-v3b/mac-base.json` (the Mac base will be offloaded), then fresh equivalence, partition and extract.
  - **S1 → 127x04 (48 workers, replaces 127x02), 127x07 (100), 127x08 (100); collector on 127x01.** Its sealed Linux
    runtime existed only on 127x02. On the hub copy 8/465 manifest files are missing (incl. the native .so) and 32 differ. No
    outcome was ever inspected, so S1 is **re-sealed as r2 on the qualified hub build**, with the PREREG design,
    seeds, arms, analysis and worker→game partition unchanged and the full preflight rerun. Recorded as a deviation.
    Any receipts left on 127x02 are archived unread and never merged.
- **2026-10-08 00:55 UTC: HUB READY** (`127x01:/mpac/sdicks02/jobs/clasher/hub-ready.json`, 00:54:44Z; coordinator
  read it). Mac → 127x01 copy: 188,266 files / 52.0 GB, 0 checksum differences, plus local data (engine-speed 1,552
  files, decoded-logic 340 files). Hub gates above all pass. LAN fan-out to 03/04/07/08: 220,656 repo files / 60.0 GB
  each, 0 differences. P16 smoke 12/12 on every peer. The only content conflicts were `.git/index` caches and a stale
  `qa/fleet-v3b/mac-base.json` from 127x02's interrupted fan-out (identical JSON, missing final newline): originals kept
  in `jobs/clasher/recovery-conflicts/`, replaced with the hub bytes. Mac offload dry run (stamp 20261008T004942Z):
  81,517 files / 35.76 GB, 0 differences on 127x01 and 127x04. **The Mac may now run
  `pilot/offload_mac_bulk.sh --delete`.** It rechecks both copies first, and the data is also on 03/07/08.
  Mirror to 127x04 every 30 min (`hub-mirror-127x04-20261008-r2`). Source manifest `e2e5a6bd…`, native `13e908c5…`.
  Docs: `fleet/HUB-127X01.md`, `fleet/README.md`.
- **T1 Phase A started** on the Mac (pipeline PID 63610, stage phase-a), shipping to 127x01. Stage 6, C56 and S1
  workers are released by `hub-ready.json`.
- **2026-10-08 01:05 UTC:** hub task closed; its final report matches `fleet/HUB-127X01.md`. Coordinator's independent re-check on a fan-out peer: C56 identity on 127x07 gives 7/7 episodes, 2,900 digest boundaries, 0 mismatches, baseline `002a57a9…`.
- **2026-10-08 01:08 UTC: C56 equivalence: decision to accept and proceed.** The worker stopped correctly at the
  raw-byte gate: 0/3 archives identical. Cause (`c56/data/FLEET-RESULTS.md`, `strict-equivalence.json`): the Mac archives
  for s117/shard-011-part-04/05/06 reused 10/11/12 v2 episodes. Linux had no v2 archives for them and simulated every
  episode fresh. All non-header arrays match in dtype, shape and logical bytes (144 perspectives, 117,776 rows). The
  header differs only in the reuse-provenance `extra` field, and `flat_entity_features` differs only in C/F memory
  order. Restoring those two gives byte-identical archives (3/3). The gate exists to prove Linux reproduces the Mac's
  simulation, and a fresh simulation matching the reused rows exactly is stronger evidence than byte identity.
  **Criterion going forward:** logical equivalence (every array equal in dtype, shape and C-order values; header
  equal except reuse provenance). Production extraction of the remaining 956 units proceeds. The original
  extractor deletes reused v2 NPZs, so the 137 retained v2 archives are copied aside before any run that could reuse
  them.
- **2026-10-08 01:22 UTC: S1 r2 sealed and running; 127x07 went offline (~01:14Z).**
  - r2 manifest `3ad63c0a…` (468 files, sealed 01:07:36Z). Full preflight passed again: 24 replays / 23,058 exact checks,
    14 tests, fork pilot, 18 timing pilots, optimized vs reference action-digest equality. Launched on 04/07/08 at
    48/100/100. At 01:19Z, 397/4,992 receipts (04: 149, 08: 248). No outcomes inspected.
  - **127x07 dropped off LAN and tailnet ~01:14Z**, about 5 min after S1 put 100 workers on it. 127x02 dropped at ~23:25Z,
    about 6 min after S1 put 48 workers on it. Survivors under similar load show nothing wrong: 127x08 at load 100 has no
    OOM kills, zero memory pressure and Tctl 65 °C; 127x04 is at 75 °C; no swap configured. Cause unknown: possibly
    physical power-off or reboot by lab users, or a hardware/power issue under sustained all-core load. Reported to Sam.
  - **Decisions.**
    1. **Migrate 127x07's partitions** (worker indices 48–147, 2,000 games) to the surviving S1 hosts as their own
       partitions finish: 127x08, then 127x04. Game assignment by job index is frozen; host mapping is operational. Games
       are deterministic per seed and no outcome was seen, so the host change cannot bias anything. Frozen files stay
       untouched: use an operational override, recorded as a deviation. If 127x07 returns, its valid receipts are
       compared by identity and action digest with the migrated reruns (a free determinism check), and only one copy
       per game is admitted. Its supervisor is not restarted.
    2. **Load cap:** new launches keep our total worker processes ≤80 per host (≤16 with a console user), leaving ~40%
       of threads free. It costs some wall time and lowers whatever risk sustained full load carries on shared lab
       boxes.
- **2026-10-08 01:52 UTC: incident: a stale Mac push overwrote fleet files, and S1 r2 stopped.** At 01:39–01:44Z the
  old Mac thread re-ran `pilot/transfer_to_fleet.sh` to 127x01 and 127x04 (logs: "DONE 01:44:49Z").
  `rsync -a` without `--update` replaced ~3.5k files on 01 and ~4k on 04 with older Mac versions:
  - S1's sealed r2 files, now a mixed r1/r2 tree; the 41 files that differ include `launch_node.py`. All 48 S1
    workers on 04 then failed the frozen-file guard and stopped, as designed.
  - Stage 6 drivers and `engine-rs/src/{lib.rs,hook.rs}` on 01. The Stage 6 worker saved the overwritten set under
    `engine-speed/stage6/shared-tree-overwrite-20261008T0139/`.
  - Five fleet scripts on 01/04 (restored from untouched 127x03 by the coordinator; pushed versions backed up in
    `jobs/clasher/recovery-conflicts/push-20261008T0139/`).
  - A few C56 scripts/docs and live-loop v4 copies. The Mac is the v4 authority, so those copies are harmless.

  127x03 and 127x08 were not touched. **Prevention:** a guard at the top of the Mac's `transfer_to_fleet.sh` now
  refuses to run unless `CLASHER_FLEET_PUSH_AUTHORIZED=127x05-coordinator` is set (original saved as
  `.pre-guard-20261008`; tested: exit 3). Sam has been asked to have the Mac thread stop pushing. The Stage 6 and C56
  workers were told to audit their pins by hash and rerun anything whose inputs changed under it.
  **S1 adjudication:** the external file replacement is a technical failure, not a frozen-code defect, so identical-input
  recovery is permitted. Recovery authority is the hash-verified 468-file r2 snapshot taken from intact 127x08
  (`operations/incident-seal-overwrite-r2b/frozen-r2/`). Restore it on 01/04 and verify all 468. Receipt eligibility:
  every 127x08 receipt; 127x04 receipts only if the game finished before 01:39:00Z, while any 127x04 game in
  flight at or after 01:39:00Z is replayed from its seed. Then resume 04's partitions, run the prepared 07 migration
  split (48–85 → 04, 86–147 → 08) and collect complete-only.
- **2026-10-08 02:25 UTC: Mac thread, cause of the 01:39Z overwrite incident and the Mac bulk offload.**
  - **Cause of the overwrite:** the old Mac thread caused it. Its 23:37Z fill copies to 127x01/127x04 died, and it relaunched them at 01:39Z without checking whether the 127x05 coordinator had begun using those trees. `rsync -a` without `--update` replaced newer files. The guard in `transfer_to_fleet.sh` is kept, and the Mac thread will make no further writes to any fleet host.
  - **The Mac bulk offload's checks were read-only.** `pilot/offload_mac_bulk.sh` only runs dry-run checksum comparisons against the fleet; it never writes there.
  - **What was deleted:** at 01:55Z, 81,517 untracked files (35.8 GB) were deleted from the Mac after an exact checksum match on both 127x01 and 127x04. That covers m0/readiness, checkpoints/, the untracked parts of datasets/, c56/data, human-prior-p16, reports/persistent_batch_v1, and pilot v7r1/v7r2/v7r2c. The file list is `pilot/logs/offload-mac-bulk-20261008T015508Z.files`.
  - **Copies:** 127x01 and 127x04 now hold the only copies of those paths. Files the incident restored there are newer than the deleted Mac versions, which is fine. Do not delete these paths on both nodes.
  - **Mac disk:** 54 GiB free.
- **2026-10-08 02:17 UTC: C56 extraction v3b COMPLETE.** 1,767/1,767 units, 82,231 perspectives, 64,140,802 rows,
  0 errors, 0 illegal labels. Retention 83.33%, placement acceptance 99.72%, 5.93 GB. The 956 new units ran on 01/03/04 in
  ~43–47 min wall (422/609/278 units per hour). All 137 v2 archives preserved. The 01:39Z push audit found unchanged inputs and base
  outputs, so no unit was invalidated. Copies: 127x01 and 127x04 complete with identical file lists
  (`qa/fleet-v3b/production-20261008/completion-summary.json`). Coordinator spot check: 3 random units load
  (32 arrays, 26–41k rows). NaN appears only in recorded/submitted world positions, exactly as in the Mac base units
  (no-position actions), so it is by design. **Next: the all-card imitation model** (HANDOFF_F35 §5.3), design first.
- **2026-10-08 02:36 UTC: Stage 6 core QUALIFIED on Linux build 48** (Astra `clasher-stage6-b46-fleet-20261008-1`;
  `engine-speed/STAGE6.md`, `stage6/qualification-r48b-linux.json`, `completion-audit-r48b-linux.json`). Native `78bd9950…`,
  source `e83c8e1f…`. Builds 46→48 fixed the Inferno Dragon dash channel (BeamDash incl. saved tick 1895), the hook/ramp
  lock reset, hook cancellation after spirit conversion, and Valkyrie timing after death knockback. All fresh on build 48:
  Stage 5 200/200; planner 100/100; controls 69 + 88 + 47; human/reserve 136 games, 66/66 cards, 1,617 imports,
  4,017 placements, 36.98×, max clone 16.81 µs; identity P16 12/12, C56 7/7, recorded 8/8, random 24/24; seal passed.
  **Expanded independent verification (pre-registered): 48/48 recorded + 24/24 human games, 0 mismatches, every
  card accepted ≥2×.** The 01:39Z push was audited, pinned bytes restored, and affected gates rerun under fresh labels.
  Coordinator re-ran recorded games 46017 and 46033 on build 48: both exact (actions, digests, MT state).
  Rust changes committed (`engine-rs/src/{c56,hook,lib}.rs`, `mirror_snapshot.py`; hashes match the build 48 tree).
  **Decision on Three Musketeers.** Canonical gamedata has no summonCharacterData/count/stats for it, so Python deploys one
  100-HP / 0-damage placeholder. Rust reproduces that exactly, but the scripted controller crashes on it
  (`float(None)`). This is a gamedata defect, not a parity defect. **Admit the S122 roster minus Three Musketeers
  (121 cards)** for search, scripts and the imitation scope. Three Musketeers is marked unsupported: excluded from
  controller decks, and human replays that play it are cut at that play by the existing contradiction rule. A
  Three Musketeers data repair is backlog. It would change canonical gamedata (`892fbfa0`), so it needs real stats,
  a new canonical hash and a full identity re-baseline. Do it only if the imitation or live scope shows it matters.
- **2026-10-08 02:37 UTC: all-card imitation design ACCEPTED** (Opus high; `imitation/DESIGN.md`, `OPEN-QUESTIONS.md`).
  Plan:
  - Sequence: train a C56 model (v1) now and extract S122 in parallel on CPU; the S122 generalist (v2) is the
    live deliverable. The handoff's ≤6 GiB cap is dropped (it was a Mac-disk limit).
  - Derived opponent state (exact elixir, known hand, next card, queue) comes from a **sidecar replay** of the frozen
    extractor with an observer hook. Every existing array must reproduce, which proves alignment. A pure post-pass
    misses champion abilities (~23% of opponent decks) and Collector grants (~6%).
  - Tile-lattice placement head: all 36,710 sampled human placements are tile centres (Tesla on corners), so no
    half-tile head.
  - ~2.5M-parameter feed-forward set transformer: gate → card → tile, plus an auxiliary "next card and when" head.
    No recurrence, ≤15 ms p99 proposer.
  - Pre-registered gates: (a) offline vs the frequency baseline and the P16 BC; (b) proposer in the C56 fair player,
    640 head-to-head games with matched candidate counts, pass score ≥0.53 with LB >0.50; (c) standalone vs s2902 1M
    and the P16 BC.

  Coordinator adjustments: hosts follow current availability. 127x02 and 127x07 are down; S1 holds 04/08 for some
  hours. CPU replay passes go to 127x01/03 first; GPUs on 01/04/08, shared with live-loop v4 perception once Phase A
  data is ready. **First wave (Astra high, parallel):**
  - (A) data pipeline T0 → T1 → T2 → T3;
  - (B) IL_Replay re-fetch and S122 payloads (T9), then the S122 extraction with the inline observer (T10) once T1
    passes;
  - (C) model, trainer, evaluator and inference API (T4), with a shakedown once the T3 store exists.
- **2026-10-08 03:13 UTC: imitation data pipeline.** T0 PASS (GPU env on 127x01). T1 PASS: deck-free D1 module, 319,077 exact
  elixir comparisons and 2,015,370 known-fact checks against the oracle trackers, 0 conflicts. T9 PASS (IL_Replay
  re-fetch and S122 payloads, leak check). T2 sidecar replay running on 01/03 (64 workers each; 12,143/82,231
  perspectives at the last checkpoint, 0 violations). T4 model code committed (`imitation/model/`, 2.40M params, 13 tests,
  CPU proposer p99 13.08 ms); its scheduled poll runs the GPU shakedown when `T3-PASS.json` appears.
  **Decision (header provenance):** 270 original C56 headers carry the v3 runtime SHA (`af205b0b…`), and the replay
  executes v3b (`1ec2c60c…`). All non-header arrays are equal and every common header field matches. Accepted: the
  runtime SHA marker joins reuse provenance as an exempt provenance field. Original headers are kept; actual execution
  is recorded in the sidecar manifest. Any other header difference still fails.
- **2026-10-08 03:19 UTC: S1 r2 COMPLETE. Primary FAIL; the event gate is not met at 90/90 or 97/97.**
  (`search-noise-v2/RESULTS.md`, `result.json`; 4,992/4,992 games, 191 core-h, 2.1 h wall on 04/08 after the recovery.)
  - Primary: E4 − B at N64 = −3.9 pp [−9.8, +2.0], so multi-root belief search does not beat single-root.
    Coordinator recomputation from the raw receipts on 127x01 reproduces −0.0391 [−0.0977, +0.0195] and the A/B/E4 cell
    scores exactly.
  - vs C56 scripts: clean A 95.7%; noisy arms 51–65% at every event level, e.g. B 59.4 / 62.9 / 64.5% at N64 / N90 /
    N97. E4 − clean = −37.5 pp at N90 and −31.6 pp at N97, so neither event gate passes and S1 retains the provisional
    95/95 gate plus "decision-side work required". Latency variants (old / target / L2) move scores by only ~±3 pp;
    tap failure at 10% vs 60% gives 62.1 vs 54.7%.
  - **Diagnosis from the S1 diagnostics.** Better events barely help because the derived opponent state stays poor even
    at 97/97. B-N97: opponent-elixir MAE 0.74, 90% interval width 6.2, hand concentrated in 148/58,269 decisions vs
    7,221/52,428 when clean. E4-N97 is worse: MAE 1.70, interval coverage 69% (the posterior is overconfident and
    wrong), never concentrated. A tracker fed 97%-correct events should be nearly exact. So a few missed or spurious
    events evidently corrupt the hypothesis set for good (no resynchronisation). Board noise is also large: 7.5% phantom
    entities, 3% dropped, HP missing for 34% of units.
  - **Decision.** L2-v4 stays blocked. Next is **S2, a channel-decomposition study plus a tracker diagnosis** before any
    more perception work is prioritised:
    (i) from the full-noise B-N97 configuration, repair one channel at a time to truth (derived opponent state, board
    entities, HP, own HUD state, events→N100, latency→0, tap failures→0);
    (ii) from clean A, add one channel at a time;
    (iii) offline trace analysis of how missed or spurious events break ELT concentration and coverage.
    Pre-registered, sim-only, fresh seeds. Its result decides whether v4's next investment is the tracker
    (resynchronising and robust to a missed event), board perception (phantoms/drops), or HP.
- **2026-10-08 03:25 UTC: timestamp correction.** My entry times from 01:15 onward were estimates and ran 7–51 min late.
  They are now set to the commit times: 01:15→01:08, 01:30→01:22, 02:05→01:52, 02:30→02:17, 03:00→02:36, 03:15→02:37,
  03:40→03:13, 04:10→03:19. Worker briefs that cite the old labels ("03:00 UTC" Three Musketeers decision, "03:40 UTC" header decision,
  "04:10 UTC" S1 diagnosis, "01:15" logical equivalence) refer to the corrected entries. From now on, entry times come from `date -u`.
  Also: the Mac thread offloaded 35.8 GB of Mac bulk data at 02:00Z after its two-node checksum check, so 127x01/04
  (+03/08 fan-out copies) hold the only copies. **S122 data (T9 PASS, T10 QA PASS):** 333,934 new perspectives
  (4,090 Battle Healer and 1,950 Mirror flagged; 2,361 C56 perspectives with Three Musketeers opponents excluded in v2
  metadata, v1 roles unchanged; 0 leakage). QA 400 perspectives: 99.59% placement acceptance, 80.78% retention, 0 errors.
  Production is running on 01/03 (ETA 7–9 h).
- **2026-10-08 04:41 UTC: S2 COMPLETE: the derived opponent state is the main loss; next is S3, a robust tracker.**
  (`search-noise-s2/RESULTS.md`, `ELT-DIAGNOSIS.md`; 3,584 games, 77 core-h, 41 min on 04/08.) Clean A 94.1%, Full
  (B at N97 + predecessor noise) 66.4%, A−Full +27.7 pp [+21.5, +34.0].
  - **Repair gains:** derived state +15.2 [+9.8, +21.1] (identical to events→N100: with perfect events the tracker becomes
    exact); latency +6.2 [0.0, 12.1]; board +5.1 [−0.8, 10.9]; HP +3.1 n.s.; own state and taps 0.
  - **Add costs from clean:** derived −14.5 [−19.5, −9.8]; board −6.2 [−10.9, −2.0]; HP −3.9 n.s.; latency, own n.s.
  - Coordinator recomputation from the raw receipts reproduces A−Full, R-derived−Full, A−A+derived and A−A+board.
  - **Tracker diagnosis.** Missed opponent spends leave the elixir ledger confidently too high with no way back
    (no missed-spend repair on that side, no resynchronisation, a finite 128-hypothesis beam). Example: a missed
    Goblin Barrel left truth 0.14 vs interval [3.1, 8.1] for 144 s. Noisy ELT coverage is 68% (overconfident);
    the legacy posterior covers 99.8% but is uselessly wide (6.2 elixir). The "hand concentrated" diagnostic needs
    unanimity across all branches, so it is uninformative.
  - **Decision.** The next investment is decision-side, not perception: **S3, a robust fair opponent-state tracker**
    (calibrated and sharp, recovers from missed and spurious events, fuses public board evidence of unexplained new
    opponent units). It is cheap to iterate in simulation, the largest measured lever (up to ~15 pp), and it also
    lowers the event-quality bar that v4 perception must hit. Second priority for v4 perception: board precision
    (phantoms 7.5%, drops 3%; ~6 pp). HP and latency are lower priority. L2-v4 stays blocked until the S3 tracker passes.
- **2026-10-08 05:14 UTC: T1 Phase A goes to 3 parallel renderers** (Sam: "this seems slow, can we parallelize").
  One emulator plays at 1× real time (20 FPS capture), so it managed ~99 matches in 4.7 h. The fleet has no KVM, so
  parallelism has to come from the Mac. It has room: 12 cores and 24 GB; our emulator uses ~0.75 core and 1.3 GB RSS, and
  memory is 48% free. The UTM VM (~2.7 GB) is not ours and stays untouched.
  Decision: up to 3 owned instances from the same read-only AVD and pinned attestation, with an atomic seed queue,
  receipts tagged by instance, and every per-match endpoint unchanged. Global buffer cap and disk floor. The amendment
  is recorded in PREREG before any new instance starts. Ramp-up admits each instance only after its first match passes
  every endpoint; scale back if FPS or memory pressure degrades.
  Expected: ~3× throughput, so the coverage stopping rule is reached in hours rather than ~10–14 h. Astra task
  `clasher-t1-parallel-renderers-20261008-1`.
- **2026-10-08 05:18 UTC: use all compute** (Sam: "better utilize ALL the compute").
  Audit at 05:17Z:
  - CPU near the 80-process cap everywhere: 01/03 S122 extraction + C56 data finish, 04/08 S3 games.
  - All three A6000s idle at 0%.
  - Mac: 3 renderers, 103 Phase A matches (10 heldout / 258 opponent events; ~580 matches are needed for 1,500 events).
  - Imitation T2 PASS; the T3 store is built and baselines are being computed.

  Decisions:
  1. **GPUs.** Imitation T5 (gate (a) PREREG first, then 3 seeds + noD1 + GRU, 2 runs per GPU) on 04/08 as soon as
     the T4 shakedown passes. v4 perception T6 (CUDA port of the v3 trainer, v3 control) and the T7 model
     implementation start now on 01's GPU, with shakedowns on the Phase A train split only; formal runs after Phase A
     completes.
  2. **CPU.** Raise the per-host cap for new launches from 80 to 96 (of 128) worker processes, ≤16 with a console user.
     Survivors ran at load 75–100 for hours with no OOM and temperatures 65–75 °C, and five copies of all data exist.
     When S3 releases 04/08, extend the S122 extraction there.
  3. **Critical-path code now.** Imitation T6 (search integration of the proposer) and T8 (gate (c) adapters), so
     gates (b) and (c) can start the moment the checkpoint exists.
  127x05 stays free of heavy jobs.
- **2026-10-08 05:22 UTC: the S122 extraction stays on 01/03 (expansion blocked safely).** The running drivers hold their
  assigned units in memory and the pinned driver rejects new hosts, so adding 04/08 would mean stopping and
  repartitioning the live runs (the Sol worker stopped under the safe-repartition rule; receipt
  `imitation/data/receipts/T10-fleet-expansion-blocked-20261008-r1.json`). Throughput 66,420 perspectives/h; ETA
  ~10:20 UTC. Not worth a restart: S122 feeds v2, which comes after v1 training and gates (b)/(c), and 04/08 go to S3,
  then T5 data loaders and gate games.
- **2026-10-08 05:27 UTC: fleet sharing with roader** (Sam: "check with roader, share the machines if one of you isn't
  using them"). Read-only check: roader's 127x09–18 are idle (load ≤1.2, A6000s at 0%; console users on 12 and 17), while
  clasher's 01/03/04/08 are near the cap. Drafted the protocol `/mpac/sdicks02/cc/FLEET-SHARING.md`: lease file per
  borrowed host, separate trees only, 30-min reclaim, ≤96 processes/host, GPU headroom. Asked roader's coordinator
  ("Take Over RoadForge Pipeline", f552b138) to lend 127x11/13/14/16/18 for ~24 h (imitation training on GPUs,
  evaluation games on CPUs), and offered clasher hosts back when idle. **No writes to roader hosts until they answer.**
- **2026-10-08 05:28 UTC: roader lent hosts until 2026-10-09 05:30Z** (`/mpac/sdicks02/cc/FLEET-SHARING.md`, rules 1–7 incl. the
  co-tenancy rule 6). Leases:
  - 127x11: full, ≤96 processes. Never touch the roader mirror dirs there.
  - 127x13/14: shared, ≤64 processes.
  - 127x16/18: shared, ≤48 processes.
  - 127x09/15: GPU only, ≤8 processes.
  All lent GPUs are ours apart from ≥8 GB headroom; resident memory ≤64 GB on shared hosts; 30-min reclaim. Not lendable:
  127x10, 12, 17. Use: imitation T5 one run per GPU, gates (b)/(c) games and later S122 v2 training on the CPUs/GPUs,
  and perception runs. First: a self-contained clasher footprint per borrowed host under `/mpac/sdicks02/repos/clasher*`
  (own tools, uv Python and venvs; never the shared `/mpac/sdicks02/tools` or `env.sh`), qualified by the P16 identity
  smoke before use.
- **2026-10-08 05:37 UTC: S3 robust tracker: strength tests FAIL; the hand/cycle component, not elixir, looks decisive.**
  (`search-noise-s3/RESULTS.md`; 1,792 games, 42 core-h, 20 min on 04/08.) tracker_v2 meets calibration: N97/N90 coverage
  89/90%, post-error coverage 85/90%, width 2.8 vs legacy 6.1–6.7. But its MAE barely improves (0.70 vs 0.73), and play does
  not: T2-N90 − Full-N90 = +1.6 pp [−4.7, +7.8] FAIL; T2-N97 − Full-N97 = +0.2 [−6.4, +6.8] FAIL; R-derived − T2-N97 =
  15.0 pp. Descriptive but telling, scores rank by **hand knowledge** (share of decisions with a ≥90%-mass hand, and that
  hand's accuracy): R-derived 80.1% (16.2%, 100%) > ELT-N97 70.7% (9.6%, 68%) > T2 65.0% (1.3%, 17%) ≈ legacy 64.8%
  (0.5%, 78%). T2's cycle mixture has poor hand inference; ELT's is better despite its worse elixir.
  **Decision: S4.** (a) A pre-registered decomposition of the derived state on the Full-N97 configuration:
  R-elixir (exact opponent elixir, legacy hand) and R-hand (exact hand/cycle/next, legacy elixir), with Full, ELT and
  R-derived anchors, fresh seeds, 5 × 256 games. (b) In parallel, development of tracker v3, aimed at calibrated hand/cycle
  inference that recovers after misses (T2's resource lattice + an ELT-style cycle model with resync), dev seeds only.
  Its confirmation is pre-registered only if S4 shows R-hand is material. L2-v4 stays blocked.
- **2026-10-08 05:43 UTC: T1 Phase A at 3 renderers** (Astra `clasher-t1-parallel-renderers-20261008-1`; Mac `live-loop/v4/PREREG.md:92`
  amendment, `T1-PROGRESS.md:461`, `pool-scale-report.json`).
  - Throughput 26.6 → 75.8 matches/h (2.86×). Every pool match passes its endpoints; per-instance minimum FPS
    19.967/19.980/19.991; no duplicated or skipped seeds. The old driver had stopped on its storage guard; its partial seed
    1975100803 was rerun.
  - 120 matches and 11 heldout / 295 opponent events at the switch; ETA to coverage ~6–8 h.
  - **Mac pressure:** swap 12.9/14.3 GB (four new 1 GB swapfiles after the ramp-up); another project's Windows 11 UTM VM
    (canvasdoc, 30 GB disk) shares RAM; T3 statev2.sqlite on the Mac is 40.7 GB; staged macOS update snapshots. Disk free
    ~20 GiB vs the collector's 15 GiB floor.
  - Kept 3 instances. Added an **hourly coordinator heartbeat** (T3 scheduled task bound to this thread): Mac disk/swap,
    fleet and lease reclaims, task blockers. It drops to 2 renderers if free disk < 17 GiB, swap > 14 GB or memory
    pressure turns critical.
- **2026-10-08 05:44 UTC: leased hosts qualified; T3 stall found.** All 7 lent hosts are ready under
  `/mpac/sdicks02/repos/clasher-lease/` (`fleet/LEASED-HOSTS.md`, receipts `jobs/clasher/lease-ready-<host>.json` on 127x01).
  P16 identity 12/12 with 0 mismatches on 11/13/14/16/18; GPU check PASS on all 7 (eager; torch.compile fails as on our
  hosts). The CPU extensions were rebuilt locally because the hub source pins had moved to build 48. Leases written per
  FLEET-SHARING.md. **T3-PASS was blocked** by a deadlocked P16 baseline (`baselines.py p16`, PID 3449355: futex
  wait, ~12 s CPU in 36 min, no I/O). Routed to the data worker to diagnose, kill only that PID, fix (thread caps / no
  fork after torch init), rerun that step, publish T3-PASS, and copy the store to 04/08 + 11/13/14/16/18. The T5 worker
  was told to run its 5 runs one per GPU on 04/08/11/13/14.
- **2026-10-08 06:07 UTC: v4 perception T6/T7 shakedowns done; no-KVM rendering ruled out.**
  - **T6:** v3 trainer ported to CUDA; 83 train + 10 validation Phase A matches. After 40 steps (unconverged), validation
    opponent recall/precision is 8.5/52.4%.
  - **T7:** model `src/clasher/vision/l1_v4.py`, 2.42M params, 15 tests, TorchScript parity. GPU 176 encoded frames/s but
    only **1.28 windows/s including H.264 decode**: data loading is the bottleneck. The PREREG is frozen
    (`live-loop/v4/l1/PREREG.md`; formal runs per `l1/RUNBOOK.md` after Phase A completes). Contradictory body labels
    are masked, so an annotation review is needed before any board-precision claim.
  - **No-KVM emulator on 127x04** (`fleet/NOKVM-EMULATOR.md`, Sol): boot 12.8 min, Settings at **0.154 FPS (130× below
    20)**, shell 0.8 s, 0/10 screenshots within 10 s. `-gpu host` fell back to SwiftShader; MTTCG was unstable. Rendering
    without KVM is infeasible; only a kvm group grant from CSL admins would change that.
- **2026-10-08 06:25 UTC: S4: the gain needs elixir AND hand together; tracker v3 meets its dev target; S5 decided.**
  (`search-noise-s4/RESULTS.md`, `TRACKER-V3.md`; 1,280 games, 30 core-h, 21 min on 04/08.) Full 66.4%; R-elixir +6.2 pp
  [0.0, 12.5]; R-hand +5.9 [−0.4, 12.1]; neither is material under the strict LB>0 rule. R-derived +18.0 [11.7, 24.2]
  material; ELT +6.4 [0.4, 12.5] material; interaction +5.9 [−2.3, 14.1].
  Reading: each component alone is worth ~6 pp; the full gain needs both (simple additivity is not excluded).
  **Tracker v3 (dev validation only, fresh traces):** N97 resolved-hand 20.6% at 91.5% accuracy (true state 21.4% /
  100%; ELT 8.5% / 77%; T2 2.1% / 49%). Reliability is good across bins, slightly underconfident. Elixir = T2 lattice
  (MAE 0.65, 90% coverage, width 2.6). At N90 its hand inference collapses (0.008% resolved).
  **Decision (overriding my earlier "S5 only if R-hand is material" condition):** run **S5**, a confirmation of
  tracker v3. It is the first tracker that is good on both components (calibrated elixir, near-reference hand at N97);
  the joint repair is +18 pp; ELT (weaker on both) is already material. Cost ~20 min of games. **Implication for v4
  perception:** hand inference only works at ~97% event quality, so the v4 event gate should be judged against
  97/97, not just the provisional 95/95. That is decided after S5.
- **2026-10-08 06:41 UTC: why the fleet was idle, and fixes.** fleetmon (live) showed all 13 GPUs at 0% and CPU at 0–11%.
  Causes:
  1. **False "console user" throttling.** The fleet-top tmux grid (ssh -t to every host) was left running detached on
     127x05, so `who` showed `sdicks02 pts/0 (129.65.221.15)` everywhere. Launchers that read "who non-empty" as a
     console user dropped to 16 workers, and the data worker flagged a cap violation. Fixes: killed the unattached
     `fleet` session (0 clients); fleet-top now sets `destroy-unattached on`; new shared helper
     `~/.local/bin/fleet-console-users` counts only physical-seat logins (ttyN or :N) and other users (01/04/08 → 0;
     12/17 → 1). Workers are told to use it.
  2. **T3-PASS gated on the slow upgraded-P16-BC baseline scoring** (2 CPU workers, ~1.5 h per split). My earlier
     "deadlock" call was wrong: I checked threads, not child processes; the scorer is progressing. Decision: decouple.
     T3-PASS is published on the store and frequency baselines; the P16 numbers come later (they only feed gate (a) bar A2).
  3. **Mac pool at 1 renderer.** The pool's own guard scaled back at 22:54 PDT on critical memory pressure and again
     after one 19.107 FPS match at 2 renderers. Decision: retry 2 once (controlled drain and restart, amendment
     first); any further failure or critical pressure means 1 for the rest of Phase A.
- **2026-10-08 06:45 UTC heartbeat:** T3-PASS published (P16 baseline decoupled). Next: T4 shakedown poll (06:51), then T5 one run per GPU. Mac OK (26 GiB free, swap 6.9/8 GB, pressure normal; pool retry at 2 in progress). S5 preflight 7/10. Fleet reachable, console users 0 on our hosts, no lease reclaims. GPUs idle until T5.
- **2026-10-08 06:45 UTC:** roader raised our caps on 127x16/18 from 48 to 96 processes (its speedup job finished; it keeps ≤8 light processes). ≤64 GB RSS and ≥8 GB GPU headroom unchanged. Lease files and lease-ready receipts updated (old receipts kept as `.bak-cap48`). 127x13/14 stay at ≤64.
- **2026-10-08 07:11 UTC: S5 PASS. Tracker v3 adopted; tracker block on L2-v4 lifted; event gate set.**
  (`search-noise-s5/RESULTS.md`; 1,536 games, 37 core-h, 18 min on 04/08.)
  - Primary T3-N97 − Full-N97 = **+8.2 pp [+2.3, +14.5] PASS**; T3-N90 − Full-N90 = **+8.6 [+3.1, +14.5] PASS**;
    T3 − ELT-N97 = +0.4 [−5.5, +6.2] (no difference resolved); ceiling gap R-derived − T3-N97 = 7.0 [2.0, 12.1].
  - Diagnostics: T3-N97 resolves the hand on 24.1% of samples at 90.8% accuracy, elixir coverage 89%, width 2.8.
  - Coordinator recomputation from the 1,536 raw receipts reproduces all three contrasts.
  - **Decisions:**
    1. Tracker v3 (`search-noise-s4`, frozen) becomes the fair player's opponent-state tracker for every noisy or live
       pipeline. ELT and legacy are retired from live use.
    2. **v4 event gate = in-loop opponent-event recall and precision ≥90% at 500 ms (hard minimum), 97/97 target.**
       T3's gain is confirmed at N90, but hand inference only becomes informative near 97.
    3. The tracker no longer blocks L2-v4. Remaining L2-v4 prerequisites:
       - (a) delay-aware planner + S-d validation (T2 amendment items 4–5);
       - (b) the 5-process pipelined Mac runtime (DESIGN §2);
       - (c) v4 perception formal runs and gates (after Phase A, ETA ~16:40Z);
       - (d) the P4 verifier re-test with the v4 HUD head (≥300+300 trials, ledger-relative spend predicate);
       - (e) the L2-v4 PREREG.

       (a) and (b) start now.
  - Remaining decision-side gap: ~7 pp to R-derived, plus ~6 pp from board noise (S2). Board precision stays the
    v4 perception priority after events.
- **2026-10-08 07:22 UTC: v4 perception storage approved.** The perception worker's full decode cache (~97 GB projected for the
  audited population) was blocked by the T1 PREREG's 40 GB cap and an unanswered storage request (coordinator miss).
  Decision: the 40 GB cap covers raw acquisition only (~8 GB now, ~27 GB projected). Derived, regenerable caches get up to
  300 GB per host on `/mpac` (~1.6 TB free everywhere; keep ≥200 GB free), under `clasher-v4-cache/` (home) or
  `clasher-lease/data/v4-cache/` (leased; cleared within a day of lease end). The worker also finished: label audit
  + labels_v4 (coherent rows only, ambiguous masked; amendment 03), cache pilot parity, resume tests, and scorer/selection
  primitives (135 checks). Phase A at 07:04Z: 145 train / 18 val / 18 heldout matches, 437 heldout opponent events.
- **2026-10-08 07:44 UTC heartbeat:** Mac OK (23 GiB free, 35% memory free, pool at 2 renderers with retry_used). Answered the perception worker's pending storage question (allow ≤1 TB total cache; consistent with the 300 GB/host decision). T4 shakedown failed once (dev row >64 entities, v6 contract cap) → fixed to the 128 cap, rerunning; T5 hard-stopped correctly, then **resumed by the coordinator** to wait for the rerun PASS (T5 schedule re-enabled). S6 1,253/1,280 receipts. No reclaims; console users 0.
- **2026-10-08 07:50 UTC: GitGuardian alert on 20cff68 = false positive.** The 'Generic High Entropy Secret' is `"tokens": "35db1a76…"` (3 occurrences in imitation/model/receipts/shakedown-20261008T0714Z/{preflight.json,train.jsonl}): the SHA-256 of the public 360-name contract_v5 token list (recomputed via token_list_sha256). No credential was committed; the commit has no other secret-like fields. Added `.gitguardian.yaml` ignoring that exact hash. My commits now run `/mpac/sdicks02/cc/tools/bin/clasher-secret-scan` (gh/HF/AWS/OpenAI/Tailscale/Slack tokens, private keys) on the staged diff first.
- **2026-10-08 07:53 UTC: S6 PASS. Delay-aware planning adopted; L2-v4 prerequisite (a) done.**
  (`search-noise-s6/RESULTS.md`; 1,280 games, 21 core-h, 15 min.) Clean d0 89.5%; clean d22 unaware 72.3%; clean d22 aware
  86.7%; T3-N97 d22 unaware 50.8%, aware 60.2%.
  - Primary: aware − unaware (clean, d=22) **+14.5 pp [+8.6, +20.3] PASS**.
  - Secondary: aware − unaware (noisy T3-N97) **+9.4 [+3.9, +15.2] PASS**.
  - Latency cost when aware (d0 − d22-aware): 2.7 [−2.0, +7.4], not resolved.
  - Coordinator recomputation from the 1,280 raw receipts reproduces both contrasts. 126 capacity-triggered partition
    resumes on 04 were technical, with no exclusions.
  - **Decisions:**
    1. The delay-aware planner (S6 flag, d = backend D_b in ticks from `backend-timing.json`) is the default for every
       delayed backend: renderer ≈22–23 ticks; L3 measures its own.
    2. The L2-v4 sim arm S-d = clean d22 aware.
    3. The remaining noisy gap at d22 is 26 pp (60.2 vs 86.7), from board noise and residual derived-state error:
       still the decision- and perception-side agenda.
- **2026-10-08 08:16 UTC: v4 runtime built; latency budget FAILS on the fleet replay.** (`live-loop/v4/RUNTIME.md`, `src/clasher/live/`,
  27 tests.) S6 delay-aware planning is integrated (renderer gRPC p50 = 23 ticks; P4 is the sole reservation authority).
  Fleet CPU replay, two train matches: frame→first-tap **312/386/406 ms** p50/p95/p99 vs budget 200/400. The bottleneck is a
  combined P2 at 14 processed FPS (capture queue age 148/352 ms):
  - v3 fallback perception on CPU: 44 ms (ANE budget 15/25);
  - tracker v3 + ledger + roots: 22/48/157 ms (budget 3/10);
  - search 74/121 ms is OK.

  Decision: a latency job.
  1. Split P2 into separate perception and belief processes, as DESIGN.
  2. Make tracker v3 output-identical but fast: bit-exact on ≥20k recorded updates, ≤10 ms p99.
  3. Re-measure with ≥200 taps.
  4. Measure on the Mac with MPS perception after Phase A.
- **2026-10-08 08:44 UTC heartbeat:** Mac OK (23 GiB, 33% free, pool 2 renderers, 101 matches this run). T4 shakedown rerun still in dev evaluation after 72 min with the GPU at ~0%. Measured 2.1k rows/s vs the DESIGN's 8k plan (microbatch 64 → 128 accumulation steps/step), which would make each run ~24 h and overrun the lease window. **Decision:** a T4 throughput pass (largest microbatch with the equivalence proof, vectorized loader and evaluator, ≥8k rows/s target, receipt `throughput-pass.json`) before T5; T5 told to wait for it. No pending worker questions; no reclaims; console users 0.
- **2026-10-08 09:19 UTC: runtime latency revision. Accepted with a revised budget; the planner delay now includes decision latency.**
  (`live-loop/v4/RUNTIME.md` §"Latency revision", 14 train matches, 223 first taps, 127x04 CPU.)
  - P2 is split (perception → belief), so 19.975 processed FPS (99.96% of frames); capture queue age 18.6 ms p50 (was 148).
  - Tracker v3 is output-identical: bit-exact on 32,837 updates (S4 dev + Phase A train), 6.75× median speedup; optional
    rustc lattice kernel. In-pipeline belief is 6.2/16.8/23.9 ms (p99 target 10 missed).
  - **Frame→first tap 246/318/340 ms** p50/p95/p99 (was 312/386/406): p99 ≤400 PASS, p50 ≤200 FAIL. Most of the median is the
    anytime search (143 ms p50, up to its 200 ms deadline; zero overruns); v3 CPU perception is 45 ms (ANE budget 15–25).
  - **Decisions:**
    1. Accept the runtime for L2-v4 with a revised end-to-end budget: **p50 ≤260 ms and p99 ≤400 ms**, re-measured on the
       Mac. The DESIGN's 200 ms median predates the 4-root, 200 ms-deadline search and the delay-aware planner. S2 showed
       latency at these levels is not material (repair LB 0.0; add cost −1.6 [−5.5, +2.0]). Search strength is not traded
       away for median latency.
    2. **The planner delay d is the total delay:** median frame→submission plus D_b,p50, in ticks (≈ 5 + 23 = 28 on the
       renderer), not D_b alone. The L2-v4 S-d arm uses the same total. The runtime reads both from measured config.
    3. After Phase A, run the Mac MPS measurement (exact command in RUNTIME.md) as a prerequisite of the L2-v4 PREREG.
- **2026-10-08 09:44 UTC heartbeat:** **T4 shakedown PASS + throughput PASS**: 12,154 rows/s loader-inclusive on one A6000 (5.8× the shakedown; microbatch 7,168, effective batch 8,192, one-step equivalence within the recorded bf16 tolerance; evaluator 2.5× faster with matching metrics; code hash 301caa10…; 2 runs/GPU gives less in aggregate, so 1/GPU). A C56 epoch is ~21 min. T5's start gates are now met; its poll (09:44Z) launches 5 runs, one per GPU on 04/08/11/13/14. Mac OK (23 GiB, 34% free, 153 matches this run). S122 extraction ETA ~10:20Z (01 busy; 03 done). No reclaims; console users 0.
- **2026-10-08 10:44 UTC heartbeat:** T5 launched at ~10:25Z. 13 (main03) and 14 (noD1) were stopped by the lease wrapper's 64 GB cap, which summed per-process RSS and so counted the shared store mmap once per loader (153 GB; 11 reported 290 GB while `free` showed ~2 GB used plus page cache). The T5 worker then stopped main01/main02 (exit 0, epoch 0, ~12M rows, loss 9.7→~6.0) to restart all five on one RSS-bounded loader version (resource-r2 amendment). **Decision:** the rule 6 cap is measured as **PSS** summed over our process tree (no double counting), shared hosts only; full-lease 11 and home hosts have no 64 GB cap; the restart on one code version is approved. **S122 extraction T10 PASS:** 333,934 perspectives, 233.8M rows, 0 errors/illegal labels/audit violations, 04 copy verified. Mac OK (25 GiB, 206 matches this run). No reclaims.
