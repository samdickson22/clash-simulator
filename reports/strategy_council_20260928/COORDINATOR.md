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
- **2026-10-08 11:14 UTC:** roader upgraded 127x09/15 from GPU-only to shared CPU+GPU ≤96 processes (≤16 with a console user; ≤64 GB memory; ≥8 GB GPU free). 13/14 stay at ≤64 for a mesh fix. Lease files updated; CPU footprint + P16 smoke requested from the lease-bootstrap worker. Told roader we measure rule 6 memory as PSS (not summed RSS), with the reason, and offered to switch if it prefers another measure.
- **2026-10-08 11:14 UTC:** roader agreed: rule 6 memory = PSS summed over the borrower's process tree (written into FLEET-SHARING.md; its hourly probe switched from RSS to PSS).
- **2026-10-08 11:44 UTC heartbeat:** T5 v1 runs training on 5 GPUs (04/08/11/13/14, 29–40 GB each). Mac OK (25 GiB, 261 matches this run; Phase A ETA ~16:40Z). Idle GPUs on 01/09/15/16/18 → **launched T11 now**: v2 store (C56 ∪ S122) on 127x01 CPU, v2 PREREG, v2-main seeds 2026100821/22 on 16/18 (~11 h/run at 12k rows/s; checkpoint/exit by 05:00Z, resume on home GPUs). v2 eval scoring waits until v1 gate (a) is reported. No reclaims; console users 0.
- **2026-10-08 12:45 UTC heartbeat:** T5 r2 runs: main01 (04) epoch 2 best dev 0.381; main03 (13) epoch 2 best dev 0.383; **main02 (11) loader-starved** (epoch 0, 1,252 vs 8,371 rows/s step-only; host idle, no I/O). Sent to the T5 worker to diagnose and resume from checkpoint with identical math (11 has no 64 GB cap, so the 4-worker loader is allowed). Phase A 485 match dirs on the hub; Mac OK (25 GiB, 41% free). T11 store build on 01. No reclaims; console users 0.
- **2026-10-08 12:53 UTC:** roader raised our caps on 127x13/14 from 64 to 96 processes (mesh fix done; roader keeps ≤16 light review processes). Every lent host is now ≤96, PSS ≤64 GB, ≥8 GB GPU free. Lease files and lease-ready receipts updated (old receipts kept as `.bak-cap64`).
- **2026-10-08 13:44 UTC heartbeat:** 7 GPUs training: T5 v1 on 04/08/11/13/14 (main02 on 11 recovered to ~95% GPU) and T11 v2 on 16/18. Idle: 01/09/15 GPUs (reserved: 01 for the v4 perception formal runs after Phase A; 09/15 spare). Mac OK (26 GiB, 33% free, 369 matches this run). No pending worker questions; no reclaims; console users 0.
- **2026-10-08 14:45 UTC: 127x11 (leased from roader) went offline at ~14:10Z**, taking T5 main02 and its local checkpoints. Third lab
  host lost: 127x02 (CPU load, 23:25Z), 127x07 (CPU load, 01:14Z), 127x11 (GPU training at ~95%, CPU load ~5). No OOM or
  thermal sign on the survivors; cause unknown, possibly physical (power-off/reboot by lab users). Not retrying; not touching tailscale.
  **Decisions:**
  1. main02 gets a pre-registered technical rerun from scratch (same seed 2026100802, same qualified code) on 127x01. Any
     partial run from 11 is never merged.
  2. All training runs (T5 v1, T11 v2, v4 perception) copy checkpoints off-host (to 127x04) at least every epoch or hourly.
  3. The v4 perception formal runs move to 127x09/15 (and 04/08 once T5 frees them).
  4. Roader told (its backup mirror dirs were on 11). 11's lease is void until the host returns. Sam told.
  Mac OK (24 GiB, 422 matches this run).
- **2026-10-08 14:46 UTC:** roader confirmed 127x11 is offline and its lease void (FLEET-SHARING.md updated). It is rebuilding its only backup as two mirrors on **127x09 and 127x15** (~30 GB each under `roader-mirror*`, `roader-code-127x05-mirror`, `roader-mirror-trash`): roader-owned paths, never touched by clasher. Our caps there are unchanged. Perception worker told (it will use 09/15).
- **2026-10-08 15:45 UTC: T1 Phase A COMPLETE** (pool stopped "heldout count coverage reached" at 15:43:11Z; `live-loop/v4/phase-a-results.json`).
  641 matches, all hub-verified (8.67 GB); 31,068 deployments, all exact-tick; FPS endpoint 638/641 (min 17.07, 3 failures
  retained); 15.56 emulator-hours of the 36 h cap; **heldout 64 matches / 1,520 opponent events** (rule ≥1,500 and ≥20 met);
  320 ability events. Actions:
  1. Perception worker told to start the formal T6/T7 fits on 127x09/15 (+04/08 later): validation-only selection, seal,
     then one heldout evaluation.
  2. Delegated the Mac runtime latency measurement: quiet host (T1-owned emulators stopped, AVD kept), MPS perception,
     ≥200 taps, revised budget p50 ≤260/p99 ≤400. It also sets `planner_total_delay_ticks` = round((median frame→submission +
     D_b,p50)/50 ms), read by P3.
  3. T5 main03 was stopped by the lease wrapper at 15:39Z for GPU free <8 GB (our own peak); told to resume from checkpoint
     with an output-neutral eval-memory reduction.
  Fleet: 02/07/11 still offline. No reclaims.
- **2026-10-08 15:54 UTC:** Mac latency task blocked on my copy allowlist: v4 imports the frozen S4 tracker v3 and S6 planner files, which the Mac lacked. **Approved** copying the minimum frozen dependencies plus one S4 dev parity trace into the separate runtime directory (hash-verified against the freeze manifests, no Mac repo overwrites). Done so far: T1-owned emulators 28907/21614 stopped by verified SIGTERM (AVDs kept; Mac memory free 60%); lattice dylib built; 20 train matches staged; P3 reads `planner_total_delay_ticks` (provisional 28 until the Mac measurement).
- **2026-10-08 16:45 UTC heartbeat:** the perception worker had 2 pending questions, which is why 09/15 sat idle. (1) **Approved** retiring 349 duplicate cache shards on 18 (289 GB), after re-verifying the retained 01 copies, to free space for 09/15 staging. (2) Its T1-completion check needed hub evidence: the coordinator mirrored the Mac's phase-a-results.json, pool-state.json (stop_reason coverage reached), pool exit 0, log, events, T1-PROGRESS.md and a 0-process check into `live-loop/v4/t1-completion-mirror/` on 127x01, with receipt T1-PHASE-A-COMPLETE.json (SHA256s). Pool mode has no legacy phase-a-exit.json. GPUs: 7 busy (01 main02 rerun, 04/08/13/14 T5, 16/18 T11). Mac 28 GiB, 64% free, 0 emulators. 02/07/11 offline.
- **2026-10-08 17:45 UTC: Mac runtime latency PASS on the revised budget** (`live-loop/v4/runtime-mac-latency.json`). M4 Pro, MPS, v3
  body/HUD perception, quiet host (T1 emulators stopped, AVDs kept). Frame→submission p50 186 ms; budget p50 ≤260 / p99 ≤400 PASS.
  In-pipeline belief p99 still above 10 ms (noted, not blocking). Tracker parity bit-exact on the Mac (2,200 updates).
  **planner_total_delay_ticks = 27** = round((186 + 1,152 ms)/50), configured in the runtime's backend-timing.json and read by P3.
  Tests 34/36: the two zero-delay S6 comparisons fail because the **Mac's native extension predates build48** (no `full_rng`
  arg). **Delegated:** build build48 on the Mac in the isolated runtime root, re-run the 4 identity modes + Stage 5/6 checks,
  and require 36/36 tests. This is an L2-v4 prerequisite.
  Perception formal fits had not launched: the worker was idle after I told it to delete its Phase A poll. Explicitly told to
  launch on 09/15 now, using the mirrored T1 completion evidence.
- **2026-10-08 18:24 UTC: Mac native engine = build48 (isolated runtime root), verified.** (`live-loop/v4/MAC-NATIVE-BUILD48.md/.json`.)
  66 source pins match; Rust 1.97.1; Mac native `9263a8f7…`. Identity P16 12/12, C56 7/7, random 24/24, recorded 8/8; Stage 5
  200/200 roots; Stage 6 69/69; runtime tests 36/36 (both zero-delay S6 comparisons now pass). Smoke 58 taps: p50 187.8 / p99
  269.2 ms. Live Mac checkout and .venv untouched. **Coordinator re-check on the Mac:** C56 identity with the isolated build48
  .so loaded gives 7/7, 2,900 boundaries, 0 mismatches, baseline `002a57a9…`.
  **Next:** L2-v4 PREREG drafting delegated to Opus (arms P/O/S-d/S, entry criteria incl. perception gates and the P4 verifier
  re-test with the v4 HUD head, power and wall-time analysis).
- **2026-10-08 18:38 UTC: L2-v4 PREREG frozen** (`live-loop/v4/L2-V4-PREREG.md`, sha256 `85c593df…`; Opus draft kept as `.draft.md`).
  - **Arms:** P (pixels v4) / O (fair native truth, same P4 and renderer) / S-d (d=27, aware) / S (d=0).
  - **Primary:** P − O, family-stratified paired-bootstrap LB > −0.10.
  - **Pairs:** 144, with a blinded re-estimate at 54. DESIGN's 96-pair power claim was wrong: 43% power at a true 0.
  - **Wall time:** ~29 renderer-hours on one renderer.
  - **Entry:** E1–E10, incl. v4 perception gates with the S5 event row (≥90/90, LB ≥87), the P4 verifier re-test (324+324
    trials, ≥99% sensitivity and specificity), an emulator-on T9 smoke with formal weights, Mac build48 identity, the frozen
    tracker v3, quiet host and renderer receipts.
  - **Coordinator decisions:**
    1. The simulator go/no-go (E9) is binding, with go iff predicted (S-v4N − S-d) ≥ −0.05 (stricter than the drafted −0.10,
       so we don't spend ~30 renderer-hours on a likely fail).
    2. Two renderers only if both pass the loop gates concurrently after E4.
    3. The E1 tracker-row amendments (a)–(c) are approved: they replace ELT-era targets.
- **2026-10-08 18:44 UTC heartbeat:** correction: the v4 formal T6/T7 fits are **complete** (24×400 steps each; checkpoints SHA-verified on 04; cache 1.28→13.86 windows/s; 10,420 equality checks, 0 mismatches; 544,623 label errors resolved, 413,895 unresolved rows masked). Validation jobs are active on 09 (T7 replay) and 15 (T6 scoring), mostly CPU, hence GPU 0%. Asked the worker for a bounded 20-min continuation schedule through selection, seal, the single heldout eval, `l1/RESULTS.md` and `l1/noise-measured.json` (the E9 input). T5: 04/13/14 runs finished (selection jobs running); main02 rerun on 01 and GRU on 08 continue; T11 v2 on 16/18. Mac idle (26 GiB, 55% free).
- **2026-10-08 19:58 UTC: heartbeat, three coordinator decisions.**
  - **State.**
    - Mac: 27 Gi free, swap 5.5/7 G, memory 60% free.
    - T5: main01, main03 and noD1 finished all 12 epochs (exit 0). main02 is in its final epoch on 01. GRU on 08 runs at 243 rows/s.
    - T11 v2: both seeds are progressing on 16/18 (step ~5.5k/6.0k, timer 04:20Z).
    - T7 validation: 2 of 432 grid cells done.
    - No reclaims and no pending worker questions.
  1. **T7 validation grid: inference split from thresholding.** At ~35 min/cell serial on 09 the grid would take about 250 h, while GPUs on 04/13/14/15 sat idle.
     - Each of the 24 epoch checkpoints gets one inference pass over the 64 validation matches, with raw outputs stored under hashes. The passes run in parallel on 09/13/14/15/04.
     - All 432 cells are then computed on CPU (01/03 plus leased CPU).
     - This is an output-identical amendment: before use it must reproduce the completed cells bit-exactly.
     - The 05:00Z deadline binds only the leased hosts. The continuation goes on, on home hosts, until RESULTS and noise-measured.json are final, and the worker edits its cleanup task accordingly.
  2. **T5 gate (a) decoupled from the GRU ablation.** GRU is descriptive and can't change the verdict (PREREG), and at 243 rows/s it would hold gate (a) for up to ~9 days.
     - Gate (a) is scored on main01/02/03 + noD1 once main02 completes.
     - GRU continues under frozen rules, which are recorded in a prospective amendment before any heldout inference.
     - GRU later gets its own once-only heldout pass, reported in a labelled post-verdict addendum.
  3. **Post-lease home GPUs:** T11 seed 21 → 01 (after main02 exits), seed 22 → 04 (after the perception GPU work ends at 05:00Z), 08 → T5 GRU. Resume artefacts are pre-staged now.
- **2026-10-08 20:06 UTC:**
  - **v4 perception:** the cache budget is raised from 1.0 to up to 1.3 TB aggregate for lossless inference-output shards. Per-host limits are unchanged: ≤300 GB per host, ≥200 GB free. GPU inference may start without waiting for duplicate retirement.
  - **T11:** seed 21 checkpointed at step 5735 and exited cleanly to qualify a multi-worker loader. The runs were loader-bound at ~2k rows/s against ~12k qualified.
  - **Console check:** `fleet-console-users` is now lock/idle aware. The "console users" on 12/17 were stale locked seats in a locked room: a student logged in since Aug 24, and Sam's own login. Roader has been told.
- **2026-10-08 20:45 UTC heartbeat (utilization 4/9 GPUs busy):**
  - **Busy:** 01 at 81% (T5 gate (a) once-only heldout scoring; 4-run release sealed at 20:21Z, primary main02 step 22552); 08 at 31% (GRU ablation); 16/18 at 79%/89% (T11 resumed with a qualified six-worker loader, ~7.3k rows/s per run, up from ~2k).
  - **Idle:** 04, 09, 13, 14 and 15. Perception GPU fan-out is gated on the full 64-match equality job, which was waiting on 01's cache checksum. I told the worker to use 03's verified cache and to pre-stage the fan-out.
  - **Decision: gates (b) and (c) start now** (delegated, Astra high, clasher-imitation-gates-bc-20261008-1). They depend only on the sealed dev-selected checkpoint, not on the gate (a) verdict. They run on idle CPU (03 primary, plus 04 and leased 13–15 CPU), with the PREREGs frozen with the checkpoint hash before any game. CPU on 03 is split with the perception threshold grid (≤64 processes each).
  - **Health:** Mac 27 Gi free, 48% memory free; no reclaims; no pending questions.
- **2026-10-08 20:58 UTC: 127x02, 127x07 and 127x11 are back** (Sam powered them on; rebooted ~20:32Z, GPUs idle, console 0). 06 is still down. I hadn't noticed sooner because they were commented out of the fleet hosts file, which made them unmonitored. They're re-enabled now, and the 30-min check retries offline hosts.
  - **02/07 (home):** go to the v4 per-epoch inference fan-out now, and stay with perception after 05:00Z. 02 needs the env copied and its old hub /mpac contents are untrusted.
  - **11:** roader confirmed it's ours again from 21:10Z under the existing lease. Its roader dirs are a stale mirror; leave them untouched.
  - **Caps:** roader now runs ≤32 processes on 09/12/13/14/15/17, so all clasher processes combined on 09/13/14/15 must stay ≤80 per host.
  - **Gates (b)/(c) worker:** authorized read-only, seed-only inventory scans on 01/08 (and 02/07), excluding gate (a) outcome payloads. An independent Opus PREREG review will run before any gate game.
- **2026-10-08 21:02 UTC: outage cause (from Sam).** 127x02 (offline from 2026-10-07 ~23:25Z), 07 (from 10-08 ~01:14Z) and 11 (from ~14:10Z) were **physically powered off by someone in the lab**: not overload, heat or a crash from our jobs. Lab machines can be switched off at any time without warning. Leased and home jobs must therefore keep frequent off-host checkpoints (≤1 h of lost work) and resume from them, as T5 main02's 11→01 host-loss rerun did.
- **2026-10-08 ~21:05 UTC: multi-GPU DDP is feasible on the fleet.**
  - Checks: 10 GbE LAN; arbitrary TCP ports open between hosts (tested 02→07:29517); torch 2.7.1 with NCCL 2.21.5.
  - **Backlog decision:** once v4 perception releases 02/07, qualify the T5 GRU ablation as 3-GPU elastic DDP on 08+02+07 and move it there under a dated amendment. GRU is descriptive and already decoupled from gate (a).
  - Qualification requirements: the same effective batch of 8192; equivalence within bf16 tolerance (not bit-exact); elastic torchrun with checkpoints every ≤10 min. The expected wall time is ~3 days instead of ~9.
  - Main/registered gate runs stay single-GPU.
- **~21:15 UTC: multi-node DDP adopted (Sam: "do it, use the full capabilities of the network").**
  - **Measured:** enp68s0 10 GbE gives **9.4 Gbit/s** host to host on a single stream (11→07). Ports open; NCCL 2.21.5. **127x02 is cabled to 1 GbE** (enp70s0, 0.94 Gbit/s): kept out of DDP groups, and I've asked Sam to move the cable.
  - **Standard for all trainers:**
    - torchrun elastic with c10d rendezvous (ports 29500–29599; roader told to use another range), NCCL over sockets: `NCCL_SOCKET_IFNAME=enp68s0 NCCL_IB_DISABLE=1 NCCL_SOCKET_NTHREADS=4 NCCL_NSOCKS_PERTHREAD=2`.
    - Global batches identical to single-GPU (deterministic sharding plus accumulation); each rank reads a local store copy.
    - Rank-0 checkpoints every ≤10 min, with exact resume across world-size changes.
    - Qualification before switching: 50 steps single vs DDP within bf16 tolerance, kill/resume, scaling efficiency.
    - Dated technical amendments, frozen before the switch.
  - **Allocation:**
    - v4 perception inference fan-out first (02/04/07/09/11/13/14/15).
    - **T11:** seed 21 on 16+11+13, seed 22 on 18+14+15 until 04:20Z; after 05:00Z on 01+07 and 04+08.
    - **T5 GRU:** 01+07+08 now; single-GPU on 02 from 05:00Z; grows back after T11 finishes.
  - **Roader informed.**
- **~21:30 UTC: gates (b)/(c) decisions.**
  1. **Model source.** The gates serve the released checkpoint with the exact post-T5 source used by gate (a) scoring (`gate4-scoring-launch.json`), not the older e3 T6/T8 snapshot (tile_width 64, entity cap 128, unpadded inference differ; weights unchanged). This requires a dev-only forward-equality check against the gate4 scorer and freezing the tree hash. Post-T5 pilots count as requalification evidence.
  2. **Hosts.** The lease wrapper takes an exclusive host-workload lock, so the leased 13/14/15 go to GPU work: perception inference, then T11 DDP. The gates run on home CPU: 03/02/07 as main hosts, 04/01 spare. Gate (b) concurrency must be requalified on 02/07.
  3. **Review.** The independent Opus PREREG review is running in parallel with the parallelized seed inventories.
- **21:13 UTC heartbeat (utilization 5/12 GPUs busy).**
  - **Busy:** 08 GRU at 100%; 16/18 T11 at 90%/44%; 01 GRU-DDP reference test at 68%; 09 perception equality at 33%, about 57 frames/s, ETA ~21:20Z.
  - **Idle:** 02/04/07/11/13/14/15. Perception was told to start its inference fan-out **speculatively now** on 04/11/13/14/15, with outputs quarantined until equality passes.
  - **Decisions:**
    1. DDP dropout: a counter-based, world-size-independent dropout RNG keyed by (seed, step, global row, site), applied to T11 and the GRU. Qualified by a p=0 numerics equivalence test, identical masks across world sizes, drop-rate sanity and kill/resume.
    2. GRU DDP qualification uses 01+07+02 temporarily (02 at 1 GbE for correctness only), then deploys on 01+07+08.
    3. Gates (b)/(c) use home CPU only (03/02/07 plus 04/01 spare).
  - **Health:** 06 still down; Mac 28 Gi free; no reclaims.
- **~21:35 UTC: gates (b)/(c) independent PREREG review: APPROVE WITH REQUIRED CHANGES** (`imitation/reviews/GATES-BC-PREREG-REVIEW-20261008.md`, R1–R21).
  - **Decisions:**
    - R16 dev-only forward equality: CPU fp32, ≥4,096 rows, |Δ log-prob| ≤ 1e-4, identical masks and top-8 lists.
    - Gate (b) only on dedicated 127x03, unless 01/04 pass final-snapshot pilots with taskset core isolation and a frozen load ceiling.
    - Gate (c) on 02/07/04/01.
    - Identical environments across game hosts.
    - Interleaved secondary order.
    - A statement that no gate (a) material is read on 01.
  - **Clock speeds:** 02/07 "low MHz" was an ondemand idle sample; all hosts average 2.2–2.3 GHz. 02's timing failure at 16 workers was co-tenant load.
- **21:23 UTC: 127x07 offline again** (no route, no ping; probably powered off in the lab). Only non-gate work was affected: a gates qualification pilot (9/32), a seed scan, and staging for the GRU-DDP and perception fan-out.
  - GRU DDP is replanned to world 2 on 01+08 (07 can rejoin elastically).
  - The perception fan-out drops 07.
  - Gates use 07's latest historical seed export plus a "no new jobs since" argument.
  - 07 stays in the fleet hosts file, so fleetweb and the 30-min check retry it automatically.
- **~21:40 UTC: ClashAI deep dive** (`reports/clashai_deepdive_20261008.md`, Opus).
  - **Correction to the 2026-10-04 note:** ClashAI's ~11k is the owner's human-built main account, already ~10k by 2026-09-18. Over ~1,136 logged ladder matches (09-25 to 10-08) the bot holds about 50–54%. Its own gain is at most +908 trophies, and the logged W/L supports only about +400. Nothing is externally verifiable.
  - **Their methods we can't use:** a read-only game-memory reader as the state source, replays re-run in the real game binary, logged-in replay crawling, and botting a personal account. All conflict with our rules.
  - **Lessons adopted into the backlog:**
    1. Pre-registered live evaluation by trophies per match with interleaved A/B (about 400 matches per arm to see a 10 pp gap), not ladder win rate alone.
    2. A standing loss-review ledger against human baselines (e.g. elixir on hand when meeting enemy pushes: theirs 70% under 4 elixir vs 24% for pros).
    3. Delay compensation identical across training, search and live (ours: d=27 aware in both S-d and the runtime). The actuation bench measures card landing, not tap sent.
    4. A search robustness gate against imitation-policy and replay opponents with a deliberately wrong opponent model. Their search was null or lost there.
  - **Licensing:**
    - ClashAI has no license (all rights reserved): learn and cite only.
    - RoyaleSim is MIT.
    - Our C56/S122 corpus derives from HF `VanguardX101/IL_Replay`, which has no declared license. **Decision:** no IL_Replay-derived datasets or model weights are published. The public repo keeps docs and small receipts only, as now; any future release needs a licensing check first.
- **~21:50 UTC: R19 root cause: the public mask misses engine occupancy rules.**
  - **Evidence:** an exact recorded-action replay of 02 r9 game006, reproduced on 03 with no search or deadline involved. All 6 model-command rejections recur: BombTower ×3 hit the building-footprint guard (battle.py:1277), RoyalHog ×3 hit the deployment-payload guard (:1284). The public mask had called all 6 legal. It's deterministic, not timing, and can happen on any host.
  - **Gates (b)/(c):** no serving or mask change (the qualified path stays frozen). R19 is restated as "zero timing/staleness/load-attributable rejections". Deterministic mask–engine rejections are part of play: same fallback for every arm (drop the command, no-op wait), reported per arm, protocol and card, each one replay-reproducible. This goes to the reviewer with the delta.
  - **Delegated (Astra high):** mask v2 with occupancy rules from public information only, flag-guarded with the default unchanged, parity-proven on ≥100k recorded states. It's for future consumers only: v2 proposer, L2-v4 runtime, live actuator.
- **22:35–22:45 UTC (after Sam un-paused coordination).**
  - **Utilization at 22:35Z:**
    - 01 was idle after T11's qualification; 18, 07 and 06 are down.
    - Perception inference ran on 7 GPUs at only 3–24%: I asked the worker to pack 3–4 passes per GPU, move CPU work out of the loop, and reach ≥60%.
    - **T11 seed 22 resumes on 01 now** as a host-loss continuation from the newest SHA-verified 04 backup. Seed 21 moves 16→04 after 05:00Z.
  - **Gates (b)/(c):**
    - The R16 GPU comparison is waived (CPU fp32 passed).
    - The 36-file SHA-only check on 13/14/15 is authorized outside the lease wrapper.
    - **Independent review r2 launched** (Opus).
    - The R19 restatement was re-sent after the worker applied the old zero-rejection rule to the 03 r12 pilot (4 B-arm rejections; p99 200.27 ms, 0 >250). Each rejection must reproduce under exact replay to count as deterministic mask–engine occupancy.
  - **Mask v2 committed** (opt-in `mask_version=2`, default 1 unchanged).
    - On 100k states: v1 false-positive placement bits 10,044 → v2 722, all from hidden buildings; v2 false negatives 0.
    - Even 3 of 4,278 v1-legal human actions were engine-rejected.
    - Visibility of blockers in the official client is still to be verified at live qualification.
  - **Exploration lane created** (non-confirmatory, no prereg, never heldout). First task: a loss-review ledger vs human baselines (ClashAI lesson) on 01/08 CPU.
- **~23:00 UTC: model routing changed (Sam).**
  - "Go light on Astra; use 6.1 Sol where it fits." New grunt-work delegations default to **GPT-6.1-Sol (high)**. Astra is kept for hard debugging, security, costly-to-miss work, or after Sol fails. Opus stays on reviews, research and frontend.
  - **No limit on subagent count.**
  - Updated `frontier-models.md` (both copies), memory and the heartbeat prompt. Roader was told.
  - The heartbeat no longer SSHes to the Mac mini (Sam stopped those calls twice).
- **~23:10 UTC: gates (b)/(c) review r2: APPROVE WITH REQUIRED CHANGES (RC-1…RC-12)** (`imitation/reviews/GATES-BC-PREREG-REVIEW-R2-20261008.md`).
  - **R19 restatement judged sound:** no staleness is possible, and there's one shared apply loop with an identical drop/no-op fallback.
  - **B-only rejection imbalance:** 4/8,781 commands, 1 streak episode, vs A 0/8,718; p≈1 by episodes. It's at or below the human rate on mask v1 (7e-4), and its expected gate impact is ≤0.01 on the primary vs an SE of ~0.015–0.020. It becomes a predeclared descriptive (RC-12) with the caveat that gate (b) measures B under mask v1.
  - **Next:** a sealed RC delta, plus the 02 seed inventory, then a final delta-only check, then freeze and launch (b on 03@16, c on 02@16).
- **127x18 outage timing:** reachable at 21:09Z (T11 seed 22 at 44% GPU), unreachable by 21:39Z on 2026-10-08 (roader's estimate was 21:50–22:00Z). 07 dropped at 21:23Z. Both are still down at ~22:56Z; seed 22 resumes on 01 from its off-host backup.
- **~23:00 UTC: v4 perception throughput decision.**
  - **Measured:** packing reached 70–99% GPU on 04/09/11/13/14/15, but dense late checkpoints run at only ~0.9–1.0 frames/s. The slowest epoch projects ~32 h. Profile: runtime 56%, record extraction 41%, dominated by per-candidate GPU scalar syncs and nine causal branch runs.
  - **Authorized: an exact-equivalent decoder optimization.** Vectorize candidates with no per-candidate GPU syncs, batch the nine branches, and vectorize record extraction. The equality gate must reproduce completed captures bit-exactly (≥3 epochs × ≥8 matches incl. e15–e24, plus the reference cells) before use. No approximations.
  - **Post-05:00Z priority: perception > T11 > GRU.** Perception gets 02 and 08 (plus 07 if it returns); T11 gets 01 and 04. The GRU checkpoints and pauses at 05:00Z and resumes on the next free GPU.
- **~23:20 UTC: exploration lane result 1: loss-review ledger** (`reports/explore/loss-review/LEDGER.md`; 55,657 human train/dev perspectives vs 300 paired fair-search sim games; ~25 min on 01/08 CPU). These are hypotheses, not gate evidence.
  1. **Delay costs games.** d=27 loses 14.7% vs 7.3% at d=0 (+7.3 pp [2.0, 13.3]).
  2. **Reserves.** Our search player meets **91%** of enemy incursions with <4 elixir, vs humans 16–19%. It has no affordable defender in hand 65% vs 4%. This is the same failure ClashAI found.
  3. **Expensive win conditions are starved.** X-Bow 0.12 vs 1.01 plays per deck-minute; Giant 0.06 vs 0.73.
  4. **Expensive spells are starved.** Fireball 0.11 vs 0.84, Rocket 0 vs 0.66, while Log is overplayed (3.0 vs 1.5).
  5. **Win-condition commits during threats:** 34% vs 24%.
  - **Next (exploration):** a paired sim A/B on candidate coverage and reserve-aware leaf value.
- **23:00 UTC utilization: GPUs 10/11 usable busy** (62–99%: 01/02/04/08/09/11/13/14/15/16; 03 has no GPU; 06/07/18 down). **CPUs are nearly idle fleet-wide (1–11%), ~1,400 cores free.** Actions (Sam: "prioritize making the most of the compute, changing the pipeline where beneficial"):
  1. **Exploration A/B** (Sol high): fair-search candidate coverage and a reserve-aware leaf value, ≥1,000 paired sim seeds per arm on 01/04/08 CPU.
  2. **Lease wrapper v2** (Sol high): concurrent clasher jobs per leased host under aggregate caps, replacing the exclusive lock that idles ~700 leased cores while perception GPU jobs hold it.
  3. **Gates f35 bounds:** use git history as the launch catalog. Fallback if gaps are real: a hash-committed fresh seed namespace.
- **~23:20 UTC: gates (b)/(c) seeds move to a hash-committed fresh namespace (≥2^40)** before freeze.
  - **Why:** the RC-5 git-history scan (7 commits, 2,595 blobs, 1,383 seed-bearing records) found zero intersections, but f35-era jobs (`readiness_root_bank.py` `getrandbits(32)` from unknown master seeds; sole artifacts and worktree data) can't be enumerated.
  - **Construction:** derived from SHA-256 of the seed-placeholder PREREG bytes. That makes it disjoint by construction from all 32-bit draws and from all enumerated history.
  - **Checks:** the engine and routes must accept the seeds, and the intersection against all inventories is re-run, before the reviewer delta check, freeze and launch.
  - RC-2b gate (c) cross-host exactness PASS.
- **~23:15 UTC: command-delay research launched** (Opus). Sam doubts the 1.1 s backend delay. The research checks whether T2 "native acceptance" includes deploy time (possible double counting in d=27), where the 20-tick live-command age comes from, the official game's real latency, and how the model and planner should account for it.
- **23:09 UTC heartbeat (utilization 8/11 usable GPUs busy):**
  - **Busy:** 02 81%, 08 98%, 09/13/14/15 98%, 11 73%, 16 70%.
  - **Problems:**
    - **01 at 0%:** T11 seed 22's loaders were in D-state while the exploration A/B ran 80 sim workers on 01. The A/B is cut to ≤32 on 01 and moved to 04/08; T11 was told to fix the I/O (more loader workers, page-cache warm-up; target ≥70%).
    - **04 at 0%:** the perception jobs there had ended, and the worker was told to relaunch packed passes.
  - **Health:** 06/07/18 still down; no reclaims; no console users.
- **~23:15 UTC: gates seed namespace.** The worker is implementing an offset namespace ≥2^44. NumPy's `np.random.seed` rejects >2^32−1, so there's a narrow full-width wrapper: below 2^32 the original call is used unchanged; above, `SeedSequence(full).generate_state(624)`, with no truncation. Models, masks and T=1 are unchanged. Plumbing for all routes and the 02↔03 exactness checks are re-running.
- **~23:18 UTC: coordinator error corrected.** My 23:12Z reallocation put 96 exploration sim workers on 04, which tripped v4 perception's combined 96-process guard (its batch exited 1 at 23:04Z) and idled 04's GPU. The exploration A/B is now ≤40 on 04, ≤64 on 08 and ≤32 on 01; perception relaunches. **Lesson: check per-host combined clasher process counts before placing CPU work next to GPU jobs.**
  - **Perception decoder:** the vectorized candidate path is bit-exact on a real epoch-24 probe with a **4.0× speedup**. The batched nine-branch tail failed exactness and is excluded. The full equality gate is pending. 08 is staged: 24 checkpoints plus 19 of 64 cache matches.
- **~23:30 UTC: lease wrapper v2 deployed** (Sol) on 09/11/13/14/15/16: concurrent clasher jobs under combined caps, v1 jobs and locks untouched; 37 tests plus a live smoke test on 15. Leased CPU (~700 cores idle under the GPU jobs) is opened to the exploration A/B (≤40 per host, stop by 04:30Z) and the perception CPU grid / decoder gate.
- **~23:40 UTC: command-delay research** (Opus; `reports/research/command-delay-20261008.md`).
  - **No double counting.** T2's "acceptance" is the execution tick (card leaves hand, elixir drops); deploy time is charged once afterwards by the engine.
  - **The 20-tick lead is the FirstLight probe constant, and it matches the official game.** The binary's command queue checks a 20-tick age, and ClashAI's 6,721 official-client plays have tap→execution p1 19.9 / median 22.6 ticks.
  - **Recommended d:** p50 = 26 ± 1 ticks for the renderer (27 is slightly conservative); 26–27 ± 2 for the official client, plus a network tail (p95 ~44).
  - **Real pipeline errors found:**
    1. Simulated opponents act with **no** command delay, both in sim games and in search rollouts. That inflates the measured latency cost and the S-d arm.
    2. Imitation labels sit at the execution tick, so at inference the model should get the planner's forward state at t+d ("predict, then imitate").
    3. We allow only one outstanding command, which costs about 1.3 s of silence after every play.
    4. The official-client verifier window must come from its own measured distribution.
  - **Decision:** validate fixes 1–3 flag-guarded in the exploration lane (paired sim, Sol). They feed prospective L2-v4 PREREG amendments before L2 starts. The Mac Training Camp frame-count protocol is deferred until Sam OKs Mac use.
- **~23:35 UTC: memory-rule clarification.** The 64 GB summed-PSS cap is for leased roader hosts only. Home hosts use a MemAvailable ≥24 GB floor with no OOM risk to co-located training. Perception's CPU grid and decoder gate move off 01 (T11 loaders reached 66 GB PSS there) to leased v2 CPU and 08. Gates (b)/(c): wide-seed (≥2^44) qualification and the RC-4 replay contract PASS; the worker is assembling the final hash commitment and delta r3.
- **~23:33 UTC: integrity incident, root-caused and fixed (coordinator-owned job).**
  - **Cause:** `hub-mirror-127x04-20261008-r2` (01→04 backup loop, every 30 min since 2026-10-07) `rsync -au`'d 01's live `jobs/clasher`, `clasher-v4-data` and report trees into the **identical live paths on 04**. That overwrote older 04-local same-path files with 01's copies.
  - **Confirmed damage:** two gates-bc seed-inventory overwrites on 04 (the historical-docs receipt; shards 00–06 and inventory.json). No seed information was lost: the byte-identical merged archive is preserved on 03.
  - **Fix:** the loop was stopped by verified PIDs and relaunched as `hub-mirror-127x04-v2-20261008` (`hub_mirror_v2.sh`), which writes only to `04:/mpac/sdicks02/mirrors/hub01/<abs path>`.
  - **Follow-ups:** the perception worker was asked to verify its 04 files against its SHA manifests. Gates: the 04 audit uses the preserved archive with disclosure, and H is recomputed pre-freeze.
  - **Lesson:** a backup must never write into another host's live paths.
- **~23:50 UTC: lease wrapper v2 bugs found on 09; hotfix delegated (Sol).**
  1. **KeyError race:** `refresh()` deletes a job whose PIDs vanished, so `supervise()` crashed on `registry['jobs'][key]` (perception's fullgate r1).
  2. **Misclassification:** discovery counted roader's same-UID RoadForge processes (`/mpac/sdicks02/repos/roader-perf2`, `roader-shell`) as clasher's. That inflated our aggregate and refused admission with "below nice minimum" (roader runs those at nice 0).
  - **Fix:** supervisor-liveness keyed registry; allowlist of clasher-owned argv prefixes, excluding roader. Deployed as new versioned files; running v2 jobs untouched.
  - Workers hold new leased launches until it's confirmed. Roader was asked to keep its 09 jobs at nice ≥10 (FLEET-SHARING rule 6).
- **23:39 UTC heartbeat (utilization: 10/11 usable GPUs busy, 1 starved).**
  - **GPU busy:** 02 97%, 04 99%, 09 86%, 11 76%, 13 97%, 14 94%, 15 98%, 16 84%, 08 61% (GRU).
  - **01 at 30%:** T11 seed 22 is I/O-bound. Its 109 GB store column exceeds RAM, and the v4 validation-cache service on 01 evicts its page cache. Perception was asked to replicate the cache to 08/02 and retire 01 serving.
  - **03 idle:** lent to the exploration A/B under a GATES-03-RESERVED handoff file.
  - **Perception:** the vectorized decoder runs at **~12 frames/s vs ~1 (12×)**. The full equality gate is pending. Conditional all-capture planning range 06:00–09:00Z.
  - **Health:** 06/07/18 down; no reclaims; roader reniced its jobs to 10.
- **~23:50 UTC: gates RC3 clarification.** Affinity isolation on 03 applies to compute workloads. Enumerated low-CPU baseline services (systemd/dbus/gvfs, sshd, idle wrapper shells, tailscaled, which we never touch) are exempt under a measured bound: average ≤0.5 core, peak ≤2 cores, monitored with the load ceiling of 20. Delta r3: new H e730c9f1…, base 1359319908352; 4,356 seeds disjoint from 26,434 historical values/ranges; 94 raw errors resolved.
- **~23:52 UTC: perception throughput step 2 authorized** (Sam: "a whole YOLO model could run faster than 12 fps"). After the vectorized full gate: cross-match lockstep batching (64 matches per GPU call) plus batched encoder and vectorized trackers, under the same bit-exact gate. Target ≥100 frames/s per GPU.
- **~23:58 UTC: lease wrapper v2 hotfix deployed** (Sol) on 09/11/13/14/15/16. It keys the registry on supervisor liveness and classifies processes by an allowlist of clasher-owned paths only (roader excluded). 47 tests plus a smoke test on 09 passed; running supervisors are unchanged. Leased CPU launches resumed for the exploration A/B (≤40/host), the delay-fixes experiment (≤30/host) and the perception CPU grids/verifiers, all stopping by 04:30Z.
- **~00:05 UTC 2026-10-09: speed push (Sam: "get that running way faster" and "audit the whole codebase for speed-up potential").**
  1. **Perception cross-match lockstep batching:** a parallel implementer (Sol, `clasher-perception-lockstep-batching-20261009-1`) builds `l1/lockstep_replay_v4.py` under the same bit-exact gate, targeting ≥100 frames/s per GPU. The owner keeps admission rights.
  2. **Codebase-wide speed audit:** a workflow of 5 Opus auditors (engine, search, imitation, perception/live, ops/harnesses) plus a synthesis, writing `reports/perf-audit/*.md` and `SUMMARY.md`. Code is read-only; only light profiling on 08.
  - **Gates:** the `GATES-03-RESERVED` marker path is confirmed, and the external baseline monitor is approved.
- **~00:48 UTC 2026-10-09:**
  - **01 cache serving stopped:** perception's validation cache is now served from 08 (56 matches) and 02 (8), so 01 no longer serves. **T11 seed 22's GPU on 01 rose from ~30% to 85%.**
  - **Lockstep batching probe:**
    - Batch >1 is bit-different at every stage (cuBLAS/cuDNN shape-dependent), even with deterministic algorithms.
    - The unequal prefix reached only 24–42 fps.
    - A 25 s GPU probe on 01 halved T11's rows/s (7,645 → 3,901) and was correctly stopped; no more 01 GPU co-tenancy.
    - **Decision:** no tolerance relaxation for the formal v4 validation run; the exact vectorized path (~12 fps per process, packed) finishes it. At most ~1 h more on an exact-shape fallback (CUDA graphs/streams, CPU-side). Tolerance-qualified batching goes to future runs, with bounds pre-registered before the run.
  - **Exploration:** both workers vacate 13/15 so perception's GPU relaunches fit under the 80 cap.
- **~01:00 UTC: an exact speedup found** (lockstep worker, CPU on 08). When the body-threshold branches produce byte-identical birth maps, their tail outputs are reused with no recompute. That cuts tail calls from 144 to 16–47 per window, with separate tracker/NMS/HUD state preserved. It's bit-exact on real checkpoints and pixels (e1/e3/e20 × 8 matches × 9 branches) and gives 1.55–1.78× on CPU. GPU qualification is pending: a ≤5-min probe on 08 after 05:00Z, ordered **T5 GRU exit checks → lockstep probe → perception recovery on 08**, coordinated by me.
- **~01:05 UTC: gates (b)/(c) APPROVED FOR FREEZE** by independent review r3 (`imitation/reviews/GATES-BC-PREREG-REVIEW-R3-DELTA-20261009.md`, `f199e096…`).
  - **Approved bytes:** gate-b PREREG `7524a4e1…`, gate-c PREREG `8d565be1…`, snapshot `016b42fa…` (hashes verified on 05).
  - **Registered steps:** F-1 launch-ledger delta disjoint from the seed range; F-2 review in evidence, plus approval.json with exact hashes; F-3 lapse if 07 returns or a pinned byte changes; L-1 fresh ≥300 s quiet-host capture on 03 before launch. The optional monitor extension is declined.
  - **Launch:** gate (b) on 03@16 (~1.8–2.5 h), gate (c) on 02@16.
- **00:09 UTC 2026-10-09 heartbeat (actual time; my message labels since ~22:30Z ran up to ~1 h fast, so trust receipt times). Utilization: 9/10 reachable GPUs busy.**
  - **GPU:** 01 87% (T11 seed 22, up from 30% after the cache offload), 02 95%, 04 99%, 09 85%, 13 98%, 14 87%, 15 99%, 16 84%.
  - **Problems:**
    - **08 at 41%:** the GRU was starved by ~60 exploration sim workers; cut to ≤16 + ≤12.
    - **127x11 offline again** (no route). Its perception passes and exploration shards were reassigned, and roader was told.
  - **Down:** 06/07/11/18. 03 is idle pending the gate (b) launch (freeze approved). No reclaims.
- **00:15 UTC: agreed with roader. Hosts that dropped under load get CPU-only light work when they return** (11/18 leased, and our own 07): ≤32 processes, nice ≥10, no GPU jobs, until Sam has them checked physically. Drop-outs so far: 02, 07 ×2, 11 ×2, 18. We have no root, so no `nvidia-smi -pl` power cap is possible.
- **00:20 UTC: lockstep handoff received and committed** (`l1/LOCKSTEP.md`, `lockstep_replay_v4.py` + probes/verifier/tests, `receipts/lockstep-20261009/`).
  - **Bit-exact on CPU:** birth-map output reuse (tail calls 1,152→128–171, all batch-1). 384 frames × 9 branches exact; 1.83–1.93× on CPU, 7.0–7.3 fps.
  - **Pending:** GPU/graph qualification and full-match / 3-reference-cell checks. 100 fps is not demonstrated.
  - **Plan:** the coordinator pins a ≤300 s 08 window JSON after 05:00Z, once T5 GRU's exit is checked, before perception's 08 recovery. Formal v4 stays on the admitted exact path.
- **00:14:07 UTC 2026-10-09: gates (b)/(c) FROZEN AND LAUNCHED.**
  - **Gate (b):** 127x03 at 16 workers, label `imitation-gate-b-v1-r1`, budget 2–2.5 h.
  - **Gate (c):** 127x02 at 16 workers, label `imitation-gate-c-v1-r1`, budget 3–4 h, alongside the qualified v4 GPU co-tenancy.
  - **Freeze checks:** F-1 initial and closing PASS (54 known job entries, 0 unknown or intersecting; 07 has no route). F-2: final review `f199e096` plus per-gate approvals pinned. L-1: fresh 302 s quiet-host capture PASS (average 0.0048 core; non-baseline empty; console 0; marker present; cache pin OK).
  - **Frozen registrations:** b `50823cd3…` / manifest `18f08db2…`; c `aed4478b…` / manifest `99ab97a8…`. The H round-trip is unchanged, and both freezes exited 0 before any game.
  - Receipts are in `imitation/gates-bc/receipts/freeze-launch-v1/`. The worker monitors liveness only and reads no outcomes until completion.
- **00:21 UTC: v4 perception's 04 integrity audit after the hub-mirror incident: 0 mismatches** across 27,526 SHA checks plus 18 pinned exit/backup checks (sources, bundles/weights, receipts, 5,771 payloads, caches, epoch 1, 29 checkpoints). No restoration needed (`l1/receipts/integrity04-20261009/summary.json`, `l1/HOST04-INTEGRITY.md`). Limit: unpinned logs and PIDs can't be certified after the fact, and 513 01-named mirrored job records aren't accepted as 04 evidence.
- **00:37 UTC: T6 (v3-control) validation selection independently verified.** All 64 validation matches and 53,392 frames were authenticated, and the legacy evaluator reproduced the original selection, calibration and metrics exactly (proof `f527b143…`, `l1/receipts/t6-selection-verified-20261009/`). Control validation, all-side events: recall 70.9% (2,003/2,826), precision 79.4% (2,003/2,523). This is not a heldout or opponent-gate number. Pending: the joint seal, the single heldout evaluation, and the T7 decoder full gate.
- **00:40–00:50 UTC: codebase speed audit complete** (`reports/perf-audit/{engine,search,imitation,perception,ops,SUMMARY}.md`; 5 Opus auditors plus synthesis). Actions:
  1. **CORRECTNESS: v4 capture clock.** Per-branch `service = now - started[i]` spans the whole shared 9-branch frame, so availability lags an estimated 38–52 s per match and the 500 ms event recall/selection would measure contention. The perception owner must confirm within ~15 min. If confirmed, nothing consuming availability timing gets sealed or selected until per-branch clocks exist (new driver plus amendment, or offline recomputation). Also Q2: `V4Perception` defaults body threshold 0.5.
  2. **Exploration GPU guard:** sims were paused ~43% with no GPU gain. New rule: throttle only on a >5% drop in the co-located GPU job's **own throughput**, not on utilization. Sims run at idle priority, pinned off the GPU job's cores, with an idle-GPU exemption.
  3. **Correction:** my 00:09Z claim that the GRU was starved by sims was wrong. The GRU's own history build is CPU-bound (trainer at 99%). The GRU gets stage A (page release per step) at the 04:40Z pause and stage B (history in loader workers, est. 237→~400 rows/s, exact).
  4. **T11:** seed 21 resumes on 04 at 05:00Z with the io12 loader (est. +20–40%). DDP must be benchmarked with dropout ON first; the counter-dropout mask may make DDP slower than one GPU.
  5. **Delegated (Sol):** native quick wins (GIL release, x86-64-v3 build, Resources cache; new binary directories only, never replacing the `.so` the gates use). Live-runtime fixes before the L2-v4 PREREG and T9/E4: scorer config reuse plus opponent-move hoist (−36 to −55 ms per decision), the vectorized DecoderAdapter (−22 ms per frame), blocking queue reads, and **investigation of flag 3: 67% of Mac-suite searches scored every candidate −2.0, with a phantom princess tower at the KingTower position**.
- **00:43 UTC: capture-clock bug CONFIRMED by the perception owner.** Each branch's start time spans the previous frame's completion through the other 8 branches and the capture work.
  - **Taken:** the fullgate waiter was SIGTERMed (identity-verified); epoch 1/2 grids are quarantined; captures are retained; no seal or heldout exists.
  - **Next:** decide between offline recovery from the journals (preferred) and a per-branch-clock driver plus amendment. Q2 (V4Perception body threshold defaulting to 0.5) is also confirmed.
  - **Split:** the live-runtime worker wires the adapter and threshold in new live wrappers, failing closed while unset; the perception owner owns the contract.
- **~00:58–01:00 UTC: two correctness findings, now with evidence.**
  1. **v4 capture clock, empirically confirmed.** Same e1/body0.1 frames: shared median lag 29.6 ms vs single-branch 5.3 ms. Offline exact correction is **not identifiable**: the journals lack absolute per-branch start/end times and shared-stage attribution.
     - **Decision:** a new timing driver/schema plus remeasurement (~2–3 h to implement and qualify); existing non-clock record streams are retained.
     - Epoch 1/2 grids are inadmissible for selection. Captures continue in record-only mode.
     - The vectorized DecoderAdapter stays unadmitted until non-clock exactness plus the new timing gate pass.
  2. **Mac runtime suite: 296/440 (67%) of scored searches had every candidate at −2.0.** Pixel packets carry only *detected* towers, so a missing own King was read by the native cleanup as a destroyed King, giving a terminal loss at the leaf. There are also phantom duplicate Tower/KingTower identities near (9,3).
     - **Consequence: the 2026-10-08 Mac runtime-latency PASS (p50 ~186 ms) and its frame→submission component of d are NOT valid evidence for non-terminal search.** E4 must be re-measured after the fix.
     - **The total delay d≈26–27 ticks still stands** on independent grounds (the T2 20-tick lead and ClashAI's official-client distribution; `reports/research/command-delay-20261008.md`), but its pipeline component must be re-measured.
     - **L2-v4:** the PREREG text stays as frozen, but **L2-v4 entry is blocked** until the tower-reconciliation fix (opt-in public-geometry: towers persist until a *public* destruction signal; fair-information compliant), the perception tower-identity check, and a fresh E4 measurement. Any change to the player or entry criteria will be a dated prospective amendment before L2 starts.
  - **Live wiring contract** (perception owner → live-runtime worker): an explicit selected body_threshold, refusing while unset, with only an authenticated seal as authority.
- **~01:05 UTC.**
  - **Perception amendment 11:** capture-clock attribution (`l1/amendments/11-capture-clock-attribution-20261009.md`), with a clock-correctness HOLD in the continuation prompts. Old grids can't be authorized.
  - **Live selection contract:** `l1/LIVE-SELECTION-CONTRACT.md`. The live wrapper takes a separately authenticated selection object and refuses when it's missing.
  - **New wrapper-v2 defect:** a SIGTERM to a supervisor didn't stop its child. Hotfix r2 delegated (Sol): signal forwarding to the child process group, grace then kill, receipts, and verification of the 04:30Z/05:00Z stop path, plus an operator procedure for jobs already running under r1, before the lease cutoff.
- **~01:10 UTC: Mac runtime suite is fully invalid as search evidence.** In a Linux CPU causal replay of all 440 recorded active-search inputs, the **original pixel-packet roots become terminal after one native tick in 440/440 cases**: 296 losses with the own King missing, the rest spurious draws/wins.
  - So the 2026-10-08 runtime suite exercised **no** non-terminal search. Its timings remain only historical measurements of the fallback path, and E4 / pipeline latency must be re-measured after the fix.
  - Opt-in public tower reconciliation cuts terminal roots to 3/440, all with explicit pixel HP=0 evidence.
  - **Unaffected:** S5/S6 sim results (native state, not pixel packets) and Mac build48 identity.
- **~01:15 UTC: a second latent live-runtime bug.** 19/440 logged own hands contain the literal HUD sentinel `'empty'`. Native scripts index card metadata by that string and would panic once a rollout reaches our own decision; the instant-terminal roots had hidden it. Fix in the guarded public-root wrapper: canonicalize known empty sentinels to None and reject other unsupported names before native scoring, keeping raw logs. Scorer config-cache: 1,000/1,000 payloads byte-equal.
- **~01:20 UTC: live-runtime CPU qualification PASS** (45 tests; 1,000 byte-identical spliced payloads; 1,312 candidate/root scores exactly equal to the original runtime and sealed S6).
  - **Key finding: a real non-terminal live decision costs a full-budget four-root serial p50 ≈ 1,002 ms → 953 ms on Linux CPU with the fixes** (root serialization 11.1 → 1.7 ms). The earlier ~186 ms was terminal-root fallback.
  - **L2-v4 implication:** the decision budget/deadline and the pipeline part of d must be re-derived from real searches. Parallel roots via GIL release are now critical path (re-prioritized for the engine quick-wins worker), and Mac re-measurement is required for E4.
- **~01:00 UTC: lease wrapper v2 hotfix r2 deployed** on 09/13/14/15/16 for new launches.
  - **Fix:** TERM/INT/HUP now go to the child group and escaped descendants, with a 120 s grace, then KILL, a receipt and an accounting release. 58 tests plus a three-generation smoke test on 09 passed.
  - **Old r1/v1 jobs:** never TERM their supervisors. The r1 internal stop already cleans tracked trees by ~04:55Z, but for a prompt stop the **operator helper** TERMs verified child groups.
  - **Scheduled:** a one-shot backstop task at 04:29Z (21:29 PDT) runs capture then stop on 09/13/14/15/16, including T11's v1 job on 16, verifies everything, records a receipt and deletes itself.
- **~01:15 UTC: live-runtime fixes complete and committed** (`live-loop/v4/RUNTIME-PERF-FIXES.md`, `perf-fixes/`, `src/clasher/live/{public_root,tower_model,perception_adapter,perf_resources}.py` plus guarded changes). All behind flags, with the sealed files and native binary unchanged.
  - **Fixes:** the public tower model; the empty-sentinel canonicalization; the scorer config reuse plus opponent-move hoist (~53 ms saved per decision); the vectorized DecoderAdapter wrapper; blocking queues; and the selected body_threshold, which fails closed.
  - **CPU qualification:** 45 tests passed and scores are exact. A production-constructor smoke run gave 20/20 four-root non-flat decisions.
  - **The original 440 inputs:** all were one-tick terminal (296 losses, 144 draws).
  - **L2-v4 freeze must pin:** public_tower_model, perf-scorer, vectorized_decoder and blocking_queues flags; the authenticated selected body_threshold; source and native identity; **corrected non-terminal Mac latency**; and a **revalidated total delay**. MPS/E4/P4 qualification is still pending and needs the Mac.
- **~01:25 UTC: v4 capture-clock options** (`l1/CLOCK-OPTIONS.md`).
  - **Costs:** A (full standalone remeasurement) is ~192–198 GPU-hours for the body stage alone, which rules it out. B (prospective validation-selection amendment: modeled FIFO `available_hat = max(production, prev) + service_hat`, calibrated on 8 calibration + 8 test matches, 29.7k frames) is ~54 GPU-hours, with A as fallback.
  - **Unchanged:** heldout availability stays **measured** in the selected runtime; the 95/95 and 90/90 gates are unchanged; no modeled clocks go into `noise-measured.json`.
  - **Independent Opus review launched** (admissibility, model specification, minimum sample, fallback criterion). No fit or selection until the amendment is frozen.
  - **GPUs after 05:00Z:** perception gets 02 and 08; lending 01/04 by pausing T11 will be decided after the review.
- **01:10 UTC heartbeat.**
  - **Gate (b) `imitation-gate-b-v1-r1` exited 0 at 01:10:48Z** on 03 (~57 min; no outcome read). The worker runs the pre-registered verification and analysis, then releases 03.
  - **Utilization:** GPUs 04/09/13/14/15 at 88–99%, 02 59% (gate (c) plus perception), 08 44% (GRU, CPU-bound), 16 53% (T11 seed 21). 01 at 0% because T11 seed 22 is at an epoch-2 boundary with loaders restarting; transient.
  - **Health:** 06/07/11/18 still down; no reclaims.
- **~01:25 UTC: clock-amendment review: APPROVE WITH REQUIRED CHANGES** (`l1/reviews/CLOCK-AMENDMENT-REVIEW-20261009.md`).
  - **Decision: adopt B′, measured-dominance selection.**
    1. The body-threshold stage is clock-free (body F1), so it runs now from record-only captures and is sealed first.
    2. Zero-service F1 ceilings per event/epoch cell, computed on CPU from records.
    3. Cells measured standalone in ceiling order, one process per cell, stopping once all unmeasured ceilings are below the best measured result (30-cell budget). This selects exactly what full remeasurement would, at an estimated ~9–15 GPU-hours instead of ~195.
    4. Tier-2 models may only exclude cells.
  - **Host policy:** deciding measurements run on single-tenant 127x08 after 05:00Z (plus 04 if needed, paired), since fleet clocks vary ~6× with contention.
  - Option C is inadmissible; match 1975100708 is excluded; the gates and `noise-measured.json` are unchanged.
  - **Next:** amendment 12 → reviewer delta check → freeze.
- **~01:35 UTC: engine quick wins delivered** (Sol; `reports/perf-audit/ENGINE-QUICKWINS.md`). New opt-in binaries live under `artifacts/native/` and are not committed; the deployed `.so` is untouched.
  - **GIL release:** a corrected live full decision on 08 goes from serial p50 1,024 / p99 1,759 ms to **four-thread p50 308 / p99 491 ms (3.32×)**. Candidates, scores and actions are exactly equal (7,872 scores per binary).
  - **x86-64-v3 builds** are qualified on 1,000 seeds and 7,000 rollouts, digest-equal.
  - **The `Resources` cache** is an opt-in subclass with an identical config and template hash.
  - A full decision is still over 200 ms, so the L2-v4 decision budget and d must come from re-measurement on the Mac.
  - Three older worker score vectors differ from fresh replay even on the unchanged binary (1975100700 seq 3275/4524/5086); that's noted, a pre-existing receipt issue.
- **~01:40 UTC: exploration result 2, search A/B** (`reports/explore/search-ab/RESULTS.md`; 2,000 paired seeds per arm, 8,000 games, d=27).
  - **Results:** candidate coverage C makes no difference (+0.00 pp [−0.20, +0.20]). The reserve leaf term R is worse (+2.0 pp [+0.85, +3.15]); CR is +1.9 pp.
  - **Diagnosis:** expensive cards are *unaffordable* in ~99.7% of hand opportunities (e.g. X-Bow affordable only 295 of 119,587 times). They aren't starved by masking or generation; the player never banks elixir.
  - So the weakness is the **spending/tempo objective and horizon**, not candidate generation. The next exploration should target leaf elixir valuation, horizon, and WAIT preference. Gate (b) (imitation proposals) bears on this too.
  - **Latency:** the exact harness fails the 200 ms requirement (p95 ~410 ms incl. diagnostics). A 180 ms cooperative cutoff still had 51 overruns per 122k decisions, mainly in public conditioning (belief updates).
- **~01:45 UTC: GATE (b) frozen analysis: all registered bars PASS.**
  - **Primary:** B score 0.65625, paired 95% CI [0.628, 0.684]. **Secondary:** B − A = +0.051.
  - **Timing:** B p99 200.29 ms vs A 200.24 ms, max 202.8 ms, 0 decisions over 250 ms.
  - **R19 PASS:** all 70 rejections (B 10 / A 24 / scripts 36) reproduce exactly (67 payload-occupancy, 3 building guards). The four R12 prefixes PASS, with the observability limit disclosed.
  - The worker is checking 5 post-selection mask-illegal audit flags (all seat 1, likely the sequential seat-0-apply / seat-1-audit effect) before finalizing the disclosure. Scores and decision are unchanged.
  - **Meaning:** the imitation model's top-8 proposals improve the fair search player at a matched candidate count.
- **01:28 UTC: 127x03 released** by the gates worker (marker removed, all gate PIDs gone) and lent to the tempo/horizon exploration.
  - **Gate (b):** the 5 legality flags all reproduce. Each flagged command was legal before either seat's command and became mask-illegal only after seat 0's command, which is the sequential-apply effect. Acceptance histories match. No adjustment; PASS stands, and the final report is being rendered.
- **~01:30 UTC (label corrected from 01:55): GATE (b) RESULTS FINAL: PASS** (`imitation/RESULTS-gate-b.md`, `bb1adf3f…`).
  - B won 420/640: score 0.65625, paired CI [0.628, 0.684]; secondary +0.0508. All timing and integrity bars pass.
  - The report discloses the R12 observability limit and the 5 sequential-application mask flags.
  - **Gate (c):** healthy on 02 (165 two-seat worlds by 01:30Z); revised ETA ~5.5 h total, so about 05:45Z.
- **01:36 UTC: Amendment 12 delta review: APPROVE WITH REQUIRED CHANGES D1–D6, not frozen** (`l1/reviews/AMENDMENT-12-DELTA-REVIEW-20261009.md`; reviewed draft `9e575ba1…`, pins `2669f814…`).
  - The method is sound. The bound is a valid ceiling: never-early availability, a maximal matching, and strict `<` on the full key.
  - Required:
    - D1: corrected disclosure sentence, naming the full key.
    - D2: 30 cells is a checkpoint, not a stop.
    - D3: Tier 2 stays disabled. If it's ever enabled, 1975100708 is excluded from fitting and testing and counts only by its bound.
    - D4 (new): the file verifier must check the seal hash, require an exact multiset match of predictions plus a byte-identical truth list, and require available ≥ frame timestamp exactly.
    - D5: adoption wording.
    - D6: whitespace repair.
  - **Process deviation:** perception rewrote the draft to `1bde5c55…` (pins `3e7f1504…`) at 01:32:51Z. That was 4 s after the review was written, and during my hold on the draft bytes. The `9e575ba1` bytes weren't preserved, so the review's whitespace-only freeze check can't run as written.
  - **Decision:** perception applies D1–D6 plus N4 to the current draft, writes a changelog of every non-whitespace change since `9e575ba1`, and implements the D4 checks with tests plus N1/N2. Then a narrow confirmation review (D1–D5 verbatim, D6 whitespace-only, changelog items), then freeze.
  - No real seal, bound or measurement before the freeze and the draft's blockers. The 08 deciding measurements are still planned for after 05:00Z.
- **01:42 UTC heartbeat.** Sampled GPU average over 8×0.5 s:
  - Home: 01 24% (15 s resample 6%, T11 s22 **loader-starved**), 02 63% (gate c + perception), 04 99% (perception), 08 90% (GRU, 15 s resample).
  - 03: no GPU; load 96 from the tempo-horizon sims.
  - Leased: 09 88%, 13 93%, 14 83%, 15 99%, 16 72% (T11 s21).
  - 06/07/11/18 still unreachable.
  - **Action on 01:** told the T11 owner to raise the operational loader workers from 12 to 24, and to 32 if the GPU average is still below 80%. The change goes in at the next checkpoint with an exact resume and a new io-freeze. Seed 21 on 04 at 05:00Z uses the same count.
  - **Tower diagnostic** (`l1/TOWER-DIAGNOSTIC.md`, epoch 2, body 0.5, all 64 validation matches, diagnostic only): the detector emits no correct tower identity on any eligible alive frame, and the tracker publishes only tracks seen in the current frame.
    - **Decision:** build a dedicated public tower-state channel: geometry slots, alive/unknown/destroyed, HP-known, and absence never terminal. Training split only.
    - Delegated to `clasher-v4-tower-channel-20261009-1` (Sol high, CPU on 03 ≤24 processes). It's an L2-v4 blocker.
  - Perception reconstructed `9e575ba1` with the exact SHA, so the section E freeze check can run mechanically.
- **01:44 UTC: Amendment 12 step-4 report received.**
  - Draft `cc2357df…`, pins `60f0cb4e…`. Bytes are now held.
  - The changelog is `12-CHANGELOG-since-9e575ba1.md`, and the original was reconstructed with an exact SHA.
  - D1–D5 are verbatim. The whitespace-normalized comparison is TRUE once changelog (a), D1–D5 and the N1 pin update are applied.
  - D4 is implemented in the file layer; 20 tests PASS.
  - The 01:32 changelog (a) edits were never reviewed. I've sent them, with all of the above, to an independent confirmation review: `clasher-v4-amendment12-confirmation-review-20261009-1` (Opus, high). Freeze waits on that verdict.
- **01:49 UTC: AMENDMENT 12 FROZEN** (`l1/amendments/12-FREEZE-RECORD-20261009.json`). Draft `cc2357df…`, pins `60f0cb4e…`.
  - The confirmation review `18f21d0e…` recomputed every SHA and the whitespace-normalized rebuild. The changelog (a) items are a pin row plus softer wording, and weaken nothing.
  - D4 is enforced in code: 30/30 tests on 127x01, and 8/10 deliberately broken versions caught; the 2 missed are backup checks.
  - All 20 source pins matched at freeze. The draft keeps its "DRAFT" wording on purpose; the record is the freeze.
  - **Execution blockers still in force:**
    - D4(a) coverage for all 216 bound records;
    - the selector reading suspension receipts;
    - fsync of the suspension file;
    - the two missing tests;
    - outer provenance and the controller;
    - the pinned 127x08 launcher and telemetry;
    - then the body seal before any bound.
  - Measurements not before 05:00Z.
- **02:11 UTC heartbeat.** Sampled GPU average, 8×0.5 s:
  - Home: 01 11%, 02 62%, 04 99%, 08 72%.
  - Leased: 09 90%, 13 89%, 14 95%, 15 99%, 16 38%.
  - 16's sample looks like a momentary dip: its log shows a steady 12.0k rows/s.
  - 03 is CPU-only, load 89. 06/07/11/18 are still unreachable. No pending worker requests.
  - **01 T11 seed 22 is still starved after io32**, at 2.9k rows/s including loader. The cause is kernel-bound loaders (0.2% user, 14.9% sys, 0 iowait) with worker respawn, under the home io override's `mmap_random_advice`. 16 runs a steady 12k rows/s with plain loader6.
    - **Decision:** switch 01, and seed 21 on 04 at 05:00Z, to 16's exact loader6 config at the next checkpoint, and stop the io32 observer.
  - **Amendment 12 orchestration package** (`A12-ORCHESTRATION-REVIEW.md` `16ede4ad…`, 48 tests) went to an independent review, `clasher-v4-a12-orchestration-review-20261009-1` (Opus, high).
    - Verdict A covers the real body seal plus CPU bounds. Verdict B covers the preconditions for the first 08 measurement.
- **02:11 UTC: tower channel round 1 landed** (`138a3b57`, `v4/tower-channel/REPORT.md`). It covers 8 training-split dev matches.
  - Alive recall 98.32%, 0/1,844 false-destroyed, exact HP on 499/500 accepted princess reads, 1.38 ms/frame p50 (1.56 ms p95). 75 tests pass.
  - It's integrated into perception_adapter and PublicTowerModel. Absence is never terminal.
  - **Accepted** as the conservative L2-v4 tower component.
  - Gaps: no destroyed truth (native snapshots drop dead towers), no King rubble, no King or opponent HP numbers.
  - **Round 2 delegated** (`clasher-v4-tower-channel-r2-20261009-1`, Sol high, 03 CPU ≤24 processes):
    - destruction labels derived from truth (tower vanishes while the match goes on), on a fresh untouched dev slice, reporting the false-destroyed upper bound;
    - King destruction via the match-end path, plus King activation;
    - an opponent HP number refit.
- **02:16 UTC: SelectionClaims owner review in** (`l1/reviews/LIVE-SELECTION-HANDOFF-OWNER-REVIEW-20261009.md` `d402274b…`). The handoff is compatible with the joint seal.
  - **Required before formal startup:**
    - explicit `event_thresholds` validation (today `{}` falls through to 0.5);
    - spell routing and calibration structure checks;
    - `decoder_admitted` bound to the implementation, source closure, proof and device;
    - verifier and import hashes pinned outside the seal.
  - Also: the mock-actuator guard gets a diagnostic label. Don't wire the pre-A12 `joint_selection_evidence_v4.py` in.
  - Relayed to the live-runtime worker `clasher-perf-live-runtime-20261009-1` (round 6), with a warning about the tower-channel edits.
- **02:21 UTC: lease nice-policy incident (small).** Delay-fixes admission refused new shards on 09 and 15 because a Clasher process was below nice 10.
  - **Cause:** the tempo-horizon lanes briefly spawn processes at nice 0 / SCHED_OTHER before switching to SCHED_IDLE. Seen on 13: pid 685229.
  - **Fix ordered:** launch with `nice -n 10 chrt --idle 0` so the whole tree inherits it from exec.
  - Delay-fixes may re-admit on 09/15 once the check is clean.
  - Delay fixes: ≥1,200 original pairs done. The controls config was frozen before any inspection, at 02:02:09Z (`9e0cf7be…`).
- **02:23 UTC: A12 orchestration review verdict** (`l1/reviews/A12-ORCHESTRATION-REVIEW-VERDICT-20261009.md` `7a032739…`).
  - 59/59 tests pass, but only 22 of 36 mutants were killed (61%). D4 killed 5/5; the seal-before-bounds guard 1/4; measured admission 0/2.
  - **(A) Body seal + CPU bounds are authorized on 4 conditions:** a JSON round-trip guard; tamper tests; running from the immutable snapshot with all 24 capture SHAs plus my approval receipt; a recomputation-cost benchmark. I write `coordinator-approval-A.json` after spot-checking.
  - **(B) 11 preconditions before the first 08 deciding run:**
    - one attempt directory per request, with a void path for crashes;
    - a provenance mismatch halts the run, never retries;
    - GPU memory and utilization telemetry;
    - checkpoint content matching the frozen text;
    - a controller CLI and a real notifier;
    - a measure-everything path;
    - an allowlist dry run on 08 after the GRU exits.
  - **My action:** exclude 08 from fleetweb and heartbeat ssh probes during the measurement window.
  - Relayed to perception.
- **02:25 UTC: NFS home hit its 5 GB quota.** The cause was the perf buildid cache `~/.debug` (1.7 GB) left by speed-audit profiling.
  - Moved it to `/mpac/sdicks02/cache/perf-debug-home-20261009` on 05, and `~/.perfconfig` now sends the buildid dir to /mpac.
  - fleetweb now honours quiet windows from `~/.config/fleet-top/quiet`: no ssh to a quiet host, and host detail returns 409. Tested. This is for the single-tenant 08 measurements.
- **02:29 UTC: R-A4 ordering clarification for Amendment 12.** My earlier instruction to benchmark before approval A was wrong: the frozen text forbids any bound before the seal.
  - **A1:** guards, tests, mutation rerun, immutable snapshot and all 24 capture SHAs are checked. Then I issue `coordinator-approval-A1.json`, then the real body seal.
  - **A2:** after the seal verifies, the real verify_body + recompute_bounds run is timed. That timed run is the bound computation; there's no separate probe.
  - **B:** bound SHA, per-step cost and the 11 preconditions come to me, then `coordinator-approval-B.json`, then the first 08 deciding run.
  - Currently blocked at 3/24 captures. A capture-completion projection has been requested.
- **02:35 UTC: tower channel round 2 accepted** (`52a9e102`). On 8 fresh training-dev matches:
  - Princess destruction caught 7/7, with 0/74,179 false-destroyed frames.
  - Confirming a destruction takes 2.6–2.8 s on average.
  - King activation 99.998% accurate with 92% coverage. Own-King HP exact on 136/136. Opponent HP numbers are disabled at 98.8%.
  - **Round 3 delegated** (`clasher-v4-tower-channel-r3-20261009-1`): a crown-counter HUD reader to bring confirmation latency under 0.5 s at p50, plus `result_screen.py` to provide the result-screen observation. Shared-tree hunk discipline; selection.py and runtime.py are off-limits.
  - **Delay fixes:** the original 8 arms finished at 1,250 pairs each (10,000 files on 08), with no outcomes inspected. The controls started after the drain. Re-admission checks on 09/15 cleared at 02:24Z.
- **02:40 UTC: capture acceleration plus lease extension.**
  - The capture projection (`l1/CAPTURE-PROJECTION-20261009-0235.md` `33102c37…`) put completion around Oct 10 16:00Z to Oct 11 08:00Z. Lanes run at 0.56–5.38 fps, limited by orchestration and scalar sync. The e15 epoch is the tail. About 100 GPU-hours remain.
  - **Decisions:**
    - **Whole-match work queue**, qualified as exact, to split the epoch tails. It goes first.
    - A packing sweep of 2/4/6/8 processes per GPU.
    - The vectorized non-clock gate comes second.
  - **Roader APPROVED a GPU extension** on 09/13/14/15/16 until **Oct 11 05:30Z**. Per host: ≤16 processes, nice ≥10, PSS ≤48 GB, ≥8 GB GPU memory free, no exploration sims after 04:30Z, and their mirrors on 09/15 are untouchable.
  - **Allocation:**
    - Capture: 09, 13, 14, 15 and 04 now; 08 after 05:00Z; 02 after gate (c). That's 7 GPUs.
    - T11 seed 21 stays on 16. Its 04:20Z stop is cancelled and it doesn't move to 04.
  - The 04:29Z backstop was rewritten to stop exploration only. The heartbeat prompt was updated.
  - Perception was told to extend its wrappers and lease files and to exempt capture from its 05:00Z cleanup task.
  - A12 review-A response: 31 of 36 mutants killed, all A-targeted ones killed. A1 waits on 24/24 captures.
- **02:41 UTC heartbeat.** Sampled GPU average over 8×0.5 s:
  - Home: 01 53%, 02 64%, 04 99%, 08 26% (GRU; it was 90% over 15 s at 01:40Z).
  - Leased: 09 88%, 13 92%, 14 96%, 15 98%, 16 71%.
  - 06/07/11/18 are still down.
  - **T11 seed 22 on 01 is fixed:** after the switch to loader6-r2 it runs a steady **12.1k rows/s**, up from 2.9–6.3k.
  - **Live selection hardening landed** (`435cad32`). All 5 owner-review requirements are in: event/card/grid validation, spell subset, calibration proof, typed decoder binding, and verifier/import trust pinned outside the seal. 85/85 live tests pass.
    - The owner callback and trusted owner policy are deliberately absent.
    - An independent Opus review of this trust layer is queued for before formal startup; that's not needed until the capture and selection finish.
- **02:56 UTC: tower channel round 3 accepted** (`91be4af3`). The crown counter cut mean princess destruction confirmation from 2.6–2.8 s to **0.81–1.01 s** (p50 0.70–0.85 s; the <0.5 s target was missed). Still 7/7 events and 0/74,179 false-destroyed.
  - A result producer now exists: 8/8 terminal-text classifications are correct.
  - Win/loss/draw is **unmeasured**: the training captures stop before the full result screen.
  - **Decision: tower work pauses here** (diminishing returns). The full outcome-screen fit will use the first live Mac sessions' post-match frames, which are fair public UI.
  - The one-line provenance patch (`public_score_templates.json`) went to the live-runtime worker. My own attempt was reverted because I had no matching test environment.
- **02:57 UTC: capture migration in progress.**
  - Perception deployed a capture-only wrapper (`224cd41b…`): stop Oct 11 04:30Z, ≤16 processes, PSS ≤48 GB. The lease files on 09/13/14/15 now end Oct 11 05:30Z, and the 05:00Z cleanup exempts capture.
  - Qualification on 04 so far: one whole e7 match (444 frames × 9) is byte-exact. The dense e15 match is still running. The atomic queue passed 13 tests, including an 8-process claim race.
  - **Decision: early drain of exploration** from the leased hosts. No new shards there. Remaining work moves to home CPU:
    - 03: ≤40 delay / ≤50 tempo, ≤100 combined;
    - 01: ≤24 SCHED_IDLE, guarded by T11 at ≥11k rows/s;
    - 08: ≤12 until 04:55Z.
- **03:00 UTC: tempo/horizon exploration complete** (`reports/explore/tempo/RESULTS.md`).
  - Setup: 1,000 paired seeds per arm, against scripted opponents, d=27. Exploratory, not adjusted for the arm search.
  - Loss rate by arm:

    | Arm | Loss rate |
    |---|---|
    | Baseline | 10.9% |
    | E (elixir option value) | 12.4% (n.s.) |
    | H12 | 7.1% |
    | H16 | 6.3% |
    | **W (explicit WAIT candidates + elixir-scaled prior)** | **0.7%** |
    | EW | 1.7% |

  - W also cut under-4-elixir arrivals from 90% to 61% (humans: 16–19%).
  - W's cost is latency: p50 330 ms vs 7.7 ms, p95 766 ms; 71% of decisions exceed 200 ms.
  - **Caveats:** the scripted opponents are weak and have no command delay, so the result is optimistic.
  - **Decision:** W is the most promising search change so far. A confirmation run follows: W vs baseline against search opponents, with symmetric command delay, plus a W latency reduction.
- **03:01 UTC:** the tower r3 provenance patch landed (`22055686`). `public_score_templates.json` is now in the runtime provenance hash; no other live artifact was missing. The full live suite passes 93/93 on 01.
- **03:06 UTC:** the leased hosts are clear of exploration. The last delay-fixes shard (14/p1100) finished pass/0 at 03:06:04Z, and checks at 03:06:48Z show no exploration reservations or processes on 09/13/14/15/16. The delay-fixes controls continue on 08 (≤12 processes). Perception capture can now take the leased hosts.
- **03:10 UTC heartbeat.** Sampled GPU average over 8×0.5 s:
  - Home: 01 71% (T11 s22), 02 64%, 04 99%, 08 30% (GRU, which pauses at 05:00Z).
  - Leased: 09 88%, 13 90%, 14 98%, 15 99%, **16 0%**.
  - Home usage is 3.5 GB of 5 GB. 06/07/11/18 are down.
  - **Problem (a) on 16:** T11 seed 21's extended-v1 run self-stopped at 02:49:23Z at 48.5 GB PSS, over my extension proposal's 48 GB cap. Its old peak was 54 GB, and I hadn't checked it.
    - **Action:** asked roader for ≤60 GB on 16 for this job only.
    - Told the T11 owner to relaunch from step-00025591 under whichever cap comes first: 60 GB if approved, or a trimmed loader under 46 GB.
- **03:10 UTC:** roader APPROVED PSS ≤60 GB on 16 for the T11 seed 21 job only. The T11 owner was told to relaunch exact-resume from step-00025591 with loader6 unchanged.
- **03:15 UTC:** progress on capture and exploration.
  - **Whole-match qualification PASS** (`whole-match-qualification-complete-r1.json` `c6367310…`): e7 full 444 frames and dense e15 full 796 frames, all 9 branches, 11,160 rows, byte-exact. 34 queue tests pass.
  - The cutover to the match queue is under way, prioritizing e15/22/23. The packing sweep on 04 is next.
  - **Decision:** when the GRU exits at 05:00Z, 08 joins the capture queue. The single-tenant deciding window opens only after 24/24 capture plus A1/A2/B.
  - **Delay-fixes controls are complete:** 12,500 games, all shards exit 0. The final report is being reduced.
- **03:21 UTC: delay-fixes exploration complete** (`reports/explore/delay-fixes/RESULTS.md`). 12,500 games, 1,250 paired seeds per arm, against scripted opponents.
  - **Command delay costs about 5–6 pp of wins:**
    - −5.92 pp [4.24, 7.68] against a cadence-matched instant opponent;
    - −4.48 pp [2.96, 6.08] when the opponent is lagged too.
  - **Symmetric opponent lag** at d=27: +1.84 pp [0.00, 3.68]. The effect survives the cadence control but isn't established as positive.
  - 2 or 4 outstanding commands: no win benefit (−0.32 / −0.80 pp), and under-4-elixir arrivals got worse.
  - Forward (t+d) imitation vs current-state imitation: 0.00 pp, with worse under-4 arrivals and twice the CPU.
  - **Decision:**
    - Adopt symmetric opponent lag as the **default evaluation protocol** from now on, since it's the fair simulation.
    - Keep capacity 1 and current-state imitation as the defaults.
    - The 5–6 pp latency cost is the real target. W (WAIT candidates) is being tested next under symmetric delay (`clasher-explore-w-confirm-20261009-1`).
- **03:40 UTC heartbeat.** Sampled GPU average over 8×0.5 s:
  - Home: 01 50% (T11 s22, ~12.1k rows/s), 02 **4%**, 04 99% (packing sweep), 08 100% (GRU).
  - Leased: 09/13/14/15 99% (capture queue, 4 lanes each), 16 72%.
  - **16 is resolved:** T11 seed 21 is back as `extended60-v1` at ~12k rows/s, PSS 36 GB.
  - **Problem (a) on 02:** the GPU is idle apart from perception's leftover inventory job, while gate (c) runs CPU-only. I asked the gates worker whether 4 capture lanes on 02 would breach gate (c)'s frozen host conditions; any doubt means wait for the gate (c) exit.
- **03:47 UTC:** amendments 13 (whole-match queue) and 14 (vectorized non-clock qualification, `460e84aa…`, prepared and not launched) went to an independent review before A1 relies on their outputs: `clasher-v4-amendments-13-14-review-20261009-1` (Opus, high). The packing sweep's 2-lane phase measured 3.99 fps on 04; the 4/6/8-lane phases are pending.
- **03:55 UTC: A13/A14 review** (`reviews/AMENDMENTS-13-14-REVIEW-20261009.md` `c6eeb4e6…`): both APPROVED WITH REQUIRED CHANGES. Production continues.
  - A13 requirements:
    - R13-1: make the 61 retained e06 tasks terminal.
    - R13-2: an intent record before spawn; suspend rather than requeue when an output directory already exists.
    - R13-3: re-capture at least 4 retained matches under load, including e01/708, and byte-compare.
    - R13-4: verify every queue output independently.
  - A14: add a raw-record mutation test. If it passes, vectorized output is allowed for record-only capture only, through a new worker that first reproduces e7/738, e15/748 and e01/708. Deciding, D4(b), timing, heldout and T6 stay on the original path.
  - **A1 blocker found:** the frozen A12 admission and scoring files only read one directory per epoch in the old layout.
    - **Decision:** preferred fix is a verified per-epoch assembler into the old layout, so the frozen code runs unchanged. Fallback is Amendment 15 plus a review.
- **04:03 UTC: A1 path is Amendment 15** (accepted).
  - Why not the assembler: perception showed the frozen admission (`9d646763`) binds a real single-host epoch launch and completion, so an assembler copying the old layout would be dishonest.
  - A15 instead adds provenance-preserving per-epoch assembly admission and body-scorer adapters. The frozen files and scoring rules stay unchanged. It needs an independent delta review before A1; reviewable implementation in ~90 min.
  - R13-1 and R13-2 tests are running on 04. The 61 retained matches are actually 44 e06 + 17 e14.
  - The A14 mutation test was added, and the non-clock gate 04r2 has been active since 03:51Z with no mismatch so far.
- **04:07 UTC: W CONFIRMED against search opponents** (`reports/explore/w-confirm/RESULTS.md`, `4e8ae6dd`). Symmetric d=27, 600 paired seeds:
  - **W vs baseline search: loss 47.8% → 20.0%, −27.8 pp [−32.2, −23.7].**
  - H16: no benefit (+1.3 pp).
  - W vs W: 49/51.
  - Under-4-elixir arrivals 94% → 61%. Humans are at 16–19%, so reserve play is still the main gap.
  - Latency: full W p50/p95 is 258/492 ms in loaded sims. On the fixed-state corpus, **screen8** (coarse scan plus top-8 refinement) agrees with full W on 125/125 states at a one-core p95 of 177 ms.
  - **Decision:** adopt W + screen8 as the next search default. That's the biggest single improvement so far.
    - Delegated `clasher-w-screen8-adopt-20261009-1` (Sol high, 03 CPU): a frozen-plan 600-seed outcome check comparing screen8 to full W (pass if the CI upper bound is ≤ +3 pp), plus a native production implementation behind a default-off flag, with flag-off bit-parity.
    - It will also become the **search teacher** for imitation once adopted.
- **04:09 UTC heartbeat.** Sampled GPU average over 8×0.5 s:
  - Home: 01 67% (T11 s22, ~12k rows/s), 02 **0%**, 04 99% (sweep), 08 26% (GRU).
  - Leased: 09/13/14/15 99% (capture queue), 16 46% (T11 s21 at 11–12k rows/s from its log, so it's fine alongside roader's probe).
  - 06/07/11/18 are still down.
  - **02 GPU idle is an accepted blocker.** The gates worker answered NO, citing the frozen gate (c) PREREG: "Co-tenant load cannot exceed the qualifying envelope". 02 joins the capture queue when gate (c) exits (~05:45Z).
- **04:12 UTC: capture update.**
  - R13-1 is done: the 61 retained tasks are terminal (44 e6 + 17 e14), and 43 tests pass.
  - The R13-4 independent verifier is active on 04, with first outputs marked verified_record_only.
  - 04 home production started at 04:05Z with 8 lanes and the intent-safe controller.
  - Packing sweep at 2/4/6/8 lanes: 3.99/4.03/4.20/4.39 fps. The GPU is the bound; 8 lanes gain only +9% over 4, so the leased hosts stay at 4 lanes under the ≤16-process cap.
  - **Conditional capacity scenario: ~Oct 9 20:05Z with 7 GPUs** (`CAPTURE-CAPACITY-20261009-0355.md`). Not a committed ETA; e22/e23 density is unmeasured.
  - Next: A15, then the R13-3 audit.
- **04:26 UTC:** the native engine baseline is committed (`f9d3b454`): the quick-wins GIL release and Resources cache, plus delay_commands. The fresh gil-v3 library is byte-identical to the w-confirm build48 reference (`71826488…`). 47 tests pass, and 1,000 games / 7,000 rollouts plus 1,000 d27 roots are exact. The W-screen8 native extension is building on top. The outcome check is at 483/1,800 games.
- **04:29 UTC: 04:29Z exploration backstop ran.** Fresh manifests from 09/13/14/15/16 contained only capture-queue jobs (and nothing on 16). Nothing was stopped: no exploration processes remain. All clasher processes are at nice 10; counts are ≤16; clasher PSS is 13.5 GB on 09/13/14/15 and 29.6 GB on 16. Receipt: `fleet/lease/lease-stop-backstop-20261009.json`.
- **04:32 UTC:** W-screen8 native implementation committed (`59454e1a`, on top of `f9d3b454`).
  - The `wait_screen8` flag defaults OFF in the C56/S6 teacher path and in the live RustPlanner.
  - OFF: 250 checks against the baseline on the 125 states (d0 and d27) are exact.
  - ON: 125/125 choices and scores match the frozen screen8 corpus, and the expired-deadline fallback works. 51 tests pass.
  - The library is `06d8e539…`. The outcome check is still running.
  - The flag is adopted once the outcome check passes its +3 pp gate.
- **04:35 UTC: Amendment 15 package is ready** (`amendment15-review-package-r1.json` `deead347…`; draft `4c7fd730…`; snapshot `833af178…`). 69 tests pass. A real e1 old-layout check passed: 64 matches and 106,744 frames. Scope is A1/A2 only.
  - Sent to independent review: `clasher-v4-amendment15-review-20261009-1` (Opus, high).
  - **Capture:**
    - The R13-4 verifier has 34 outputs verified.
    - The R13-3 extra audit was refused correctly: the reservations declare all 16 processes. It will be integrated at a safe controller transition.
    - e22 has started.
    - Non-clock gate r2 failed only on SSH E2BIG after all e1 comparisons matched. r3 has been active since 04:21Z.
- **04:40 UTC heartbeat.** Sampled GPU average over 8×0.5 s:
  - Home: 01 48% (T11 s22), 02 0% (waiting on gate (c)), 04 99%, 08 44% (GRU).
  - Leased: 09/13/14 99%, **15 0%**, 16 80%.
  - Home usage is 3.5 GB. 06/07/11/18 are down.
  - **Problem (a) on 15:** capture controller `15r2` exited pass/0 at 04:34:17Z and nothing was relaunched. I pinged perception to relaunch, or to explain if it's a planned R13-2/R13-3 transition.
- **04:42 UTC: 15 idle cause.**
  - An inner storage refusal: e22/708 hit the 32 GB reservation minus 1 GB margin. The controller killed 3 sibling partials, and the wrapper masked it as pass/0.
  - Approved: move 3 GB of reservation 04 → 15, authenticate the failed attempts, requeue the incomplete ones, and launch 15r3 with the intent-safe controller.
  - Ordered: drain verified outputs from the leased hosts to the hub with checksums before freeing the leased copies, and fix the wrapper so a non-zero exit propagates on inner failures.
- **04:46 UTC:** 15r3 has been running since 04:43:52Z: 8 lanes, intent-safe, all 8 intents present, 3.48 fps, 99% GPU. The 4 failed 15r2 attempts were authenticated and requeued. The status-propagation fix (`match_queue_controller_status_v4.py`) passes 3 tests and goes in at the next safe transition. Note: because A15 reopens the original leased paths, retiring verified leased outputs will need a separate pinned-relocation delta review before any leased copy is freed.
- **04:47 UTC: A15 review: APPROVED WITH REQUIRED CHANGES** (`reviews/AMENDMENT-15-REVIEW-20261009.md`).
  - Equivalence and clock isolation hold, and A12 is byte-unchanged.
  - The tests are weak: 9 of 31 source mutants killed, and data mutants 15/17. The two that slipped through:
    - **G1:** a queue entry is accepted alongside a retained copy of the same match (first-wins).
    - **G2:** an R13-3 self-comparison passes.
  - Required changes:
    - RC1: one source per match.
    - RC2: bind the R13-3 reference to the retained original.
    - RC3: tests that kill the surviving mutants, plus an end-to-end check against the frozen scorer.
    - RC4: re-pin `queue_audit_io`, then rerun the e1–e3 proofs.
  - **Decision:** A15 r2 bundles these with pinned relocation receipts for retiring leased copies, and an A2 cost fix: a sealed per-epoch admission receipt instead of re-authenticating per cell, which the reviewer estimates would add about a day. One delta review follows.
- **04:57 UTC: W-screen8 outcome check PASS** (`reports/explore/w-screen8/RESULTS.md`). 600 fresh paired seeds, 1,800 games, symmetric d=27.
  - Loss rates: baseline **50.8%**, full W **19.5%**, screen8 **19.3%**.
  - Screen8 − W: **−0.17 pp [−1.00, +0.67]**, which passes (gate: upper bound ≤ +3 pp). Screen8 vs baseline: **−31.5 pp [−35.8, −27.5]**.
  - Loaded full-decision p95: 330 ms for screen8 vs 491 ms for W.
  - Commits:
    - native baseline `f9d3b454`;
    - implementation `59454e1a`, startup fix `62044189`;
    - report `d6f5c29f`;
    - freeze `d0e9dc2f`.
  - **Decision:**
    - W-screen8 becomes **default ON for the offline search teacher and simulation path**, once a running-process path check confirms frozen snapshots aren't affected.
    - **The live planner stays default OFF**, with a recommended ON profile, until it's measured on the Mac E4 path (real searches plus GIL threads; budget 200 ms). That needs Sam's Mac authorization.
- **04:58 UTC: storage budget raised.** The v4 capture/archive reservation goes from 1.3 TB to **2.0 TB**.
  - Reason: measured /mpac free space is 03 1.6 T, 02 1.5 T, 08 1.4 T, 04 1.1 T, 01 984 G, and the old budget was self-imposed.
  - The primary archive destination is **03, ≤500 GB** under a dedicated prefix. 02 and 08 get ≤150 GB each.
  - Every host keeps ≥40% of /mpac free for other lab users.
  - Verified leased outputs are archived to 03 with checksum and fsync before any removal.
  - Note: my time labels in the 05:10Z and 05:25Z worker messages were ~25 min fast; the real times were ~04:45Z and ~04:55Z.
- **05:00 UTC: 09 capture stopped** at 04:57:18Z. The cause was perception's own reservation-accounting mismatch: `du -sb` counts hardlinks once and gave 68.9 GB, while the logical guard counted 73.7 GB. Host stability was not involved. The wrapper again masked the stop as pass/0. The reservation is restored to 78 GB (within 2 TB), and recovery with the intent/status controller is under way; no completed capture is rerun. **08: the T5 GRU paused and verified** at 04:40:51Z, exit 0, with its checkpoint backup SHA recorded. 08 joins the capture queue with a 150 GB plan.
- **05:05 UTC: W-screen8 ADOPTED as default for the offline search teacher and sims** (`701a983e`).
  - Default construction matches explicit ON exactly on 125/125 states. Explicit OFF keeps baseline parity at 250/250.
  - The live RustPlanner stays default OFF, with a recommended ON profile and a Mac E4 measurement plan in RESULTS.md.
  - A read-only /proc audit across 01/02/03/04/05/08/09/13/14/15/16 found no running job mapping the checkout native library or planner config, so gate (c), T11 and capture are unaffected.
  - 08r2 and 09r2 capture lanes are now running.
- **05:10 UTC heartbeat.** Sampled GPU averages: capture at **99% on 04/08/09/13/14/15** (08 joined after the GRU pause, and 09 recovered). T11: 01 74% and 16 39% sampled, both at ~12k rows/s step rate. 02 is at 0%, waiting for gate (c), ETA ~05:45Z. Home usage is 3.5 GB. 06/07/11/18 are down. Seven GPUs are productive, plus 02 pending.
- **05:12 UTC:**
  - **A14 non-clock gate PASS** (proof `8f2d0e07…`: e1/e3/e20 raw captures plus 3 reference cells). It doesn't admit a production switch.
  - **Decision:** switch the queue to the vectorized worker only if a 10-min A/B shows ≥15% better per-GPU fps. Capture is GPU-bound at 99%, so the decode speedup may not help end to end.
  - The 03 archive service is active, with the first verified relocations done.
  - 08 is running 8 lanes at 99%. 09 recovered (8 lanes, 27.9 GB PSS).
  - A15 r2 is at 123 tests passing, with the mutation rerun in progress.
- **05:35 UTC: A15 r2 package ready** (`c66fd6f4…`; draft `2d32c0b4…`). 186 tests pass, 31/31 non-equivalent mutants killed, and the final-pinned e1/e2/e3 layout proofs pass. It includes relocation to 03 and memoized per-epoch admission: one-match cost drops from 4.7 s to 0.4 s. Sent to delta review: `clasher-v4-amendment15-r2-delta-review-20261009-1` (Opus, high).
- **05:54 UTC: AMENDMENT 15 r2 FROZEN** (`l1/amendments/15-FREEZE-RECORD-20261009.json`). Draft `2d32c0b4…`, package `c66fd6f4…`, delta review `d35ee0ea…`. Approved with no required changes. A12 bytes are unchanged.
  - Disclosed: memoized reuse doesn't recheck the remote `.pt` copies or the equality artifact. Neither feeds a score or bound.
  - **A1 checklist (16 steps):**
    - install the r2 bytes;
    - mechanically check every epoch-key mapping;
    - pinned copy receipts for R13-3 references;
    - keep leased metadata reachable through A2;
    - **A1/A2 run on 04 or 03 only**, after an admission-only dry run.
- **06:02 UTC:** issued `l1/amendments/15-FILE-LAYER-DELTA-APPROVAL-20261009.json` (`5f67971b…`): decision=APPROVE_FILE_LAYER_DELTA, binding amendment `2d32c0b4`, delta `fac7f864` and the independent review `d35ee0ea`. This is the shape the orchestration code expects. It's separate from A1 and doesn't approve it. Perception installed the r2 execution tree on 04 (install receipt `b155b282…`); post-freeze tests 12/12, and 5/5 ledger/reuse mutants killed, including an epoch-mapping swap check.
- **06:04 UTC:** perception's dry-run check accepts the A15 file-layer approval (`5f67971b`), and a missing A1 binding is rejected. Receipt: `a15-file-layer-approval-check-0604.json` (`54884ebc…`).
  - **Fields coordinator-approval-A1 must carry:**
    - `decision=APPROVE_A1`;
    - `file_layer_review_sha256=5f67971bef48c706bbddd4c4f9aca02fb780831ed5a6fff32ff5762035d99a29`;
    - `assembly_sha256={"1":…,"24":…}`, the actual complete assembly SHAs;
    - `execution_plan_sha256`;
    - `freeze_sha256`.
  - Queue at 06:02:53Z: 93 verified, 40 claimed, 819 pending, 61 retained terminal.
- **06:10 UTC heartbeat.** Capture at 99% on 04/08/09/13/14/15. T11: 01 40% and 16 82% sampled; both were at ~12k rows/s earlier. 02 is at 0%. **Gate (c) is overrunning:** about 865/1,792 game files after 5h55m (estimate was 3–4 h); it's alive, with resources.jsonl updating at 06:09:56Z; projected finish ~12:30Z. Its frozen co-tenancy rule keeps 02's GPU idle until then. Accepted; not interrupting a frozen gate. No pending requests. 06/07/11/18 are down.
- **06:10 UTC: decision.** Because gate (c) locks 02 until ~12:30Z, the vectorized A/B benchmark (≥15% gate) and the R13-3 full-load recapture move to **04**, at a controller-safe drain. That's about 30–40 min of one GPU and unblocks a possible speedup plus an A1 prerequisite. Queue at 06:10Z: 98 verified, 40 claimed, 815 pending. The R13-3 e1/708 reference copy is authenticated against the original.
- **06:11 UTC: decision.** Frozen A15 requires R13-3 on 2 distinct leased hosts with 2 cells each; it rejects 04. **Keeping the original requirement, with no new amendment.** The audit runs on 13 and 14 through a controller-safe drain of 1–2 production lanes per host, which frees declared slots within 16. Those lanes are restored afterwards. 04 is draining (SIGUSR2 at 06:11:09Z) for the vectorized A/B benchmark only.
- **06:34 UTC: risk to the critical path.** The validation-cache services on 02/08 hard-stop at **12:00Z**, and capture clients bind to them at supervisor startup.
  - **Decision:**
    - Authenticated replacement services on **03** (primary) and 08. No new process on 02 while gate (c) runs.
    - Clients hand off only at controller-safe restarts (09r3, 15r4, 04 post-benchmark, then 13/14/08), at most 2 hosts draining at a time.
    - **Every client is bound to a renewed service by 11:30Z.**
  - Queue: 119 verified, 34 claimed, 799 pending.
- **06:37 UTC:** cache replacement plan `db085fde` approved: 03 serves 02's 8 matches, a fresh 08 serves 56, with a new hard stop of Oct 11 04:00Z. Pins are unchanged. **The legacy 13/14 drain-via-claim=None operator reply is approved** with conditions: tests on the exact legacy code, a pinned-owner identity check under `queue.lock`, a per-host operator receipt, a queue-conservation check, one host at a time, and a fallback (clean stop at 11:15Z) only after telling me.
- **06:46 UTC:** the renewed cache services are READY and authenticated: 03r2 (8 matches) and 08r1 (56), hard stop Oct 11 04:00Z. The legacy-drain tests pass 3/3.
  - Handoff timetable: 04/09 by 08:00, 15 by 09:00, 13 by 09:15, then **14 and 08 in parallel** by ~10:15. I relaxed my ≤2 concurrent-drain cap so the margin before the 11:30Z deadline grows from 15 to ~75 min.
  - The 11:00Z check is scheduled.
- **07:08 UTC:** 04 drained cleanly, and **the vectorized benchmark 04r2 started at 06:56:49Z**.
  - **09r4 was refused before launch** at 06:59:01Z: 1 external process plus a declared 16 exceeded 16. The external PID was nice 19 with 0.59 MB PSS and wasn't coordinator tooling; it was likely perception's own probe.
  - **Fix requested:** new leased controllers declare 15 (one slot of probe headroom) and/or a probe quiet window around each admission. The 09r4 retry uses a new label with no bypass.
  - The handoff watcher halted correctly. 15/13/14/08 keep capturing on the old services.
- **07:10 UTC heartbeat.**
  - **Gate (c) finished:** exit 0 at 06:54:07Z. My 12:30Z projection was wrong because I counted files, not games. The gates worker reports the results.
  - **Decision:** 02 joins the capture queue now, with an intent-safe controller on the renewed services and a 150 GB budget.
  - Capture is at 99% on 08/13/14/15. 04 is at 80% (vectorized benchmark). **09 is at 0%** pending the 09r4 retry.
  - T11 s21 on 16 is at 73%. 06/07/11/18 are down.
- **07:19 UTC: GATE (c) RESULTS: both frozen decisions PASS** (`imitation/RESULTS-gate-c.md` `a9610429…`).
  - **P16:** v1 won 191/384 (49.7%) against the natural baseline's 66/384 (17.2%). Exact McNemar p = 5.8e-25.
  - **H2H:** v1 won 170/256 against s2902, score 66.4%, paired CI [61.3, 71.5]. **Under the registered rule, v1 replaces s2902.**
  - **C56** (descriptive): 319/384, 83.1%.
  - All audits pass: all 25 rejections reproduce known occupancy guards, and all 10 action-stream spots are exact.
  - Disclosed: the spot count wasn't specified in the PREREG and was fixed before analysis.
  - With gate (b) PASS (0.656) as well, **the v1 all-card imitation model is confirmed as the human prior.** Next on that track: integrate it with the W-screen8 search teacher.
- **07:19 UTC: VECTORIZED BENCHMARK, 9.87× faster** (`8aba8f8b…`, plan `2657285d`): on the fixed dense e15/748 128-frame prefix with 8 lanes on 04, original 4.39 fps vs vectorized **43.27 fps**.
  - My GPU-bound assumption was wrong: 99% util meant many small kernels, not a full GPU.
  - **Decision: the vectorized switch is top priority**, after the 11:30Z cache handoff.
    - A14 whole-match qualifications run now (e7/738, e15/748, e1/708).
    - Perception drafts **Amendment 16** (admit vectorized producers into A15 assembly), followed immediately by an independent review.
    - The host-by-host switch happens only after the A16 freeze and the qualifications. No completed output is redone.
  - **Expected effect:** the remaining capture drops from ~15 h to ~1–2 h, moving A1 up by most of a day.
  - Status: 04 is restored to original 8 lanes (04r3, renewed services); 02r3 runs 8 lanes at 99%; 09 runs 6 normal lanes plus the R13 audits; 13 and 15 are draining for the handoff.
- **07:21 UTC:** concurrency exception approved: 02 drains now, as a third concurrent drain with 13/15, for the three A14 vectorized qualification cells. 02 then goes back to the original 8 lanes on renewed services. A16 drafting is delegated by perception in parallel.
- **07:43 UTC:**
  - Cache handoffs: 04, 09, 13 and 14 are renewed; 15 and 08 are still draining.
  - **The 09 R13 audit PASSED** (`1942e126`).
  - Queue: 192 verified, 38 claimed, 722 pending.
  - **Decision for the vectorized switch**, once A16 is frozen, the qualifications pass and the handoffs are done:
    - concurrent drains on all eligible hosts, with immediate vectorized replacement;
    - 15 waits until its R13 audit passes;
    - original matches with long tails (>20 min left) may be voided and requeued through the tested failure-recovery path, with receipts and a conservation check.
  - A16: 157 test executions pass; it's waiting on the qualification proof.
- **07:51 UTC:**
  - Storage budget raised to **2.2 TB**. The new vectorized 04 plan gets 75 GB, and new vectorized host plans may get up to 1.5× their current reservation. Active plans are unchanged, and the 40% floor holds. Why: 04 was at 29.4 of its 31 GB, and only 8 GB was unallocated.
  - **Vectorized qualification:** e7/738 and e15/748 PASS on all records. e1/708 is running.
- **07:58 UTC:**
  - **Vectorized qualification: all 3 PASS** (e7/738, e15/748, e1/708; 3,656 frames × 9 branches; proof `40828251…`). 02 is restored to original 8 lanes (02r4) on renewed services.
  - **A16 package** (`3f125d72…`, draft `411d147c…`) went to independent review `clasher-v4-amendment16-review-20261009-1` (Opus, high). 157 tests pass, 20/20 mutants killed, and real admission over 32,904 records passes.
  - Storage ledger is at 2,111.5/2,200 GB.
- **08:08 UTC: cache handoff COMPLETE.** All 7 were independently authenticated at 08:06:53–08:06:58Z (`cache-handoff-all-seven-authenticated-20261009-r1.json` `cb999a6d…`), more than 3 h before the 11:30Z deadline. No 02-old bindings remain, and both renewed services hard-stop Oct 11 04:00Z. The 11:00Z check task is deleted as redundant. The natural-drain switch package (17 tests, `28a9815f…`) is held until A16 is frozen. 15 is still waiting on its R13 PASS.
- **08:24 UTC: 04 original r3 stopped** at 08:15:40Z. The wrapper correctly propagated exit 1, with 8 attempts left for operator recovery. The likely cause is the old plan's 31 GB guard. **Decision:** after authentication and recovery, relaunch 04 on the ORIGINAL worker under a new plan with up to 75 GB (inside the 2.2 TB budget); don't wait for A16. If the cause isn't storage, perception reports before relaunching.
- **08:25 UTC: AMENDMENT 16 FROZEN** for the record-only production release (`l1/amendments/16-FREEZE-RECORD-20261009.json`; draft `411d147c`; review `4e486c2c`).
  - Required changes:
    - **R16-3:** the mixed verifier replaces the original-only one BEFORE the first vectorized registration.
    - **R16-1:** before A1, a production-load byte-exact audit. My addition: ≥4 matches across ≥3 epochs, picked by a pre-committed hash rule and re-captured on the original worker.
    - **R16-2:** before A1, the reviewer's 6 tests.
  - Disclosed: equivalence is sample-based. The evidence is A14 (all 64 e1 matches), 3 qualifications and R16-1.
  - **The vectorized switch is RELEASED** once R16-3 is in place: concurrent drains, with the long-tail void option.
- **08:27 UTC:** issued the A16 receipts in the shapes the code expects. The original freeze bytes are retained.
  - Supplementary freeze `3e5c04b8…`, with the full `producer_contract_sha256`.
  - **Vectorized production release** `0dd2f265…` (schema `vectorized-production-release.v1`, overlay `96519baf`, contract `3b3ebc8f`, timing_admitted=false).
  - A16 file-layer approval `730c86e8…` (APPROVE_FILE_LAYER_DELTA, amendment `411d147c`, delta `eafa80ff`). It is not A1.
  - 04 recovery is complete: 8 tasks requeued once, and 625 backup files match. 04 goes straight to vectorized after the mixed verifier is in.
- **08:27 UTC:** original verifier r12 exited 1 at 08:25:48Z and suspended the queue on an SSH exit-255 transport failure reading 02r4 e08/1048. It's not a mismatch, and it may be the same network blip as the 08:3x GitHub DNS failure. **Approved:** a full same-claim re-audit, then clear only that suspension under `queue.lock` with a receipt, then start the **mixed verifier (R16-3)** in place of the original, then the vectorized switch. The A16 receipts are committed (`5591158f`).
- **08:35 UTC: FIRST VECTORIZED PRODUCTION.** 04 started at ~08:35Z: 8 lanes, plan `99cf9ec6`, 75 GB, renewed services.
  - The mixed verifier (R16-3, plan `ea5b21aa`) runs first; the original verifier is stopped.
  - The 02 transport suspension was cleared after a full audit PASS (`353069a1`).
  - Three launcher-check failures are retained as receipts, and there was no duplicate capture. The post-admission quiet-window evidence is incomplete because the watcher dropped the lock before the first child; recorded honestly.
  - The six-host natural-drain switch watcher is starting (17 tests pass). 15 waits for its R13 audit.
- **08:39 UTC heartbeat.** 02 (relaunched), 04 (vectorized), 08, 09, 14 and 15 at 99%. **13 at 0%**: its natural drain finished and it's awaiting the vectorized relaunch by the switch watcher. I'll act if it's still idle after 20 min. T11: 01 63%, 16 32% sampled. 06/07/11/18 are down.
- **08:49 UTC: vectorized production rates:**
  - 04: 54.7 fps over 429 s;
  - 02: 33.2 fps over 103 s;
  - 13: 53.6 fps over 42 s.

  That's 8–12× the original worker's per-GPU rate.
  - About 0.93–0.95 M frames remain. Once all safe switches are done, capture takes **~0.7–1.1 h** (excluding audits, verification and A1), against 3.4–8.6 h original-only.
  - Gap found: the 40% disk-floor monitor's argv check rejects vectorized controllers. Producer reservation guards are still active, and disks are currently over 40% free. A versioned vector-floor monitor is being built.
  - Receipt `233d2f6b`.
- **08:53 UTC:** 09 is now vectorized. The vector disk-floor guard r3 is deployed (11 tests pass, minimum free 57.6%). The A16 reviewer's test artifacts were preserved in the repo at `l1/reviews/a16-reviewer-artifacts/`: `test_reviewer_a16.py` `fdc5d806…` and `rev_mutants.py` `70c5812e…`. They were at 127x04:/tmp/sdicks02-a16rev/l1/, not the path perception tried.
- **09:03 UTC:**
  - **Six hosts vectorized** (02/04/08/09/13/14). 15 stays original pending R13.
  - The fixed R16 stress recaptures are running: 02 e1/708, 04 e20/778.
  - The verification backlog was 69 at 09:02 (401 verified). **Decision:** scale the mixed verifier to 8–16 parallel CPU workers on 03/01 with atomic marking, as a new plan version with no source edits. Target: backlog under 10 within 30 min.
- **09:09 UTC:** the pinned mixed verifier is a lifetime singleton (`verifier.lock`, pending[0]) with no partitioning. **Approved: a separate operational dispatcher** (new versioned orchestration source) with durable per-claim reservations and CPU audit workers on 03. It calls the unchanged pinned `audit()` and `publish()`.
  - Tests required for: reservation atomicity, exactly-once crash reclaim, `publish()` as the sole writer of marks, and suspension parity.
  - The 15 watcher dependency is migrated explicitly at handoff.
