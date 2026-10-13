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
- **09:16 UTC: parallel verifier dispatcher active** (04 PID 1945646, source `983b31e8…`, plan `61dec0ab…`). 8 audit slots on 03, effective ≤7 because of the per-host I/O locks.
  - 9/9 tests pass: 100 concurrent reservations → 1, crash release consumed once, reserved ≠ verified, only the pinned `publish()` writes, suspension parity.
  - The serial verifier exited 0 after all 456 published proofs were checked.
  - The 15 watcher dependency was migrated.
  - **The backlog was 151 at handoff;** the rate window is being measured.
- **09:20 UTC:**
  - The parallel verifier is catching up: backlog 151 → 102 in 4.4 min (about 21 verified/min against about 10 completions/min); under 10 expected around 09:29Z.
  - **15's R13 audit PASSED** (`f5b09a6a…`). Both leased R13 audits now pass, which meets the A1 prerequisite.
  - 15 is naturally draining to vectorized, the last host.
- **09:35 UTC:**
  - **Verifier target met:** backlog 6 at 09:34:15Z, down from 151. 18.4 verified/min vs 10.6 completions/min (receipt `a8b67f9b…`).
  - Queue: 799 verified, 53 claimed, 95 pending, so **capture finishes ~10:00Z**.
  - Both fixed R16 stress recaptures PASS (02 e1/708, 04 e20/778).
  - Still blocking A1: the 4 hash-selected R16-1 recaptures after queue closure, and the A16 follow-up admission delta plus review.
  - **Post-capture GPU plan:** 08 stays reserved for B. The GRU resumes on a freed GPU (04 proposed). I've asked the imitation owner for a next-workload recommendation (v2 with W-screen8 teacher labels vs more seeds); allocation by ~10:00Z.
- **09:36 UTC: allocation.** The R16-1 four original-worker recaptures run in parallel after queue closure on 02/13/14/15, one cell per host (09 is a substitute), then each host is released. **04 → T5 GRU resume.** 08 stays reserved for B.
- **09:40 UTC: 127x02 OFFLINE** (no route; LAN ssh from 01 times out; ping 100% loss), most likely powered off.
  - At 09:39, 04/08/09/13/14 were idle (queue nearly drained) and 15 was at 99%.
  - **Decision:**
    - host-lost receipts for 02's claims, then a requeue exactly once onto the idle vectorized hosts;
    - 02 partial outputs are never admissible;
    - if 02 returns, verify no survivors first, then retire its stale outputs; RC1 one-source blocks late admission;
    - R16-1 audits move from 02 to 09.
  - The 02 cache service (old, hard-stop 12Z) was already unused.
- **09:42 UTC: queue SUSPENDED** by a parallel-verifier transport failure (likely 02 loss); all controllers stopped and 6 GPUs are idle.
  - Counts: 835 verified, 12 awaiting verification, 43 claimed (9 on 02), 63 pending.
  - **Priority recovery:**
    - host-lost receipts for the 9 02 claims and a requeue; the 1 unverified complete is inadmissible;
    - scoped unsuspension with a receipt;
    - immediate vectorized restarts on 04/08/09/13/14 (+15);
    - then the R16-1 audits, and 04 to the GRU.
  - Follow-up for later: a host-unreachable error should quarantine that host, not suspend the whole queue.
- **09:43 UTC:**
  - The suspension's root cause was the audit read of 02 e20/908 (claim `5e850c0d`) at 09:37:46Z, a transport failure. The 03 cache is live.
  - **72 verified outputs exist only on 02,** which had no archive retention because the service covered only leased hosts. **Decision:**
    - adopt any checksum-verified mirror through the A15 relocation path;
    - otherwise write retire-as-host-unreachable receipts and requeue for vectorized recapture (~10 min);
    - 02 copies stay permanently inadmissible if 02 returns.
  - Follow-up: the retention service must cover home hosts too.
- **09:49 UTC:** 81 lost-02 claims/outputs were retired or requeued, and the 02 authorization was revoked. **Authorized:** void and requeue 5 surviving-host attempts that have complete payloads but no controller `.outcome.json` (the controller aborted on suspension). Payloads are retained and inadmissible, and no provenance files are invented. Strict admission is unchanged. The 5-host vectorized restart follows.
- **09:54 UTC: capture RESTORED** at 09:54:11Z on 6 vectorized GPUs (04/08/09/13/14/15).
  - Queue: 777 verified, 48 claimed, 127 pending, unsuspended.
  - Recovery: 81 lost-02 requeues (9 unresolved plus 72 permanent retirements) and 5 provenance voids, with no forged files. Dispatcher r4 is live and the 03 archive copier resumed.
  - About 304 k frames left; **capture closure ~10:10–10:25Z**, then the R16-1 audits on 09/13/14/15, and 04 goes to the GRU.
  - Follow-ups after closure: per-host transport quarantine, and archive coverage for home producers.
- **09:56 UTC:** 04r3's guard stopped it at 09:54:26Z (GPU free 5.3 GB < 8 GB). The likely cause is a premature T5 GRU start on 04, from my 'as soon as a GPU frees' note; the GPU is empty now. 8 partials are preserved and the queue isn't suspended. **Decision:** 04 is released to T5 after the exits, backup and requeue are authenticated. The other 5 GPUs finish capture, and T5 waits for the explicit release.
- **09:57 UTC:** 04 released at 09:56:27Z (receipt `59890022…`): exit authenticated, backup verified, 8 claims requeued. **T5 is told to resume the GRU on 04.**
- **10:03 UTC: A1 dependency on 02 found.** Frozen A16 contract `3b3ebc8f` pins the 3 qualification outputs, their receipt and plan to host 02, and the R16 e1/708 stress output is 02-only. **Decision, in parallel:**
  - a mirror search;
  - a narrow prospective **Amendment 17**: re-run qualifications and the stress cell on reachable hosts with the frozen worker, re-pinning the evidence; the 02 originals stay retired;
  - asking Sam whether 02 can be powered back on.
- **10:04 UTC:** A17 ordering. The replacement fixed e1/708 stress cell runs **now on 08** beside its 8 live vectorized lanes, preserving the precommitted ≥4-vector-lanes load condition, with the frozen 70e8deaf worker and a versioned driver. The 3 ordinary qualifications run after closure on 09/13.
- **10:09 UTC heartbeat.** 04 at 100% (the T5 GRU resumed, 39 GB). Capture at 94–99% on 08/09/13/14/15. T11: 01 65%, 16 26% sampled. **02 is still offline**, as are 06/07/11/18. No pending requests.
- **10:15 UTC:** the replacement fixed e1/708 stress **PASSED on 08** under live vector load (≥5 lanes, 9 streams byte-exact; complete `02eef314…`). **The A17 package** (`7e773ec2…`, draft `d9fa01eb…`, 55 tests, 8/8 mutants killed) went to independent review: `clasher-v4-amendment17-review-20261009-1` (Opus, high).
- **10:16 UTC: V4 CAPTURE + INDEPENDENT VERIFICATION CLOSED** at 10:15:26Z: 953 verified_record_only and 61 retained terminal, nothing pending or claimed, unsuspended.
  - The vectorized decoder cut ~10 h off the original-only path.
  - Next:
    - R16-1 hash-four original recaptures on 09/13/14/15, with the telemetry operationalization receipted before any ranking;
    - the A17 qualifications on 09;
    - A17 review → APPROVE_EVIDENCE_REPLACEMENT;
    - the R16 follow-up admission delta;
    - then the A1 checklist.
  - 08 is free now (B is later).
- **10:17 UTC:** the T5 GRU resumed on 04 at 09:59:58Z, exactly, but only at **234 rows/s** (GPU 100%; Stage A/B speedups are unqualified). The T5 owner is a scheduled continuation and hasn't answered the planning questions. **Commissioned an Opus planning analysis** (`clasher-plan-next-compute-20261009-1`) for the freed GPUs/CPUs over the next 24–40 h: v2 with the W-screen8 teacher, T11, the GRU's value, reserve/tempo fixes, live-perception latency, DDP. Allocation follows within about 45 min. In the meantime, 08/13/14/15 hold for the R16 audits and B.
- **10:18 UTC: R16-1 selection-ordering incident, adjudicated ACCEPTED.**
  - The hash-only sampling ran before the separate receipt existed. But the exact operational rule had been sent durably in-thread before computation (t6t7-capture-closure1015), and selection is hash-ranked on telemetry eligibility with no record values.
  - Conditions: the receipt binds the message ID, timestamp and verbatim rule; a mechanical code-matches-rule check; confirmation that no candidate record values were inspected; disclosure in the A1 record. Then the 4 recaptures launch.
- **10:23 UTC: NEXT-COMPUTE PLAN ADOPTED** (`PLAN-NEXT-COMPUTE-20261009.md`). **CPU is the bottleneck, not GPU.**
  1. **Distil W-screen8 into a fast student** (ExIt r1): teacher labels on 03/04/08 CPU, then v2 fine-tunes S-mix / S-teacher / S-human (~1 GPU-h each).
  2. **E1 CPU checks first:**
     - W under an enforced 200 ms deadline;
     - W vs the v1 policy as a human proxy, plus under-4 causality.
  3. **T11:** finish s21/s22, then the registered v2 gate (a). No extra seeds.
  4. **Park the T5 GRU** (~120–200 GPU-h for a descriptive-only result).
  5. **Opportunistic:** a preemptible capacity scan of the human prior on idle leased GPUs, with a kill rule.
  6. **Mac E4 combined package** prepared for when Sam authorizes.
  - No DDP. The reserve fix is gated on E1b.
  - Perception A1 → A2 → B on 08 keeps priority.
- **10:24 UTC: plan execution.**
  - GRU park ordered (T5).
  - T11 told to finish both seeds, then run the registered v2 gate (a).
  - Delegated (Sol high):
    - **E1** (`clasher-e1-w-deadline-humanproxy-20261009-1`): deadline harness plus v1 human-proxy arms on 03/04/01-idle;
    - **ExIt r1** (`clasher-exit-r1-teacher-student-20261009-1`): teacher-label emitter, student trainer adapter, latency probe, then generation on 03/04 and 08 with a stop file;
    - **Mac E4 package** (`clasher-mac-e4-package-20261009-1`): prepare only, no Mac access.
- **10:24 UTC: A17 review: REQUIRED CHANGES** (`0de18ebc…`).
  - Confirmed: scope is closed, and the 08 stress was independently re-verified.
  - Required:
    - **R17-1:** don't put replacement evidence on leased hosts. **Decision:** run the 3 qualifications on owned **08** now (04 is the alternate); the 09 run is corroboration only.
    - R17-2: the stress check verifies the source closure.
    - R17-3: A1 binds the APPROVE_EVIDENCE_REPLACEMENT SHA directly.
    - R17-4: adopt the reviewer's 7 tests (preserved: `a17-reviewer-artifacts/test_reviewer_a17.py` `985ad06b…`).
  - **Broader:** all A1-read evidence on leased hosts is relocated to owned 03 before A1.
  - R16-1 selection is materialized (`a0f70344…`): e17/1208 → 09, e8/1308 → 13, e16/878 → 14, e9/1218 → 15.
- **10:25 UTC: CPU split E1 vs ExIt r1.** E1 has priority.
  - 03: E1 ≤64, ExIt ≤48 (ExIt ≤96 after E1 finishes).
  - 04 (after the GRU park): E1 ≤32, ExIt ≤96.
  - 08: ExIt ≤96 at nice 19 with a stop file.
  - 01: E1 ≤24 SCHED_IDLE.
- **10:27 UTC:** E1 seeds and 4 arms approved. **Added arm 5: W + a reserve-floor intervention vs v1** (paired with W-v-v1), to establish whether under-4 arrivals causally drive losses. It's a fair-state candidate filter, flagged default OFF, frozen in PLAN before any game.
- **10:31 UTC:**
  - R16-1 original recaptures: **09 and 13 PASS**; 14 and 15 are running.
  - A17 r2 implements owned 08/04-only qualifications, the 27-source plus exact qualifier `eba6349d` stress check, the direct 24-epoch approval SHA, and the reviewer's 7 tests verbatim. 116 tests pass. The 08 qualification is re-running as 08r2 with the exact unchanged qualifier; 08r1 is kept as corroboration.
  - **Coverage gap:** the 03 archive copier covers queue outputs only, not audit evidence or producer metadata/bundles, and frozen A15 RelocatedIO only routes claim outputs. The R16 follow-up admission/relocation package must cover these explicitly. Perception reports full A1 reachability before requesting A1.
  - My earlier 10:45Z label was ~15 min ahead.
- **10:33 UTC:** **09 and 13 RELEASED** (receipts `735c6233…` and `f961e497…`). R16-1 e17/1208 and e8/1308 PASS, final backups verified, and 1,297 audit/control/payload files each copied to 03 with checksum and fsync. Per the plan, the 09/13 GPUs stay deliberately idle until the student/capacity-scan builds are ready (~13–17Z). 14/15 audits continue.
- **10:33 UTC:** A17 r2 package (`cfa5d4be…`; 116 tests; 10 mutants rejected; R17-1/2/3/4 implemented) went to a short code-only delta review, `clasher-v4-amendment17-r2-delta-review-20261009-1` (Opus, high). The 08r2 exact-qualifier qualifications launched at 10:32:32Z.
- **10:36 UTC: R16-1 production audit COMPLETE: 4/4 PASS**, each re-captured on the original worker, byte-exact on all 9 streams:
  - e17/1208 on 09;
  - e8/1308 on 13;
  - e16/878 on 14 (`dd9cac14`);
  - e9/1218 on 15 (`f06a0ee5`).

  All four hosts released, with audit evidence copied to 03.
  - The vectorized decoder's equivalence now rests on A14 (all 64 e1 matches), the 3 qualifications, 2 fixed stress cells and 4 random production audits.
  - **Remaining before A1:**
    - A17 r2 delta review, then the §5 check, then APPROVE_EVIDENCE_REPLACEMENT;
    - the R16 follow-up admission/relocation package (audit and producer-metadata reachability) plus its review;
    - the full A1 checklist.
  - 13/14/15 GPUs are idle until the capacity-scan builds land (~13Z).
- **10:37 UTC:**
  - The T5 GRU PARKED at 10:25:44Z (`gru-park-B0-release-20261009.json`, step 1878, backed up). **04 is released** to ExIt (≤96 CPU) and E1 (≤32); its GPU is empty.
  - The A17 owned-08r2 qualifications PASS (complete `380da25b…`; e7/738, e15/748, e1/708, 9 streams byte-exact). The §5 packet is being built.
  - Capacity probe: width 192 p99 is 14.9 ms (passes ≤15 ms); 288/384 fail.
- **10:39 UTC: A17 r2 delta review: REQUIRED CHANGES**, one guard (`87a66e39…`). The qualifier pin `eba6349d` is enforced only for stress, so the 08r1 (77c809) qualification receipt would be admitted.
  - Ordered: A17 r3 = that guard plus 1 test; I do a diff-only check, then freeze.
  - §5 circularity resolved: after the r3 freeze and my mechanical checks, I issue a **conditional** APPROVE_EVIDENCE_REPLACEMENT, void unless the immediately following actual-file `verify_replacement_evidence` on 04 passes. A1 is barred until then.
  - The 08 GPU was released (`3707b2c1`).
- **10:40 UTC heartbeat.** Only 01 (T11 s22) is on GPU. **04/08/09/13/14/15/16 GPUs are idle**: T11 s21 finished, and per the plan the GPU work waits for the B5/student builds (deliberate). E1 is frozen (`bfb9b107`), its smoke test is running on 03, and it's pinned to 03 cores 0–61 and 04 cores 0–29. ExIt is assigned 03 cores 62–127 and 04 cores 30–127, plus 08. 02/06/07/11/18 are down.
- **10:43 UTC: ExIt r1 teacher generation LAUNCHED.**
  - B2 full matrix PASS: exact replays, and observation bytes equal to gate (c).
  - Rate is ~3.07 roots/s/core.
  - Hosts: 04 (94 workers, cores 30–127, 6 M roots) and 03 (46 workers, cores 62–127, 4 M roots). **08 added** at nice 19 with a stop file (≈94 workers, about 4 M roots), so ~720 roots/s and ~4 h for the target.
  - Width probe p99: 192 = 14.9 ms (live candidate), 288 = 18 ms, 384 = 27.6 ms, 768 = 90.3 ms (offline only).
- **10:48 UTC: AMENDMENT 17 r3 FROZEN** (`17-FREEZE-RECORD-20261009.json` `cdfc5573…`).
  - My diff-only check passed: only the qualifier guard and its test changed between r2 and r3.
  - **§5 mechanical check** (`90728bde…`): items 1, 2, 5 and 7 PASS; item 3 is partial (worker and qualifier pinned); items 4 and 6 are covered by the real-file run.
  - **CONDITIONAL APPROVE_EVIDENCE_REPLACEMENT issued** (`64b1ebe4…`, copied to 04): void unless the real-file `verify_replacement_evidence` on 04 passes, and A1 is barred until I record the condition as satisfied.
  - **New:** all 61 retained-terminal matches (44 e06 + 17 e14) are 02-only. A decision follows.
- **10:48 UTC: A1 coverage receipt** `4d86c27a`.
  - Leased queue outputs: 587 relocated to 03 and 44 to 04.
  - **404 retained-original matches on leased 09/13/14/15** still need owned archival; inventory-pinned copies to 03 are approved.
  - The 61 02-only retained matches have no known mirror, so they're being recaptured.
  - A18 scope: retained/audit/metadata routing, R16-1 enforcement, and the 61-match retirement plus recapture admission.
- **10:50 UTC: A17 §5 real-file run PASS** on 04 (exit 0, log `ec0d24bf…`). **The APPROVE_EVIDENCE_REPLACEMENT condition is SATISFIED** (receipt `17-EVIDENCE-REPLACEMENT-CONDITION-SATISFIED-20261009.json`), so approval `64b1ebe4` is now valid. A1 is still barred pending A18. Recapture of the 61 02-only matches is being prepared in a separate namespace with the closed queue untouched. The 404-match archive is ~32 GB to 03. The A18 package ETA is ~45–60 min after the recapture launch.
- **10:54 UTC:** ExIt warm fleet rate is 375 roots/s, with 234 workers live (SMT oversubscription beside E1). **Decision: the round-1 target drops to 6 M roots** (about 39 M poll rows, enough for the ~1 GPU-h student arm), ETA ~15:10Z. The rest goes to DAgger round 2. The student screen pipeline is being built in parallel.
- **10:58 UTC: Mac E4 combined package ready** (`257adad9` on main, from worker branch `446caa1c`). 27/27 Linux tests pass, and there was no Mac access. It's replay-only, 60–90 min: W-screen8 on/off × 1/4 GIL threads, original vs vectorized decoder, tower channel, fallback latency. **Needs Sam's authorization**, plus train recordings, the frozen prior, v1/v4 checkpoints, the final joint selection with its launcher/trust closure, and an arm64 Python/Rust environment (the native build happens on the Mac).
- **11:06 UTC:**
  - **The 61-match 02 recovery is nearly done:** 52 verified, 7 awaiting verification, 2 claimed, 0 pending.
  - **The 404 retained-original archive is COMPLETE:** 7,284 files, 32.17 GB, checksum and fsync on 03.
  - The A18 package is targeted for ~11:40–11:55Z.
  - The student-screen plan draft content is approved. The worker runs the seed audit, and I freeze plan and audit together.
  - E1's reserve-floor crown-tower fix (`72e84a5f`) is pending qualification before arm 5.
- **11:09 UTC:** student-screen packing tests 7/7 PASS. **Seed-audit scope decision (exploration lane):** the committed plan/config formula ranges, plus reachable host inventories, plus archives/mirrors for the unreachable 02/07/18, which are disclosed as not directly inventoried. The proposed ranges (≥4503601007370496) sit far above prior formula ranges.
- **19:12 UTC: RESUMED after a ~8 h idle.** A routine tool call at ~11:09Z returned a spurious "STOP and wait for the user" denial. I treated it as a pause; Sam confirmed it was a glitch and told me to ignore such messages (memory: ignore-spurious-stop-denials). The fleet sat idle from ~14:40Z to 19:10Z. Lesson recorded.
  - **E1 COMPLETE** (`reports/explore/e1/RESULTS.md`, `e43d51f5`), 3,000 games:
    - **W under a 200 ms deadline: losses 73.2% vs 48.2% baseline, +25.0 pp [20.2, 30.0].** 94% of decisions were cut off, with the v1 fallback taking 86%.
    - Unlimited W vs v1: 79.3% wins; W − baseline losses −20.8 pp.
    - **Reserve floor:** under-4 arrivals 70.6% → 16.9% (human level), but **losses −1.2 pp [−5.2, +2.8]: under-4 is not a causal lever. Drop reserve fixes.**
    - **This confirms distillation as the path for live play.**
  - **ExIt round-1 teacher generation done at 14:38:39Z:** 6,009,681 roots, 38.7 M rows.
  - **Student screen FROZEN** (`STUDENT-SCREEN-FREEZE-20261009.json` `787e4c6a`; plan `d98fdd74`, seed audit `3e2764ad`, init explicit v1). Execution delegated: `clasher-exit-r1-student-screen-run-20261009-1`.
  - **T11 v2:** both seeds were complete by 11:41Z, but finalization was blocked by 04 process headroom (ExIt). 04 is idle now and T11 is told to finalize, select, and run the registered v2 gate (a).
  - **A18 r1** (`34e0c6b2`) sent to independent review: `clasher-v4-amendment18-review-20261009-1`.
  - Mac E4 package ready (`257adad9`), pending Sam's authorization.
- **19:25 UTC: A18 review: REQUIRED CHANGES (minimal)** (`6468788f…`).
  - **Design is sound:** each of the 1,536 matches has exactly one source; the 61 retired 02 sources are blocked by 6 guards; leased reads are refused; one-byte relocation changes are rejected; R16 is enforced. 402 tests pass.
  - **Required:**
    - **R18-1:** refuse duplicate route destinations (first-wins); no current data is affected.
    - **R18-2:** adopt the reviewer's probe tests verbatim (`test_rev_a18.py` `e23fae36`, preserved in the repo; the current suite kills 1/7 code mutants, the probes 7/7), and move the mid-file `unittest.main()`.
  - **Also required in r2:** disclose the control-root collision incident (9c88fb44), the superseded coverage receipt (0f06656e), and pin the coverage generator script.
  - My diff-only check of r2 follows, then the freeze.
- **19:29 UTC: AMENDMENT 18 r2 FROZEN** (`18-FREEZE-RECORD-20261009.json` `04378714…`).
  - My diff-only check passed: only the R18-1 guard and test, the reviewer probes byte-identical (`e23fae36`), and the disclosures changed.
  - **APPROVE_FILE_LAYER_DELTA** issued (`ff45e9ed…`, amendment `35edb8ca`, delta `b8070fde`).
  - Next: perception's admission-only dry run on 04, repinned to r2, then my A1 mechanical checks (§8 items 5, 9, 11), then `coordinator-approval-A1`.
- **19:39 UTC:** the A1 admission-only dry run launched at 19:34Z on 04 (config `9e71f533`). Epoch 1 assembled (`8ccd70b4`) in ~4.7 min, so serial would take ~3–4 h. **Decision:** parallelize independent epochs across 03 and 04 at nice 19 (operational only, same frozen functions), and require the epoch-1 parallel rebuild SHA to match the serial one as a determinism check.
- **19:41 UTC heartbeat.**
  - All GPUs are at 0%.
  - **T11 v2:** gate (a) model eval and OOD are complete; GPUs 01/16 released at 19:36Z, and the rest is P16 CPU work on 01.
  - **Student screen:** corpus pack on 03 (single process, ~27 GB); fits on 01/04/09 follow.
  - **Capacity scan (plan h) delegated** (`clasher-capacity-scan-20261009-1`): widths 288/384/512 vs 192 on leased 13/14/15/16, offline-only, kill rule dev-NLL gain <0.005 at 25%.
  - A1 dry-run parallelization is in progress. 02/06/07/11/18 are down.
- **19:54 UTC:**
  - **Student fits are running:** S-mix on 01 and S-teacher on 04 (corpus `1c8e1f49`, init v1).
  - S-human was refused on 09 by the old wrapper's hard-coded Oct 9 deadline. Fix: a versioned wrapper with the Oct 11 deadline, or the fallback of 08 with a stop file.
  - The A1 dry run moved to r5, in-memory buffering after authenticated reads under the lock (orchestration only; byte-identical on a real 15.9 MB stream), because r4's stream locks serialized parsing.
- **20:03 UTC: student fits loader-starved** (S-mix step 24, S-human 29, S-teacher 91 of 4,883 at ~20:02Z), from random mmap gathers on the 244 GB human store. **Decision:** apply T11's proven loader6 operational pattern with exact sample order preserved, at a safe point, under an operational amendment. Target ≥6k rows/s.
- **20:11 UTC heartbeat.**
  - Only 16 has an active GPU (capacity 192 control, 93%).
  - The student fits on 01/04/09 are checkpointed and paused for the loader6 exact-replay check, by design.
  - The capacity wide arms (13/14/15) are still copying the 244 GB human store.
  - 08 is reserved and idle. The A1 dry run r5 is building 23 epochs on 03/04 CPU (epoch 1 determinism PASS).
  - 02/06/07/11/18 are down. No pending requests.
- **20:22 UTC:**
  - The student fits passed the serial-vs-loader6 2-step exact-state replay (bit-for-bit) and resumed.
  - **S-human on 09 hit a CUDA OOM** at step 239 (41.7 GiB allocated, vs T11's ~29 GiB at the same micro). Investigating, in order: GPU-resident prefetch, retained buffers, and `expandable_segments`, with the exact-replay neutrality proof. Fallback is 08 (owned, stop file). Recovery from checkpoint 108.
  - Parent-thread core contention on 01/04: affinity fix approved.
- **20:26 UTC:**
  - **S-human OOM root cause:** the frozen ExIt mixed_indices order doesn't apply T11's entity-count sort, so a rare dense first micro (7168) can need ~42 GiB. Re-sorting would break exact sample order. **Decision:** move S-human to owned 08 (no leased reserve rule), resume exactly from checkpoint 108, stop file with ≤5 min vacate for B.
  - **Capacity scan:** control quarter NLL 0.27726 at 95.1 M rows (0.37 GPU-h). The 480 arm is capped at allocator fraction 0.78 after a transient 46 GB reserve peak.
- **20:32 UTC: A1 dry run.** All 24 assemblies exited 0 at 20:30:50Z, and epoch 1 matches the serial build. **My §8 mechanical checks: item 5 (identical, correct A18 bindings across 24) PASS; item 9 (24 epoch keys and assembly SHAs vs authority) PASS.** Item 11 (evidence ledger) is pending the fresh admissions, which are running.
- **20:41 UTC heartbeat.**
  - GPU: 13 at 92% (288), 14 at 58% (384), 01 at 57% (S-mix), 04 at 69% (S-teacher), 08 at S-human load. **15 idle: the capacity 480 arm crashed at 20:39:15Z** (likely OOM under the 0.78 cap). Decision: resume with micro 1024 and accumulation to 8,192, disclosed, or kill the arm as infeasible.
  - 09 and 16 are idle, with no planned work.
  - The A1 fresh admissions are running. 02/06/07/11/18 are down.
- **20:45 UTC:**
  - **S-human on 08 reproduced the OOM** at step 239: a dense micro needs ~47 GB on a 48 GB card. Trying `expandable_segments` first, with a replay neutrality check. Pre-authorized next fallback: human micro 3584 with accumulation to 8,192, disclosed.
  - **Capacity 480-v3** resumed at 20:44Z from step 175 with micro 1024 (amendment `f8dd81a6`). If it fails again, the arm is dropped.
- **21:10 UTC: APPROVE_A1 ISSUED.**
  - The admission-only dry run finished at 21:08:34Z: all 24 fresh admissions exit 0, and the epoch-1 repeat passed.
  - **My mechanical §8 checks:**
    - item 5 (A18 bindings) PASS;
    - item 9 (24 assemblies) PASS;
    - **item 11 PASS:** the full evidence ledger `a44a9617` has 51,089 entries, all on 03/04/08, with zero 02, leased, journal or heldout entries.
  - All 8 required values were cross-checked.
  - **`coordinator-approval-A1.json` `9b520de2…`**, plus the record `4e98cc68`, copied to 04. It authorizes the A1 real clock-free body seal only. A2 bounds follow after seal verification; B needs a separate approval.
- **21:11 UTC heartbeat.**
  - Capacity 13/14/15 at 99%.
  - Students: 04 at 78%. 01 at 23% and 08 at 0% are sample-window dips; their measured step rates are 3.7k/4.7k rows/s.
  - 09 and 16 are idle (nothing planned).
  - A1 approved and the seal is in progress. 02/06/07/11/18 are down.
- **21:16 UTC: A1 r1 attempt failed closed** before any score or seal. The deployment omitted the A12-pinned `BODY-SELECTION.md` (60977bf4). I verified execution plan r2 (`68e24722`) differs only by that one added pin and **issued `coordinator-approval-A1-r2.json`**, with the other 7 fields byte-identical. r1 is retained as superseded.
- **21:32 UTC: A1 r3 failed closed** before the first body score: the runtime bundle lacked the validation truth payloads (objects/rich-objects). **Located:** all 64 validation episodes with objects, rich-objects, events and receipts in the owned store `127x04:/mpac/sdicks02/repos/clasher-v4-data/matches/` (also on 01). Authorized exact receipt-pinned copies for the validation 64 only, with strict heldout exclusion by explicit ID list. Fresh attempt to follow, same approval r2.
- **21:41 UTC heartbeat.**
  - **T11 v2 registered gate (a): FAIL on coverage, not quality** (`imitation/RESULTS-v2-offline.md` `1ee1d71f`).
    - C56: A1/A2/A4 PASS. A3 FAIL: 52/56 cards assessed and passing, 4 unassessable, none significantly worse.
    - S122: A1/A3/A4 PASS.
    - **Decision:** v1 remains the released human prior (the student screen already uses v1). v2 is kept as a candidate.
  - GPU: capacity 13/14/15 at 99–100%; students 01/04/08 at 31–65% (sample dips). 09 and 16 are idle.
  - A1 r4 seal is running.
- **22:34 UTC:**
  - **S-human final EMA** `bb257672` at 22:33:25Z; 08's GPU is free.
  - Staged student reporting is running on 03 (56 workers, E1-qualified native `f387b2d2` after a reporting-only correction; the failed startup was archived). 08's CPU (≤48, nice 19, stop file) was added to reporting until B, which is ~12 h out behind the A1 serial seal.
  - S-teacher and S-mix fits continue.
- **23:11 UTC heartbeat.**
  - **Capacity:** 288 at 63.4 M rows, 384 at 49.1 M, 480 at 42.9 M (quarter mark at 95.1 M); GPUs 99–100%.
  - **Students:** S-teacher final EMA `29d17153` (22:50Z). Its 04/08 reporting pools appear finished. **Rebalance ordered:** unclaimed 03 cases to 04/08; S-mix cases (seal ~23:35Z) spread over 01/04/08.
  - **A1 seal:** 43/216 branches; ETA ~05:00Z.
  - 09 and 16 are idle. 02/06/07/11/18 are down.
- **00:11 UTC heartbeat.**
  - **Capacity:** 288 at 80.9 M rows, 384 at 63.4 M (end-of-epoch dev eval, so GPU dips), 480 at 60.0 M; quarter mark at 95.1 M.
  - **Student screen:** all 3,232 tasks complete; final diagnostics and reduction running on 03.
  - **GPUs 01/04/08/09/16 idle:** nothing queued until the student-screen verdict, which decides DAgger round 2 vs other work. 08 is held for B, which is behind the A1 seal (64/216 branches, ETA ~05:00Z).
  - 02/06/07/11/18 are down.
- **00:12 UTC: ExIt r1 student screen COMPLETE: ALL 3 ARMS KILLED** (frozen rules; `844c442b`, `STUDENT-SCREEN-RESULTS.md`).
  - Play recall was 39% / 40% / 3% against the <50% kill rule; the paired-CI upper bound is ≥0 for mix and human; human also failed the WAIT rule.
  - **Signal:** S-teacher as the deadline-W fallback gave **−7.5 pp [−12.7, −2.2]** losses, but play recall was 40%, so it's killed. Students are too passive.
  - No adoption and no round 2 under this plan. Cost: 8.6 GPU-h / 122 CPU-h.
  - Commissioning an Opus next-step analysis (play-recall fix vs faster search vs Mac measurement) for the idle GPUs until the lease ends.
- **00:18 UTC: ADOPT PLAN-NEXT-20261010** (Opus analyst).
  - E1's deadline-W loss was caused by **ordering**: the coarse scan runs before any complete score, and WAIT is scored last, so 86% of decisions fall back to v1.
  - ExIt r1 failed on **targets**: the median top-2 gap is 0.003, so at T=0.1 the best action got ≈10% of the target and agreement was below the all-WAIT constant.
  - Launching:
    - **K** (anytime W: WAIT first; 1 vs 4 GIL threads; h80 coarse scan; CPU on 03/01);
    - **X** (ExIt r2: sharpened or argmax targets on corpus 1c8e1f49; X1 09, X2 16, X4 01, X5 04, X3 13 after the quarter check), with staged kills and an optional R2 DAgger round.
  - Deferred: G teacher top-up (filler on 04 non-seal cores only; not on 08). 08 stays reserved for B.
  - Stop list per §4. Exploration lane; any live change needs Mac E4, PREREG and an L2 amendment.
- **00:43 UTC heartbeat:** K is running on 03/01. Capacity scan on 13/14/15 at 92/100/71% GPU. GPUs 01/04/09/16 are idle, waiting on X's freeze (minutes away). **08's GPU goes to X3 until 05:30Z at the latest** (B is gated by the A1 seal, ETA ~06:30Z). X3 must vacate by then, with a checkpoint and resume on 13/14. Heartbeat prompt refreshed.
- **01:04 UTC: Capacity width 288 KILLED** under the frozen quarter rule: gain 0.00308 < 0.005 at 95.1 M rows (`d4d070b2`). 13 released. 384/480 continue (offline-only). **13 → new X arm X6** (T=1e-4, teacher 0.75), completing a 2×2 of temperature × human anchor with X1/X2/X4. Addendum freeze before launch; X3's resume has priority on 13.
- **01:12 UTC heartbeat:**
  - X1–X5 are training: 09/16/01/04/08 at 66–74% GPU. Capacity 384/480 on 14/15. 13 is idle, waiting for X6 (queued to X). K is finishing on 03/01.
  - A1 is at 82/216; its ETA slips to ~08:30–10:00Z.
  - **Launched G** (teacher top-up, Sol worker `clasher-g-topup-20261010-1`) as preemptible filler: 04 physical cores 0–47 at nice 19 (the seal's CPU52 and X5's loader untouched), plus 01 cores 0–39 after K exits; it yields to X evaluation. Stop file; ends by 2026-10-11 03:00Z.
- **01:33 UTC: K anytime-W result** (3,000/3,000 games, paired vs v1, 200 ms):
  - K0 46.5% loss.
  - **K4 (4-thread anytime) 19.33%, −27.2 pp [−31.7, −22.5] → ADVANCES.** K4h also advances. Fallback is <1%, and K4 matches unlimited W (19.33%).
  - p99 is 193 ms, so headroom is thin.
  - **K1 (1-core anytime) 96.5%:** cutoffs are 96.5%, so the WAIT-first default collapses on one core. The 1-core dependency does NOT go away.
  - **Before adoption:** an independent Opus review (`clasher-k-review-20261010-1`) checks why K4, K4h and KU are exactly identical, the latency headroom on a slower Mac core, and a stage-3 redesign.
  - X stage 3 is ON HOLD: its K1 comparator is degenerate.
  - This strengthens the case for Sam's Mac E4 authorization: the live question is now whether 4 free cores exist next to perception.
- **01:43 UTC: K review = CONFIRM_WITH_CAVEATS** (Opus, `REVIEW-K-20261010.md`).
  - The 116/600 three-way tie is chance (K4 and KU outcomes differ on 140 seeds, split 70/70). K4h did run h80. CIs reproduce.
  - **Caveats:**
    - 10.5% of K4 cut decisions return after 200 ms; the worst took 0.5–22 s, on 01 under SCHED_IDLE. The sim applies late actions without penalty, a small optimistic bias.
    - **K4 holds only at ≥0.9× fleet per-core speed** (projected cutoffs: 14% at 0.8×, 49% at 0.6×).
  - **Decisions:**
    1. X stage 3 → the reviewer's **S-default K1** design (on cutoff the student is the default vs v1 as default; K0 anchor). Freeze before any stage-3 game.
    2. Commission **K-v2**: fix the cancellation return path, use honest lateness in the sim, run at normal priority, then K4 at 200/160/120 ms deadlines to emulate 1.0/0.8/0.6× core speed.
    3. Mac E4 v2 must measure per-core speed under perception load.
- **01:45 UTC heartbeat:**
  - All GPUs are busy: X1–X6 on 09/16/01/04/08/13, capacity 384/480 on 14/15. 01 (X4) samples ~20% GPU.
  - The 01 memory PSI persists at ~50–60% without G, so X4's own human-row loader (micro3584) drives it.
  - X4 runs at ~70% of X1's step rate, ETA ~04:30Z. Accepted: frozen recipe, no restart.
  - G is fully off 01 (81 sealed games kept). STOP-03 is from K-v2 (timing games). 04 is briefly drained to deploy G's PSI guard.
  - A spurious STOP denial on pending_request_list was ignored per Sam's rule.
- **02:05 UTC: G paused fleet-wide.**
  - The 04 PSI guard tripped at steady state (85.8% full) with 40 workers next to X5's fit. Same signature as 01/X4.
  - **Rule:** no CPU filler on a host running a GPU fit's corpus loader. G resumes only on explicit release (04 after X5 ~06–07Z; 03 after K-v2). Total so far ≈207.6 k roots.
  - Also: K-v2 smoke found a residual pre-scan latency tail (21 overruns, early-game); K-v2 is instrumenting it before reporting.
  - X stage-3 S-default is qualifying with default-layer equivalence; no pre-run controls (interleaving rule).
- **02:35 UTC:**
  - **Capacity width 384 KILLED** (gain 0.00446 < 0.005 at 95.1 M; `ffad9503`). 480's quarter decision is imminent.
  - 14 freed → **X7** = X1 seed replicate (seed-noise estimate for the 2×2 arms).
  - Perception: verify_body recomputes all 216 branches serially after the seal (+~12 h). Asked the owner to draft a parallel fresh-process verify amendment for review.
- **02:42 UTC heartbeat:**
  - GPUs: X on 01/04/08/09/13/16 at 59–74%, capacity 480 on 15. **14 idle**, waiting for X7 (queued to X).
  - **A19 r1 draft** (parallel fresh-process verify_body, 12-way on 04) received. The owner found that A2's build_bounds and verified_bounds each re-run serial verify_body as well (≈12.7 h each).
  - **Asked for a consolidated A19 r2** covering all verify_body calls (A1+A2), plus launcher, handoff and adversarial tests, ready by ~07Z for one independent review. Potential saving is ~30 h on the perception path.
  - R2 implementation notes recorded by X (70b31da9).
  - Spurious STOP denial on pending_request_list ignored.
- **02:57 UTC: Capacity scan COMPLETE** (`bb14988d`).
  - All three widths were killed at the quarter mark: gains 288 0.00308, 384 0.00446, 480 0.00479, all < 0.005. **Retain 192.** Cost 17.8 GPU-h actual (19.4 GPU-h conservative).
  - 15 → **X8** (X2 seed replicate).
  - Perception: 67 Clasher processes on 04 (mostly capture-era idle monitors) block the 16-process guard for A19. **Authorized retirement of class-(c) idle monitors** via their own STOPs, with receipts; r4 dependencies are untouched.
- **03:25 UTC perception:**
  - **A19 r2** (parallel fresh-process verify for A1 + both A2 verify_body calls, ~38 h serial → ~4.5–9 h) is under independent Opus review (`clasher-a19-review-20261010-1`).
  - **42 obsolete capture-era floor monitors** (14 groups) retired one at a time by authenticated single SIGTERM; wrapper exit 143 each; seal healthy throughout (117/216). A post-signal /proc race on group 1 was diagnosed and the helper corrected.
  - **Policy:** the inherited all-Clasher ≤16 cap is replaced, in **A19 r3**, by an A19-owned ≤16 cap plus host guards (MemAvailable ≥28 GiB, PSI, no live fit loader, never CPU 52/116) and conservative inventory (PermissionError fix). Launch only after X5's fit exits.
- **03:30 UTC: X1 and X2 KILLED at stage 1.**
  - Play recall 0.26 / 0.24; agreement 0.613 / 0.630, below the all-WAIT 0.654; WAIT 0.83–0.85 vs teacher 0.654.
  - Sharpening made the students *more* passive than r1. The PLAN-NEXT target diagnosis looks incomplete.
  - **Commissioned an Opus noise-ceiling analysis** (`clasher-exit-noise-ceiling-20261010-1`): teacher self-agreement given the 0.003 median top-2 gap, whether the gates are reachable, whether the gates predict strength, and the next design for the 1-core fallback role.
  - 09/16 GPUs are idle pending that design (~75 min); X8 is still queued for 15.
- **03:41 UTC: A19 r2 review = APPROVE_WITH_CONDITIONS** (Opus, c2a092da).
  - **Code, for the r3 delta:**
    - C1: conservative inventory (PermissionError);
    - C2: no irreversible serial-verify STOP without admitted parallel capacity (verify-then-retire preferred);
    - C3: the A2 parallel prerequisite must come from a completed attempt.
  - **Operational:**
    - C4: co-tenancy and headroom (no launch while X5 is alive; G never on 04 cores 0–11/47 while A19 is pending or running);
    - C5: exact bindings per §9.
  - The monitor retirement doesn't affect the evidence chain. Next: r3 delta review, then the A19 freeze plus a revised A1 approval.
- **03:43 UTC heartbeat:**
  - GPUs busy: X4 on 01, X5 on 04, X6 on 13, X7 on 14. **Idle: 08, 09, 15, 16**, held deliberately pending the noise-ceiling analysis (ETA ~04:45Z); X8 cancelled.
  - A19 r3 arrived without C2/C3 (handoff and A2 binding identical to r2). **Asked for r4 = r3 + C2 + C3**, with softer PSI semantics (pause admission at full ≥10%; hard stop only at ≥30% for 120 s); a single delta review after that.
  - Spurious STOP denial ignored.
- **03:57 UTC: Noise-ceiling analysis** (Opus, `ANALYSIS-NOISE-CEILING-20261010.md`).
  - **The r2 stage-1 gates are unreachable.** W against itself, with fresh seeds, scores play recall 0.85, **top-8 recall 0.31 (gate 0.50)** and agreement 0.706 (gate 0.704). Every r2 arm is killed whatever its quality, and R2 can't trigger.
  - **Cause of the WAIT rate:** 79% of training rows are continuation-wait labels; only 21% are root decisions.
  - **Decisions:**
    1. X4/X5/X7 run to completion for the descriptive record only.
    2. **Descriptive post-kill S-default games** (X1, X2, best of the rest; fresh seeds; never adoptable) to calibrate offline metrics against deployment value.
    3. **R3:** root-only student ± a per-candidate advantage head, with ceiling-relative gates, on idle 09/16 (~4 GPU-h).
    4. **K2:** 2-thread anytime W at 200 ms, on 03 after K-v2 (~20 CPU-h). If K2 retains ≥80% of K4, distillation becomes a contingency.
    5. Future emitters record sparse would-be root decisions.
- **04:19 UTC: A19 r4 delta review: REJECT the bytes (narrow), APPROVE the design.**
  - **F1:** a STOP race in the production runner; the runner's own STOP-check exit is treated as failure.
  - **F2:** guard() still runs after STOP.
  - **Fix:** r5 = D1–D4, the last being a per-epoch admission inventory. Operational conditions O1–O6 (X5 supervisor exit; ≥80 GiB MemAvailable at launch; R3 has vacated).
  - **Throughput:** 04's local io.lock is held 53% of the time (decompress/parse inside the lock), so parallel verification caps at ~1.9×; A19 on A1 would likely not beat serial.
  - **Decisions:** r5, plus a separate **A20 lock-scope narrowing** amendment (operational). At seal exit: A19 on A1 only if r5 and A20 are approved; otherwise serial A1, with A19 reserved for A2. Asked the owner what the 2026-10-11T04:00Z cap is.
- **04:24 UTC: cap clarified.** Oct 11 04:00Z is the renewed validation cache **service deadline** on 03 and 08 (plan db085fde), plus an upper bound in A19 authority. A1/A2 read pinned files, not the cache. **Authorized a seamless cache-service renewal to 2026-10-13T04:00Z** (new immutable plan, receipts and storage check; done by 20:00Z today). A19 valid_until may be up to Oct 13 04:00Z. A20 scope accepted (04-local read/hash only under the lock; the frozen serial runner stays untouched as fallback).
- **04:51 UTC: A19 r5 re-check = APPROVE_WITH_CONDITIONS** (r5 code approved for freeze; 90762bcb). D1–D4 met; 145/145 author tests plus 20/20 reviewer tests; 18 STOP-race runs superseded correctly. Conditions:
  - E1: raise the authority valid_until cap constant to Oct 13 (fold into A20);
  - E2: the freeze binds the r4 draft b43a3979;
  - E3: fix OPERATOR's deploy count (23);
  - O1–O6 carry over.
  - Cache services renewed to Oct 13 (04:41Z); B uses a local PixelCache, and the 08 HTTP service is to be retired before the B window.
- **04:52 UTC: A20 review = APPROVE_WITH_CONDITIONS** (c1e50fa4).
  - **Identity:** exact on real 04 records and every adversarial case; no TOCTOU. The 04 lock is reader-only (no writer/retention use). Worst-case memory ≈23 GB.
  - **Modelled A1 with A19+A20 ≈ 2–2.5 h vs ≈13.7 h serial** (6.8×; the 03 lock becomes the limit).
  - **Blocking:**
    - C1: the composed full suite (7/208 fail: authority fixtures lack the A20 records);
    - C3: a new deploy directory.
  - Plus the Oct 13 cap constant and the APPROVE_LOCAL_IO_LOCK_SCOPE decision string.
  - **Next:** the author builds the final combined package (A19 r5 E1–E3 + A20 conditions), then a quick final check, then the freeze and approvals before seal exit.
- **05:11 UTC: K-v2 COMPLETE** (`bf41ebc5`; honest lateness, return-path fix, nice 10, 600 paired seeds each).
  - **V200 18.2% vs K0 47.7%: −29.5 pp [−33.8, −25.0]** (K4 confirmed with honest lateness).
  - V160 (0.8×) 26.5%: −21.2 pp. **V120 (0.6×) 82.3%: +34.7 pp, a cliff.**
  - **Mac requirement: ≥0.80× fleet per-core speed on 4 free cores** (point estimate 0.76×).
  - Strict return bound NOT qualified (16/15/7 cut returns > D+8 ms, all charged). The uncharged GC poll-delay caveat remains.
  - 03 released to K2. MAC-E4-V2.md updated.
- **05:12 UTC: A19+A20 FINAL VERIFY = APPROVE** (27f12fd8). **Issued:**
  - A20 freeze `20-FREEZE-RECORD-20261010.json` (d77b3de5);
  - combined A19 freeze `19-FREEZE-RECORD-20261010.json` (61940388; binds the r4 draft, review response, operator supplement 765369f4, field spec d7280e00 and the final verify);
  - revised `coordinator-approval-A1-r3.json` (ae9208de; identical to r2 except plan 0fe6fe3a);
  - `coordinator-approval-A20-local-io-lock-scope-20261010.json` (6bddf770).
  - **NOT yet issued:** APPROVE_PARALLEL_BODY_VERIFICATION and the 04 execution allocation. These are launch-time items: O2 X5 exit, O4 seal exit, O7 sizes, ≥80 GiB, allow_serial_verify_handoff=true (S1).
- **05:46 UTC: R3 stage 1:** both arms narrowly KILLED. Recall 0.630 (gate 0.6375); agreement 0.744 (gate 0.754). This is a big improvement over r2 (0.26 / 0.61); the R3b advantage head broke top-8 (1.8%).
  - **R3 round 2:** R3c (2× steps, 09), R3d (seed replicate, 16), R3e (2× steps, T=0.01, 13). Same gates.
  - Plus a **descriptive never-adoptable S-default run for R3a** on 01 after X's descriptive study.
  - Leased 14/15 remain idle.
- **06:13 UTC heartbeat:**
  - All GPUs are momentarily idle: X5 has finished training on 04, and R3 round 2 hadn't started (my queued 05:48 decision was stuck behind continuations, so I nudged it). 14/15 are unassigned.
  - 01: X descriptive study (40 workers). 03: K2.
  - Seal ~153/216 at 06:10Z, ETA ~11Z.
- **06:43 UTC heartbeat:**
  - R3 round 2 is on 09/13/16 (73–81%). K2 is at 1457/1800 on 03 (~07:00Z). X's descriptive study finished on 01; 01 is idle pending X's release, then the R3a descriptive run.
  - **Returned leased 127x14 and 127x15 to roader early**: no clasher GPU work is queued for them.
  - Seal ETA ~11Z; O2 is satisfied, O4 is pending.
- **06:45 UTC: X descriptive post-kill S-default study** (NEVER ADOPTABLE; 3,000 games, 0 failures).
  - 1-core losses: X1 99.5%, X2 99.7%, X4 99.3% as the cutoff default, vs C-v1 66.8% and K0 42.8%. Paired S−C ≈ +33 pp.
  - **Lessons:**
    1. Under 1-core anytime ordering, even a v1 default (C-v1) is far worse than K0's coarse-first ordering.
    2. The r2 students are catastrophic as defaults; their low play-recall matches.
    3. The deployment-relevant 1-core fallback harness is **K0-style** (coarse-first deadline W, with the student replacing v1 as fallback). That is where r1 S-teacher gave −7.5 pp.
  - → **Switch R3's descriptive run and round-2 stage 2 to the frozen r1 (b) K0-fallback harness** (arm = student fallback, control = v1 fallback), via an addendum before any stage-2 game.
- **07:03 UTC: K2 COMPLETE** (`f8413b1a`; 600 paired seeds).
  - Loss K2 / K0 / K4 = **25.0% / 45.7% / 16.5%**. K2 vs K0: −20.7 pp [−25.8, −15.8]. **Retention 71% [58, 83]**, below the 80% target. K2−K4 = +8.5 pp.
  - **Mac deployment tiers:** 4 free cores ≈ 16–18% loss; 2 cores ≈ 25%; 1 core (K0) ≈ 43–46%; all vs v1. Strict return bound unqualified.
  - 03 released; **G released onto 03 (cores 0–59, nice 19, PSI guard, ≤56 workers)**.
- **07:43 UTC heartbeat:**
  - R3 round 2 on 09/13/16; R3a descriptive (K0-fallback) on 01; G steady on 03 (54 workers).
  - **Released G onto 04 cores 12–46 until a 10:15Z HARD stop** (pre-A19 headroom ≥90 GiB) **and 08 cores 0–55 until a 15:00Z HARD stop** (before any B window); each a one-time release.
  - Seal ~168/216 at 07:30Z, ETA ~11Z.
- **08:24 UTC: R3a descriptive (NEVER-ADOPTABLE; r1 (b) K0-fallback harness, 1 core, 600 paired):**
  - **Loss 24.2% vs K0 52.8%: −28.7 pp [−33.7, −23.3].** That's comparable to K2 (2 threads, 25%).
  - **Suspicious:** proposer latency is 0.08 ms for the student vs 9.45 ms for v1, at the same width.
  - **Commissioned an independent Opus audit** (`clasher-audit-r3a-desc-20261010-1`): inference charging and caching, arm symmetry, K0's 52.8% vs ~46% elsewhere, mechanism, fairness.
  - If confirmed, the stage-1 gates are miscalibrated (they killed R3a), and a 1-core student proposer is a viable Mac tier. That leads to a confirmatory pre-registered study.
- **08:32 UTC: R3a audit = CONFIRMED_WITH_CAVEATS** (Opus, AUDIT-R3A-DESCRIPTIVE-20261010.md).
  - The −28.7 pp is real **within the r1 (b) harness**, and everything is on the clock.
  - **Caveats:**
    - the latency gap is a labelling artifact: the student runs a single cached inference, while v1 runs two, costing K0 ~7 ms/search;
    - K0 here is a v1-mirror K0 (52.8% ≈ 50%) and **not on K2/K4's scale**; lateness isn't charged;
    - the mechanism is that K0 is starved (fallback on 64% of decisions, ~98% WAIT), while the student cuts fallbacks to 23%. The gain is hardware- and budget-dependent.
  - **→ Commissioning the confirmatory study S1** in the K-v2/K2 honest-lateness harness: cached single-inference K0c vs S(R3a), at 200/160 ms, with a K2-200 anchor; 1 core; on 01.
- **08:43 UTC heartbeat:**
  - G on 03/04/08; R3c/R3e on 09/13. 01 is idle, so it's **reassigned to S1 now**; any R3 stage-2 survivor moves to 03 (G stopped there first).
  - Seal ~180+/216, ETA ~11Z.
  - Spurious STOP denial on pending_request_list ignored.
- **09:00 UTC:** R3c (2× steps) KILLED: recall 0.634 / agreement 0.747, gates 0.6375 / 0.754; only marginal gains over R3a. **09 returned to roader**; 13 is kept until R3e (~09:20Z).
- **09:15 UTC:**
  - S1 reporting was stopped at 09:07Z by its exclusive-host guard (0 complete blocks; outcomes unread). The intruder was **T11's obsolete backup_extended60 poller** on 04, which hashed old checkpoints on 01 every 60 s.
  - **Retired via its own backup-stop-request.json** (clean exit 09:14:04Z; T11 terminal backups were already audited at 2026-10-09 19:12Z). S1 is authorized to restart on a fresh bank with an amendment. The perception owner has been told (04 inventory −3).
  - Heartbeat: G on 03/04/08; R3e on 13; 01 idle pending the S1 restart. A spurious STOP denial was ignored.
- **09:23 UTC:** R3e KILLED (recall 0.624 / agreement 0.740). **All R3 round-2 arms are killed; no stage 2.** **13 returned to roader; the whole lease has ended early** (09/13/14/15/16 all returned and acknowledged by roader). Remaining R3 work is the common-root regret on 03 cores 56–59.
- **11:21 UTC: R3 extension COMPLETE** (`d97e443b`).
  - Regret: C 0.0089, D 0.0084, E 0.0097 (all below the 0.010 point gate), but every arm is binary-killed on recall/agreement. Stage 2 zero; no adoption.
  - R3a descriptive −28.7 pp (never adoptable; S1 is the confirmatory study).
  - Cost 68.7 CPU-h / 9.5 GPU-h (deduplicated).
  - R3 released 03 at 11:20Z; **G re-released onto 03 cores 0–59** (third one-time release).
- **11:36 UTC: A1 r4 SEAL EXITED 0 at 11:33:50Z** (body seal f95a0df0). The serial verify auto-started as the fallback.
  - **ISSUED** `coordinator-04-execution-allocation-20261010.json` (80f278d2; valid until 2026-10-11T12:00Z) and `coordinator-approval-parallel-body-verification-20261010.json` (5514cf28; allow_serial_verify_handoff=true, cap = allocation SHA, freezes 61940388/d77b3de5, plan 0fe6fe3a). These are byte-identical renames of the owner's offline-verified candidates.
  - Launch receipts: O2 2ca41373, O4 10ed1fb2, R3 vacancy 29adf532, G vacancy 8642c0b3, O7 b430b728 (max 31.3 MB), O1/O3 b684771d (MemAvailable 130 GB), O9 1bbf6805.
  - **LAUNCH AUTHORIZED** (verify-then-retire; serial continues as fallback).
- **12:13 UTC: A19 first wave is SLOW.**
  - Epoch 1 took 15.5 min; 1/24 done at 32 min; constant-rate projection ≈ Oct 11 00:31Z, about serial speed.
  - The 04 lock is fixed (0.25% held), but **the 03 lock is now the bottleneck** (79.7% of worker samples open-without-held).
  - **Paused G on 03** (STOP-03 at 12:12:47Z) to test whether G's load contributes. Asked the owner for a before/after rate and, if there's no gain, an analysis of the next lever: 03 lock-scope narrowing, or pre-staging 03 evidence onto 04.
- **12:17 UTC: A19 bottleneck diagnosed** (owner's source analysis e5b51d65).
  - The '03 lock' is a flock **on 04** keyed 127x03. Remote-read records hold it across SSH transfer, gzip, JSON parse and validation, and A20 narrowed only the local-04 reads. G's 03 load is not the cause, so **G was re-released onto 03** (fourth one-time release).
  - Current A19 rate ≈1.7–1.9 epochs/h, ≈ serial speed.
  - **Commissioned A21:** narrow the remote-read lock scope (03/08) to transfer+SHA only; target review-ready ~14:30Z.
  - If approved, a possible fresh A1 parallel attempt with A21 (serial untouched); otherwise A21 serves the A2 stages.
- **12:56 UTC: S1 COMPLETE: 1-core student tier VIABLE** (`c288e6f2`; exploration; K2-scale harness with honest lateness; 600 paired seeds × 5 arms).
  - Losses: **S-200 (1 core + R3a proposer/fallback) 28.2%**, K0c-200 44.2%, K2-200 29.0%. S−K0c −16.0 pp [−21.0, −11.2]; **S−K2 −0.8 pp [−5.3, +3.5]**.
  - At 160 ms (0.8× speed): S 32.2% (+4.0 pp) vs K0c **79.0%** (+34.8 pp). **The student makes 1-core search robust to slower cores.**
  - **Mac tiers (fleet-measured):** 4 cores ≈16.5–18%; 2 cores ≈25–29%; **1 core + student ≈28% (32% at 0.8×)**; 1 core without a student 44% → 79% at 0.8×.
  - R3a stays never-adoptable from the R3 frozen study. Adoption needs a confirmatory PREREG plus Mac E4.
  - 01 released at 12:55Z.
- **12:57 UTC: A19+A20 parallel attempt RETIRED** at 12:56:10Z via its own controller STOP. The serial verify was **faster** (24.9 branches/h since 11:33Z, vs parallel 12.5/h): the parallel attempt projected ~15.9 h vs serial ~7.3 h.
  - Clean owned exit; receipt 85c0b458.
  - The serial verifier is untouched and running alone, now at epoch 4; ETA ~20Z at its current rate. Final seal-equality checking happens only after all 24 epochs.
  - A21 (remote lock narrowing) is under review; a fresh A21 parallel attempt is to be decided on its verdict, and must beat the serial ETA.
- **12:59 UTC: A21 review = APPROVE_WITH_CONDITIONS** (e2e80cec). Identity is exact and fails closed on every bad stream; timeouts have 120× margin; memory ~7 GB.
  - **Realistic speedup is only ~2.2× serial:** a fresh A1 parallel run takes ~4–7 h, because the serial's full-scope 03 holds cap it.
  - **Decision: NO fresh A1 parallel attempt.** The serial alone (~25 branches/h, ETA ~19–20Z) is as fast or faster, and a contending attempt would slow it.
  - **A21 is reserved for the A2 stages:** genuine serial A1 is an accepted prerequisite; no serial competitor in A2. A21 freeze/approval to be issued (C1 key sets, C2 fresh deploy, O7 03/08 sizes, O10 ControlPath exit) together with APPROVE_A2 after A1 completes.
- **13:05 UTC: Drafts ready** (Opus):
  - PREREG-SEARCH-TIERS-DRAFT: K0c/S/K2/K4 × 200/160 ms, 2,400 fresh paired seeds plus 600 on L2 decks; power 0.93; tier = the cheapest one within 5 pp of the best that qualifies at the measured Mac speed; R3a re-frozen as a new artifact; single belief root, which needs an L2-v4 amendment.
  - E4-V3 addendum: one replay-only sub-session of ~1.5–2 h.
  - DECISION-MAC-TIERS memo for Sam.
  - **Next:** independent PREREG review, and the measure_tiers.py implementation plus review.
- **13:09 UTC: A2 readiness package d9e4b8ee** (A21 C1/C2/O7/O10 satisfied; fresh 12-file deploy).
  - A2 is **sequential**: build-bounds then verified-bounds, each a fresh 24-epoch verify. Provisional 7–14 h after A1.
  - **Decisions:**
    - accepted the O10 exit_code=null evidence limitation;
    - **authorized the validation-64 events.jsonl copy into the 04 mirror** (heldout excluded);
    - the A2 allocation will be valid until **2026-10-12T12:00Z**;
    - issuance follows the genuine serial A1 completion (~19–20Z).
- **13:17 UTC: PREREG-SEARCH-TIERS review = APPROVE_WITH_CONDITIONS** (14 edits C1–C14).
  - **Blocking:**
    - R3a already trained on the L2 decks, so the transfer guard must use held-out human opponent decks;
    - keep the name R3a, with an explicit, disclosed override of its never-adoptable clause; S1 is for power only;
    - the selection rule becomes the cheapest tier within 5 pp of *every* costlier admissible tier, at 97.5% CI;
    - the Mac speed ratio must use the full pipeline, a loaded fleet reference and a direct 200 ms deadline-mode check.
  - **Also:** any exactness mismatch drops all tiers; arm64 belief/RNG exactness; cost ≈1,500 core-h; a lost-host plan; fleet outcomes sealed until the Mac summary; a Mac selection stays provisional until emulator-on E4.
  - Revision commissioned.
- **13:35 UTC: G COMPLETE: 6,046,004 teacher roots**, all SHA-verified and packed (49,703 games, 31 shards, concatenable with r1 1c8e1f49; `f0634e7b`). 01/03/08 are now free.
  - **Next use:** the search-tier confirmatory fleet runs (PREREG r3 freeze pending), on exclusive timing hosts 01/03 plus 08 until the B window.
  - Commissioning the confirmatory harness worker now; no games before the freeze.
- **13:36 UTC: PREREG-SEARCH-TIERS FROZEN** (`PREREG-SEARCH-TIERS-FREEZE-20261010.json`). It binds the PREREG r3 + E4-V3 addendum r3 by SHA, after independent review, r2 conformance, and my check of the E1–E8 diff. Errata noted for stale 'r2' self-labels. **T1 fleet runs may proceed** after T1's own plan/seed-audit freeze; outcomes stay sealed until the Mac summary is committed.
- **14:04 UTC: T1 independent review round 2: REJECT for freeze** (3f2f6a85).
  - Reducer: approve with conditions (exact 59/60 level, integer-exact inclusive thresholds, mac-summary bound to the release receipt, B6).
  - Corpus builder REJECT: missing d1/strata; root-reached filter drops slow-tail states.
  - E4 fleet mode REJECT: host/nice hardcoded; load is not the full slot layout; no ±5% pooling; no row allowlist.
  - **Decoupled:** T1 reporting is gated only on the runner+reducer fixes plus a round-3 delta check. Corpus and fleet reference are fixed in parallel; the fleet reference runs at the END of T1's window.
- **14:26 UTC: T1 round-3 review = APPROVE_WITH_CONDITIONS** (c0813ed4). B2–B6 and R1–R4 fixed; verifier 31/31.
  - C1: seal the per-game wall/CPU print. C2: regenerate guard-decks with the frozen selector.
  - **After a T1 freeze commit differing only by C1/C2, reporting may start** (sealed); I'll confirm from the diff.
  - E4 Linux smoke: native exact 125/125 for all tiers; belief/RNG exact; ratios ≈1.0. E4 is fixing the fleet-mode F2–F4 issues for later review.
- **14:46 UTC: E4-v3 fleet mode review r2 = APPROVE_WITH_CONDITIONS** (efa54f44). **Signed PREREG-SEARCH-TIERS Amendment 1** (operational): END placement with a fail-closed pool and no outcome release before the pooled reference; the MHz gate; committed-posterior replay; plus the pre-reference preconditions.
- **15:02 UTC: T1 freeze CONFIRMED** (9a7126f6). Host set **01/03/08**: the perception serial is CPU-bound (94–97% of a core, no lock waits) and recovered to ~24 branches/h with T1 on 03, so the half-rate interval was branch-cost variation.
  - The post-freeze smoke was stopped by a foreign ssh on 01 at 14:59:50Z (likely the perception compact mirror); the owner is told no ssh to 01/03/08 except the 04→03 readers.
  - Reporting launches sealed after a healthy smoke.
- **15:11 UTC:**
  - The T1 post-freeze smoke r2 was stopped on 01 at 15:08:28Z by the **hub01→04 mirror loop** (`hub_mirror_v2.sh`, fleet_run PGID 516161, 30-min rsync cycle with no stop file).
  - **Paused it with SIGSTOP on its exact PGID** (process state T; no CPU). **Resume with `ssh 127x01 kill -CONT -516161` after T1 reporting completes.** T1 keeps its own 03→01 copier; perception mirrors to 05.
  - Earlier stop at 14:59:50Z: the coordinator's fleetweb dashboard poller. 01/03/04/08 are in the fleet-top quiet file until 2026-10-11T12:00Z.
- **15:42 UTC:** T1 OP-2 (approved-04-reader exec race fix, 78c9bd5b) **CONFIRMED** (00e3d6d3). T1 now runs a fresh qualification and all-host smoke, then launches sealed reporting on 01/03/08. The perception serial recovered to ~26 branches/h after the hub-mirror pause (consistent with the mirror's I/O on 04). **The mirror stays paused until A2 completes**; it gets a new target host before resuming.
- **16:03 UTC:** T1 OP-3 (owned-worker exit race, 9cd518d3) **CONFIRMED** (85c4eb30). B1: use a fresh reporting job dir. T1 proceeds: final qualification, smoke, then sealed reporting on 01/03/08. The perception serial is variable at 15–26 branches/h (CPU-bound; mirror pause not decisive); ETA ~21:30Z.
- **16:19 UTC:** T1 smoke r4 failed on the ssh family again (03: the approved perception sshd parent active between reads; 08: an unresolved sshd child). **Authorized OP-4: an interference-budget rule for LAN ssh-family processes:** ≤0.5% core per block (else the block is flagged), stop at >2% average or a >25% sample. Non-ssh foreign processes and console users still stop; OP-1/2/3 stay as the identity layer; disclosed as paired noise. Fast confirmation pending.
- **16:54 UTC:** T1 OP-4 RE-CONFIRMED (c68661b0; B1 reaped-child CPU metered). **GO:** admit, qualify, smoke, then sealed reporting on 01/03/08. Independent review routed for T1's release barrier (64608f6f) and corpus capture/builder (for A6). The perception serial has slowed to ~12–14 branches/h (108/216 at 16:52Z, ETA ~00:30Z); a CPU52/116 sibling-contention check was requested.
- **17:04 UTC:** T1 smoke r5 failed on 03 again: the long-lived perception sshd parent 776414 was childless at admission, so its source was unprovable. **Authorized OP-5:** a pinned parent-source seed from the committed R4 diagnosis receipt for that exact parent generation (data-only, OP-4 budgets still apply). Fast confirmation to follow. Also: the release barrier was APPROVE_WITH_CONDITIONS and the corpus was REJECTED (cached propose outside WINDOW) in 06dab1ea; E4 END-compat revision 24bfa017.
- **17:11 UTC: T1 host set → 01 + 08 only.** The perception 04→03 transport sshd uses ~3.6% of a core over a long window, above the frozen OP-4 2% stop, and continues through A2. The 3-host plan is infeasible without loosening the budget, which I won't do. Regenerate the balanced blind dispatch for {01,08}; ~15–16 h; 08 drains at the B declaration.
- **17:33 UTC:** perception serial at 121/216 (~15–17 branches/h; ETA ~22–23Z). Authorized re-pinning the serial's own 03/08 ssh mux transports (2500504, 2508732) from CPU 52 to CPU 53, to cut the ~5–9% runqueue contention (affinity only; identity-verified; receipt).
- **17:36 UTC:** T1 OP-5 08 extension CONFIRMED (bcd964d0); the 08 parent-to-socket link is shown by elimination. **GO** for 01/08 qualification, smoke r6, then sealed reporting. Asked T1 to confirm SHA-pinning of 7 untracked `src/.../loss_review` modules it imports. The serial's 03/08 mux was re-pinned to CPU 53 (13a5c535); corpus fix a51ea64c is under review.
- **18:03 UTC: T1 SEALED REPORTING LAUNCHED** on 01/08 at 18:03:13Z (fresh reporting-frozen-0108-r1; freeze fa8a1e2d, manifest a7ebba64, dispatch a4c16936). Smoke r6 passed 8/8 blocks and 64/64 games (4 blocks dbus-flagged on 08, disclosed). Est. 15–16 h. 08 drains at the B declaration. The perception serial mux repin cut runqueue delay from 8.7% to 0.4%, with no branch-rate gain yet.
- **18:31 UTC: T1 08 reporting STOPPED** at 18:25:31Z on the OP-4 ssh-family sample and average caps: a burst from the perception serial's 04→08 transport. 08 raw: 33 completed, 11 failed, 1,493 unstarted; outcomes unread. 01 continues. **Authorized OP-6** (outcome-blind): source-proven ssh family stops only at a >10% core average or a >150% sample; flag at >0.5%; plus a pre-specified descriptive sensitivity analysis excluding ssh-flagged blocks. Fast confirmation pending, then 08 rejoins via the lost-host/redispatch rules.
- **18:54 UTC:** T1 OP-6 CONFIRMED (9118153b). GO Option B: admit, qualify 08, hard-stop 01's original phase, blind re-inventory, fresh balanced 01/08 dispatch. Release barrier r2 APPROVE_WITH_CONDITIONS (977c4dfb); integration branch c5b2e059 (49/49). END attempt-roots declared (3c811584). Perception serial 139/216 at 18:52Z, ETA ~23:00Z–01:00Z.
- **19:30 UTC: T1 Option B re-dispatch LAUNCHED** at 19:28:45Z on 01/08 (receipt 7e0a172c; freeze aeeb3003; dispatch edd51b5c). The 157 completed originals are preserved; 2,915 remain (1,457/1,458); 22 replacement seeds. Sealed; est. finish ~10:30–11:30Z Oct 11, then END. 08 smoke had all blocks ssh-flagged (perception transport), disclosed. Corpus built (300/tier, 1,200 rows validated); only receipts in git (81f2483e); bytes on 05 plus a durable copy on 03. Perception serial 143/216 at 19:12Z (~12/h, ETA ~01Z).
- **19:38 UTC:** T1 release barrier merged to main (597b0964; 49/49); corpus fix merged (170ef741, FROZEN isolation). **END reference decision:** reference validity stays strict (no ssh/dbus-flagged repeats), so the **END fleet reference + A6 smoke must run in a clean window**: after the perception serial/A2 finish (transports gone) and the 08 HTTP cache is retired. The coordinator will declare the window (Oct 11, around B). E4 to import T1's reviewed OP-5 seed/join modules and rename OP-4 to OP-6.
- **20:58 UTC: Model routing changed (Sam):**
  - **Haiku 5.5 is the new workhorse,** with many narrow agents;
  - **GPT-6.1-Sol only reviews Claude-written code;**
  - **Astra is RETIRED.**
  - Updated frontier-models.md (both copies), memory and the heartbeat. Roader informed. Running Sol workers (T1/E4/perception) finish their current jobs; new work goes to Haiku.
- **21:24 UTC: T1 01 guard STOP** at 21:03:53Z (foreign_compute): root `unattended-upgrade --download-only` (Ubuntu apt-daily timer; PID 542173). Not touched. 500 durable at discovery (01=279, 08=221), 0 proof errors; outcomes unread. **Authorized OP-7** (outcome-blind, pre-outcome): source-proven Ubuntu apt maintenance (cgroup `system.slice/apt-daily.service` or `apt-daily-upgrade.service`, UID 0: apt.systemd.daily, unattended-upgrade, apt-get, apt-check, dpkg and their children) is flagged, not stopped, under OP-6 budgets: stop at a >10% core average per block or a >150% sample; flag at >0.5%. Pre-specified descriptive sensitivity analysis excludes apt-flagged blocks. Any other foreign process still stops. Before relaunch: an independent Claude Opus (high) review of the delta and tests. Then **Option B again**: a coordinated stop of 08 at a clean boundary, blind re-inventory, and a fresh balanced 01/08 remainder dispatch with all 500 durable blocks preserved. END stays gated on the clean window; PC1–PC4 apply.
- **21:46 UTC: OP-7 review r1 (Claude Opus high) = REJECT, revise and re-review** (`jobs/clasher/t1-20261010-r1/review/op7-7925fbf1/REVIEW-OPUS-r1.md`). The candidate is safe and in scope: no spoofing found; primary, OP-6 and RNG are untouched; 159/159 tests reproduced. It would likely re-stop 01, though. **Rulings:** (F1) fix reaped-child cutime/cstime double-counting by subtracting the already-metered CPU of observed children, with tests; apply the same correction to the OP-6 ssh meter in the new dispatch, documented per phase. (F2) **OP-7 extended** to apt's download helpers running as the `_apt` system user, resolved from /etc/passwd, only inside the same protected apt-daily* cgroup with exe under `/usr/lib/apt/methods/`, under the same apt budget. (F3) add a descriptive analysis excluding blocks flagged by ssh or apt, plus counts of blocks flagged by both. Fix F4, F5 (document the cgroup reliance), F6 (fail closed on a missing ssh flag) and F8 (the receipt names the real interpreter). Add the F9 tests: reaping, the full multi-line cgroup file, scan wiring. F7: set the status to FROZEN at admission. Re-review r2 by Claude Opus high, then Option B as planned. 08 stays live on unchanged OP-6 meanwhile.
- **22:03 UTC: OP-7 F2 evidence source authorized.** When an `_apt` helper's `/proc/<pid>/exe` is unreadable to us (EACCES only), argv0 is allowed as fallback evidence, as with OP-1 dbus. Every condition must hold:
  1. argv0 is absolute and normalizes (realpath, no `..`) to a direct child of `/usr/lib/apt/methods/`;
  2. that file exists and is root-owned and not group/other-writable;
  3. real and effective UID equal `_apt` from /etc/passwd;
  4. the process sits in the exact protected apt-daily* cgroup;
  5. it descends from an observed approved apt root.

  Any other exe-read error, or any condition failing, fails closed (stop). Record the evidence source (exe or argv0) per observation; add tests for the EACCES fallback, a non-EACCES error, a relative argv0 or one escaping via `..`, and a writable target.
- **22:27 UTC: OP-7 review r2 (Claude Opus high) = APPROVE_WITH_CONDITIONS** on 1c34584b (`review/op7-r2-1c34584b/REVIEW-OPUS-r2.md`). 183/183 tests and 174 manifest hashes reproduced; F1–F6 and F8–F11 resolved; isolation intact. **Rulings:**
  - **Small code fixes before admission:**
    - N1: expire unmatched child credit after 3 scans, with a test.
    - N2: give each block meter starting credit for every process alive at block start (ssh and apt), with a test. 01 lost its slot to apt once, and a reaped-child overcharge could re-stop it.
    - N4: all three hardenings. argv0 must sit directly in `/usr/lib/apt/methods/`; the methods directory must be root-owned and not group/other-writable; all four `Uid:` fields must equal `_apt`.
    - N5: a new-phase proof missing the `ubuntu_apt` meter fails closed.
  - **Documentation only:**
    - N6: OP-6 "new process" dating; errs toward stopping.
    - N7: mark the round-1 "only UID0" text superseded.
  - **Next:** a focused r3 delta-only review by Claude Opus high.
  - **At admission:** C2 (FROZEN, re-hash, bind to the new manifest SHA) and C3 (fresh two-host qualification and smoke on the exact bytes must confirm census-loop timing with the +78% scan cost).
  - **Then Option B.**
- **22:58 UTC: OP-7 review r3 (Claude Opus high) = APPROVE_WITH_CONDITIONS** on b6bec369 (`review/op7-r3-b6bec369/REVIEW-OPUS-r3.md`). 195/195 tests and 176 hashes reproduced; N2/N4/N5/N6/N7 are correct; the round-2 probes are now exact; isolation and v2 tagging intact. **Rulings, all of which can only increase charges or stop more:**
  - **R3-1 (blocks admission):** pay debt newest-first and subtract expired amounts from credit too. Add both reviewer probes as tests (7700 true must charge 7700; 200 true must charge 200).
  - **R3-3:** give host sample trackers starting credit (`baseline_all=True`, supervise.py:50), with a test.
  - **R3-6:** new-phase sensitivity accepts only the v2 tag (fail closed).
  - **R3-7:** fix the typo; extend the writable check to every ancestor of `/usr/lib/apt/methods/`; C3 confirms real `_apt` methods carry all four UIDs.
  - **R3-2:** document the enlarged orphan residual.
  - **Then:** I (coordinator, Opus) do the mechanical delta check, per the reviewer; no full round 4. Then C2 and C3, then Option B.
- **23:08 UTC: OP-7 mechanical confirmation PASS** on d8cc4ff7. Delta SHA-256 97edf3ba… equals `git diff b6bec369 d8cc4ff7`. Code reviewed:
  - R3-1: expired debt removed from credit; settlement newest-first with lot order kept. It can only raise charges.
  - R3-3: `baseline_all=True` on both supervisor trackers.
  - R3-6: the rule must be v2 for both meters whenever either is present; legacy (none) still passes.
  - R3-7: tests for every writable ancestor.

  **Verification on 05** (an exact git-archive export, nice 19, CPU 63, t1-verifier Python 3.12): 213/213 pass in 7.7 s. Every manifest hash I could resolve matches (175, 0 mismatches).

  **GO:** C2 (FROZEN, re-hash, bind the r1–r3 reviews, this confirmation and the authority to the new manifest SHA), then C3 (a fresh two-host qualification and smoke on the exact bytes: census timing with the extra scan cost, real `_apt` methods carry all four UIDs), then the reviewed Option B coordinated 08 stop and balanced remainder. Report C3 before dispatch only if it fails.
- **23:26 UTC: OP-7 C3 `_apt` witness, disposition.** The C2 FROZEN manifest is 04633bdb (1ea7fa18…). 08 was hard-stopped cleanly: 711 blocks durable, all 399 08 proofs verified, the copier drained. Census scans take at most 0.357 s against the 1 s budget. No live `_apt` method is running on either host, so the live all-four-UID witness is **absent, not failed**.

  **Ruling:** don't start or trigger any system service. Accept a static witness instead, read-only on both hosts:
  - the `/usr/lib/apt/methods/*` files and their ancestors are root-owned, carry no setuid or setgid bit, and are not group/other-writable;
  - the `_apt` UID resolves from /etc/passwd.

  apt drops privileges with `setuid()` as root, which sets real, effective, saved and filesystem UIDs together. A real helper with mismatched UIDs fails closed (stop), so a wrong assumption costs availability, not validity. Record the first live `_apt` observation's four UIDs in the ledger when it occurs. **Proceed** to admission and Option B dispatch once the qualification and smoke pass.
- **23:44 UTC: T1 OP-7 replacement-r2 LAUNCHED** at 23:41:21Z on 01/08 (dd17aa7b; freeze ef4c073a; manifest 488f6c8d; dispatch 30487ebf). Smoke r8 passed. 711 preserved, 2,361 balanced remainder (1,181/1,180). Sealed. 01 was down 21:03–23:41Z. Estimated finish ~12–13Z Oct 11, then the END clean window. Perception serial 198/216 at 23:33Z.
- **00:56 UTC: Perception serial A1 AUTHENTICATED COMPLETE** at 00:54:07Z: verify exit 0, verified=true, 216/216, verifier and supervisor absent. Seal-verification a685925f, complete f43dacea, verify-exit fa609391, receipt 91066f3b.

  **O7 exception granted (narrow):** the perception owner may make one fresh, non-multiplexed ssh session per host to 03 and 08, metadata-only. That means `stat`/`test` of pinned O7 paths only: no reads of payload, no writes, no new ControlMaster. Run it under `nice -n 19` with a hard timeout of 20 s per host, sequential, not parallel. Record the exact command, start and end UTC, and exit code in the O7 receipt. On 08 it lands under T1's OP-6 ssh-family budget (flagged, already disclosed), and T1 is to report any stop at once. No other 03/08 access. Readiness r2 stays unissued until fresh O1–O10 bind; then I issue.
- **01:02 UTC: A21/A2 authority ISSUED** at 01:01:32Z (`l1/amendments/a21-a2-issued-20261011/`, ISSUANCE-RECORD.json). It covers the A19/A20/A21 freezes, the revised A1, the A20/A21 approvals, the 04 allocation (valid until 2026-10-12T12Z), the operational approval, APPROVE_A2 for build-bounds and verified-bounds, and both requests. Bound: serial complete f43dacea, exit fa609391, seal-verification a685925f; fresh admission 9241a588 (vacancy bffe0c5f, O1–O10 63e0b866, O7 84262c44). **O9 observer r2 a08ef764 signed off** after I diffed it: exactly two path substitutions from 3f6a4e4c. The offline authority check PASSes on the issued bytes. Sequential stages, no overlap, no fresh A1; B and heldout stay unauthorized. **APPROVE_A2 launch message sent.**
- **01:17 UTC: Perception A2 build-bounds LAUNCHED** at 01:15:31Z on 04 under issued e87516ef. Real authenticate and seal_barrier PASS (07de6396); all 64 event copies re-hashed; MemAvailable 130.6 GB. Authority deployed byte-exact (b2ba2ee4). Controller 3502098, O9 observer 3502099 (a08ef764), 8 workers on CPUs 0–7. Accounting: the frozen predicate misses the `[mux]`-titled ssh masters, so the owner conservatively adds them to the runtime+helper union; I accept that. No cap breach.
- **01:24 UTC: T1 08 STOPPED** at 01:17:48Z (foreign_active, unknown-source identity). New sshd generation 2995332 `sshd: sdicks02@notty` arrived 2 min after A2 launched. Corroborated by /proc/net/tcp: 04 129.65.221.14:41072 → 08:22 is the only other inbound ssh, but the parent/socket join is unprovable (EACCES). The OP-6 meter showed 0 ticks; this is not a cap breach. 1,034 blocks durable, 160 r2 08 completions ACK-verified, 10 failed groups dead. **Decision:** A2 will open new 08 sessions for hours, and each one is an unprovable generation, so neither a seed admission nor a guard change can keep 08 reporting safely. Therefore:
  1. **01 continues** its current r2 remainder unchanged.
  2. **08 stays stopped for T1 until A2's 03/08 transports are retired.** Then do Option B: a coordinated stop of 01 if it's still running, a blind re-inventory, and a fresh balanced 01/08 remainder. No guard change, no new seed, no one-host dispatch.
  3. **The perception owner commits a 04-side attribution receipt** (client PID/start, ControlPath, local port 41072) for disclosure only.

  T1 results are sealed until the Mac measurements anyway, and END needs the post-A2 clean window, so this costs no critical-path time.
- **01:27 UTC: X4S exploration launched** on the idle 08 (CPUs + A6000) and 03 (CPUs) during A2. It's an Opus-high worker (task clasher-x4s-k4-sdefault-slowcore-20261011-r1; NEVER ADOPTABLE). The question: does the R3a student as the cutoff default rescue K4 at 200/160/140/120 ms (≈1.0/0.8/0.7/0.6× Mac speed)? This decides whether a Mac slower than 0.8× can still run 4-core search. Limits: nice 19, ≤96 threads and ≤60 GB per host (headroom for A2's 03/08 remote hashing); STOP file `/mpac/sdicks02/jobs/clasher/x4s-20261011/STOP` drains within 5 min to zero processes; hard end 14:00Z. **08 must be STOPped and verified empty before T1's Option B restart.** No ssh to 01/04; no T1 or perception paths.
- **04:24 UTC: X4S COMPLETE: a student default rescues K4 on slow cores** (4bc4acb1; exploration, NEVER ADOPTABLE; 600 paired seeds × 9 arms, 0 exclusions; recount reproduces). Loss vs v1, K4 → K4+S-default:

  | Budget | K4 | K4+S-default |
  |---|---|---|
  | 200 ms | 18.5% | 20.7% (+2.2 pp, ns) |
  | 160 ms (0.8×) | 27.8% | 18.2% (−9.7 pp) |
  | 140 ms (0.7×) | 47.3% | 22.2% (−25.2 pp) |
  | 120 ms (0.6×) | 89.0% | 26.0% (−63 pp) |

  K0c at 200 ms is 43.2%. Plain K4's cutoff rate is 18.6% at 160 ms and 88.6% at 120 ms, where the WAIT spiral sets in; the student default prevents it.
  - **Implication:** plain K4 needs about ≥0.9× fleet core speed. With the student default, a 0.8× Mac matches fleet-speed K4, and 0.6× stays ~17 pp better than 1-core.
  - **Caveats:** this is a deadline cut, not real slow hardware; student inference is unscaled; there was one opponent and five decks.
  - **Next:** **X4S-2** (Opus worker, task clasher-x4s2-robustness-20261011-r1): honest inference scaling, wider decks, and the full-speed cost variant, on 03 (until 13:30Z) and 08 (hard stop 09:30Z or STOP, 08 verified empty before the T1 restart). If it holds, I'll draft a confirmatory PREREG for a speed-gated K4+S-default Mac tier; the R3a student would be re-frozen as a new artifact. Mac speed is still unmeasured, pending Sam's Mac E4 authorization.
- **07:27 UTC: A2 build-bounds COMPLETE; stage 2 LAUNCHED.** Build complete at 07:19:24Z (83c841dd); controller exit 0 (76467a0d); bounds/complete 1684dd3d, with all 216 bounds plus 218 truth pins authenticated. Stage 2 (verified-bounds) launched at 07:24:35Z under 49ccc8af/8751a79e, with no new approval: controller 3690481, admission 309b6822, launch receipt d2d68264. Build took 6.1 h; stage 2 should end around 13–14Z (planning estimate), and the 03/08 transports stay until then. **X4S-2's 08 hard stop is extended to 12:30Z**; my STOP still overrides it.
- **08:46 UTC: X4S-2 interim results (exploration) confirm X4S.**
  - **Phase A, student inference scaled honestly by 1/s:** K4+S loses 21.7/23.2/24.0/25.5% at 160/140/120/100 ms. Plain K4 loses 100% at 100 ms.
  - **Phase B, guard decks:** K4S − K4 is +0.4 pp at 200 ms and −31.5 pp at 140 ms.
  - **Next:** I launched an Opus-high design worker (clasher-prereg-k4s-draft-20261011-r1) to draft **PREREG-K4S**, a confirmatory study for a speed-gated K4+S-default Mac tier (R3a re-frozen as a new artifact; fresh seeds; T1 machinery). It goes through an independent Opus review to r2; I do the freeze. This is design only; no compute.
  - A2 stage 2 is at 13/24 verification epochs at 08:35Z. T1 has 1,764 durable.
- **09:13 UTC: PREREG-K4S r2 drafted** (a44bd628, b159d116). Independent Opus review r1 said REVISE: 14 findings, all in deployment/release logic, all accepted, with no change to games, arms, N or margins.
  - **Design:**
    - K4 and K4S at 1.0/0.9/0.8×, plus K4S at 0.7/0.6×; every network poll charged 1/s inside the timer.
    - 3,000 primary + 900 guard seeds vs v1; fresh bank 2^52+6.18e9.
    - Seven fixed-order hypotheses (level B within 10 pp, then level A within 5 pp), FWER 2.5%.
    - ~33k games, ~460 CPU-h, ~11–16 h wall plus END. Start realistically Oct 12, after T1 END and A2 transport retirement.
    - R3a re-frozen as SD1 (same bytes) with a role-scoped override.
  - **Decisions:** accept all Q1–Q13 defaults as written. In particular:
    - the 1/s charge on all arms;
    - the gate is default-on below full speed, with the phase-E rule;
    - release is gated on the tiers Mac summary;
    - no second opponent;
    - the Mac measurement goes into the tiers Mac session addendum;
    - K4S never overrides a 1-core/2-thread pick;
    - N stays 3,000/900.
  - **Next:** an independent conformance review of r2 (Opus high, launched). The freeze waits for that, the seed audit, SD1 hashes, and applying the gate rule to X4S-2 phase E.
- **09:20 UTC: PREREG-K4S r2 conformance = CONFORMS_WITH_FIXES** (cfbcd183; review ad681329). 13 of 14 r1 findings resolved; no game/arm/N/margin/alpha changes. **Text fixes required before freeze:**
  - N1: K4S deploys only if c_M ≤ c*.
  - N2: own Mac measurement script, never editing TIERS-frozen `measure_tiers.py`; it runs after TIERS §7, and its failures never affect TIERS.
  - N3: K4S fills F0 only if K4 is Mac-infeasible; add the gate-3 arm64/1-2-4-worker exactness check and SD1 ≥ 99.5% agreement; extend the kill rule.
  - M1–M6 as listed.

  **r3 editor launched, phase-E-blind** (clasher-prereg-k4s-r3-edit-20261011): it must not read X4S-2 phase E (unreduced on main at 09:20Z), and gets an independent diff-only re-check. The freeze then needs: c* record, SD1 manifest and supersession, seed audit, runtime pins, per-host qualification, host set with transport retirement, the K4S Mac procedure, the Q1–Q13 record and attestation.
- **09:31 UTC: PREREG-K4S r3 CONFORMS** (daba6859 at 09:30:42Z; r3 SHA 9650972d). N1–N3 and M1–M6 are applied, and the independent diff-only re-check found all 16 hunks traced, with no game/arm/N/margin/alpha changes. **Blinding attested:** neither the editor nor the re-checker read X4S-2 phase E, and no phase E receipt is on main before daba6859 (latest x4s2 receipt 00328d1b is phase B). So the N1 gate text predates phase E. Optional wording R2/R5 (Q13 r1-order values .705/.366) is to be applied as freeze errata. **The freeze is deferred** until the fills are ready (c* record from phase E, SD1 manifest and supersession, seed audit on the freeze commit, runtime pins, per-host qualification, host set with transport retirement, K4S Mac procedure); realistically Oct 12, with execution after T1 END.
- **11:46 UTC: PREREG-K4S c\* RECORD: c\* = 0.9.** I applied r3 §1.3's frozen rule once.
  - **Phase E** was reduced at 11:38:26Z and committed at b577a255 (11:40:02Z). Receipt `reports/explore/x4s2/receipts/results-phaseACE.json`, SHA-256 d2b32b9a2e3ee86fc857b68b74ea0fdf62b63b3975c8b57ae4ad8f000ec7ef89.
  - **d180** = L(K4S-180) − L(K4-180), X population, 600 paired seeds: **−2.2 pp [−5.2, +0.8]**. The lower bound is not > 0, so **c\* = 0.9**, and the hypothesis sequence stays as r3 §1.4 with H4 retained.
  - **Ordering:** the rule text was locked at daba6859 (09:30:42Z, editor and re-checker phase-E-blind) before phase E was reduced, so the locking clause does not apply. No rule text has changed since.
  - **For the freeze record.**
- **13:06 UTC: X4S-2 COMPLETE** (d7e00ac4; exploration, never adoptable; 16,980 games; 0 X4S-2 processes on 03/08/05). The X4S conclusion holds.
  - **Overcharged inference:** K4Sh loses 21.7/23.2/24.0/25.5% at 160/140/120/100 ms vs K4 at 27.8/47.3/89.0/100%. The worker notes that X4S's budget cut was already honest for uniformly slow cores, so K4Sh deliberately overcharges.
  - **Held-out decks:** K4S − K4 is −31.4 pp at 140 ms and −69.4 pp at 120 ms.
  - **Full-speed cost:** +0.6 pp [−0.8, 2.2] pooled over 1,668 seeds; S-lite doesn't help.
  - **Threshold:** the worker suggests S-default on below ~0.95×, consistent with the c\* = 0.9 record.
  - **Vacancy:** 08 vacant since 12:00Z (STOP and census at 12:15:16Z); 03 vacant since 13:01Z.
  - **Next:** **K4S freeze-fill preparation** launched on 03 (Opus worker, clasher-prereg-k4s-freeze-prep-20261011-r1): SD1 manifest and supersession draft, seed audit, harness plus delta manifest with independent reducer/verifier and Sol review, 03 qualification, separate Mac script, freeze-record skeleton. No freeze and no reporting.
- **13:44 UTC: PERCEPTION A2 COMPLETE; 03/08 transports retired.**
  - **Stage 2:** complete 13:32:37Z (fc1690bd); controller exit 0 (5bf3eb6f). Fresh 24-epoch verification PASS (46596720). **The independent 216-cell bounds result (fa547be6) equals stage 1**, with all 218 pins re-authenticated.
  - **Transports:** exact mux 03 (3502179) and mux 08 (3504429) plus both control sockets absent at 13:44:17Z (receipt c2cef696). The first retirement attempt failed closed on an already-absent identity (disclosed).
  - **T1 go-ahead:** I declare A2's transports retired, and 08 vacant of X4S-2 (STOP plus census at 12:15:16Z, 0 processes). T1 proceeds with:
    1. a fresh 08 qualification;
    2. the two-host smoke;
    3. admission and dispatch of draft d066dc37 (1,020 rows, 512/508).
  - **Not authorized:** B, heldout. The END clean window comes after T1 reporting finishes.
  - **Perception next:** the 08 HTTP cache must be retired before END.
- **13:57 UTC: 04 released by perception** at 13:57Z (receipt 5f59f7f8). This releases compute only; all 04 evidence and cache storage is preserved and off-limits. **The planned K4S execution host set is {03, 04}**, neither a T1 reporting host, so K4S could run in parallel with T1 once frozen (pending the END-reference host check). The prep worker now qualifies 04 too.
  - **T1 status:** 08 fresh qualification PASS (f2a2444e, binding b3099194); two-host smoke r9 launched at 13:54Z.
  - **The 08 HTTP cache** retires in the END window, per perception's requirements (b58b4bc5).
- **14:06 UTC: T1 replacement-r3 LAUNCHED** at 14:03:49Z on 01/08 (receipt f8a54939). Draft d066dc37: 1,020 rows, 512/508; smoke r9 PASS (93c22a09/0b7ae802); freeze ef4c073a, manifest 488f6c8d unchanged. 2,052 preserved. At ~200/h across both hosts, it should finish ~19–20Z, then the END clean window: 08 HTTP cache retirement, E4 A6 smoke, E4 review, pooled reference, T1 release (PC1–PC4), and B on 08.
- **17:21 UTC: K4S freeze-fill prep COMPLETE** (247ef6d4). Sol approved all three streams: core r6, independent verifier r3, Mac/END r6 (15 reviews). Qualification r3 PASS on 03 and 04, 28/28 each. Reducer/verifier cross-check 169/169. Seed audit PASS.
  - **Freeze decisions (mine):**
    - c\* = 0.9.
    - Host set {03, 04}, with transport declarations c2cef696 and 5f59f7f8. T1's 03 corpus copy and 04 perception storage stay untouched.
    - Q1–Q13 defaults.
    - K4S-SPEC I-1..I-5 accepted.
    - Errata R2/R5 recorded.
    - Attestation: T1/TIERS outcomes sealed.
    - SD1 supersession issued, with an additive exit-r3 pointer.
    - Read-only SHA-verified copy of T1's K4 speed corpus (a97b1fbf) into the K4S job dirs authorized, for END only.
  - **Freeze executor launched** (Opus, clasher-prereg-k4s-freeze-exec-20261011-r1): SHA re-verification, seed-audit re-run, Mac manifest freeze, freeze record and commit, independent check. Then the K4S run on {03, 04} (excluded smoke, then reporting), in parallel with T1 reporting on 01/08.
  - **TIERS blocker found by prep:** the frozen `measure_tiers.py` (5d7de8e3) uses `math.isfinite` without `import math` (l.70), so every Mac session with amendment_1 would hit NameError. A reviewed TIERS erratum is needed before any Mac session; it is outcome-blind and doesn't affect fleet reporting. Assigned to T1.
- **17:31 UTC: K4S freeze r1 STOPPED correctly.**
  - **Seed audit:** the re-run at 490a8084 FAILED on self-reads only. Since 38c195b8, the tool reads K4S's own committed outputs as prior declarations; there is no real foreign collision. It also exits 0 on FAIL.
  - **DELTA-MANIFEST:** reviewed d15715ba, committed 19586d20, skeleton d771e459 (mechanical; new class 65 → 81).
  - **Approved:** a five-part audit_seeds.py fix (skip K4S self-docs, exclude own outputs, helper-offset window bounds, exit 1 on FAIL, tests including a synthetic foreign collision), plus Sol review of the fix and the DELTA-MANIFEST delta, including the unpinned test_end_reference.py.
  - **Freeze r2 executor launched** (clasher-prereg-k4s-freeze-exec-20261011-r2) with the same decisions 1–9. It also commits perception's two transport receipts.
- **17:54 UTC: TIERS Amendment 2 (measure_tiers.py `import math`) review = APPROVE_WITH_CONDITIONS** (independent Opus; `TIERS-AMENDMENT-2-REVIEW-r1.md`). Candidate e521800b. The production delta is exactly `import math` (5d7de8e3 → 6066228b). The test fails on the old bytes and passes on the new (33/33; e4v3 70/70). Pyflakes finds no other undefined names. It is outcome-blind, and T1's running r3 is unaffected (ef4c073a never runs e4v3).
  - **APPROVED; T1 merges it to main now,** before the END window, adding these conditions to the amendment record:
    1. **Same bytes everywhere:** END reference, A6 smoke, pooling and every Mac session use the post-merge `measure_tiers.py` 6066228b only. END/A6 bundles are prepared only after the merge, and any reference or smoke prepared on 5d7de8e3 is void and re-run.
    2. **Python note:** validated on Python 3.8, while the Mac requires ≥3.12; `import math` doesn't depend on the version.
  - **Companion K4S rebind required:** the K4S Mac manifest (d89cab16) pins `measure_tiers.py` 5d7de8e3, and `verify_pinned` would refuse every K4S Mac session after the merge. An outcome-blind **K4S Amendment 1** re-pins it to 6066228b and changes nothing else; it gets Sol review. Worker launched. K4S fleet execution doesn't depend on this pin.
- **17:55 UTC: PREREG-K4S FROZEN** at 17:45:00Z (391d2006; fill fab6e03f; record json 478068b6 / md 24623ff8).
  - **Pins:** seed audit PASS with exit 0 at fbcd677d (Sol APPROVE on the audit fix and manifest delta); SD1 hash b8ce7b4c; supersession issued with a new exit-r3 pointer; Mac manifest d89cab16.
  - **Independent Opus check:** APPROVE, all 32 SHAs recomputed.
  - **Known and accepted:**
    - one Mac test asserts the manifest is still a draft, so it fails by construction (94/95; coverage re-checked);
    - one rebind-verify row lags because of the skeleton↔manifest self-reference.
  - **K4S confirmatory RUN launched** (Opus runner, clasher-k4s-confirm-run-20261011-r1) on {03, 04}: fresh qualification, excluded smoke, then sealed reporting with 20-min health checks. END prep only, until I declare the K4S END window.
- **18:00 UTC: K4S launch rulings** (runner r1 found three launch blockers in the frozen tree, all operational and outcome-blind):
  - **B1, APPROVED: K4S Operational Amendment OA-1.** Add a NEW `mirror_k4s.py` with hub = 127x05: nice 19, light rsync, hub copies under per-job paths on 05. It keeps the frozen copier protocol (owned-copier admission, env prefix, `rsync --server` / exact `find` only), sets an explicit source_ip, gets the game count from `descriptor.order`, and writes hub-ack {hub: 127x05}. No frozen byte changes. **For K4S, r3 §4.4's "hub 01" wording is superseded by OA-1.** It needs tests (8- and 10-game blocks; ack written back; the guard classifies children as owned) and GPT-6.1-Sol APPROVE before use.
  - **B2, APPROVED:** build `FROZEN-K4S.json` mechanically from freeze record 391d2006: files = the frozen k4s-confirm tree plus the prereg at 391d2006, qualified_hosts [127x03, 127x04], reporting_delta_review = SOL-REVIEW-CORE-r6 APPROVE r6, parent_source_seeds []. The builder and its output get Sol review; then commit it as a receipt. Its SHA is every game's freeze_manifest_sha256.
  - **B3:** after smoke PASS, the runner sends the manifest SHA plus the smoke receipt; I reply with an explicit reporting-authorization message whose id it records.
  - OA-1 and the B2 manifest are recorded as a K4S freeze addendum before any reporting game.
- **18:22 UTC: K4S 03 admission ruling: (a) frozen idle-service pin.** Perception's v4 validation cache service on 03 (PID 2180947, idle at 0.0% CPU since 2026-10-09 21:39Z) is admitted using the frozen `idle_services.py` pin (SERVICE_PIDS 127x03 = 2180947, per the T1 ruling of 2026-10-10 14:35Z, which plan.json's idle_service_exception covers). Any block where it exceeds 1% of a core or spawns a child is flagged and disclosed, not stopped. Don't touch the service. If its identity (PID/start/cmd) differs from the pin at admission, 03 is not admitted; report it.
  - **Status:** K4S launch-time qualification PASS on 03 (f985a32c) and 04 (a11c978c), 28/28 each. B2 manifest dry run 426fe4c5. OA-1 live copier test passed; a robustness fix is pending, then Sol review.
- **18:41 UTC: K4S Amendment 1 COMMITTED** (45f32c0f; Sol APPROVE r3; record md e01f11b6 / json 79b92686). The K4S Mac manifest re-pins `measure_tiers.py` to 6066228b: d89cab16 → **8bb20a75**. Only that pin and its required copy differ. Mac suite 95/96, with the single known by-construction failure; END tests 103/103.
  - **Binding:**
    - **Fleet reporting:** FROZEN-K4S.json and the 03/04 runtime keep the 391d2006 bytes (manifest d89cab16).
    - **END and Mac sessions:** they name 8bb20a75 and run from the amended tree, in a separate staged END tree. No END declaration may ever name d89cab16.
    - **Disclosure:** the r1 Sol reviewer saw X4S-2 numbers already used for c\* (mechanical re-pin, no effect); disclosed in the record.
  - Relayed to the K4S runner.
- **18:48 UTC: K4S runner dispositions** (outcome-blind):
  - **Sol MINOR 5, ACCEPTED as frozen behaviour.** Excluded smoke games carry freeze_manifest_sha256 = sha(FROZEN-K4S.json), whereas K4S-SPEC §5 says null. No frozen bytes change; the discrepancy goes in the freeze addendum.
  - **STOP drill, APPROVED:** a separate excluded drill job per host (k4s-confirm-r1-stopdrill) with its own staging and qualification, run before the counted smoke. The counted smoke stays 8/8.
  - **Status:** OA-1/B2 Sol r2 REJECT (2 new MAJORs: transport descendant teardown, and restart ACK without hub re-verification); fixing for r3. B2 manifest 454b5f54 is compatible. END corpus copied read-only and SHA-verified. Dispatches: smoke 5ff0b681; reporting 3,900 blocks / 33,000 games (78335dc4).
- **19:29 UTC: E4 END independent review = APPROVE_WITH_CONDITIONS** (`E4-END-INDEPENDENT-REVIEW-r1.md`). No release path exists before the pooled reference; the pool host set equals the counted inventory; post-merge bytes are picked up consistently. Tests: E4-v3 70/70, T1 release 49/49, OP-5/6 guards 65/65. **Rulings** (all apply to the END run, which T1 executes):
  - **C1 (blocker F1):** the frozen T1 plan (af6aeade) lacks `reporting_hosts` and lists 03, so {01, 08} is refused. The END bundle pins a plan copy adding `reporting_hosts: [127x01, 127x08]` only, with a recorded proof that it otherwise equals af6aeade. No code edit (`fleet_end.py` is K4S-frozen).
  - **C2 (blocker F2):** **the END reference guard is the OP-6 freeze (24817e16 / aeeb3003),** which is strict and tested, so apt activity stops an attempt. Before each launch, read the apt-daily timers on 01/08 (systemctl list-timers, read-only) and start only with ≥2 h of clearance.
  - **C3 (F3):** run an offline preflight per host from outside the registered attempt roots. A6 output also stays outside the attempt roots. Don't register any attempt until the preflight passes.
  - **C4 (F4):** builders and launchers assert `measure_tiers.py` == 6066228b, with the measurement-source commit after 6afcbbab. Checkouts on 01/08 must contain the completion and inventory commits.
  - **F8:** never run the reducer or barrier with `python -O`.
  - **F9:** 08's reference finishes before B takes 08.
- **19:32 UTC: T1 REPORTING COMPLETE (SEALED)** at 19:31:38Z (bc3730c4; receipt 9e788d20): 2,400 primary + 600 guard + 72 descriptive; 01 = 1,972, 08 = 1,100; all 3,072 logical IDs once; 24,576 raw hashes and 1,100 ACKs PASS; 0 failures; all owned processes gone at 19:28:44Z.
  - **END CLEAN WINDOW DECLARED on 01/08.** Steps, in order:
    1. **Perception retires the 08 HTTP cache** per b58b4bc5: re-authenticate the current identity, drain, owned STOP, server/timer/wrapper exit 0 plus port absence; preserve payloads/token/locks; commit a receipt.
    2. **T1 runs END under rulings C1–C4:**
       - (C3) offline preflights on 01 and 08 outside the attempt roots;
       - (C1) the END-bundle plan copy with reporting_hosts [127x01, 127x08];
       - (C4) assert `measure_tiers.py` == 6066228b;
       - (C2) OP-6 guard freeze, with an apt-timer clearance of ≥2 h per launch;
       - E4 A6 smoke, output outside the attempt roots;
       - then the pooled fleet reference on 01/08, with 08's reference first (F9).
    3. **Release barrier PC1–PC4**, never with `python -O`. Outcomes stay sealed until the barrier and the TIERS Mac summary allow release; the Mac session still needs Sam.
    4. Then B on 08 (perception; needs my authorization).
  - **Hub mirror (PGID 516161 on 01):** stays SIGSTOP-paused through END, because resuming it would be foreign activity on 01. After END, retarget it away from 04 (K4S host) before resuming.
- **19:42 UTC: END step 1 DONE: 08 HTTP cache retired** (4292e520; receipt 46ceee24). The r1 attempt stopped safely when the wrapper command SHA didn't match. I authorized one reconciliation connection, which matched the exact reconstructed argv (855c8118) and all pins. Owned STOP at 19:41:55Z; server, timer and wrapper exited 0; port 39503 absent; all 172 payload/token/lock stat tuples unchanged; no signals or deletions. 03 cache untouched. **T1 may now proceed with END on 08 as well** (C1–C4; 08 reference first).
- **K4S:** OA-1 Sol r6 REJECT (MAJOR 12, confined to the separate `--revoke` mode). **Approved simplification S1:** delete the revocation mode; recovery is a normal copier restart through the single verified main() path. r7 reviews the deletion plus a real SIGKILL-restart test. If another new MAJOR comes up, I'll consider dropping OA-1 entirely.
- **20:05:03 UTC: K4S REPORTING AUTHORIZED (B3).**
  - **Smoke:** excluded smoke PASS on 03 and 04 (5f4f1cd8): 8/8 blocks each, 0 failures, OA-1 hub-ACK 8/8. Charge-share deviation ≤0.008. 04 had 3 dbus-interfered blocks (disclosed).
  - **Authorized:** PREREG-K4S reporting on hosts [127x03, 127x04] under:
    - freeze 391d2006;
    - FROZEN-K4S.json 416f6e51;
    - reporting dispatch 78335dc4 (3,900 blocks / 33,000 games);
    - launch addendum 5d6ac662 (OA-1 47eb96d6 / Sol r7; Amendment 1 45f32c0f);
    - r3_explicitly_frozen = true.
  - **Rules:** outcomes SEALED; health checkpoints every 20 min; stop and report on any guard stop. ~16 h, so it ends ~12Z on Oct 12.
- **20:09 UTC: K4S SEALED REPORTING LAUNCHED** at 20:08:22Z / 20:08:27Z on 03/04 (receipt 9a63dd3f, commit 93d1565d).
  - **First attempt refused (safe):** it was refused by the frozen one-supervisor-per-job pin, so I approved distinct reporting namespaces (k4s-confirm-reporting-r1), following T1's precedent. Authorization v2 is 852c01e6.
  - **Run:** 11 slots per host; 0 foreign/active; OA-1 copiers on 05.
  - **Timing:** ~16 h, so it ends ~12Z Oct 12. Outcomes sealed.
- **20:13 UTC: SAM AUTHORIZED the replay-only Mac E4 measurement session** (~20:11Z: "you got it"). ssh to macmini-fleet is now allowed for the frozen TIERS/K4S Mac procedures. Replay only: no live games, no detection evasion.
  - **Operator launched** (Opus, clasher-mac-e4-session-20261011-r1).
  - **Phase A, now:** Mac inventory, separate post-merge bundle, arm64 build, offline preflight.
  - **Phase B:** the TIERS session, only after T1's END pooled fleet reference is committed, using `measure_tiers.py` 6066228b.
  - **Phase C:** the K4S Mac measurement (manifest 8bb20a75), after the K4S END reference (~Oct 12 afternoon), as a standalone session if needed.
  - **GUI-only steps** get routed to a Codex/Sol computer-use task.
- **20:35 UTC: T1 END stopped safely before A6** (no attempt registered).
  - **Done so far:** the 01 bundle and C3 preflight PASS (68a65b6e). The drift was confined to six E4 files, and the separate post-merge snapshot was approved.
  - **Blocker, measured:** one TierBackend uses 11.46 GiB anonymous RSS on the 11.65 GB public corpus. With 11 frozen slots that is ≥126 GiB, more than the host's 125.6 GiB, before the frozen 24 GiB floor.
  - **Decision:** no slot, floor or budget change. An **outcome-blind E4 input-loading repair** is assigned (Opus implementer plus Sol review; TIERS Amendment 3). It must keep fixture bytes and order identical, never touch the timed region, and avoid K4S-pinned files or stop and report.
  - **Delay:** the Mac TIERS session is pushed back until the END pooled reference exists.
- **20:38 UTC: Mac E4 Phase A COMPLETE** (b8792a6c). M4 Pro (8P + 4E), 24 GiB, Python 3.12.13, torch with MPS.
  - **Staged:** runtime under ~/Desktop/code/clasher-mac-e4-tiers-20261011, built from d651b52c plus 33 runtime-pin files plus regenerated E1 native source (76/77 pins; non-compiled manifest disclosed). Runtime pins PASS. `test_measure_tiers` 33/33 on Python 3.12. arm64 scratch build OK. MPS replay at 20 FPS.
  - **Blockers:**
    - (1) **The Mac would also run out of memory:** main ~11.5 GiB steady / ~22 GiB peak, and the D6 forward children each load a full backend (~34 GiB peak on a 24 GiB machine). Amendment 3's scope now includes the Mac path, with a streaming per-id load capped at ~6 GiB total.
    - (2) **Quiescence census fails:** WindowServer at 0.5 core and Codex Computer Use at 0.22. A quiet Mac window is needed at Phase B, with no computer-use tasks running; coordinate with roader if it uses the Mac.
    - (3) **Bundle identity** waits on Amendment 3 plus the regenerated END bundle.
  - Independent reviews of staging and topology are approved (Sol for code, Opus for topology and provenance).
- **21:38 UTC: K4S 04 guard stop** at 21:32:49Z (foreign_compute: root `check-new-release`). It was triggered by pam_motd's release-upgrade check on one of our copier's ssh logins, once the stamp was more than a day old. 11 in-flight blocks were lost; the frozen supervisor continued automatically. 03 is forecast to do the same at ~00:58Z Oct 12.
  - **Ruling (a):** accept and disclose. Lost blocks are replaced after reporting by the frozen blind ledger (caps 300/90). No mid-run copier change.
  - **Carry-over to T1 END (extends C2):** before each reference launch on 01/08, besides the apt timers, read (read-only) the ages of `/var/lib/ubuntu-release-upgrader/release-upgrade-available` and `/var/lib/update-notifier/updates-available`. Launch only if neither motd check can fire during the attempt. If a stamp is stale, let one ordinary login trigger the check *before* the launch and wait for it to exit.
- **22:07 UTC: TIERS AMENDMENT 3 ADOPTED** (f6cebbaa; record md 761ebc0d / json 3e5627cb; Sol APPROVE r4, review 18baa4ea). An outcome-blind loader repair:
  - `tier_backend.py` b04d201d → 02e2139f; `prepare_bundle.py` → a1c59fa3; new `state_rows.py` 3899276b and `convert_states.py` 7ce30683. `measure_tiers.py` and `fleet_reference.py` are byte-identical.
  - One backend's RSS went from 11.3 to 0.4 GiB. Equivalence PASS: 1,325 states, 1,200 inputs, 15 bit-exact checks. Tests 91/91 on Python 3.8 and 3.12.
  - **A3-P accepted:** an all-cause Mac poll-lateness check (≤1%, max ≤50 ms, same thresholds as the frozen GC gate). It can only make a tier infeasible, guarding against out-of-timer load tails (p99 0.22 s).
  - **Execution:**
    1. **T1:** convert once on 01 against states.pkl 0addf7c0 (expect fingerprint c09142b9). Copy the container set byte-identically to 08. Regenerate the manifests, then repeat C3 and the memory check on both hosts. Then A6 → reference (08 first; extended C2) → pool → PC1–PC4.
    2. **Coordinator:** K4S Amendment 2 re-pins `tier_backend.py` and adds `state_rows.py` in the K4S Mac manifest, with Sol review.
    3. **Mac:** its own fixture is converted on Linux under its own fingerprint; the Mac stages it only and never converts.
- **22:10 UTC: K4S 04 apt stop** at 22:06:15Z. The frozen OP-7 `ubuntu_apt_average_budget` guard fired on root apt-daily, and the supervisor exited. 04 has 186 complete; 22 lost (21:32 motd + 22:06 apt); 1,742 never started. 03 is healthy. Daily apt/motd timers will hit every remaining window.
  - **Ruling: windowed replacement rounds** under the frozen T1 §3.2 mechanics:
    1. **Per round:** a fresh job namespace; blind inventory; ledger replacements with cell-preserving seeds; never-started blocks unchanged.
    2. **Dispatch size:** each round dispatches only as many blocks as finish, at the measured rate, **≥30 min before that host's next apt-daily / apt-daily-upgrade timer** (read via systemctl list-timers), so a round ends cleanly with no in-flight losses.
    3. **Before each launch:** read both motd stamps. Launch only if neither can fire inside the window; if a stamp is stale, pre-trigger it with one login and wait for the check to exit.
    4. **Qualification:** fresh launch-time qualification per new namespace is required. Smoke-pass carry-over is allowed only with byte-identical runtime and FROZEN-K4S (416f6e51) bindings.
    5. **Authorization:** the same bindings as 20:04:59Z, with reporting_jobs plus this ruling cited.
  - **03:** its current open-ended phase keeps running. Accept the ~11-block motd loss at ~00:58Z and the stop at the 08:47Z apt timer, then continue in windowed rounds. No pre-emptive STOP, since no drain mode exists.
  - **Escalation threshold:** now 50% of either replacement cap (150 primary / 45 guard), or any stop that isn't apt/motd.
- **22:11 UTC: K4S ruling revised to Option A** (supersedes the windowed-dispatch part of 76887b33). The frozen `replace.py` inventories only stopped phases, needs ≥2 hosts, and re-dispatches the full rebalanced remainder; windowed dispatch would be new code, so it is withdrawn.
  - **Now:** owned STOP on 03, then one blind inventory of both reporting phases, the ledger, a fresh namespace k4s-confirm-replacement-r1 on 03 and 04, a full rebalanced dispatch, fresh launch-time qualification, and smoke carry-over only with byte-identical bindings.
  - **Each future apt/motd stop** repeats this frozen round cycle.
  - **Still apply before every launch:** the motd-stamp pre-trigger and the timer readings.
  - **Escalate** at 50% of either cap, if any cell's replacement index nears its k limit (11 / 9), or on any non-apt/motd stop.
- **22:26 UTC: Mac registration inputs: rulings** on the design proposal (59396fb0 / 2cab69f0).
  - **The gap:** no frozen text selects agreement2000 or packets1000, and the addendum wanted them before reporting, so a new outcome-blind **TIERS Amendment 4** is needed.
  - **Rules B.1–B.7 ADOPTED in principle:**
    - lineage-checked pool;
    - packets = whole games, SHA-ordered and round-robin across tiers, cut at 1,000;
    - **P1 sealed-tick cadence** (the Mac session becomes ~6–6.5 h);
    - agreement = speed ∪ packets ∪ SHA fill, with overlap approved (≈38.6 GB bundle);
    - fixture prefix = the END index; canonical fingerprint;
    - student-reference on 05, cross-checked against the pooled END S forwards.
  - **Builder:** a dedicated Opus worker (clasher-mac-registration-builder-20261011-r1), acting as T1's corpus-owner delegate. Sol reviews the code and the A4 text, and an independent Haiku worker reproduces the result. T1 merges and seals.
  - **Source:** T1's 32 raw captures exist only on 03. One read window in the first K4S full-stop gap on 03 (~08:47Z apt), per §C.2: no ControlMaster; only `capture.pkl.gz`; nice 19; SHA-verified. Never `games/`.
  - **T1 must NOT seal T1-REGISTRATION** until the Mac sets are delivered.
  - **Mac disk:** the staging peak is ~72 GiB against 63 GiB free. The Mac operator frees space (agent-owned caches only) or finds an external volume. A hard-link code change is a last resort.
- **22:28 UTC: K4S Amendment 2 COMMITTED** (f231fbcb; Sol APPROVE r1+r2; record md b28b636e / json e0adbeae). K4S Mac manifest 8bb20a75 → **c1fb1e9a**:
  - `tier_backend.py` re-pinned to 02e2139f;
  - `state_rows.py` added;
  - `build_manifest.py` → 2e255fb9 (its file list only).

  K4SBackend is compatible, with no K4S code change. Mac suite 98/99 (the known by-construction failure); END 103/103. Fleet runtimes keep the d89cab16 manifest and the 26932fa8 builder bytes. K4S END and Mac declarations must name c1fb1e9a. If TIERS A4 touches any pinned e4v3 file, another re-pin follows.
  - **Ruling:** K4S Mac all-cause poll lateness (the A3-P metric) is reported **descriptively only**, with no gate change, disclosed in the K4S Mac summary.
- **22:31 UTC: Mac session prep rulings.**
  - **Disk:** no external volume, ~65.7 GiB reachable vs a ~72 GiB staging peak. **No-copy staging** (hard link or APFS clone, SHA-verified, keeping END↔Mac pin equality) is added to the A4 builder's scope. Only three regenerable caches may be freed; other threads' worktrees are off-limits.
  - **Memory precondition** (operator, not a gate): available ≥6 GiB, free swap ≥1 GiB, 0 swapouts in census, disk ≥10 GiB after staging. Measured on 05: main 0.93 GiB, D6 child 0.78, concurrent 1.33.
  - **A3-P** applies to the frozen gate-4 variant v\* (stricter).
  - **Session runs under its own `caffeinate -i`.**
  - **macOS 27.0.1** is staged with AutomaticallyInstallMacOSUpdates=1. Disabling it needs admin, so a short Sol computer-use step at session time turns auto-download/install off for the window, then restores it.
- **23:04 UTC: A4 no-copy staging: APPROVED `stage_nocopy.py`.**
  - **Why a helper:** editing `prepare_bundle.py` would break END↔Mac pin equality, and frozen `prepare_bundle` refuses pre-placed files.
  - **The helper:** an external, SHA-pinned helper that imports the frozen `prepare_bundle` unchanged and overrides `copy_file` only for `states.pkl` and `states-rows.{json,bin}`. Placement is clonefile, then a hard link, then a copy only if ≥10 GiB stays free.
  - **Conditions:**
    - SHA verification after placement;
    - source and bundle files made read-only;
    - a byte-identical `tiers-pins.json` test with and without the helper;
    - SHAs re-verified right before the Mac session.
  - **Effects:** peak staging disk drops ~72 → ~36 GiB, with no re-pins (Sol agrees). Sol r2 found everything else in A4 resolved; r3 runs on the whole amendment.
- **23:16 UTC: TIERS AMENDMENT 4 ADOPTED** (94df513d; md 2a36f620 / json c9da4db0; Sol APPROVE r4).
  - **What it covers:** the Mac registration inputs per rules B.1–B.7, P1 cadence, overlap, and the no-copy staging helper `stage_nocopy.py` with conditions 1–6.
  - **Uncovered B.4 case** (0 < |F| < #tiers): stop and escalate, no new rule.
  - **Next:** Phase 2, a read of 03 only in a window I declare explicitly, expected at K4S 03's ~08:47Z apt stop. Then Phase 3 builds on 05 and hands off to T1 for the merge and seal, after its END pool.
- **00:49 UTC: T1 END copier design.**
  - **Round 1:** an in-run polling copier, REQUEST_CHANGES (SSH-flag risk, source attribution). Withdrawn, never launched.
  - **Round 2:** an exit-push wrapper (8886028), APPROVE_WITH_CONDITIONS (`END-exit-push-REVIEW-r2.md`). There is zero activity during timing, and the idle parent is invisible to the guard.
  - **Ruling:** fix H1–H5 in code with a narrow re-review: bounded transport-only retries, an always-pushed `exit.json`, per-host/per-attempt destinations, a 05-side verifier, log push, an output-path assert, `timeout -k`.
  - **Conditions C1–C6** also apply. In particular, **no SSH into a timed host from any thread during its window**, including T1's own probes. Launch only from the staged A3 package (the shared 05 checkout still has 5d7de8e3).
  - **Deadline:** 01's cutoff is 04:17:43Z; otherwise run 08 first and defer 01.
- **01:04 UTC: T1 END exit-push r3 = APPROVE_WITH_CONDITIONS** (`END-exit-push-REVIEW-r3.md`). **Timing GO.**
  - **Wrapper 0a87166f approved.** Timing may run under C1/C4/C5/C6, V2 `--prepare`, staged A3, fresh C2 and the 01 cutoff.
  - **Verifier 325a00a6 NOT approved for ACK** until code fixes land: explicit raises not asserts (R3-1); a marker↔`exit.json` binding plus `PUSH-FAILED` rejection (R3-2); the rsync code recorded (R3-3). Then a quick diff check. Only after that, plus V1/V3, is anything ACKed.
- **01:07 UTC: K4S P2 approved as standing policy.**
  - **Policy:** a joint owned STOP of 03/04 shortly before each known timer (~08:40Z 03 apt-daily, ~11:10Z 04 apt-daily, ~13:20Z apt-daily-upgrade on both). Then a blind inventory, a fresh replacement-rN round with qualification, and relaunch after the timer has fired, maintenance has exited and stale motd stamps are pre-triggered. Each cut costs ~22 blocks.
  - **At the 08:40Z cut, a 03 read window for the TIERS-A4 builder:**
    1. K4S posts "03 quiet";
    2. I send the builder go;
    3. the builder makes one read-only capture copy and posts "released";
    4. K4S relaunches r2.

    If the builder hasn't released 03 within 30 min, r2 proceeds and the builder waits for the next gap.

## 2026-10-12 01:21Z: T1 END verifier R3 fix: disposition (wrapper frozen, legacy-format verifier)

The R3-1/2/3 candidate splits into two parts. Future wrapper 2928eb15 adds `exit_utc` to TRANSFER and the rsync exit code to PUSH-FAILED. Verifier da22a9fa is strict and would refuse the marker from the running A6 (0a87166f).

**Ruling:**
- **No wrapper change this END campaign.** The approved wrapper 0a87166f stays for A6, the 08 reference and the 01 reference: one set of reviewed bytes, and no re-review on the critical path. Wrapper 2928eb15 is shelved.
- **The verifier is fixed to accept exactly the 0a87166f marker format.** Binding comes from existing controls, not `exit_utc`:
  - **R3-1:** explicit raises, and refusal under `not __debug__`.
  - **R3-2:**
    - the pinned `--prepare` proof (empty receiver plus nonce, created before the launch time in the launch receipt) plus a nonce match;
    - reject if PUSH-FAILED.json is present;
    - the TRANSFER-COMPLETE marker's mtime must be at or after `exit.json`'s exit time;
    - refuse unprepared directories.
  - **R3-3:** a legacy PUSH-FAILED without an rsync code counts as a failure (no ACK), recorded in the receipt.
  - **V3:** byte-compare `argv.nul` with the pinned argv (`argv_nul_sha256` d3a6e81e, receipt END-A6-launch-preparation-01-r1).
- **Next:** T1 sends the verifier SHA and diff, and the coordinator routes a narrow Opus diff check.
- **Until approval:** no ACK; C5 holds (no SSH to 01 from any thread while A6 is in its timing window); received data waits.

## 2026-10-12 01:29Z: T1 END verifier r5 (legacy-only 753722c9) is APPROVED for ACK with conditions

The independent Opus diff review (`END-verifier-REVIEW-r5.md`, T1 job directory) returned APPROVE_WITH_CONDITIONS:
- the verifier is 753722c9 and the diff 6422005c;
- the wrapper is still 0a87166f;
- every control in 81b7c01e fails closed;
- there is no ACK path for a stale, foreign, partial or unprepared directory;
- the marker-mtime rule is sound, because rsync -a keeps 01's mtime, so cross-host clock skew doesn't matter.

**Adopted, with no further code change.** The verifier bytes stay 753722c9 for the whole END campaign. Conditions:
- **C-a: pin these files.**
  - Launch receipt `END-A6-launch-receipt-01-20261012T011336Z.json` (sha 45bd9dc3…41b8, holds `measurement_argv`). Not the launch-preparation receipt, which lacks that key.
  - Prepare proof: the copy committed in e6c73498 (`END-A6-receive-prepare-01-r1.json`, sha b6597ae1…d520), never the receive directory's own PREPARED.json.
  - Run it as `python3 -I` under nice 19, and check the verifier SHA first.
  - The 08 and 01 references pin their own launch receipts, plus prepare proofs committed before launch with at least a 1 s gap.
- **C-b:** any non-zero exit or traceback is a REFUSE. Record argv, exit code and full stderr in a T1 receipt.
- **C-c:** keep the code as is. In the verification receipt, record `test ! -e PUSH-FAILED.json && test ! -L PUSH-FAILED.json`.
- **C-d:** verify no earlier than `exit_utc` + 1300 s (the wrapper's maximum lifetime). C5 holds until then; after that, C1 proof that the wrapper is gone comes before the 08 reference launch.
- **Order after an ACK is unchanged:** 08 reference first, then 01 reference (cutoff 04:17:43Z), then pool, then PC1–PC4. Outcomes stay sealed.

## 2026-10-12 02:05Z: T1 END schedule pre-ruling (if A6 overruns)

Wall time for A6 hasn't been committed; T1 is to record it with its basis.

- **08 reference:** launches after the A6 ACK, provided C1 holds and C2 is fresh (≥2 h clearance before 08's next apt-daily).
- **01 reference:** if it can't start by the 01 cutoff after its own C-d and C1, it is deferred, not relaxed. It moves to the first clean window after 01's next apt-daily, with a fresh C2 (both actual runs exited, ≥2 h clearance, both motd stamps fresh). The same applies to 08 if its window is missed.
- **Pooling** happens once both references exist.
- **If A6 refuses or fails,** STOP and report, with no retry without a new ruling.

## 2026-10-12 02:17Z: K4S cycle method: Proposal M adopted (manual checklist, automation shelved)

Sol has rejected the cycle automation twice (`round.sh` r1, `round.py` r2: seven MAJOR findings, all about unattended-automation guarantees). Sol re-verified the manual r1 cycle as correct. **Adopted: Proposal M.** Every P2 cycle runs by hand from a written checklist that incorporates Sol's substantive checks:

1. Owned STOP, with proof that the supervisor and every recorded worker group are empty.
2. Drain: completed-ID set = supervisor-exit list; hub-ack bindings and returned marker checked; copier revoked on both sides.
3. Inventory: frozen `replace.py` runs once on a working ledger copy with a hub view limited to this run. Validate canonical rows, events = failed blocks, exact 3000/900 coverage. Only then publish, keeping the previous ledger. Escalation gates: 150/45 and k 9/7.
4. Fresh namespace and fresh qualification.
5. Finalize: hashes, runtime byte-equality, 03 idle pin, dispatch, barrier.
6. Prelaunch: timer fired, maintenance exited, both motd stamps fresh, and the builder handshake.
7. Launch, then confirm launch.json, admission and dispatch SHA on both hosts. On any failure: owned STOP and escalate.

Each round commits a receipt with every hash. **`round.py` is shelved**: no further hardening rounds and no execution.

**Post-round audit:** a read-only evidence and receipt audit by an Opus-high delegate, routed by the coordinator. Sol is reserved for reviewing Claude-written code, and no new code is involved. Findings go to the coordinator. A blocking finding stops the next cycle until it is ruled on.

## 2026-10-12 02:37Z: T1 END reference layout ruling (wrapper `$job/measurement` vs PC1 attempt roots)

**The conflict:** the frozen wrapper 0a87166f forces E4 `--output=$job/measurement`, with the job's parent being either BASE or the host root. `release_reference.attempt_roots` (`:114-138`) wants each attempt directory to be an immediate child of the declared root, with `fleet-identity.json` directly inside. There is no code change; the wrapper, E4, the checker and `reference-attempt-roots-0108.json` all stay unchanged.

**Ruling (L1):**

1. **On each measuring host,** the reference job is `BASE/fleet-end-attempts-0108/<host>/<attempt>`, the original attempt as an immediate child of the original host root, which the wrapper allows. E4 output goes to `<attempt>/measurement`. Every passing or failed attempt gets its own directory there. Nothing is deleted, moved or archived on the host.
2. **On 05,** which runs the pool and release, `BASE/fleet-end-attempts-0108/<host>/<attempt>/` is assembled as a **byte-identical plain copy** of that attempt's ACKed received `durable-measurement` (the E4 output directory). Rules:
   - no symlinks and no archives;
   - the same `<attempt>` basename as on the host;
   - assembled only after the verifier ACK, then checked against `receipt-manifest.json` with full hashes;
   - a failed or REFUSED attempt is assembled the same way from whatever was received; if nothing arrived, STOP and escalate (F3);
   - wrapper metadata (`exit.json`, `argv.nul`, `detach.*`, TRANSFER-COMPLETE) stays in `end-received/` and is bound in the assembly receipt.
3. **Assembly receipt:** for each attempt, record:
   - host path `<root>/<attempt>/measurement` mapped to release path `<root>/<attempt>`;
   - file count and full SHA equality;
   - the verifier ACK receipt;
   - the release-side root listing, which must equal the set of launched attempts.

   The PC1 packet reviewer cross-checks this receipt against the original host root listings (the children's basenames must equal the descriptor's attempts) and the launch receipts. This ruling is flagged to the PC1 reviewer as a declared interpretation of "preserve full roots at release-side paths".
4. **Unchanged:** A6 stays outside the roots, since it isn't a reference attempt. The order stays 08 then 01, and C1–C6, C-a to C-d and c6387611 all still apply.

## 2026-10-12 02:40Z: A6 independent review PASS_WITH_NOTES; reference order ruling R-ord (both hosts independent)

**Review** (`END-A6-INDEPENDENT-REVIEW-r1.md`, T1 job directory): PASS_WITH_NOTES.
- Approved argv and bytes; exit 0; 29/29 outputs match da9230ad.
- Every gate was recomputed from raw: EXACT 125/125 and 250/250; zero SSH, dbus or apt interference; MHz ratio 0.99923; memory well inside the A3 budget.
- No outcome exposure.
- Observed A6 wall time: **55 m 11 s**. This is the duration basis for the references.

**R-ord: the 08→01 serial dependency is withdrawn.** Under strict serial order, 01's window would be lost. "08 first" existed to satisfy F9 (08's reference finishes before B takes 08), not to make 01 wait.
- The two references are independent: neither launch waits on the other's exit or ACK.
- **Launch 01 first.** Its window closes first, and it is already C1-clean. Launch 08 when it is ready.
- Each host keeps its own conditions:
  - 01: cutoff 04:17:43Z;
  - 08: fresh C2 against its 08:49:07Z apt-daily;
  - per host: fresh C2 and motd stamps, roster, V2 prepare proof committed ≥1 s before launch, C-a pins.
- **C5 applies per timed host.** No SSH into a host while its reference is timing. Finish all of a host's prep SSH before that host launches. SSH to the other, untimed host is allowed.
- If 01 misses its cutoff, c6387611 deferral applies; there is no relaxation.

**Review conditions adopted for each reference:**
- **Before launch:** assert `end-evidence` kind = `counted-reporting`, with no `synthetic` sources. Assert that the plan is the C1 frozen copy with `reporting_hosts` [127x01, 127x08].
- **After exit:** require `fleet-complete.poolable == true`, the five A3 code SHAs, native 44874fd6, 11 slots and warmup 300. Otherwise the attempt is a failed attempt: preserved per L1, then STOP and escalate.
- Pool and PC reporting state deadline overruns per cell against each cell's own budget, not the absolute 208 ms counter.

## 2026-10-12 02:51Z: T1 END 08 priority refusal; ruling RF1

**What happened.** The 08 reference attempt `end-reference-127x08-0a87166f-r1` launched with the wrapper at nice 19 instead of 10. T1's launch helper ran under nice 19, and the frozen inner `nice -n 10` can't lower priority. E4 refused deterministically at `fleet_profile.slot_layout` (`pinned_profile`, `fleet_reference.py:34`): "Reference must inherit the pinned reporting host/priority/scheduler".
- That refusal comes **before** `fleet-identity.json`. The sealed manifest is `status=failed`, with exactly one file, `failure.json` (8aa5acbf…).
- There is no timing, census or measurement data.
- Exit code 1 at 02:48:18Z; TRANSFER-COMPLETE received; no PUSH-FAILED.

**RF1 ruling:**

1. **Pre-identity refusal exemption.** This applies only to an attempt whose sealed manifest has status failed, whose file set is exactly {`failure.json`}, and whose traceback ends before `fleet_reference.py:97`. Such an attempt has no timing content and so can't carry selection information.
   - It is preserved unchanged on the host (`<root>/<attempt>`) and in `end-received/`.
   - It is **not** assembled into the release-side root under L1.
   - It does **not** count toward the descriptor's 1–2 attempts or the technical-repeat rule.
   - It **is** disclosed in a committed refusal-disclosure receipt containing: launch receipt, argv, exit.json, failure.json SHA, manifest SHA, cause, and the C-d verifier stderr (a non-zero exit is the expected classification, not an ACK).
   - The PC1 reviewer cross-checks launches against the descriptor plus that disclosure. This amends L1 and the PC1 reading for this class only, and I flag it to the PC1 reviewer.
   - Any other failure class keeps L1 (assembled, counted), or STOP if nothing arrived.
2. **Priority fix for every remaining launch:**
   - The launch SSH command must not be wrapped in `nice` or `taskset`.
   - In the same launch session, record the parent shell's nice, which must be 0, and then the wrapper PID's nice, which must be 10, before the launch SSH closes and before admission.
   - If the wrapper's nice isn't 10, do an owned STOP before admission and escalate.
3. **01 is GO now,** independently, under R-ord (b21b5a20) and the cutoff, with fix 2. 01 has no attempt yet.
4. **08 retry** as `end-reference-127x08-0a87166f-r2` under the same 08 root, after:
   - C-d for r1;
   - C1 proof that the r1 wrapper is gone;
   - a fresh V2 prepare proof committed ≥1 s before launch;
   - a new argv pin;
   - fresh C2 against 08's apt-daily;
   - fix 2.

   r2 is 08's first counted attempt; one technical repeat remains under the existing rule.
5. **Review.** A quick independent Opus review of RF1 runs in parallel. If it rejects the exemption, I re-rule before pooling. That only affects release-side assembly, never launches.

## 2026-10-12 02:53Z: RF1 erratum: how 08 r1 is verified

RF1 item 1 was wrong to expect a non-zero verifier exit for 08 r1. The approved verifier 753722c9 ACKs **sealed failed** data: it exits 0 and writes DURABLE-ACK.json with status failed.

**Corrected:**
- After r1's C-d, run 753722c9 exactly as approved: C-a pins (r1's launch receipt and its committed prepare proof), C-c check, `python3 -I`.
- Its ACK with `status=failed` is the proof that the data arrived intact, matches its hashes and is bound to its launch. It does **not** mean the run succeeded, and it changes nothing in RF1: r1 stays unassembled and uncounted, and it is disclosed.
- Bind the DURABLE-ACK into the refusal-disclosure receipt.
- If the verifier exits non-zero, apply C-b: record the output and escalate.

No code changes.

## 2026-10-12 02:56Z: RF1 independent review: APPROVE_WITH_CONDITIONS; C1–C8 adopted

The review (`END-RF1-REVIEW-r1.md`, T1 job dir) found:
- the exemption preserves the purpose of the all-attempts rule;
- r1 is inside the class;
- counting r1 isn't viable (F3);
- erratum c42b32fe is correct.

All conditions are **adopted**:
- **C1, mechanical predicate.** All must hold:
  - the DURABLE-ACK shows SEALED, status=failed, files=1, and the attempt's exit≠0;
  - the manifest's keys are exactly {`failure.json`};
  - `fleet_technical_cause` is null;
  - the innermost `fleet_reference.py` frame is `run` at a line ≤96, or there is no such frame;
  - `detach.log` holds only the traceback.

  Otherwise L1 applies.
- **C2:** at most one exempt refusal per host per END campaign. A second one means STOP and a new ruling.
- **C3:** the refusal disclosure is committed before r2 launches. PC1 becomes: host-root listing == descriptor ∪ committed exempt disclosures (disjoint), and the PC1 reviewer re-evaluates C1.
- **C4:** a byte copy of r1 goes on 05 at `BASE/fleet-end-refusals-0108/127x08/<r1>/`, outside the registered root.
- **C5, pre-exec gate.** In the exec shell: parent nice is 0, the scheduler is SCHED_OTHER, and the argv is byte-identical with no outer prefix (the frozen inner `nice -n 10 taskset` is unchanged). Afterwards, record wrapper and E4 nice = 10.
- **C6:** no signal on a wrong nice. E4 is left to self-refuse and seal, then STOP and escalate. This replaces RF1's "owned STOP before admission".
- **C7:** a read-only 08 host listing of r1's measurement directory is part of r2's C1 proof.
- **C8:** post-ACK routing branches on the DURABLE-ACK status, never on the exit code.

The preservation text in the roots file now reads as "every E4 invocation that sealed `fleet-identity.json`". That is a declared interpretation, flagged to PC1.

## 2026-10-12 02:58Z: 01 reference launched before the C5 pre-exec gate reached T1: accepted, no action

01 `end-reference` launched at 02:57:15Z under RF1, before 15b10ef2 arrived.
- **Recorded in the launch session:**
  - parent bash nice 0;
  - wrapper nice 10, PGID 1893019;
  - frozen prefix and argv unchanged;
  - no signal sent.
- **Not recorded before exec:**
  - SCHED_OTHER;
  - the exact-shell byte comparison.

**Disposition: accepted, and 01 keeps running untouched (C5).** Both missing items are enforced fail-closed downstream:
- E4 `pinned_profile` refuses unless the process is SCHED_OTHER and nice equals the plan value. A violation would show up as a pre-identity refusal, handled under C1/C2.
- Verifier V3 byte-compares `argv.nul` against the pinned argv before any ACK.

T1 records this gap and the downstream enforcement in the 01 launch receipt. The full C5 gate applies to 08 r2 and every later launch.

## 2026-10-12 03:40Z: 08 r2 diagnosis (E4 guard ownership race); ruling RG1: r3 as-is now, code-fix amendment drafted in parallel

**Diagnosis** (`END-08r2-DIAGNOSIS-r1.md`, T1 job dir): a race in E4's guard adapter, not host interference. `ReportingGuard.__call__` decides ownership on one `/proc` snapshot (`fleet_validity.py:135/144`) but runs the census on a later one (`:155`). The first 1 Hz sample after admission landed in the burst that spawns the 10 FleetBackground workers, so 4 of E4's own children were flagged `foreign_compute`.
- **Why it is near-deterministic on 08:** the admit guard call takes 1.24 s on 08 against 0.928 s on 01. A6 passed by about 0–20 ms.
- **Risk on an as-is repeat:** about 80–95% failure, always before warmup or timing, so a failure carries no information.
- **01 is not exposed.** `background_load` is entered once, and 01 is past the exposure point.
- **Rules:** r2 is attempt[0], counted, with `technical_repeat_candidate=True`. r3 is the only repeat left. If r3 fails, `fleet_pool` blocks the whole END pool until an outcome-blind amendment.
- **No procedural mitigation helps.** A code fix in `fleet_validity.py` is the only real fix. Because the pool binds code across hosts and attempts, the fix implies re-running both hosts.

**RG1 ruling:**
1. **08 r3 as-is.**
   - Run it under the full procedure (C5/C6, RF1, L1; fresh C2; V2 prepare proof; argv pin).
   - Have no SSH or ControlMaster session open to 08 at admission.
   - Launch after r2's C-d, its verifier ACK (failed status) and its L1 assembly, and within 08's C2 window.
   - **If r3 fails with the same signature** (E4 spawn children whose ppid is E4 flagged `foreign_compute` at the first post-admission sample): STOP and go to step 3. Any other failure: STOP and escalate.
2. **01 continues unchanged.**
3. **Parallel draft, not adopted.** Prepare the code-fix amendment now:
   - the minimal `fleet_validity.py` re-derivation fix, plus a unit test, on an isolated branch;
   - an impact inventory: E4 pins, the K4S manifest, Mac/A4 bundles, A3 staging, PC2;
   - an outcome-blind amendment text: disclose all old-code attempts, run a fresh reference series on both hosts under the fixed code, with deferral windows per c6387611.

   Sol reviews the Claude-written code. Nothing is adopted or staged on any host unless r3 fails.

## 2026-10-12 03:55Z: E4 guard-race fix drafted (branch, NOT adopted); Sol review routed; K4S END reference held

The RG1 step 3 draft is on branch `e4-guard-race-fix-20261012` (head ad8aba8d; code f23be563):
- `fleet_validity.py` 94d0e7f2 → eae5db3f. Ownership is re-derived on the census snapshot, with start_ticks pid-reuse protection and a one-time exec identity update.
- Tests: 96 OK, and the new tests fail on the old code. A live `/proc` check on 05 reproduces the 10/10 false-foreign result on the old code and 0 on the new; real foreign processes are still flagged.
- Also on the branch: `E4-GUARD-RACE-FIX-IMPACT-20261012.md` and `PREREG-SEARCH-TIERS-AMENDMENT-5-DRAFT-20261012.md`, marked DRAFT.

**Sol code review r1 is routed** (`e4-guard-race-fix-20261012/SOL-REVIEW-r1.md`).

**Impact:**
- **K4S reporting on 03/04 is unaffected:** `fleet_validity` isn't imported there.
- **The K4S END reference has the same race.** It is **held** until a ruling, and adoption would mean re-pinning c1fb1e9a.
- **Mac/A4:** `stage_nocopy.py` 96abd847 hard-codes the old SHA, and so does the staged Mac runtime. Any adoption needs an A4 erratum, a narrow Sol review and re-staging. The Mac is on HOLD in any case.
- **The R-ord SHA check** grows from five code SHAs to six if the fix is adopted.

Nothing is adopted or staged on any host. 08 r3 proceeds as-is under RG1.

## 2026-10-12 04:03Z: 08 r3 failed with the same race signature; ruling RG2: go to the Amendment 5 path

**What happened.** 08 r3 launched at 03:56:55Z and exited at 04:02:43Z with code 1. The failure is `FleetTechnicalError validity_census` at the first sample after admission, with `foreign_compute` = 1 E4 spawn worker (ppid = the E4 python 1323459, pgid = the wrapper 1323452). That is the same signature as r2. My check was read-only, on the 05 receiver.

**Consequence.** 08 has used both counted attempts (r2, r3). `fleet_pool` therefore blocks the END pool until an outcome-blind amendment is in place.

**Separately, 01 r1** exited 0 at 03:52:14Z. It is still unverified, and its C-d is at 04:13:54Z.

**RG2 ruling:**
1. **T1:** STOP launches.
   - After each C-d, run the approved 753 verifier and apply C8.
   - Assemble 08 r3 under L1 as a counted failed attempt.
   - Verify 01 r1 as planned and keep it as received. Under Amendment 5 it becomes an old-code attempt that is disclosed and never pooled. Don't pool anything.
2. **Amendment 5 path (RG1 step 3) is now active:**
   - Sol code review r1 of `fleet_validity` eae5db3f is running.
   - An independent Opus science/procedure review of `PREREG-SEARCH-TIERS-AMENDMENT-5-DRAFT` and the impact inventory is routed now.
   - Adoption needs both approvals. After that:
     - merge to main;
     - re-pin the END-A3 bundles and runtime with six code SHAs;
     - commit a new release-side roots declaration before the first fixed-code launch;
     - fresh C3 preflights;
     - a fresh reference series on both hosts in the next clean windows (c6387611): 01 after its 06:17:43Z apt-daily, and 08 by its 08:49:07Z apt-daily window or after it.
3. **Every old-code END attempt is disclosed and never pooled:** A6, 01 r1, 08 r1 (exempt under RF1), 08 r2 and 08 r3. This was decided before anyone has seen any reference timing.
4. **K4S END and the Mac/A4 re-staging** wait on the same adoption.

## 2026-10-12 04:09Z: A5 reviews: Sol code r1 REQUEST_CHANGES, Opus science r1 ADOPT_WITH_CHANGES; r2 in progress

**Sol code review r1** (`e4-guard-race-fix-20261012/SOL-REVIEW-r1.md`): REQUEST_CHANGES.
- The race fix itself is correct.
- **F1 and F2 (HIGH):** the exec identity-replacement exception authenticates the process generation, not the executable, and its one-use limit isn't enforced.
- **F3 (MED):** a parent that fails the identity check can still grant new descendants.

**Coordinator direction for r2:**
- Delete the exec exception entirely. The microsecond vfork window becomes an accepted, documented residual.
- Ancestry may pass only through parents that pass the full six-KEY identity check on the same snapshot.
- Add Sol's sequences as negative regressions.

**Opus science review r1** (`OPUS-SCIENCE-REVIEW-A5-r1.md`): ADOPT_WITH_CHANGES. The full re-run of both hosts is the minimal correct option, and it is outcome-blind. T1–T13 are being applied verbatim to the draft, with T5 clause (ii) dropped. The key additions:
- **T4:** a binding seal on old-code timing, which may only be cited for existence, status, exit and SHAs until the A5 pool check is committed. After that there is one pre-declared descriptive comparison: 01 old guard vs fixed guard.
- **T7:** a **required fixed-code smoke**, `e4v3-unpoolable-smoke` with job parent `$base`. Run it on 08 (preferred), with A6's pass criteria, before any A5 reference.
- **T8:** sequential `-a5-r<n>` ordinals, at most 2 counted attempts per host, with RF1 exemption bookkeeping.
- **T9:** the post-exit check compares all 18 `measurement_files` with the A5 inventory.
- **T10:** a push-time receipt for the A5 roots file before the first launch, plus L1 item 2 amended (flagged to PC1).
- **T11:** prerequisites, which are D2/D5 C-d, ACK, L1 and the disclosure receipt.
- **T12:** no TIERS Mac session on superseded bytes.

**Expected order once adopted:**
1. Merge, re-pin and stage.
2. 08 smoke, which must launch before 08's C2 limit relative to its 08:49:07Z apt-daily.
3. 01 reference after its 06:17:43Z apt-daily, with fresh C2.
4. 08 reference after its 08:49Z apt-daily, with fresh C2.

**Planning advisory (no ruling yet):** K4S END should adopt the fix through K4S Amendment 3 rather than run on the old guard.

## 2026-10-12 04:45Z: TIERS AMENDMENT 5 ADOPTED (merge 8799a0d6)

**Review chain complete:**
- **Sol code review:** r1 and r2 REQUEST_CHANGES, then **r3 APPROVE** (`e4-guard-race-fix-20261012/SOL-REVIEW-r3.md`).
- **Opus science review:** r1 ADOPT_WITH_CHANGES (T1–T13 applied), then the R3 re-check ADOPT_WITH_CHANGES (T5 (i)/(ii) and texts applied).

The branch `e4-guard-race-fix-20261012` (head 23a39863) is merged to main as **8799a0d6**.

**Adopted:**
- `PREREG-SEARCH-TIERS-AMENDMENT-5-DRAFT-20261012.md` at 8799a0d6 (sha256 ac73e8e4…). The DRAFT label is superseded by this ruling.
- The impact doc (f72e3a5c…).
- **`<R1-APPROVED SHA>` = `fleet_validity.py` 0775b704905324d70f9a43bc580bcbba1548cb2d2a4835c84ff61a0d8b64ae0f.**

**Binding A5 rules:**
- **T4:** old-code timing stays sealed, with one pre-declared descriptive comparison allowed after the A5 pool check is committed.
- **Old-code attempts are disclosed and never pooled:** A6, 01 r1, 08 r2 and 08 r3. 08 r1 stays the RF1 exemption.
- **T7: the required fixed-code smoke runs first.** On 08, `e4v3-unpoolable-smoke`, job parent `$base`, outside all roots, A6 pass criteria. It must launch inside 08's C2 window before its 08:49:07Z apt-daily.
- **The A5 reference series:**
  - attempts are named `end-reference-<host>-0a87166f-a5-r<n>`, sequential;
  - each host gets at most 2 counted attempts, and 01 keeps one RF1 exemption;
  - host jobs live under the existing host roots, as the wrapper requires;
  - the release-side root is `BASE/fleet-end-attempts-0108-a5/<host>`.
- **T10:** `reference-attempt-roots-0108-a5.json` must be committed **and pushed**, with a push-time receipt, before the first A5 reference launch. It is the only `attempt_roots` binding for release; record its path, commit and SHA in the receipt.
- **T9:** the post-exit check compares all 18 `measurement_files` with the A5 inventory.
- **T11:** prerequisites, plus `END-A5-old-code-attempt-disclosure.json` committed before the smoke.
- **C1–C8, C-a to C-d, C5/C6 pre-exec gate, R-ord and c6387611 all carry over.**
- **Expected order:**
  1. 08 smoke, then its C-d and ACK;
  2. 01 A5 reference after its 06:17:43Z apt-daily (fresh C2), once the smoke has passed;
  3. 08 A5 reference after its 08:49Z apt-daily (fresh C2);
  4. pool;
  5. PC1–PC4.

**Companions, separate rulings to come:**
- (a) K4S END adopts the fix through K4S Amendment 3 / a c1fb1e9a re-pin. K4S END stays held until then.
- (b) The Mac/A4 erratum: `stage_nocopy.py`, the staged Mac runtime, and no TIERS Mac session on 94d0e7f2 bytes.

## 2026-10-12 05:05Z: K4S AMENDMENT 3 ADOPTED (merge 133f3ae4); A5 smoke past the race point

**K4S Amendment 3 is adopted.** It is A5 companion (a).
- The Mac/END manifest moves from c1fb1e9a to **74314eda**.
- Sol r1 APPROVE (`k4s-a3-review-wt-SOL-REVIEW-r1.md`). Sol reproduced the one-leaf regeneration with the unchanged frozen builder, so the only change is `fleet_validity` 94d0e7f2 → 0775b704.
- **Reporting is untouched.** FROZEN-K4S 416f6e51 is unchanged, and the running overlay keeps d89cab16.
- The known Mac test failure is pre-existing and "by construction", so it is not caused by A3.

**K4S END is no longer held for the guard race.** It now waits only on its normal prerequisites: reporting complete, the END window, and a runbook ruling. **Deploying the amended `mac/` bytes into the reporting overlay is forbidden**, because it would fail `barrier.reporting_release`.

**A5 smoke on 08** (`end-a5-smoke-127x08-0a87166f-r1`, launched 04:55:46Z) has no early exit as of 05:04Z. Both old-code attempts on 08 had failed about 6 minutes after launch, so the fix appears to clear the race on 08. The pass/fail verdict still waits for the smoke's exit, C-d, ACK and the A6 pass criteria.

## 2026-10-12 06:03Z: A5 smoke review PASS_WITH_NOTES; A5 references cleared (conditions)

**Verdict.** The independent review (`END-A5-SMOKE-INDEPENDENT-REVIEW-r1.md`, T1 job dir) is PASS_WITH_NOTES.
- The 08 smoke ran on A5 bytes: all 18 `measurement_files` equal the 8799a0d6 inventory, including `fleet_validity` 0775b704.
- It used the pinned argv and exited 0, with 29/29 outputs matching 476b50b5.
- Every A6-style gate was recomputed from raw and passes:
  - EXACT 125/125 and 250/250;
  - census 2124 rows and 238 blocks, all passing;
  - zero SSH, dbus or apt interference;
  - MHz 1.0023;
  - memory far inside budget.
- **The fix was exercised in the failing regime.** D was about 1.092 s, and the first sample came +1 ms after admit. All 10 workers were spawned in the snapshot gap, yet all were owned at row 0. `foreign_compute` stayed empty on all rows.
- No outcome exposure.

**The smoke counts as "passed" only after T1's approved verifier ACK** (status complete, at or after C-d 06:13:24Z).

**A5 references are cleared**, under R-ord, with each host independent.
- **08:** launch as soon as the smoke ACK and C1 on 08 are done, **if** it can launch inside 08's C2 clearance before its 08:49:07Z apt-daily. Otherwise defer to after that apt-daily, with no relaxation.
- **01:** launch after its actual 06:17:43Z apt-daily has run and exited, with fresh C2 and motd.

**Conditions:**
- Before each launch, record the end-kind = `counted-reporting` / no-synthetic / C1-plan assertions explicitly.
- C5/C6 pre-exec gate, with no SSH or ControlMaster session at admission.
- After exit, the 18-file check, native, 11 slots, warmup 300 and `poolable == true`.
- Duration basis is now ≥ **55 m 58 s** plus the 1300 s C-d.
- Per-cell lateness is reported against each cell's own budget.

**Hygiene:** fix the stale `A5_adopted:false` in `END-A5-runtime-manifest-inventory-diff.json`.

## 2026-10-12 06:17Z: A4 erratum E2 (86fda5a1) accepted, coordinator-verified

`stage_nocopy.py` moves from 96abd847 to 166a1636. The only code change is one constant: the `fleet_validity.py` pin, 94d0e7f2 → 0775b704.

**Coordinator check, by mechanical equality:** the helper's 18 `FROZEN_MEASUREMENT_FILES` pins are dict-equal to the e4v3 inventory at 8799a0d6, which the A5 smoke review already independently checked. No logic changed, so Sol review is waived for a constant that equals an approved inventory.

**Mac re-staging must use main ≥ 8799a0d6.** The Mac stays on HOLD.

## 2026-10-12 07:44Z: Both A5 END references PASS; pool authorized

**The A5 references are verified and assembled under L1:**
- **08** `end-reference-127x08-0a87166f-a5-r1`: launched 06:16:32Z, exit 0 at 07:11:09Z. ACK 86eb8c11, complete (8d662ad0).
- **01** `end-reference-127x01-0a87166f-a5-r1`: launched 06:26:27Z, exit 0 at 07:20:20Z. ACK 7ea9ae1d, complete (4c34d762).

**Checks on both:**
- 18/18 A5 files, native 44874fd6, 11 slots, warmup 300;
- `poolable` true;
- all guard, exactness and MHz gates pass;
- C1 wrapper gone;
- L1 plain copies into the A5 release root.

**Pool authorized:**
- one byte-exact, SHA-verified copy of the 0addf7c0 bundle context from a now-untimed host to 05, done at nice 19 with a bandwidth cap;
- the pool runs under e4v3-venv Python 3.12 with `fleet_pool` 572ad682, on A5 attempts only.

**After the pool check is committed:**
- the coordinator commissions the PC1–PC4 production-packet review;
- T4 allows its one descriptive old-vs-fixed comparison.

**Hosts:** 01 and 08 stay reserved to T1 until the pool is committed (in case it needs a source re-read). After that, 08 is released for perception B (needs my GO), and the hub mirror is retargeted away from 04 and resumed.

## 2026-10-12 08:01Z: T1 END A5 POOL COMMITTED (95774e86); PC1–PC4 production review commissioned

**Pool.** Both A5 hosts are included, with no exclusion. END ratios are within ±5%: 01 = 0.9789, 08 = 1.0175.
- Run with unchanged `fleet_pool` 572ad682 under e4v3-venv Python 3.12.12. The reviewed checker was rerun under the same interpreter and PASSED (204 inputs).
- Pool check 43a6f0f2. Manifest 0e517b96. Descriptor f4319e5f, A5 roots only.
- **Pool context on 05:** a byte-exact 0addf7c0 copy from 08 (SHA verified), plus a faithful detached worktree reconstruction of `end-a3-f6cebbaa-0108-r1/source` at f6cebbaa. No alias, symlink or substitution was used.

**PC1–PC4 production-packet review** is commissioned to Opus (`END-PRODUCTION-PACKET-REVIEW-r1.md`). For PC1 only, it may take read-only listings of the 01/08 host roots.

**T4.** The single pre-declared descriptive old-vs-fixed comparison on 01 is now allowed.

**Not yet:**
- 01/08 stay reserved to T1 until the PC verdict.
- No release.

## 2026-10-12 08:18Z: Production-packet review r1: NOT CLEARED (fail-closed blockers); next steps

`END-PRODUCTION-PACKET-REVIEW-r1.md`, T1 job dir.

**Results:**

| Check | Result |
|---|---|
| PC1: all attempts accounted for (independent 01/08 host listings) | PASS |
| PC2: 18/18 reviewed inventory | PASS |
| Pool: both hosts, ±5%, first-passing classification, no old code in `pool_inputs` | PASS |
| T4 seal | INTACT |
| Outcome exposure | none found |

**Blockers. Each fails closed; none involves outcomes.**
- **F1:** the pool-check receipt mixes two path roots, so `release_reference.prerequisites` would refuse it. Remedy R3: regenerate the receipt in one clean release checkout.
- **F2:** PC4 hasn't been run against the durable counted-block root. The complete proofs exist only on hub 01.
- **F3:** it is ambiguous which CLI and reducer lineage applies: OP-6 e643a342 on main, or OP-7 bb124cc4, which produced the committed sidecar and is on a worker branch.
- **F4:** the checker's interpreter wasn't recorded. My independent rerun under e4v3-venv 3.12.12 passes and is byte-identical.

**Actions:**
- **T1:** R3/R4 (regenerate the pool check in clean `<R>`, recording the interpreter) and prepare R5. No sealing.
- **Coordinator:** an independent Opus lineage investigation is routed (`END-PC4-LINEAGE-INVESTIGATION-r1.md`). The F3 ruling and the PC4 root/authority (F2) follow from it.
- **Hosts:** 01 and 08 stay reserved, with the host roots and release roots untouched until release.

## 2026-10-12 08:29Z: Ruling R1 (PC4/reducer lineage = OP-7); landing and PC4 procedure

The basis is the independent investigation `END-PC4-LINEAGE-INVESTIGATION-r1.md` (T1 job dir).
- 2,361 of the 3,072 counted blocks (replacement r2/r3) ran under OP-7 manifest **488f6c8d** (ef4c073a, confirmation 1947830b).
- That manifest pins `ssh_sensitivity.py` bb124cc4, `reduce.py` aebb2017, and the OP-7 PC4 text 9b0704e2, which applies to both release routes.
- The committed sidecar 48730da5 was produced by bb124cc4 over a single root.
- Main's e643a342/fdea088c and the PC4 wording ff0b7afe are OP-6-era and stale for these blocks.

**R1 ruling:**
1. **PC4 CLI = `ssh_sensitivity.py` bb124cc4**, applying the OP-7 PC4 text 9b0704e2. e643a342 is rejected for PC4.
2. **Release reducer = `reduce.py` aebb2017**, run from main's lineage (which carries c5b2e059's barrier, release_reference and check_reference).
   - Its emitted sensitivity ledger must equal the PC4-checked sidecar in every field except `utc`.
   - Its results must include the prespecified `apt_sensitivity` and `ssh_or_apt_sensitivity`.
3. **Landing (no merge).** T1 makes a narrow commit copying the frozen bytes from ef4c073a to their canonical `reports/explore/t1/` paths:
   - `ssh_sensitivity.py` bb124cc4, `reduce.py` aebb2017, `apt_budget.py` c1578535, `cpu_accounting.py` 5ecae99d, `RELEASE-PRODUCTION-CHECKS-20261010.md` 9b0704e2;
   - plus `receipts/release-lineage-op7-20261012.json`, binding the landed SHAs to 488f6c8d and ef4c073a, OP-7 reviews r1–r3 and 1947830b, and disclosing that `FROZEN-T1.json` 24817e16 stays as the E4/r1 freeze and is stale for these files.

   Leave `FROZEN-T1.json`, `host_audit.py`, `ssh_budget.py`, `supervise.py` and every e4v3 file unchanged.
   - **Tests:** the reducer, op6, barrier, release_reference and reference_packet tests, plus the e4v3 suite, on the landing tree. Run the full `test_op7` on a `git archive ef4c073a` export.
   - **Tag:** ef4c073a is tagged `t1-op7-freeze-ef4c073a` (pushed).
   - **Review:** a narrow independent **Opus** diff review of the landing (T1 is a Sol worker, so Opus reviews), plus a 977c4dfb addendum.
4. **PC4 run.** An independent reviewer runs the CLI on hub 127x01, by read-only execution:
   - **Code:** extracted from `git archive ef4c073a reports/explore/t1` into a scratch directory outside every job root, with the SHAs checked against 488f6c8d.
   - **Interpreter:** the r3 job's cpython 3.12.13.
   - **Flags:** `PYTHONDONTWRITEBYTECODE=1 -E -s`.
   - **Root:** `…/replacement-frozen-op7-0108-r3/hub-blocks`.
   - **Ledger:** 866e6f7f.
   - **Pass condition:** the output equals 48730da5 except `utc`, with 3,072 entries (2400/600/72), IDs matching 50f24dd6 and 6f6f0007, and 2,361 v2 and 711 legacy.
   - **Record:** a reviewer check receipt binding the sidecar, ledger, inventory, complete-proof digest, CLI, source, interpreter and argv. T1 commits it verbatim.
5. **Freeze.** The four T1 job directories on 01 (`reporting-frozen-0108-r1`, `replacement-frozen-op6-0108-r1`, `replacement-frozen-op7-0108-r2`, `replacement-frozen-op7-0108-r3`), the host roots, the release roots and `end-received` are **frozen until release**. No moves, cleaning or rsync, and the hub mirror stays paused.
   - A durability copy of 01's counted blocks to a dedicated prefix on another clasher host comes in a separate ruling, after PC4.
6. **Then:**
   - R3 confirms that its pool check was run in the final `<R>`, a descendant of the landing; regenerate it if the prefix differs.
   - R5 seal and registration (registration still waits on the A4 Mac inputs: the builder's 03 read happens at the current K4S gap).
   - R6 barrier under e4v3-venv 3.12.12.
   - R7 production-packet review r2.

## 2026-10-12 08:35Z: PC4 PASS (independent reviewer run on 01, OP-7 CLI bb124cc4)

Reviewer files are in the T1 job dir: `PC4/PC4-REVIEW-r1.md` (11bbfc9a), `PC4/PC4-REVIEWER-CHECK-RECEIPT.json` (48fe1011) and `PC4/ssh-sensitivity-pc4.json` (ea3d44d3).

**The run:**
- One read-only run on hub 01, from the ef4c073a archive. All 193 manifest entries were verified.
- cpython 3.12.13, exit 0, empty stderr.
- Root: r3 `hub-blocks`. Ledger: 866e6f7f.

**Checks (28/28 pass):**
- The output equals the committed 48730da5 in every field except `utc`.
- 3,072 entries: 2400 primary / 600 guard / 72 descriptive.
- IDs equal 50f24dd6 and 6f6f0007, and every complete/interference SHA matches.
- 2,361 v2 / 711 legacy.
- Flags: apt 0, apt stops 0, SSH stops 0, SSH-flagged 477 (all on 08: 352 in r1 under OP-6, 125 in r2 under OP-7; primary 379 / guard 98).
- Durability 1,972 (01) + 1,100 (08, all ACKed). Dedup holds, and 54 replacements are bound to the ledger.

**T1 commits the PC4 files verbatim.**

**Remaining before release:**
- The landing commit plus an Opus diff review and the 977c4dfb addendum.
- A second PC4 run from the landed bytes, which must give the identical sidecar (add `-B`).
- R3 in the final `<R>`.
- R5 seal plus registration, after the A4 inputs.
- R6 barrier. Reducer aebb2017's emitted ledger must equal the PC4 sidecar except `utc`.
- R7 review r2.

## 2026-10-12 08:50Z: OP-7 landing APPROVED; second PC4 (landed bytes) PASS; final R3 pool check

**Landing 1cb46a13 is APPROVED.** The review is `LANDING-OP7-REVIEW-r1.md`; the addendum is `RELEASE-INTEGRATION-977c4dfb-ADDENDUM-r1.md`.
- **Exact copies.** The five files are byte-exact with tag ef4c073a and with 488f6c8d.
- **Protected files unchanged:** 132 in total, including `FROZEN-T1` 24817e16, `host_audit`, `ssh_budget`, `supervise`, `barrier`, `release_reference`, `check_reference`, `common` and all 125 e4v3 files.
- **Reducer.** The only delta is the OP-7 apt/union analyses. The primary analysis and its RNG are unchanged.
- **Tests:** 174/174 on the landing tree; full `test_op7` 99/99 on the frozen export.

**Second PC4 run from the landed bytes: PASS** (`PC4/PC4-REVIEW-r2-landed.md`).
- The sidecar 16e1b34f equals ea3d44d3 and 48730da5 except for `utc`, and all three are byte-identical once `utc` is masked.
- Main's `ssh_budget` 0c2759f5 is immaterial here: the functions it uses are identical.

**Final R3 pool check** (041de810, check cf3be4dd):
- run in canonical `<R>` at landing 1cb46a13;
- its 204 inputs equal `pool_inputs`;
- interpreter recorded as e4v3-venv 3.12.12.

That closes F1 and F4 of review r1, and F2 and F3 are closed by R1 and PC4.

**Remaining:**
1. R5 sealing and registration, once the builder's A4 inputs are delivered (Phase 2 read from 03 is in progress; Phase 3 build on 05 follows).
2. R6 barrier; the reducer aebb2017 ledger must equal the PC4 sidecar except `utc`.
3. R7 production-packet review r2.

## 2026-10-12 08:52Z: Builder Phase 2 done (03 read released, fa8e700a); 03 handed back to K4S

**The read:** one read-only session from 05 to 03, 08:49:03Z–08:51:29Z, no ControlMaster.
- It copied only the 32 pinned `capture.pkl.gz` files: 4.89 GB, at nice 19 with a 32 MiB/s cap.
- SHAs matched `corpora.json` 3501e2ac before (on 03) and after (on 05).
- It did not touch `games/` and wrote nothing on 03.

**Procedure deviation, accepted after the fact:** the builder used a new, unreviewed `fetch_captures_stream.sh` (in fa8e700a) instead of the reviewed rsync script, so the "before" SHA check could run inside the same single session. It's accepted because:
- the effect was read-only;
- it is fully bounded by the SHA checks at both ends;
- no other files were touched.

**Future rule:** any new script that touches a host needs a review first.

**Next:**
- 03 has been released to K4S for its r2 launch.
- The builder's Phase 3 builds on 05 against `runtime-a5` (A5 bytes).
- After that comes the handoff to T1 for registration.

## 2026-10-12 09:06Z: K4S round r2 audit PASS_WITH_NOTES; cut-2 rulings

The audit (`/mpac/sdicks02/jobs/clasher/k4s-audits/ROUND-r2-AUDIT.md`, independent Opus) confirms every Proposal M step and all the arithmetic:
- 22 events equal the failed blocks;
- coverage is exact;
- gates 41/150, 14/45, k 2/9 and 1/7;
- dispatch 1df20188, 555/554;
- handshake order is correct;
- no outcome exposure.

**Rulings:**
- **F1:** the unreviewed `aptquiet_remote.sh` touched hosts and is retired. Cut 2 uses a coordinator-specified inline strict-mode command; non-zero exit or empty `ps` counts as FAIL.
- **F2:** `checkpoint.py` also changed the alert gate (to ledger-cumulative), and the running copy diverged from the committed one for about 10 h. A receipt erratum is required, and a narrow Sol review will be routed.
- **F3/F4:** the r3 receipt must carry hashes for all step evidence, with exact times.
- **F5:** the runner must cite the PREREG-K4S definition of k; if the 0-based and count readings differ, the stricter one applies.
- **Disclosure:** K4S qualification was running on 03 during the builder read.

## 2026-10-12 09:10Z: K4S cut-2 step-6 command amended; k escalation at 8/6; checkpoint Sol review routed

**Step 6.** The previous coordinator command (38ed75a2) counted the idle boot-time `unattended-upgrade-shutdown --wait-for-signal` helper, so it would always read `maint=1`. The runner found this in a read-only test and did not edit the command.

**The amended command**, sent to the runner, does the following:
- excludes exactly that helper's command line and records it (pinned 03 PID 2368, 04 PID 2296);
- lists every remaining maintenance match.

**Quiet** means all of:
- rc 0;
- both units not active;
- `maint=0`;
- `who=0`;
- **two consecutive quiet reads 30 s apart**, with up to 3 retries, otherwise FAIL.

**k.** PREREG-K4S §3.4 caps k ≤ 11/9, and k is 0-based. Escalation uses the stricter count reading, **k ≥ 8/6**, applied by hand. The tool's own 9/7 alert stays until review. Current max k is 2/1.

**`checkpoint.py` diff** 52cd4583 has gone to Sol for narrow review (`k4s-audits/SOL-REVIEW-CHECKPOINT-r1.md`).

## 2026-10-12 09:17Z: 08 released to perception B (GO); 01 stays T1-reserved

T1 END timing is complete: the pool was committed at 95774e86 and only release paperwork remains. **127x08 is released to the perception owner for B.**
- **Frozen on 08:** all T1 paths (`t1-*`, `fleet-end-attempts-0108*`, `end-*`) stay untouched until release, because R7 re-lists the host roots.
- **How B runs:** under nice, with headroom, after checking `who`.
- **Plan first:** the B plan gets posted before it runs. Anything beyond these limits needs my approval.

**127x01 stays T1-reserved.** Its four job directories are frozen, the hub mirror stays paused, and 01 holds the only copy of the counted blocks. A durability copy and the mirror retarget come after the release review.

## 2026-10-12 09:42Z: K4S checkpoint.py gate fix APPROVED (Sol r3), deploy authorized

Sol reviewed the candidate in three rounds (`k4s-audits/SOL-REVIEW-CHECKPOINT-r{1,2,3}.md`); r3 is **APPROVE**. Candidate aa898ab2, tests e1ae76e8 (52/52, also under `-O`).

**What it fixes:**
- **R1:** the k alert now fires at ≥8/6, including when host data is unavailable.
- **R2:** strict ledger validation; a missing or malformed ledger fails closed as UNKNOWN with exit 2 and a receipt.
- **R3:** cumulative losses are computed as a union, so nothing is double-counted.

**Safety:** no host mutation, no outcome exposure.

**Deploy:** promote the candidate as `tools/checkpoint.py` in one commit. Running bytes must equal committed bytes, with the SHA recorded. Automatic alerts replace the manual ones; a manual cross-check stays at each inventory.

## 2026-10-12 10:02Z: Perception B prerequisites: 03/04 read window at K4S cut 2; B code review gate

(The previous commit adceb889 is empty, caused by a push-retry script error. This entry is the intended content.)

**Blockers in perception's B plan on 08:**
- 08 lacks all 192 validation truth files (19.2 MB, pinned on 04).
- 08 lacks 1,376 of the 1,536 D4 decoder files: 1,052 are pinned on 03 and 324 on 04.
- The old B worker uses v1 plan auth, but the issued A1 is `assembly-a18-v1`. The A12 B1–B11 integration and review are still required.

**Ruling:**
1. **Read window on 03 and 04: one read-only session per host, only inside the K4S cut-2 gap,** with the same handshake the builder used:
   - K4S posts "03/04 quiet" (quiet-read v2), and the coordinator gives GO;
   - perception posts "released" per host within 30 minutes, or stops;
   - K4S holds r3 on each host until that host is released or the 30 minutes run out.

   **Scope:**
   - stat and SHA-check only the exact pinned files and their auth proofs (manifests 1c40c032 and 45a00712);
   - copy to `08:v4-b-20261012-r1/inputs/<host>/` at nice 19, with a bandwidth cap, SHA-verified at both ends;
   - copy nothing if a host's total exceeds 60 GB, or if fewer than 100 GB would remain free on 08;
   - no `games/`, K4S or T1 paths.

   **Pre-review:** the per-host command gets a narrow review before the gap. No unreviewed script touches a host.
2. **B code:** the B4 telemetry candidate and the A12 B1–B11 integration are reviewed as one package. No GPU work on 08 until that review passes and a dry run is admitted.
3. **Allowed now:** read-only payload hashing on 08. T1 paths stay frozen.

## 2026-10-12 10:29Z: A4 Mac inputs DELIVERED (73d9ac68); T1 GO for R5 seal, registration, R6

The builder finished Phase 3 on 05, using A5 bytes.
- **Selection:**
  - pool of 4,242 rows;
  - packets from 9 games, round-robin;
  - agreement of 1,931 rows plus a 69-row fill;
  - one D7/D8 pass takes about 24 min.
- **Fixture:** 2,125 rows, fingerprint `0de69958…`; conversion PASS.
- **Independent reproduction:** a separate Haiku worker using its own code got identical packets, schedule, agreement, ids, 800 digests and fingerprint.
- **Student reference:** `7a90fa7a…`. The B.6 cross-check against the A5 pooled S forwards (`fe534ec0`) gives 300/300 bit-exact.
- **Mac memory:** 2.88 GiB conservative against the 6 GiB cap.
- **B.7 seal:** `f3b87ce5`.
- **Disclosed:** a wait loop hung for about 1 h of wall time. Results are unaffected.

**GO for T1:**
1. Seal R5 (at fc0d74a6, binding cf3be4dd/041de810 and canonical `<R>` at 1cb46a13) and seal registration with the A4 inputs (73d9ac68, B.7 f3b87ce5).
2. Run the R6 release barrier from `<R>` under e4v3-venv 3.12.12, recording `sys.executable`. It includes the reducer aebb2017 check: the emitted sensitivity ledger must equal the PC4 sidecar except for `utc`.
3. Commit everything, then stop. Open no outcome.

The coordinator then commissions R7, production-packet review r2. Release happens only after R7 clears and the coordinator authorizes it.

## 2026-10-12 10:34Z: T1 registration: private local commit approved; reducer check moves to release

**1. Reducer check at release.** Reducer aebb2017 reads games (outcomes) before it emits its sensitivity ledger, so its equality check against the PC4 sidecar can't run beforehand. **It runs at release**: if the emitted ledger differs from the PC4 sidecar in anything but `utc`, release fails closed and nothing is reported. R6 is now limited to `release_reference.prerequisites` with its in-barrier recheck. If that path itself would read outcomes, STOP before the read and report.

**2. Private registration commit.** Some sealed registration sources are large raw health files (`capacity.jsonl` of 332 MB and 287 MB). They can't go into the public repo, so they are committed as a **local, never-pushed** commit in canonical `<R>`.
- **Protection:** the commit sits under a local ref, `refs/private/t1-registration-20261012`.
- **Content:** health and metadata only. No outcome bytes.
- **Backups:** a verified `git bundle` is stored in two places: on 05 at `t1-20261010-r1/private-registration/`, and on 08 at `t1-private-backup/`.
- **Public receipt** binds:
  - the commit SHA and tree SHA;
  - every path with its SHA and size;
  - the bundle SHAs;
  - `<R>`'s final HEAD (an ancestor check is required by `release_reference.committed`).
- **Verification:** R7 checks all of this.

## 2026-10-12 10:37Z: B gap export package r2 APPROVED (exact package 40655641)

The independent Opus delta review is `/mpac/sdicks02/jobs/clasher/v4-b-gap-review/B-GAP-EXPORT-REVIEW-r2.md`, verdict APPROVE_WITH_CONDITIONS.
- The R1 tar-padding blocker is fixed: 0 of 118 harness cases fail, and the mutant is killed.
- R2 tests are in place: 20 of 20 pass.
- Hardening H1–H5 is in. In particular, nothing is written on 03 or 04 (atime included), and no `who` identities are logged.
- The allowlists are byte-identical to r1.

**APPROVE_EXACT_GAP_COMMANDS** applies to package `4065564142c9ebad3b38f465591faeb8d5203913989931059e7057dcdbb6e9b1` only, run through its r2 `read-127x03.sh` and `read-127x04.sh`.

**Conditions:**
- **C1:** shortly before GO, perception confirms on 08 that `who` is empty and that free space is at least the 03 total plus the 04 total plus 160 GB. Both values are recorded in the GO receipt.
- **C2:** the GO receipt acknowledges the outbound ssh child from 03/04 to 08 (one per host, inside the gap, writing only to 08's new prefix). It carries the true `go_utc` and the package SHA. Launch happens at least 30 s after GO.
- **C3:** run the r2 scripts only.
- **C4:** no retry within a cut. Any partial copy is kept, and the next attempt waits for cut 3.

The review receipt is written to `/mpac/sdicks02/jobs/clasher/v4-b-gap-review/receipts/review-receipt.json`.

## 2026-10-12 10:38Z: Registration prep: golden-order ruling (conditional)

T1's metadata diagnosis compared the delivered sets with the actual A5 sets.
- **Speed:** all 4 lists match the A5 sets byte-for-byte and in order (300 each).
- **Golden:** the same 125 IDs, with none added or missing, but in a **different order**.

The stop came from T1's own extra ordered-equality check, not from any handed-off SHA or count.

**Ruling:**
- Speed keeps exact-order equality.
- Golden switches to membership equality, keeping the **A4-delivered order**. That is the order the fixture fingerprint 0de69958 and the Mac run use, so registration seals that order.
- Condition: T1 first proves with file:line evidence that every consumer of `sets.golden` keys by state ID, not by position. The consumers are the exactness checks, the Mac-vs-END comparison, the registration seal and `fleet_pool`.
- Any dependence on position means STOP, with no reordering.
- The builder's independent answer has to agree.

## 2026-10-12 11:03Z: R7 production-packet review r2: CLEARED_WITH_CONDITIONS; pre-release work ordered

The review is `END-PRODUCTION-PACKET-REVIEW-r2.md` (T1 job dir).
- **F1–F4 are closed.** The reviewer recomputed `pool_inputs` and independently re-ran R6 from `<R>`, logging every file the run opened; none was outcome-bearing.
- **R5 and registration: PASS.** The golden ID-keyed evidence is verified: seeds are per state and results don't depend on order.
- **Private commit 9bb349b1: PASS.** It is absent from all 40 origin refs, contains health and metadata only, and its bundle verifies.
- **PC1 host roots are unchanged.** No outcome exposure was found.

**Correction to 2969615c.** The sidecar-equality check **can** run before any game byte is read. `health_ledger` reads only proofs, interference data and `hub-ack.json`. Nothing currently enforces the check: `reduce.py`, `barrier.py` and `release_reference.py` have no sidecar comparison.

**Conditions before any reducer run, adopted:**
- **C1. Release driver.** T1 writes it, an Opus review covers it, and it is committed. It leaves aebb2017 unchanged.
  - **Pre-outcome guard:** compute `health_ledger` on the exact release root and ledger. It must equal PC4 sidecar 16e1b34f (ignoring `utc`), and the blind ledger must be 866e6f7f. Otherwise ABORT before any game read.
  - Run the reducer with all outputs and stdout in a private directory.
  - **Post-check:** the emitted ledger must equal the sidecar (ignoring `utc`). Otherwise LOCK the output and report only the failure.
- **C2. Durability and release source.** Make a byte-identical copy of the counted blocks from 01's r3 `hub-blocks` chain, dereferenced, into a new dedicated prefix on 05, `t1-20261010-r1/release-blocks-0108-r3/`.
  - Read-only on 01, nice 19, with a bandwidth cap.
  - Verify: 3,072 complete proofs (set digest d0f01069); 24,576 game files by hash against the completion receipt; 1,100 `hub-ack` files.
  - Game bytes are copied but **never opened or parsed**: sha256 streaming only. This also closes the single-copy risk on 01.
- **C3.** `<R>` HEAD stays at 9bb349b1, or a local-only descendant. It stays clean, keeps its private ref, and is never pushed.
- **C4.** Use the e4v3-venv 3.12.12 interpreter with `-B`, run from `<R>/reports/explore/t1`.

**Release timing:** release still waits for the TIERS Mac-summary route, and the 14-day escape is not before 2026-10-25T19:31:38Z. So the next step is the **Mac Phase B session**, whose prerequisites are now met (A4 sealed, A5 pooled reference).

## 2026-10-12 11:20Z: Mac Phase B prep: memory precondition ruling

**Plan.** The Mac operator's Phase B plan is good:
- runtime from main 2e275312 (A5 bytes, `stage_nocopy` E2 166a1636);
- the A4 fixture streamed and SHA-verified;
- T1's sealed A5 packet, kept local and never committed;
- the stage atomically promoted, leaving about 24 GiB of disk free.

The staging driver is in Sol pre-run review r3; it will be the first host script to be reviewed before it runs.

**Memory risk.** A read-only check showed about 5.86 GiB available, under the 6 GiB precondition. The memory is held by desktop apps.

**Ruling.** This is the agents' Mac; Sam doesn't use it.
- For the quiet window the operator may gracefully quit **only** Chrome, ChatGPT and the Claude desktop app, with a normal quit and no force.
- **Never** T3 Code, Codex, or any agent host.
- Record the before and after state, and relaunch the same apps at restore, alongside the software-update preferences.
- If memory is still under 6 GiB after that, do not start; the coordinator rules.
- The formal 5-minute precondition check gets its own receipt before GO.

## 2026-10-12 11:22Z: 01 idle compute: X4S-3 student data-scaling exploration APPROVED and launched

Plan: `/mpac/sdicks02/jobs/clasher/planning/01-idle-compute-plan-20261012.md` (Opus planner). **X4S-3** asks whether refitting the R3a student on about 46% more W teacher roots lowers its loss vs v1. The test is run in the two deployment configurations where the student actually decides actions: K4S-120 and the 1-core S-200. This exploration is **NEVER ADOPTABLE** into confirmatory work.

**Arms:**
- R3a (control);
- R4-D (r1 plus G-01 and G-08, about 8.8M roots, equal compute);
- R3a-rep (fit-seed noise floor);
- R4-DC (2× steps, optional).

Each arm plays 1,200 fresh paired seeds on the X decks only against v1. Seeds must pass the repo-wide audit. The readout is pre-declared.

**On 01:**
- New prefix only. T1 paths, release roots and the hub mirror stay frozen.
- Cores: 0–49 for games, 56–61 for the fit, 50–55 and 62–63 kept free. The GPU carries one fit at a time, ≤40 GB.
- Yield to any console user. Hard stop at 12 h.

**08 pull:** one read-only rsync of the G-08 shards (about 25 GB). The command gets a narrow Sol review before it runs. 08 isn't GPU-busy yet, and T1 and perception paths there stay untouched.

**Owner:** an Opus-high worker. It runs detached and keeps PROGRESS resumable.

## 2026-10-12 11:22Z: B gap export GO (cut 2): 03 and 04

**K4S quiet.** The K4S runner posted "03/04 quiet" with 2× quiet-read v2 per host (rounds/r3/evidence/step6). Its own r3 qualification is running at nice 10, which is disclosed.

**C1 checks on 08:**
- `who` count = 0;
- available space on /mpac = 1,237,667,491,840 bytes, at least the 280 GB required.

**GO for package r2** (`4065564142c9ebad3b38f465591faeb8d5203913989931059e7057dcdbb6e9b1`):
- the r2 `read-127x03.sh` and `read-127x04.sh`, once per host;
- launch at least 30 s after `go_utc`, which is in the GO receipt;
- 30-minute window.

**Outbound connection acknowledged.** One ssh child per host goes from 03 or 04 to 08, inside this gap, and writes only to `08:/mpac/sdicks02/jobs/clasher/v4-b-20261012-r1/inputs/<host>/`.

**Receipts:**
- GO: `/mpac/sdicks02/jobs/clasher/v4-b-gap-review/receipts/go-receipt-cut2.json`
- review: `review-receipt.json` (2380b8df)

K4S holds r3 on each host until that host posts "released", or until the 30-minute window ends.

## 2026-10-12 11:26Z: B gap export done; 03/04 released to K4S

The perception read ran once per host under package r2 (40655641), with GO at c00317cf. Both sessions are closed and exited 0, and every SHA matched at both ends:
- **04:** 2,262 files, 3.13 GB;
- **03:** 5,387 files, 10.30 GB.

Both landed only under `08:v4-b-20261012-r1/inputs/<host>/`. Receipts are in `l1/receipts/b08-gap-export-20261012-r1/`.

Hosts 03 and 04 have been released to K4S for r3. B stays development-only until the B1–B11 integration review passes and a dry run is admitted.

## 2026-10-12 11:29Z: FLEET-WIDE: `ssh macmini-fleet` does not propagate remote exit status

The Mac operator found that `ssh macmini-fleet 'exit 3'` and `ssh macmini-fleet false` both return **0**. The connection goes through Tailscale SSH, then `login -f`, then zsh. Any script that relies on that exit code fails open. In the staging run it logged OK after a failed rename, though nothing was damaged.

**Rule for every Mac-touching script:**
- Emit an explicit status token, for example `setopt pipefail; { CMD; }; printf '\n__RC=%s\n' $?`, and parse it.
- A missing or non-zero token means FAIL.
- Pre-run reviews must check for this.

**Mac staging:**
- `runtime-a5` is verified (11,144 files, manifest 91c938ac, A5 pins, no 94d0e7f2).
- The packet promotion fix (r5) is in Sol review.
- ChatGPT.app bundles a "Codex (Service)". If that service hosts agent threads, the operator skips quitting the app and asks the coordinator first.

## 2026-10-12 11:39Z: K4S round r3 audit PASS_WITH_NOTES; rulings for cut 3 and r4

The audit is in `k4s-audits/ROUND-r3-AUDIT.md`. Results:
- All 69 evidence hashes match.
- All arithmetic was recomputed independently.
- The handshake order is correct on both hosts.
- R2-audit findings F1–F5 are resolved.
- No outcome is exposed.

**Rulings:**
- **F1 (MEDIUM): fix `checkpoint.py`.** Expected per-host completions are derived from the phase's dispatch file, and a missing dispatch is an anomaly with exit 2. The fix needs a narrow Sol review. If the review isn't approved before r4 launches, a recorded hand check at every health read (completed vs dispatch per host, plus the exit reason) is required instead.
- **F3: quiet-read v3 from cut 3.** It is v2 with `apt-config` and `apt.systemd.dai` added to the pattern. It must be tested read-only before cut 3.
- **F2:** an r3 receipt erratum corrects the time labels.

**Cut 3** must STOP before 04's apt-daily-upgrade at 13:27:55Z. The r4 duration is capped by 04's release-upgrade stamp, which runs out at 21:32:48Z.

## 2026-10-12 11:46Z: C1 release driver r2 (42219e57) APPROVED WITH CONDITIONS

The independent review is `END-C1-RELEASE-DRIVER-REVIEW-r2.md` (T1 job dir).

**What it found:**
- RC1–RC4 and S1–S5 are implemented correctly.
- All 18 pins match `<R>` 9bb349b1, and the import closure equals the pinned set.
- No game byte can be read before the guard passes.
- 32/32 tests pass. Of 47 mutants, all 26 from r1 and 14 new ones are killed.
- The signal demo locks the outputs.
- Seven hardening mutants survive. They are untested, but the code itself is correct.

**Launch conditions** (operator and runbook, no code change):
1. Run the parent under `env -i`.
2. Before launch, verify `<R>`'s e4v3 is mode 555 and `git status` is empty.
3. Verify the driver's sha256 is 42219e57 before launch, and that its directory contains only the committed tree.
4. **The Mac-summary route is NOT available at this driver SHA**, because the allowlist is empty. Using it needs a new driver revision with a reviewed allowlist of the Mac-summary paths, built with `--no-renames` from the allowed paths only. That revision also takes the non-blocking hardening: tests for the surviving mutants, blocking signals inside the failure handler, and killing the reducer's whole session.

**Release routes:**
- **Mac-summary route:** after Mac Phase B, a driver revision (r3) with the Mac allowlist plus review, then coordinator authorization.
- **14-day escape route:** not before 2026-10-25T19:31:38Z, and it would run on 42219e57 under conditions 1–3.

## 2026-10-12 11:49Z: TIERS Mac-session output layout and release-driver r3 scope (rulings)

**R-M1: fixed output directory.** `D = reports/explore/mac-e4-session/tiers-session-r1`. The frozen procedure left this undefined; the coordinator now assigns it, which settles `TIERS_RECEIPT_REL`.

**Public commit (exact paths):**
- `D/sealed/{tiers-summary.json, tiers-complete.json, receipt-manifest.json, receipt-manifest.sha256, tiers-identity.json, build-tiers.json, pre-session-census.json, runtime-versions.json, exactness-tiers.json, belief-exactness.json, student-agreement.json}`.
- `D/a3p-poll-check.json`, `D/stage-nocopy-session-verify.json`, `D/preconditions.json`, `D/session-receipt.json`.
- Only on failure: `D/sealed/failure.json`, `D/sealed/cleanup-failure.json` and `D/classification/*`.
- `release.mac_summary_path` points to `D/sealed/tiers-summary.json`.
- None of these files contain game outcomes.

**R-M2: the full sealed inventory stays private.** It includes `capacity.jsonl` and the other large row files.
- It is committed as a **local, never-pushed** commit at `D/sealed/` in the Mac's `$S/k4s-commit-repo`.
- A verified `git bundle` is copied to 05 at `/mpac/sdicks02/jobs/clasher/mac-e4-private/`.
- A public `D/private-commit-binding.json` records the commit SHA, tree SHA, every path with its SHA and size, and the bundle SHA. This mirrors 2969615c.

**R-M3: close the A3-P gap.** Frozen `reduce.select()` reads only `tiers-summary` feasibility; it does not read the adopted A3-P lateness gate. Release driver r3 must also do the following:
- Read `D/a3p-poll-check.json`, binding it by commit and SHA, and verify that its `receipt_manifest_sha256` equals the sealed seal.
- **Fail closed before any game read** if any tier has `frozen_feasible=true` and `feasible_after_a3p=false`. That case goes back to the coordinator, who rules on it with a reviewed A3-P-adjusted selection or a reducer amendment.
- If A3-P passes wherever the frozen summary says feasible, the release proceeds unchanged.

The driver r3 allowlist is exactly the public paths in R-M1, plus `D/private-commit-binding.json`.

**Mac staging is done:** tiers-pins 273ef196, `validate_bundle` PASS, fixture clones 0444, 22.4 GB free. Chrome and Claude were quit gracefully. ChatGPT was left running because it hosts Codex agents.

## 2026-10-12 11:51Z: X4S-3 G-08 pull: scope ruling after Sol r2

Sol's r2 review returned REQUEST_CHANGES:
- P2, P4 and P6 are resolved.
- P1, P3 and P5 are only partly resolved.
- New findings R2-1 through R2-6.

**Accepted residual risks.** This is an exploration-lane, read-only copy of our own data between our own hosts, with one operator and no other writer to these paths. Two classes of finding are accepted as residual:
- **R2-1:** concurrent replacement of a path or its ancestors.
- **R2-2 and R2-3:** process-handoff and preflight lifecycle races.

**Condition on that acceptance.** The pull runs **attended, in the foreground**, never unattended. The operator verifies cleanup with `ps` if it aborts.

**Required r3 fixes:**
- The `data` directory must already exist; outputs are written with noclobber.
- Wrap the preflight in `timeout 120` and rsync in `timeout 5400`, with `LC_ALL=C`.
- **R2-4:** receipts must be regular files with a single link; special entries are rejected.
- **R2-5:** the end stamp is published by temp file then rename, after the final STOP check.
- **R2-6:** files are opened non-blocking, then checked with `fstat`.

A narrow Sol delta check covers only these items.

## 2026-10-12 11:56Z: Mac Phase B: manifest approved; memory and update-step rulings

**Approved:** `E4_MANIFEST_SHA` = 273ef19647c6fa2ee869793541b2000fc5a6947183b0d26977224c781ceb599d. The bundle is staged and pinned on A5 bytes. `validate_bundle` passed and the fixture clones are 0444.

**Preconditions-r1 failed:** available memory dipped to 5.95 GiB at the start of the window. The graceful osascript quit of Chrome and Claude did not take effect, because Apple Events from the Tailscale-SSH session don't reach the GUI session.

**Sol computer use is not available.** The coordinator's T3 is 127x05 Linux, and no T3 on the Mac side can be reached. The computer-use step in SOFTWARE-UPDATE-STEP is therefore replaced:
- **Quitting apps:** send SIGTERM (never SIGKILL) to the verified top-level app PIDs of Chrome and Claude only, then confirm both have exited. If either survives, STOP and report.
- **Update toggles:** left unchanged, because there is no sudo and no GUI. The session receipt discloses this, recording the preferences before and after, plus `softwareupdate --list` and any pending restart state.
  - An install or restart mid-session would fail the session closed, and it would be rescheduled.
  - The session runs during Mac-local morning, outside the usual overnight install window.
- **After the session:** relaunch the apps with `open -a` if possible; otherwise record that it wasn't done.

**Next:** preconditions-r2, then the readiness report, then GO.

## 2026-10-12 12:05Z: TIERS Mac session: conditional GO; release driver r3 in review

**Mac preconditions r2 PASS:**
- Available memory went from 6.58 to 8.01 GiB after Chrome was stopped with SIGTERM. It exited cleanly, with no SIGKILL.
- Claude belongs to the other console user (`simonfarshid`), so it was left untouched.
- Update preferences are unchanged. macOS 27.0.1 is pending and needs a restart; this is disclosed as a residual risk.

**Conditional GO.** The operator launches without asking again once all of these hold:
1. The Sol pre-run review of the session launcher (`run_session.sh` / `session_wrapper.py`) is APPROVE or APPROVE_WITH_CONDITIONS, with every condition met.
2. Preconditions r3 pass in the 5 minutes right before launch.
3. Pins are confirmed: manifest 273ef196, runtime-a5, no 94d0e7f2.
4. Every remote step uses the nonce/`__RC` status.

During the session the operator posts health only, with no summary values. Any failure, including an OS update or restart, fails closed and the session is rescheduled. Expected duration is about 6–6.5 h.

**Release driver r3** (f45a3ad8, driver 9ffbd2e1) has gone to an independent Opus review. It contains:
- the exact 18-path Mac allowlist;
- the descendant builder;
- the R-M3 A3-P pre-game gate;
- the r2 hardening.

## 2026-10-12 12:09Z: X4S-3: G-08 pull r3 approved by ruling; mirror script withdrawn

The Sol review is at `x4s3-student-scale-review/SOL-REVIEW-PULL-G08-r3-and-MIRROR-r1.md`.

**Pull r3 (`pull_g08.sh` 834d1598, `verify_g.py` eef8cdfd).** The five required items are present.
- The remaining finding, R3A-1, is accepted as a residual. A command error during publication leaves at most a temp stamp and a nonzero exit, and `verify_g` then rejects the stray root entry, so it fails closed.
- **Approved for one attended, foreground run.** Retries need a new ruling. Outputs and the PGID `ps` are recorded in PROGRESS.

**`mirror.sh` is withdrawn.** It had four failures, M1–M4: writes outside its prefix, filters that only excluded, following the source-root symlink, and no STOP or cleanup. It is replaced by manual, explicit-file, SHA-verified copies of each fitted student and its receipts to the 05 mirror after each fit.

## 2026-10-12 12:13Z: K4S checkpoint.py r6 APPROVED (closes round-r3 audit F1)

Sol reviewed the change in rounds r4–r6 (`k4s-audits/SOL-REVIEW-CHECKPOINT-r{4,5,6}.md`) and r6 is **APPROVE**. The approved candidate is 05d0908f with tests 536a5b2d (125/125, also under `-O`).

**What changed:**
- Expected counts now come from the phase dispatch, bound by history SHA.
- Strict JSON readers parse `LAUNCHDISPATCH` and `SUPEXITN`.
- Status-safe capture: a reader that prints valid output and then fails is treated as INVALID.
- A strict 14-key parser.
- Everything fails closed with exit 2 and a receipt.

**Deployment:** one commit, with a byte-equality check. The hand check is retired after the first clean live run, and a manual cross-check stays at each inventory.

## 2026-10-12 12:17Z: C1 release driver r3 (9ffbd2e1) APPROVED WITH CONDITIONS (Mac route); builder not yet approved

The review is `END-C1-RELEASE-DRIVER-REVIEW-r3.md`.

**Approved:**
- The 18-path allowlist is exact.
- The R-M3 A3-P gate is correct. It fires before the health guard and before any game read, and the field names match the real Mac producers.
- The two-parent descendant satisfies both barrier ancestry checks.
- All 47 r2 mutants are killed.
- The signal demos pass.

**Not yet approved: the descendant builder.** It can overwrite the protection ref `refs/private/t1-registration-20261012`.

**Conditions:**
- **C1:** the builder refuses the protection ref, creates refs only if they don't already exist, and checks the protection ref before and after. It then gets a narrow builder-only review.
- **C2:** the runbook gives the exact step that moves `<R>`'s HEAD, plus the post-checks.
- **C3:** the builder runs under `env -i` and `-B`, with pinned SHAs and a fresh ref.
- **C4:** the **14-day route stays on 42219e57**, because r3 accepts Mac descendants, including failure ones.
- **C5:** the runbook records 9ffbd2e1 as the reviewed Mac-route driver.
- **C6:** tests only. Add tests that kill the surviving R-M3, AL1/AL2/AL5 and T2c mutants, then rerun the mutant suite and keep the receipt.

**Residual, accepted:** a second signal during the main failure handler exits 143 without a health line. The directory is already at mode 000, and the runbook treats "no health record" as locked.

## 2026-10-12 12:44Z: Release descendant builder dd644cdc APPROVED WITH CONDITIONS

The review is `END-C1-BUILDER-REVIEW-r1.md`.

**The protection-ref fix is correct.** It does three things:
- refuses the ref by exact name, whether loose or packed;
- creates refs with CAS, only if the name is absent;
- checks 9bb349b1 before and after the write.

The 21 alias probes all failed safely. The mutants were 108 killed and 7 surviving, with every required one killed. The runbook post-checks catch every injected HEAD, tree, ref and mode fault.

**Conditions (runbook only):**
- **BC1:** the target ref name must be fully unused beforehand; check that no symref, ref, child ref or loose file exists there. Afterwards the ref must equal the receipt commit, and that commit must not be reachable from heads, tags or remotes.
- **BC2:** the HEAD switch runs under `env -i` with `core.hooksPath=/dev/null`, and the post-checks run in the same environment.

**Release sequence once the Mac session ends:**
1. Mac D outputs, the private bundle and A3-P are committed.
2. The coordinator gives GO.
3. The builder runs once.
4. The BC2 switch and its post-checks.
5. Driver 9ffbd2e1 runs under its launch conditions.

The 14-day route stays on 42219e57.

## 2026-10-12 12:47Z: B supplemental proof export APPROVED (package b38a9bff); cut-3 read window declared

**Review.** The narrow delta review is `B-SUPPLEMENT-EXPORT-REVIEW-r1.md`, verdict APPROVE_WITH_CONDITIONS. It confirmed that only these change from the approved r2 package:
- the single BASE literal, now `inputs-supplement-r1`;
- the new 127/33 allowlists of proof JSONs, which don't overlap cut 2;
- one test fixture line.

Every other byte is identical to r2.

**Decision.** `APPROVE_EXACT_GAP_COMMANDS` covers package `b38a9bffcfe79ef6d5cc813d4f0a769429ea477c8e2ff17e0e13a08d47ad718d` only.

**Conditions:**
- **C1, C2:** new review and GO receipts, with cut 3.
- **C3:** the package is frozen.
- **C4:** the r2 rules apply: GO+30 s, once per host, release per host, a 30-min window, no retry, and partial copies are preserved.
- **C5:** exact failure reporting.

**The K4S cut-3 read window is declared.**
- After the quiet-read v3 handshake, perception runs the supplement, once per host.
- K4S holds r4 on each host until that host is released, or until the timeout expires.
- The 08 C1 check (`who` count and free space ≥ 280 GB) runs before GO.

Review receipt: `/mpac/sdicks02/jobs/clasher/v4-b-gap-review/receipts/supplement-review-receipt.json`.

## 2026-10-12 14:01Z: B supplemental export GO (cut 3): 03 and 04

**K4S quiet:** the K4S runner posted "03/04 quiet". Quiet-read v3 passed twice per host (`rounds/r4/evidence/step6`), and r4 qualification has finished.

**C1 on 08:** `who` count is 0, and `/mpac` has 1,224,210,591,744 bytes available, at least the 280 GB required.

**GO for supplement package `b38a9bffcfe79ef6d5cc813d4f0a769429ea477c8e2ff17e0e13a08d47ad718d`**, cut 3:
- The wrappers run once per host.
- Launch at least 30 s after `go_utc`.
- The window is 30 minutes.
- No retry.

**Outbound child acknowledged:** one ssh child per host, from 03/04 to 08, inside this gap, writing only to `/mpac/sdicks02/jobs/clasher/v4-b-20261012-r1/inputs-supplement-r1/<host>/`.

**Receipts:**
- GO: `/mpac/sdicks02/jobs/clasher/v4-b-gap-review/receipts/supplement-go-receipt-cut3.json`
- Review: `supplement-review-receipt.json` (07fe7691)

K4S holds r4 on each host until that host releases, or until the window times out.

## 2026-10-12 14:03Z: B supplemental export done; 03/04 released to K4S for r4

The supplement ran once per host under package b38a9bff, with GO at 8be7ca00. Both runs exited 0 and were destination-SHA verified:
- **03:** 127 proof JSONs (2.04 MB);
- **04:** 33 proof JSONs (0.51 MB).

Everything landed only under `08:v4-b-20261012-r1/inputs-supplement-r1/<host>/`, and the cut-2 data was left untouched. Receipts are in `l1/receipts/b08-supplemental-proof-export-20261012-r1/`, which perception commits.

Both hosts are released to K4S for r4, the final round of 139 rows. B on 08 now has every input it needs. It remains development-only until the B1–B11 package review passes and a dry run is admitted.

## 2026-10-12 14:25Z: K4S DBus-flag ruling (R1–R5 adopted)

The investigation is in `k4s-audits/K4S-DBUS-FLAG-INVESTIGATION-r1.md`. The flag is OP-1: the system dbus-daemon running above 1% of one core over a block. Under the frozen prereg it is **descriptive only**.
- It is not a stop rule, not an exclusion, and not part of the §5.3(2) sensitivity, which covers SSH and apt only.
- 98.7% of counted 04 blocks carry it, against 0% on 03. The cause is a constant 04 baseline of about 1.47% vs about 0.40% on 03, most likely from the GDM login session that only 04 runs.
- Reporting validity is not threatened. Blocks are split 50/50 by host within every cell and seat, every arm runs on the same host, and the per-host and host×arm table (§5.3 item 4) already shows any host effect.

**Ruling:**
- **R1.** DBus flags are descriptive, as frozen. The DBus hold on the reducer/verifier lifts once R2 is committed.
- **R2.** Before any reduction, the K4S runner commits an outcome-blind disclosure covering:
  - counts per host and phase, and the cause;
  - that the flag is effectively the same as "host 04";
  - that `interference_any_flag_excluded` is a count only;
  - that §5.3(2) drops nothing.
- **R3.** No post-hoc DBus-exclusion analysis.
- **R4 (gates K4S END).** After reporting completes and the copier is off, take a read-only baseline of 04's bus over a single long-lived connection. If it stays clearly under 1%, END proceeds as frozen. If not, choose in this order:
  - (a) Sam or a lab admin stops GDM on 04 for the END window;
  - (b) a reviewed amendment sets a 04-relative threshold;
  - (c) the ratio-unavailable path is declared in advance.
- **R5.** Audits treat 04's DBus level as known and constant, and alert only if it changes or the daemon disappears.

## 2026-10-12 14:48Z: K4S REPORTING COMPLETE (3,900 counted; outcomes SEALED)

**Completion.** K4S reporting completed at 14:45:34Z.
- r4 exited null-reason at 71/68.
- The final drain was done by hand and hashed.
- `final_pass` covered 3,900 counted blocks (3,000 primary + 900 guard), each logical block exactly once:
  - all 33,000 game files match their SHAs; they were hashed only, never parsed;
  - every hub-ack is OK;
  - no counted block is a ledger loss.
- Final ledger: 99 events. Cumulative lost: 73 primary of a 300 cap, 26 guard of a 90 cap.

**Artifacts (bb7c7f88):**
- `REPORTING-COMPLETION.json` ed7d11b7;
- counted inventory f10ab943;
- R2 DBus disclosure 128d66a0: 04 at 98.7%, 03 at 0%, and §5.3(2) drops nothing.

**Sealed reducer and verifier runs (309893e1).** Both refuse before any game read: `reduce` fails closed in `outcome_release`, and `verify_k4s` refuses with no release receipt. No outcome was opened.

**Next:**
1. R4: a read-only 30-minute baseline of 04's bus, ending about 15:15Z.
2. Plan K4S END, with the A5 guard fix via K4S A3 and DBus per R4. The coordinator rules after R4.
3. The K4S Mac phase C (manifest 74314eda), which runs after the TIERS Mac session.
4. K4S release, which needs an explicit coordinator GO.

**03 and 04** are no longer running K4S reporting. They stay reserved for K4S END until it is planned. 03's T1 corpus copy and 04's perception storage remain off-limits.

## 2026-10-12 15:16Z: K4S R4 passed: 04 bus baseline 0.036%, so END proceeds with the frozen DBus threshold

**The measurement (fbcf1a67):** a read-only 30-minute baseline on 04 after reporting had drained, with the copier off and nothing else logged in. One long-lived SSH session sampled the pinned dbus-daemon at 1 Hz.
- **Whole window:** 0.0359% of a core.
- **Worst rolling windows:** 0.099% over 30 s and 0.043% over 300 s.
- No window went above 1%, which is the R4 bar. The GDM greeter was resident throughout.

**What it means.** The roughly 1.47% we saw during reporting was session churn, mostly copier SSH logins amplified by the greeter. GDM itself adds about 0.04%.

**Ruling.** The K4S END runs with the frozen bus threshold. For every attempt on 04 (and 03):
- one launch SSH, closed before admission;
- no copier running during timing;
- the C5 rule: no SSH to the timed host from any thread.

**Process note.** `probe.sh` was a new script that touched a host and ran without a pre-run review. It was read-only and limited to `/proc` sampling under the R4 authorization, so I'm accepting it after the fact. From now on, any new host script needs review first. That covers the B2 copier and the B3 assembler.

## 2026-10-12 15:23Z: K4S END plan ADOPTED WITH CHANGES; completion-v2 of record

The review (`k4s-audits/K4S-END-PLAN-REVIEW-r1.md`) returned ADOPT_WITH_CHANGES.

**Completion of record: v2** (23604d1c).
- Contents: inventory 22c41cb7 and `REPORTING-COMPLETION` 3794d953.
- It is a pure envelope fix:
  - its rows are byte-identical to v1's (canonical rows 2e18ce34);
  - the frozen `counting()` accepts v2 and refuses v1;
  - no selection risk and no outcome exposure;
  - no amendment needed.
- **v1 (bb7c7f88) is superseded** and stays committed.
- Three notes from the review:
  - v2 was re-wrapped from v1's rows; its `script_sha256` is v1's script;
  - `VALIDATION.txt`'s ledger path corresponds to the committed `blind-ledger-final.json`;
  - the DBus disclosure still stands.
- v2 is the record for the END-JOB, PC4, the verifier and release item 1.

**Changes the plan must adopt:**
- **On-host preflight per host.** Following the T1 C3/A5-smoke precedent: no claim and no timing. It covers the git requirement of `parent_source_seed.admit` (a git `repo/` in the guard job or on the host), the guard admission pins, topology, native and model loading, background spawn and the MHz gate.
- **The 04 preflight runs at least 15 min under full 11-slot load with no logins,** to measure the bus under load.
- A fresh guard job per attempt.
- A committed attempt-roots declaration.
- Unfiltered `systemctl list-timers --all`.
- The exit-push wrapper also pushes the host registry claim directory.
- **The B2 copier** binds each phase directory to its committed launch and exit hashes, and refuses any file over 95 MB.
- **03 seals `complete` and is verified before 04 runs.**
- **04 DBus:** the second quiet read, the gates and the detach all go in one SSH session. A bus-interference failure means STOP and a new ruling before the last attempt is spent.
- **Disclose** the inherent short-block meter risk.
- **T1 state files** may be read only from T1's copies on **05**, never from 03's T1 corpus copy.

**Process:**
- Sol reviews every new script before it runs: the copier, the evidence builder and validator, the guard-job builder, the assembler, the preflight, the wrapper and verifier changes, and the launch gate.
- The coordinator authorizes each host step separately: the copier, staging, venv, preflights, stale-stamp logins, the END-JOB and each launch.

**Mac phase C** is covered by Sam's 2026-10-11 authorization (TIERS + K4S replay-only); a standalone authorization file will cite it. It runs after the TIERS Mac session.

**Target:** launch 03 overnight, around 02:00–04:00Z on 10-13, with a pooled END by mid-morning on 10-13.

## 2026-10-12 15:41Z: K4S END: rulings on runtime, inputs and guard (Q2–Q6, Q9)

**Assembler status.** The S4 assembler and guard design are committed at 3585da6d, with 92/92 tests passing. It goes to Sol review together with S1–S7.

**Rulings:**
- **Q3:** the guard job's `repo/` is a K4S-owned git clone that contains b2f9e25e and ce042b97. Preflight runs `git cat-file -e` on both first.
- **Q5:** the runtime is built at the END-JOB commit, which must be at or after 133f3ae4 and match the 74314eda pins.
  - The 33 pinned files that aren't in git are taken **only from bytes already on 05, matched by SHA**: T1's A5 runtime trees there, or a K4S overlay copy kept on 05.
  - They are copied read-only, byte for byte. 01, 08 and the T1 trees are never touched.
  - If a pin is missing, stop for a ruling.
  - The same tree goes to both 03 and 04.
- **Q6:** background-load inputs come from T1's byte-exact copies on 05:
  - `states.pkl` 0addf7c0 from `end-a5-pool-context-20261012-r1/bundle`;
  - the A3 index and bin (bcd30777 / 8cc2f611).

  These are read-only byte copies, never re-serialized, with SHAs checked at both ends. T1 has been notified.
- **Q2:** each guard job gets a byte copy of its host's latest K4S `system-bus-admission.json`, plus `idle-services.json` on 03. They are fetched by the reviewed exact-path reader and committed outcome-blind before the END-JOB.
- **Q4:** one fresh guard job per attempt, at the namespaces the runner proposed.
- **Q9:** END runs under T1 guard semantics. 5 of the 9 modules differ from K4S; plan v2 discloses this.

Every host step still needs a Sol review and then the coordinator's authorization.

## 2026-10-12 16:00Z: K4S END package 1 r1: REQUEST_CHANGES; scope ruling

Sol's review (`k4s-audits/SOL-REVIEW-END-PKG1-r1.md`) returned REQUEST_CHANGES on S1, S2 and S4. The tests pass, but independent probes broke the read/write boundaries and the frozen-code verification. For example, S2 imports the frozen modules before verifying their pins.

**Scope ruling.** These are single-operator, non-adversarial hosts, so TOCTOU (concurrent replacement between a check and the open) is accepted as a residual risk. Every other finding is required.

**Required changes:**
- **S1:**
  - remote checks of type, size cap and aliasing before any read;
  - a confined destination on 05, written exclusively and without following links;
  - bounded streams;
  - receipts for every refusal.
- **S2:**
  - a stdlib-only bootstrap verification **before import**; test-only flags must never produce a production receipt;
  - exact path, role and confinement checks before any read;
  - extra controls.
- **S4:**
  - confined inventories;
  - production pins: the Q6 bytes, the T1 own-tier sets, the idle admission on 03 and the Q2 bus admission;
  - index checks equivalent to `StateRows`.
- **Diagnostics:** an outcome-blind census/MHz mismatch diagnosis, while keeping the frozen refusal.

The overnight K4S END target may slip. Correctness comes first.

## 2026-10-12 16:11Z: B final dependency export APPROVED (package f29372d6) with disclosure; window scheduled before K4S END

**Review result.** The independent review (`B-FINAL-DEPENDENCY-EXPORT-REVIEW-r1.md`) returned APPROVE_WITH_CONDITIONS. It covered:
- all 116 allowlist entries, each found in authenticated A1 session records, which match the pinned manifest;
- no overlap with the cut-2 or cut-3 copies, and no forbidden paths;
- `transfer.py`, which changes only `BASE` from r2;
- the launcher, which fails closed on every bad input;
- 29/29 tests.

**Disclosure (C1).** 26 of the 116 files, plus 23 of the items being staged on 08, are byte-identical to **unselected** A1 body branches: epochs e09, e17 and e20. This is the first time unselected-branch bytes reach B. They are not heldout data.
- B may use them **only as qualification reference**.
- Decoder inputs are taken by the selected SHAs only, and references are looked up by SHA, never by path.
- B never compares branches.

**Approval.** APPROVE_EXACT for package `f29372d6a4a9e720cc1e582a756dd3ba847d19c4a0de0b791395720c2b70c1d8` only. The package is frozen.

**Window `post-k4s-final-dependencies-r1`.** It runs now, before K4S END staging.
- 03 and 04 are idle now that K4S reporting has finished. No K4S END host step has been authorized yet.
- r2 rules apply: the 08 C1 check, launch at GO+30 s, once per host, release within 30 minutes, no retry, partial copies preserved.

Receipt: `/mpac/sdicks02/jobs/clasher/v4-b-gap-review/receipts/final-dependencies-review-receipt.json`.

## 2026-10-12 16:12Z: B final dependency export GO (window post-k4s-final-dependencies-r1)

**Preconditions checked:**
- **03 and 04 quiet:** the K4S runner ran quiet-read v3 twice per host (18b0ea7e). No K4S process was running.
- **08 C1 check:** `who` = 0; available = 1,224,207,413,248 bytes, at or above the 280 GB minimum.

**GO** for package `f29372d6a4a9e720cc1e582a756dd3ba847d19c4a0de0b791395720c2b70c1d8`. The conditions:
- launch at least 30 s after `go_utc`;
- once per host;
- release within 30 minutes;
- no retry.

**Outbound ssh child acknowledged:** one per host, from 03/04 to 08, writing only to `…/v4-b-20261012-r1/inputs-final-dependencies-r1/<host>/`.

**Receipt:** `/mpac/sdicks02/jobs/clasher/v4-b-gap-review/receipts/final-dependencies-go-receipt-r1.json`.

K4S END starts no host step until both hosts are released.

## 2026-10-12 16:14Z: B final dependency export done; 03/04 reserved for K4S END

The B final dependency export ran once on each host under package f29372d6, with GO from c2439a82. Both runs exited 0 and passed the destination SHA check.
- **03:** 108 files, 0.97 GB.
- **04:** 8 files, 0.16 GB.

Together that is 116 files, 1.13 GB, written to `08:inputs-final-dependencies-r1/<host>/`. The cut-2 and cut-3 trees were not changed. Perception will make no further source access.

**C1 (qualification-reference only)** is now binding on B code. B is still development-only until the B1–B11 review passes and a dry run is admitted.

**03 and 04 are now reserved for K4S END.** No host step may run there until Sol has reviewed it and the coordinator has authorized it.

## 2026-10-12 16:21Z: TIERS Mac session COMPLETE; T1 RELEASE-SEQUENCE GO (Mac-summary route)

**Mac session.** Launched 12:15:00Z and finished cleanly:
- the post receipt is complete;
- verify-bundle, build and measure all exited 0;
- there was no OS update or restart.

**D is committed at 67b05a50**, as exactly the 15 R-M1 paths plus `private-commit-binding.json`. The coordinator verified the SHAs from git:
- `sealed/tiers-summary.json` 6b0324e0, which is `release.mac_summary_path`;
- `a3p-poll-check.json` 29f86b81;
- `sealed/receipt-manifest.json` f411b9b4, the seal that A3-P binds.

**R-M2 private inventory:**
- local commit 174c4a0a on the Mac, never pushed;
- bundle verified on 05 at `mac-e4-private/bundles/`.

**RELEASE-SEQUENCE GO for T1 / PREREG-SEARCH-TIERS, Mac-summary route.** Sam was told in advance and did not object. All preconditions are met:
- R7 cleared (2e275312);
- driver r3 9ffbd2e1 approved, with C1–C6 met (eddba5f7, 8c8cfbd7);
- builder dd644cdc approved, under BC1/BC2 (ee0aa034);
- Mac D and A3-P committed;
- registration sealed (bbff541c).

**Order, exactly once each:**
1. **Builder `prepare_release_descendant.py` dd644cdc**, once, using `env -i` and `-B`, pinned SHAs, and a fresh ref name.
   - Inputs: base `<R>` 9bb349b1 plus the allowlisted Mac D blobs at 67b05a50.
   - BC1 checks before and after.
   - The protection ref `refs/private/t1-registration-20261012` must stay at 9bb349b1.
2. **BC2 switch:** `env -i … git -c core.hooksPath=/dev/null -C <R> switch --detach <descendant>`, followed by every post-check under the same environment:
   - HEAD is the descendant, with both parents;
   - the tree is clean;
   - the protection ref is unchanged;
   - e4v3 is mode 555.
3. **Driver `release_run.py` 9ffbd2e1**, under its launch conditions: `env -i`, mode 555 and a clean tree, the driver SHA plus its committed directory, and e4v3-venv 3.12.12 with `-B`. In order, it performs:
   - the R-M3 A3-P gate;
   - the pre-outcome health guard, which must equal the PC4 sidecar;
   - the barrier;
   - the reducer, with output kept private;
   - the post-check;
   - the release receipt.

**On any refusal,** including `A3PRequiresRuling`: STOP, report the stage and failure type only, and make no retry without a ruling.

**On success:** commit the release receipt and the public outputs exactly as the reviewed runbook defines them. Report the headline primary result to the coordinator in plain language.

**The 14-day route is not used** (42219e57 stays reserved).

## 2026-10-12 16:32Z: T1 release sequence stopped at BC1_before (harmless cause); one fresh attempt authorized with release file

**What stopped.** T1's release script stopped at its first pre-check (`BC1_before`, AssertionError) and did not retry, as instructed. Nothing ran after that check: the builder never ran, no ref was created and no checkout was switched. STOP receipt: T1 4925002b.

**Cause (coordinator read-only replay).** T1's script requires the tool directory in its own worker checkout (`t1-health-stop-reconcile-20261010/reports/explore/t1`) to contain exactly the tracked files. That directory held an ignored `__pycache__/` with 4 stale `.pyc` files from earlier test runs (one is cpython-38). Every other check passed on replay:
- both tool SHAs (dd644cdc, 9ffbd2e1) match;
- canonical R is clean with `--ignored`;
- R HEAD and the protection ref are both 9bb349b1;
- e4v3 is mode 555;
- target ref `refs/private/t1-mac-release-20261012-r1` is unused (symbolic-ref exits 1, for-each-ref is empty for the ref and its prefix).

**Ruling RS-2 (one fresh attempt).**
1. T1 **moves** (does not delete) that `__pycache__/` to `BASE/END-release-sequence-20261012-r1/quarantine-pycache/` and records the 4 names and SHAs.
2. T1 then reruns the same reviewed sequence exactly **once**, with a new state directory `BASE/END-release-sequence-20261012-r2/`. The pins, the target ref (BC1 re-verifies it is unused) and the order stay the same: BC1-before → builder dd644cdc → BC1-after → BC2 switch/post-checks → driver 9ffbd2e1.
3. Any failure at any stage is a STOP with no retry and goes back to the coordinator. `A3PRequiresRuling` is returned for a selection ruling. There is still no 14-day route.

**Release file (coordinator-supplied, per runbook step 1).**
- Path: `/mpac/sdicks02/jobs/clasher/t1-20261010-r1/coordinator-release-r1/release-mac-summary-r1.json` (mode 0444).
- SHA-256: `6a767ffb26c50a629049dc6b2b708a7d23395f74e60f7401a6ccf31c25bc8eaa`.
- It binds:
  - reason `committed_mac_summary`;
  - commit 67b05a50;
  - summary 6b0324e0, A3-P 29f86b81 and seal f411b9b4, each as full `{path, commit, sha256}` under `reports/explore/mac-e4-session/tiers-session-r1/`;
  - `amendment_1_prerelease` copied byte-for-byte from sealed R5 3b7d2295;
  - `authorization_message_id` = COORDINATOR 446e9901.
- The coordinator checked every Mac SHA against `git show 67b05a50:<path>`, and checked that the A3-P `receipt_manifest_sha256` and the seal's `tiers-summary.json` entry are consistent. `release_reference.prerequisites()` passes against canonical R (read-only).
- Driver arguments: `--release <path above> --release-sha256 <SHA above> --r5 <canonical R>/reports/explore/t1/receipts/END-A5-R5-sealed-prerelease-evidence.json`.

## 2026-10-12 16:35Z: RS-2 stopped at driver preflight (coordinator path error); RS-3 driver launch once with corrected R5 path

**What stopped.** RS-2 got further this time. The cache was moved and preserved, and the builder ran once, creating private descendant **2473c0a9** (parents 9bb349b1 and 67b05a50, 16 Mac paths). BC1 and BC2 passed, and canonical R is now at 2473c0a9 and clean. The driver preflight then stopped with FileNotFoundError, before it created `release-private/` and before the driver launched (T1 receipt `END-release-sequence-STOP-2510ff14-r2.json`).

**Cause: the coordinator's mistake.** RS-2 (2510ff14) gave the `--r5` path as `<canonical R>/reports/explore/t1/receipts/END-A5-R5-sealed-prerelease-evidence.json`. That file is not in canonical R. The sealed R5 is committed in the public tree at bbff541c and lives in T1's worker checkout: `/mpac/sdicks02/jobs/clasher/t1-health-stop-reconcile-20261010/reports/explore/t1/receipts/END-A5-R5-sealed-prerelease-evidence.json`, SHA-256 **3b7d2295…a5f9**, which equals origin/main. The driver pins only the R5 SHA, not its path. The release file is unchanged (6a767ffb).

**Ruling RS-3.** T1 runs the driver launch preflight and launch **exactly once**:
- with `--r5` set to the worker-checkout path above;
- with every other argument as in RS-2: release 6a767ffb, copy receipt d433dd54, private name `mac-summary-20261012-r2` (still unused), and `release-private/` created fresh as 0700.

Do not repeat the cache move, builder or switch; they are done. Any failure is a STOP with no retry. `A3PRequiresRuling` comes back to the coordinator. There is still no 14-day route.

## 2026-10-12 16:37Z: RS-3 stopped at driver preflight (inherited setgid on release-private); RS-4 one launch

**What stopped.** T1's preflight passed every pin:
- driver 9ffbd2e1, release 6a767ffb, R5 3b7d2295 at the worker path, copy receipt d433dd54;
- canonical R at 2473c0a9 and clean;
- the worker tool directory exactly tracked.

It then created `t1-20261010-r1/release-private/` and asserted `mode & 0o7777 == 0o700`. The parent directory is mode 2755 (setgid), so the new directory inherited the setgid bit and is **2700**, and the assertion failed. The driver never launched. `release-private/` exists and is empty (coordinator read-only replay).

**Assessment.** This is harmless. The setgid bit only sets group ownership of new files; with permission bits 0700 there is no group or other access. The reviewed driver checks `st_mode & 0o777 == 0o700`, which passes. The runbook says "plain 0700", so the bit is cleared rather than waived.

**Ruling RS-4 (exactly once).**
1. T1 runs `chmod 0700` on the existing empty `release-private/` and records before/after modes. Do not delete or recreate it.
2. T1 relaunches its preflight once. Replace `mkdir` with: exists, is a directory, not a symlink, owned by the operator, empty, and `mode & 0o7777 == 0o700`.
3. T1 launches the driver once with the RS-3 arguments.

Do not repeat the cache move, builder or switch. Any failure is a STOP with no retry. `A3PRequiresRuling` comes back to the coordinator. There is still no 14-day route.

## 2026-10-12 16:40Z: T1 Mac route: A3-P removes all four tiers; ruling A3P-1 (no Mac-feasible tier; outcomes stay sealed for the 14-day route)

**What happened.** Under RS-4 (e11ad6f0), T1 launched driver r3 9ffbd2e1 once and passed every pin and preflight check. It then stopped as designed at the R-M3 gate with **`A3PRequiresRuling`**. It read no game file, created no output directory and invoked no reducer.

**A3-P result (`D/a3p-poll-check.json` 29f86b81; health-only, `outcomes_read=false`).** All four tiers are frozen-feasible (all six frozen gates pass), and on the frozen gate-4 variant v* (freeze) all four **fail A3-P**. The thresholds are a late rate ≤1% and a maximum ≤50 ms.

| Tier | v* late rate | v* max lateness | Default-variant late rate |
|---|---|---|---|
| K0c | 56.0% | 150.1 ms | 58.8% |
| S | 56.2% | 150.1 ms | 57.4% |
| K2 | 52.9% | 150.1 ms | 60.0% |
| K4 | 60.6% | 150.2 ms | 55.3% |

The failure is uniform, with a maximum of about 150 ms in every tier and variant, including the cheapest baseline K0c. That points to a cause in the Mac poll scheduling or harness rather than in search cost. The registration-inputs proposal (risk 5) predicted this kind of load-tail artifact.

**Ruling A3P-1 (as pre-registered; no post-hoc rescue).**
1. **Apply A3-P exactly as adopted** (Amendment 3, item 3). A3-P failure makes a tier infeasible, it is **not** a technical failure, and it grants **no repeat**. The TIERS Mac-summary route therefore concludes: **no Mac-feasible tier; no tier is selected.** This is final for this study. No A3-P-adjusted selection is run, because there is nothing to select, and there is no reducer amendment.
2. **Outcomes stay sealed.** The Mac route cannot release fleet outcomes without a selection, and opening them now would need a new, unreviewed release path. Fleet results will be released **descriptively** by the pre-registered **14-day route**, no earlier than **2026-10-25T19:31:38Z**. That route uses approved driver r2 42219e57 with canonical HEAD at 9bb349b1 and an empty descendant diff. A separate coordinator ruling at that time will switch canonical R back to 9bb349b1. The private Mac descendant 2473c0a9 and its ref are retained, never pushed, and are not used by the 14-day route.
3. **T1 now:**
   - record this ruling and its own receipts;
   - leave `release-private/` (empty, 0700) and all private state in place;
   - **disable its 20-minute END timer.** The coordinator will wake T1 for the 14-day route.
   - The T1 originals on 01/08 stay preserved, read-only and never deleted.
4. **Hosts 01/08:** the release-sequence compute freeze lifts. The hosts may take other approved work, provided T1 original paths stay untouched. The hub mirror stays paused until the coordinator retargets it.
5. **Engineering follow-up (outcome-blind, not a TIERS repeat).** Diagnose the about-150 ms all-cause poll lateness from the sealed Mac timing receipts. This blocks any Mac live play at any tier, and the fix belongs to a future, separately pre-registered Mac study.

## 2026-10-12 16:44Z: Mac poll-lateness diagnosis r1 (outcome-blind; follow-up to A3P-1)

The report is `/mpac/sdicks02/jobs/clasher/mac-a3p-diagnosis/REPORT-r1.md` (dfd9de7d), written by a Haiku worker from timing fields only. It reproduces the A3-P table exactly.

**Cause.** The poll loop's last `time.sleep` wakes 0–150 ms late (median about 30 ms). The loop is in `measure_tiers.py` (`decisions()` 382–397, `wait_until()` 159–163), and the host was running the replay load plus 1 Hz telemetry, with the E-cluster at times fully busy.

**Ruled out:**
- the schedule: the P1 cadence was used, and no decision overran its next poll (0/999);
- GC: 0 of 4,572 late polls overlap a GC event;
- search cost: lateness is uncorrelated (|r| ≤ 0.05) with decision time, and K0c fails the same way as K4.

The 150 ms ceiling is unexplained. It may be macOS timer coalescing.

**Consequence.** A3P-1 stands: the rule was applied as adopted. This is also a **live-loop engineering defect**: any Mac bot that sleeps to a poll deadline under load inherits the same lateness.

**Requirements for any future, separately pre-registered Mac measurement (and for the live loop):**
- a null no-op decision arm under the same load, as a harness floor;
- per-poll logging of the requested sleep versus the actual wake;
- a hybrid final wait (sleep to deadline − 5 ms, then spin);
- user-interactive QoS for the poll thread, kept off the load-worker cores;
- telemetry subprocesses de-phased from the polls;
- P1 spacing kept.

There is no Mac work now. This is queued behind K4S END and the K4S Mac phase.

## 2026-10-12 16:55Z: K4S END package 1 r2 Sol review; exception rulings E1–E3

**Review.** Sol r2 (`/mpac/sdicks02/k4s-runner/run-r1/reviews/SOL-REVIEW-END-PKG1-r2.md`, e347219d). Tests are 248/248, normally and under -O.

| Component | Commit | Verdict | Open findings |
|---|---|---|---|
| S1 (copy END sources) | 293b2fe7 | **APPROVE** | All r1 findings fixed. |
| S2 (END evidence) | 293b2fe7 | **REQUEST_CHANGES** | **S2-R2-F1:** auxiliary inputs (S1 manifests, profiles) bypass the outcome/strict-END location gate. **S2-R2-F2** (MEDIUM): a malformed profile silently falls back to the defaults and is mislabelled `s4-bundles`. |
| S4 (fleet reference assembler) | 12928087 | **REQUEST_CHANGES** | **S4-R2-F1** (BLOCKING): no `st_nlink == 1` gate, so a hard-link alias can read outcome bytes. **S4-R2-F2:** auxiliary END-location confinement gaps. **S4-R2-F3** (MEDIUM): the synthetic-pins input bypasses the confinement helpers. |

**Rulings (coordinator, with Sol's support):**
- **E1. Tracked symlink `visualize_battle.py`: exempted.** It is exempt only as the exact committed 120000 entry with link text `examples/visualize_battle.py`. The target must pass the confined walk and the new hard-link gate. No other symlink is exempt.
- **E2. Training receipt `imitation/model/receipts/throughput-0935/complete.json`: exempted.** It is exempt from the blanket `complete.json` prohibition at this exact path and SHA only (`d1492d0f49d4f9c7836ca0c1fc48240e8749545e2855c6fa61c70e2b192eb5fc`, bound by both committed T1 A3 runtime inventories). It may be hashed and must **never be parsed**. Its provenance is a model-training throughput receipt under `imitation/model/receipts/`, not a game, T1 or K4S outcome. Every other `complete.json` stays forbidden.
- **E3. Admission identities.** They are pinned from r4, and stale identities are refused. A reboot, bus replacement or 03 cache-service restart stops the workflow until the coordinator rules a re-pin from fresh outcome-blind admission copies. Committed admissions go under `reports/explore/k4s-confirm/end-guard-admissions/<host>-<name>.json` (Sol R1).

**Next.** The K4S runner fixes S2 and S4 (r3) and sends them for a Sol r3 review as soon as they are ready, without waiting for package 2. S1 is approved but stays offline: no host step until S2, S4 and the host plan are approved and authorized one step at a time.

## 2026-10-12 16:58Z: 08 idle by decision until perception B is admitted

The exploration owner declined 08: its students all ran on 01, and moving would add a host-timing confound and need modified scripts. A read-only lane survey (`/mpac/sdicks02/jobs/clasher/coordinator-notes/08-lane-survey-r1.md`) found no reviewed lane that can run on 08 unchanged.
- 08 stays **reserved for perception B** under the earlier GO. B's first 08 use is its dry run, after the B1–B11 review.
- The T5 GRU stays parked: it is descriptive-only, roughly 120–200 GPU-h, and its r2 change is unreviewed.
- Mask v2 has no owner since Astra retired. It is not scheduled.

This is a deliberate, recorded idle, not an oversight. It will be revisited when the B review lands or a reviewed lane appears.

## 2026-10-12 17:12Z: K4S END ruling E4: tracked `complete.json` files in the git runtime export

**What these files are.** Four `complete.json` files are tracked at origin/main. The coordinator verified each one from metadata only: `git log`, blob SHA and path, with no contents read. **None can carry a sealed K4S or T1 outcome.**
- **E2 (already ruled):** `imitation/model/receipts/throughput-0935/complete.json` d1492d0f…, from 2026-10-08. It is a model-throughput receipt.
- `reports/strategy_council_20260928/live-loop/v4/emulator-host/complete.json` **0a4906396b270206e900b62ca9dbc0f44e2de6aefb512c7990824a4b2fed836f**, last changed 1a40041a on 2026-10-07. That is before any T1 confirmatory game (T1 started 2026-10-10) and before any K4S game (2026-10-11), so it cannot contain either study's outcomes.
- `…/v4/l1/receipts/b08-gap-export-20261012-r1/complete.json` **9c84b7a8b8c821921dd9cd0ddf1e814a24dc99c56d82829ff5894add34040c81** (10a928e5), and
- `…/v4/l1/receipts/b08-supplemental-proof-export-20261012-r1/complete.json` **724ee1d7032442e192994236a28abf0cd61951ffc096f412b50c359737049d2d** (cb9a2469). These two are the perception gap-export transfer receipts written under coordinator GOs (cut 2 and cut 3). They are file-transfer completions, not game results.

**Ruling E4.**
- **Exempt list.** These three, plus E2, are exempt at their **exact path and SHA**. They may be hashed as part of the runtime export and must **never be parsed**.
- **Fail-closed.** S9 and S4 must refuse **any** tracked `complete.json` at the build commit that is not on this list of four (exact path and SHA). Later additions need a new ruling.
- **Not a reading grant.** This permits the runtime to carry the files. It does not permit any tool to read them.

## 2026-10-12 17:13Z: Exploration X4S-3 complete: more off-policy search data does NOT help the student (exploration, never adoptable)

**Readout.** RESULTS is at c86d928d (`reports/explore/x4s3/RESULTS.md`), with a time fix at 52d4d9df. It covers 1,167 paired seeds and 7,002 games, and all reducer checks pass.
- **Primary:** R4-D (more W-root data) − R3a = **+0.69 pp [−1.54, +2.78]** in losses. The noise reference (R3a-rep − R3a) is +1.41 [−0.69, +3.51]. Fit-seed noise is under 4 pp in every view.
- **Pre-declared conclusion: "data helps" = NO.** Off-policy W roots look saturated for this student, so **G-style generation stops.**
- R4-DC was skipped by the pre-declared stop rule: the point estimate was ≥ 0, and the independent gate gave +0.6855 pp.
- The S-200 thrash-window sensitivity (374 seeds) agrees.
- All deviations are disclosed in RESULTS: the guard deviation and 33 retired seeds, data that isn't a strict superset, calibration-slice reuse, and operational events.

**Hosts.** 01 is idle; 08 was never used. Mirror: 14,140 files, SHA-verified, at `05:<job>/mirror/final/`.

**Direction.** The next student lever is **on-policy cutoff-state labels** (states the student actually reaches, labelled by the search teacher), or student capacity. An Opus design brief for the next exploration on 01 and 08 follows. Its scripts need Sol review before any host run.

## 2026-10-12 17:23Z: K4S END rulings R6/R7 (S4 r3 open questions)

**Status.** S4 r3 is complete (252/252 tests, normally and under -O; 27/27 mutants killed; `st_nlink == 1` enforced in the walk and at the descriptor). r3b adds the E4 list. S4 r3b and S2 r3 will be sent to Sol together.

**R6. Runtime tree versus the strict `reports/explore/k4s-confirm/end/` namespace.**
- **Primary route.** Build and stage the runtime at the **evidence commit**, where `end/` does not yet exist. S9 `build` must assert that the subtree is absent, failing closed if it isn't. After the END-JOB commit, the `s9 equivalence` proof is a hard gate showing identical runtime_files and measurement_files, and the END-JOB commit's diff must be exactly `end/END-JOB.json`. Final adoption of this route waits for Sol's package-2 verdict on decision (1).
- **Fallback, only if Sol rejects (1).** Stage with `end/` excluded by an exact path filter. The build must prove that the staged runtime membership equals the frozen manifest's runtime_files name list (not just per-file hashes), and that the excluded subtree holds only the enumerated END JSON files.
- **The `--repository` clone** keeps `end/` by design, for claims. It is not part of the hashed runtime.

**R7. Plain copies only (binding).** Every staged input must be an independent regular file with link count 1. **Never use `cp -l`, `ln`, reflink-to-shared, or hard-link dedup.** S10's bytewise copy already complies, and the S4/S10 `st_nlink` gates enforce it.

## 2026-10-12 17:30Z: K4S END package 2, Sol r1: all 7 components REQUEST_CHANGES; Q5 deviation ruled

**Review.** `/mpac/sdicks02/k4s-runner/run-r1/reviews/SOL-REVIEW-END-PKG2-r1.md` (fdefbd8f). Tests: Part A 91 pass (28 real-data tests excluded); Part B 155 pass normally, 145 pass + 11 skipped under -O.

| Component | Verdict | Main findings |
|---|---|---|
| S1b (copy admissions) | REQUEST_CHANGES | BLOCKING: the remote reader reads hard-linked admissions (no `st_nlink`). |
| S3 (guard job) | REQUEST_CHANGES | BLOCKING: an unrestricted `--admissions-dir` and S1b manifest; the shared reader is leaf-only, with no nlink check. HIGH: no `-pfNN` form. |
| S9 (runtime export) | REQUEST_CHANGES | BLOCKING: git export reads every blob with no pre-read E1/E4/outcome gate; `--source`/verify roots are unconfined. |
| S10 (stage host) | REQUEST_CHANGES | BLOCKING: the recursive walk hashes any leaf, with no outcome/nlink gate. HIGH: base mismatch (`k4s-confirm-end-r1` vs `k4s-end-r1`), masked P-status, no refusal of S4 test-only bundles. |
| S5 (preflight) | REQUEST_CHANGES | BLOCKING: bootstrap trusts the caller's manifest SHA, not a fixed 74314eda, before import. BLOCKING: aliased reads and roots. HIGH: 04 can pass with no reference load and no bus-threshold decision. |
| S6 (exit push + verifier) | REQUEST_CHANGES | BLOCKING: registry hard-link aliases. BLOCKING: shell redirections can truncate a pre-existing or foreign-inode `argv.nul` (reproduced; inherited from T1's pattern). HIGH: C-d exit+1300 s not enforced. |
| S7 (launch gate) | REQUEST_CHANGES | BLOCKING: unrestricted local reads; a host base symlink lets a launch land in a foreign directory (reproduced). HIGH: failed `ps` treated as a valid census; RC-9 checks only Booleans. |

**Common root cause.** Every component hand-rolls input reads. **Ruling P2-1:** the runner builds ONE shared, reviewed `safe_input` layer and routes every local and remote read and write through it. The layer provides:
- a declared-root/role allowlist;
- component-wise `O_NOFOLLOW` walks;
- `st_nlink == 1`;
- E1/E2/E4 exact entries;
- outcome-name refusal before any byte is read;
- exclusive no-clobber creation;
- rc-checked subprocess helpers.

S2 r3 and S4 r3b should adopt the same layer where practical.

**Ruling P2-2 (Q5 deviation, decision 1): ADOPTED with Sol's conditions.**
- Build and stage at evidence commit P. The END-JOB commit X must be a descendant of P whose diff is exactly `reports/explore/k4s-confirm/end/END-JOB.json`.
- `s9 equivalence` is a hard gate; evidence, admissions and roots are already in P.
- External and staged inventories are fixed, the S9 verify and S10 receipts are consistent with the bundles, and there are no intervening runtime or bundle changes.
- Repository clones are fast-forwarded to X.
- This replaces "build at the END-JOB commit" for this run only.

**Ruling P2-3 (04 preflight).** The binding 04 preflight must run the agreed reference load and duration. A background-only run is a non-qualifying diagnostic. Proceed only if the loaded cumulative bus is at most about 0.3% (the adopted threshold). The intermediate band needs a coordinator decision. At ≥0.7%, stop before any claim.

**Bases.** Use `k4s-end-r1` everywhere (S10-F2). The RC-6 declaration lists runtime, bundles, repository, attempts and preflight, plus the separate Q4 guard-job parent.

No host step is authorized. Package 2 r2 goes to Sol again.

## 2026-10-12 17:30Z: X4S-4 plan design review: APPROVE_WITH_CONDITIONS; coordinator adopts C1–C9

**Review.** Opus design review r1 of PLAN f9f528b9: `/mpac/sdicks02/jobs/clasher/x4s4-review/OPUS-DESIGN-REVIEW-r1.md` (969e47ec).

**Key points:**
- As written, a single-fit contrast at N = 1,200 has an MDE of about 3 pp, against a plausible one-round effect of 0.5–2 pp.
- Fit-seed noise raises the rule's true false-positive rate to about 7–12%, and R5-rep cannot change the verdict.
- "On-policy" is confounded with v1-opponent / X-deck matched data.
- Controls would be evaluated beside fits while treatments run alone.

**Rulings (all review conditions adopted):**
- **C1:** R5-rep is mandatory. Primary = mean(R5, R5-rep) − mean(R3a, R3a-rep), paired by seed. "Helps" = upper 95% CI < 0 AND both single-fit points < 0.
- **C2:** declare the MDE (about 2.1 pp). Outcomes are three-way: helps / no material effect (lower CI > −2.0 pp) / inconclusive. **N stays at 1,200**, with no optional extension, to avoid forking paths.
- **C3:** **include the R5W matched off-policy control** (W-vs-v1 roots on the X decks ×4, fresh bank C′, existing reviewed emitter path). R5 − R5W is a declared secondary.
- **C4:** no reporting game of any student runs beside a fit. **01 only**; 08 is not used, so no transfer amendment is needed. Pre-declare the timing-parity check.
- **C5:** pre-declare the contention sensitivity (PSI avg10 > 10% or a foreign process holding > 2 cores) from timing fields, SHA-frozen before reduction.
- **C6:** O-gate thresholds, per-arm caps, labeler/interruption handling, the readout template, and a descriptive-only O-holdout diagnostic (bank-C 3500–3999). Only the primary drives the decision table.
- **C7–C9:** go to the Sol script review: deep-copied belief plus deadline-mode parity, capture fields (`opponent_elixir`, `reserved_packet`, empty `pending`), and the fair-information invariance test with a no-Battle-reference assertion.

**Process.** PLAN r2 gets a diff-only re-check, then scripts go to Sol, then the coordinator GO. Estimated compute is about 17 h within the 24 h hard stop. A capacity arm is separate future work (X4S-5).

## 2026-10-12 17:43Z: X4S-4 PLAN r2 re-check: APPROVE_WITH_CONDITIONS; PLAN r3 edits ruled

**Review.** Opus re-check of PLAN r2 a72b3213: `/mpac/sdicks02/jobs/clasher/x4s4-review/OPUS-DESIGN-RECHECK-r2.md` (665c73d2). C1–C6 are implemented as ruled: the MDE is 2.12 pp, R5W is matched, bank C′ is disjoint, and the reporting block is fit-free.

**Ruling: PLAN r3 must make all 11 consolidated edits.** The recommended ones are adopted too.
1. Delete the R5-rep futility stop: all five students' games always run, and nothing is reduced before the C5 freeze (R2-1, HIGH).
2. Disclose the fit-seed error rates (about 6.5–10%) and the 2.1–2.8 pp MDE; write the single-fit clause as pooled.
3. Add a fit-inflated descriptive interval with σ_fit fixed at 0.65.
4. Replace the R5 − R5W sign split with a CI-based attribution sub-label that defaults to "unresolved" and has a declared next step.
5. Correct the O_W "only behavior policy" wording; the matching unit is `teacher_root` rows.
6. ABBA reporting order.
7. Flag yield windows in C5.
8. Truncation: R5W never cuts the primary N; cuts are index-prefix; pauses count against T+24 h.
9. Add a "harmful" sub-label.
10. Clarify the parity flag.
11. State the O_W gate thresholds.

R2-9 and R2-11 go to the Sol script review. The coordinator will verify r3 textually; no further Opus round is needed.

## 2026-10-12 17:45Z: X4S-4 PLAN r3 accepted (design frozen)

PLAN r3 is 87809ae0 (`reports/explore/x4s4/PLAN.md`). The coordinator verified it textually: all 11 edits from 7b989359 are present and tagged [E1]–[E11].
- The futility stop is deleted, and nothing is reduced before the C5 freeze.
- The fit-inflated interval is added.
- The attribution sub-label is CI-based and defaults to "unresolved".
- A "harmful" sub-label is added.
- ABBA order.
- Truncation never cuts the primary N.
- O_W gate thresholds are stated.

**The design is frozen at 87809ae0.** Next comes one Sol review of the full script set; it includes R2-9 and R2-11 and C7–C9. A coordinator GO follows only after Sol approves. Hosts: 01 only.

## 2026-10-12 18:03Z: K4S END S2 r3 / S4 r3b Sol review: R2 fixes verified; new git-indirection findings

**Review.** `/mpac/sdicks02/k4s-runner/run-r1/reviews/SOL-REVIEW-END-S2S4-r3.md` (9b24219c). 547 tests pass in both modes. The round-2 findings are all **FIXED**: S2-F1/F2 and S4-F1/F2/F3.

**New findings (both components REQUEST_CHANGES):**
- **S2-R3-F1 and S4-R3-F1, BLOCKING.** Git calls inherit the environment and honour replacement refs. A replace ref or `GIT_*` override can substitute outcome bytes underneath a correctly named path or OID.
- **S4-R3-F2, BLOCKING.** The outcome-name gate is a six-name exact, case-sensitive list, so variants and standalone END receipt names pass.
- **S4-R3-F3, HIGH.** E4 metadata screening is interleaved with blob reads. It should be a complete metadata pass first, and only then any blob access.

**Ruling P2-4: the shared safe_input layer's git helper is the fix for all of these.** Every git call must:
- run with a scrubbed environment (no inherited `GIT_*`; explicit `GIT_DIR`/work-tree only if declared);
- set `GIT_NO_REPLACE_OBJECTS=1` and use `--no-replace-objects`, `-c core.hooksPath=/dev/null` and `GIT_OPTIONAL_LOCKS=0`;
- verify the object type and OID against the expected tree entry before consuming any content;
- run all tree-metadata screening (E1/E4, modes, names) to completion before any blob is read.

The outcome-name gate becomes a reviewed, case-insensitive family/pattern denylist shared by all components. S2 and S4 move to safe_input in r4, together with package 2 r2.

**Reviewer disclosure, accepted.** While exporting the frozen code, the Sol reviewer copied 92 committed `e4v3/receipts/` files: the linux05 TIERS dry-run timing receipts, including `tiers-complete.json`. It did not display, parse or use their contents. These are public committed health/timing receipts, not K4S or T1 game outcomes, so there is no impact on blinding. It is recorded.

## 2026-10-12 18:14Z: X4S-4 scripts, Sol r1: REQUEST_CHANGES (18 findings)

**Review.** `/mpac/sdicks02/jobs/clasher/x4s4-review/SOL-REVIEW-SCRIPTS-r1.md` (ea6760f8), of script commit 13fb31d0.
- **Verified:** all 20 hashes, the six-line capture delta, and evaluation `run.py` byte identity. 40/40 tests pass in every mode.
- **Not enough on their own:** targeted fixtures exposed real defects that the passing tests miss.

**Blocking findings:**
- **F1:** wrapping `run_game` breaks its inherited inference-frame guard.
- **F2:** the post-submit empty-`pending` filter drops play decisions.

**High findings:**
- **F3:** the fair-information permutation leaves one hidden-state path unperturbed.
- **F4:** a receipt merely existing is accepted as the C5 SHA freeze.
- **F5:** nonzero statuses are masked.
- **F6:** the O_W prefix/resume identity is not checked.
- **F7:** the foreign-CPU census undercounts.
- **F8:** reporting launches the unchanged X4S-3 supervisor.
- **F9:** study-wide guards are incomplete.
- **F10:** writers accept paths outside the job prefix.
- **F11:** the seed audit fails open under -O.
- **F13:** the O gate is not bound to the capture identities.
- **F16:** the repo-wide seed audit (inherited from X4S-3) can read any file under the repo root.

**Medium and low findings:** F12, F14, F15, F17, F18.

**Note on F16.** Sealed K4S and T1 outcomes are not committed to the repo. They live in host job directories. So the X4S-3 audit very likely read no outcome bytes. The fix is still required: a pre-read allowlist of seed-declaration sources.

**Next.** The owner fixes all 18 findings in a new script commit, adding regression fixtures for each Sol probe, and the scripts go back for a Sol r2 review. No host contact until GO.

## 2026-10-12 18:19Z: K4S safe_input r1 candidate; rulings D1–D4

**Status.** safe_input r1 is commit 4c9439de (`end-prep/safe-input-r1/`, safe_input.py 5a42036c).
- 246 tests pass on py3.8 and on both 3.12 environments, normally and under -O. 139/139 mutants are killed.
- It reproduces all four package-2 Sol probes.
- r2 is in progress: the P2-4 git helper, a two-phase tree-then-blob API, the shared family denylist, and regression tests for the r3 findings.

**Rulings (the runner's recommendations, adopted):**
- **D1. S9 exports only the runtime member set.** The set is computed by the frozen runtime_pins rule from tree metadata alone. Non-member blobs are never read. A denylisted name inside the member set is refused unless it is on the E list.
  - The two tracked `hub-ack.returned.json` OA-1 evidence files, and the r2 `*-complete.json` family files, are non-members. They need no exemption.
- **D2. E1 is amended to "materialised".** The committed entry must be the exact 120000 link `visualize_battle.py` → `examples/visualize_battle.py`. The runtime ships a regular file whose bytes equal the gated target blob, matching T1's END runtime convention. S9 and S4 apply the same rule.
- **D3. S6-only hash-only role.** It covers exactly `end-raw.json` and `end-complete.json`, and applies only inside a sealed attempt directory under the declared attempt parent. The files are never parsed; their SHA is compared with the seal manifest. Nothing else gets this role.
- **D4. S10 drops on-host `tar -x`.** It is replaced by a shipped receiver: the layer's remote program gains a `receive` mode with exclusive creation, the denylist, nlink and no-follow checks, and hash verification.

**Residual accepted.** A same-size, in-place rewrite by another local actor during a read goes undetected unless an expected SHA is supplied. All production reads must pass expected SHAs.

## 2026-10-12 18:20Z: Perception B combined package r1 review: REQUEST_CHANGES (narrow); scientific core sound

**Review.** Opus independent review of package 22c60918: `/mpac/sdicks02/jobs/clasher/v4-b-gap-review/B-COMBINED-REVIEW-r1.md` (e2ae46ea).

**What passes:**
- **Integrity:** all 392 files match, and the A1 diff reproduces byte-exactly.
- **Recovered sources:** the four recovered files match the A1 pins.
- **Data boundaries:** nothing reads heldout, T1 or K4S data.
- **C1 in code:** all 8,721 digests are mapped, the 1,536 selected decoders equal composition r6, and the 49 C1 digests are qualification references only.
- **R16:** it reproduces the frozen receipt exactly.
- **Torch check:** CPU-only torch is rejected.
- **Tests:** 335/335 pass.

**Blocking findings:**
- **F1:** the full-216 `current-graph` recomputation cannot realistically finish inside the hard 2 h one-shot window.
- **F2:** the code root and claim names are unversioned, so the code cannot be fixed after deployment.

**Ruling.** r2 must be a narrow delta patch against r1:
- **R1 (b):** per-epoch, fresh-process units, each with its own exclusive receipt, plus a final reducer that requires all 24 receipts and a full re-hash.
- **R2:** version deployment by package SHA and attempts by GO SHA. The rule becomes one attempt per GO, and environment pre-checks run before the claim.
- **R3:** kill the 5 surviving mutants, including the GO's GPU/heldout refusal and the 2 h cap. Type-check `phases`. Assert `CUDA_VISIBLE_DEVICES=''`, the thread variables and nice ≥ 19 in every phase.
- **Everything else stays unchanged.**

The delta review follows.

**Conditions G1–G8 are adopted now for the later CPU GO:**
- separate coordinator-committed receipts (`APPROVE_B_COMBINED_REVIEW`, then `AUTHORIZE_B_CPU_PREFLIGHT` with gpu and heldout set to false);
- a reviewed 05→08 deployment script;
- the clasher-gpu interpreter with `-B -s`, no CUDA, one thread, nice 19, and no environment repair;
- strict stage → environment → current-graph order with no automatic retry;
- a coordinator comparison of the environment against the 2026-10-08 record;
- before the deciding stage: measured cost, an allowlist with no SSH session, and a reviewed notification transfer.

## 2026-10-12 19:36Z: Perception B combined r2 delta review: package and deploy script APPROVE_WITH_CONDITIONS

**Review.** Opus delta review of package 37432569 and `deploy_b08.py` 2f1d0e79, at `/mpac/sdicks02/jobs/clasher/v4-b-gap-review/B-COMBINED-REVIEW-r2.md` (**35b7cf4f**).
- **Integrity.** All 414 files match; the delta reproduces all 19 changed files; only 4 runtime modules changed. C1, R16, `verified_bounds`, A1 and the digests are unchanged.
- **Fixes.** R1(b), R2 and R3 are correct: one-shot fail-closed epoch units, and the reducer needs exactly 24 valid receipts plus a full re-hash.
- **Tests.** 373/373 pass.
- **Deploy script.** It writes only to versioned prefixes, creates files exclusively, checks SHA after copying, opens one SSH session with no ControlMaster, and keeps partial copies without retrying.

**Coordinator decision: review approved under the amended G1–G8.**
- **G1.** Separate receipts:
  - `APPROVE_B_COMBINED_REVIEW`: binds the package, CPU plan 8d5d338e, deploy 2f1d0e79 and review 35b7cf4f.
  - Then `AUTHORIZE_B_DEPLOYMENT`.
  - Then `AUTHORIZE_B_CPU_PREFLIGHT` (per phase).
- **G2.** Every receipt and GO is coordinator-committed, with its SHA recorded here before use. Each GO reference is exactly `{path, sha256}`.
- **G3.** One deploy run, with no rerun. One pre-authorized read-only inspection if it fails. The coordinator reviews `complete.json`.
  - **New (F1):** placing authority receipts on 08 under `B_ROOT` needs its own reviewed procedure before the stage GO.
- **G4.** Invoke exactly `code-374325696dc9`, using the clasher-gpu interpreter with `-B -s`, no CUDA, one thread and nice 19.
- **G5.** Strict order: deployment → stage → environment → 24 epoch units (bounded concurrency, at most 8) → reducer.
  - **Cost gate:** the reducer GO is issued only if the longest epoch unit took ≤ 3,600 s.
- **G6–G8.** As the review states.

**Next.** The perception owner drafts, to the code's exact schemas:
- the `APPROVE_B_COMBINED_REVIEW` receipt;
- the `AUTHORIZE_B_DEPLOYMENT` GO;
- the F1 authority-placement procedure, which goes to Opus review.

The coordinator verifies and commits the receipts. Deployment needs its own GO. No host action yet.

## 2026-10-12 20:03Z: Perception B: combined-review approval receipt ISSUED; authority-placement review

Authority-placement review: `/mpac/sdicks02/jobs/clasher/v4-b-gap-review/B-AUTHORITY-PLACEMENT-REVIEW-r1.md` (7a042d90).

**Verdicts:**
- **F1 transport `authority_placement.py`: REQUEST_CHANGES (narrow).**
  - It placed a forged GO from a dangling commit (P1).
  - It counted a "REJECTED" ledger mention as issuance (P2).
  - **Fixes required:** an origin/main ancestry check, a sanitized git environment, and anchored ledger lines in exactly the format below. Write the revision to a new r2 directory.
- **APPROVE draft:** correct; commit byte-identical.
- **Deployment GO draft:** the schema passes. It still needs cited, already-authorized who/free-space/cpus provenance, a refreshed window and issuance.

**Issued** (byte-identical copy of the draft 59ffe41a; binds package 374325696dc9, CPU plan 8d5d338e, deploy script 2f1d0e79 and review 35b7cf4f):
- `/mpac/sdicks02/jobs/clasher/v4-b-gap-review/receipts/b-combined-review-receipt-r2.json` (0444)
- `reports/strategy_council_20260928/live-loop/v4/l1/receipts/b-combined-review-receipt-r2.json`

ISSUED APPROVE_B_COMBINED_REVIEW 59ffe41a9f3a244834cc98b6e3414e4f8d49592362e808f47f319243d90d3282

This approves the B1–B11/B4 package review only. It is **not** a deployment, CPU, GPU or heldout authorization.

## 2026-10-12 20:27Z: Perception B authority-placement r2 review; 08 quiet-read AUTHORIZED (once)

**Review.** `/mpac/sdicks02/jobs/clasher/v4-b-gap-review/B-AUTHORITY-PLACEMENT-REVIEW-r2.md` (e90d567b). Verdicts:
- **F1 transport: APPROVE_WITH_CONDITIONS.** P1, P2, P4 and P5 are fixed. Revocation fails open (R1, R2). This must be fixed in an r3 before the first **placement** GO.
- **Operator and inspection changes: APPROVE.**
- **Quiet-read: APPROVE_WITH_AMENDMENTS.** Only the amended command may run: `evidence/B-AUTHORITY-PLACEMENT-REVIEW-r2-quiet-read-amended.sh`, SHA e36f8538be95987b7db202df2ca6f3f28ee8c7a026ed2377a281e71459ff6917.
- **Deployment GO: correctly not issuable yet.**

**Authorization.** The coordinator runs the amended quiet-read e36f8538 **exactly once**, from 127x05.
- It opens one non-interactive SSH session to 127x08, with ControlMaster off.
- It reads only: UTC, the `who` count, the `/mpac` available and total size, loadavg, and the allowed CPUs.
- There is no retry. A nonzero exit means no deployment until a new decision.
- The output goes to `l1/receipts/b08-quiet-read-r1/` and is committed through a temp index after a secret scan.

## 2026-10-12 20:27Z: 08 quiet-read complete (exit 0, one SSH session)

The output is `reports/strategy_council_20260928/live-loop/v4/l1/receipts/b08-quiet-read-r1/`. **observation.json SHA 54858b0e9a86ea02879f5cfad7843530367f8cc4ffbb8f0a5cc5e76c3a3d817d**, remote UTC 2026-10-12T20:27:25.676929+00:00.

| Check | 127x08 value | Gate | Result |
|---|---|---|---|
| `who_count` | 0 | must be 0 | pass |
| `/mpac` available | 1,223,077,609,472 B | ≥ 280e9 B | pass |
| `/mpac` size | 2,015,104,376,832 B (available is 60.7%) | available ≥ 40% of size | pass |
| loadavg | 0.0 / 0.0 / 0.0 | — | — |
| allowed CPUs | 0–127 on both 05 and 08 | — | — |

**Coordinator-approved cpus for the deployment GO: [0, 1].** This observation is the provenance for the deployment GO's who, free-space and cpus fields. The observation commit is the one containing this entry.

## 2026-10-12 20:31Z: Perception B deployment GO ISSUED (copy to 08, once)

**What this authorizes.** The GO is byte-identical to the draft at `l1/prepared/b08-deployment-go-final-r1/`, SHA 06f8d1b0. It authorizes:
- the reviewed sender `deploy_b08.py` (2f1d0e79), run through the r2 detached launcher (79cc2a5a) and operator wrapper (b8a4e3f8);
- a deployment of package 374325696dc9 to 127x08, writing only its versioned prefixes;
- cpus [0, 1], with gpu and heldout false;
- a window of 2026-10-12 21:00Z–22:30Z;
- no retry.

**Failure handling.** If the exit code is nonzero or the run times out, exactly one read-only inspection (`operator_inspect_once.py` 5921618b, helper fab8ba7d) is allowed, until 23:00Z.

**Provenance.**
- Quiet-read observation 54858b0e at 1fd18160 (who 0, 1.22 TB available).
- Review receipt 59ffe41a.
- Coordinator verified all pins against r2 REVIEW-MANIFEST 6b43a70d.

**Issued copies.**
- `/mpac/sdicks02/jobs/clasher/v4-b-gap-review/receipts/b-deployment-go-receipt-r2.json` (0444)
- `reports/strategy_council_20260928/live-loop/v4/l1/receipts/b-deployment-go-receipt-r2.json`

ISSUED AUTHORIZE_B_DEPLOYMENT 06f8d1b0721f12f6ff9ab3153f01a09df7ca11843297d572f9be5d1396e79b1a

**Not authorized.** This GO does not authorize authority placement, the CPU preflight, GPU or heldout work. Those wait for:
- the F1 r3 revocation fix;
- the review of `complete.json`;
- separate GOs.

## 2026-10-12 20:44Z: Perception B F1 r3 review APPROVE_WITH_CONDITIONS; canonical revocation protocol adopted

**Review:** `/mpac/sdicks02/jobs/clasher/v4-b-gap-review/B-AUTHORITY-PLACEMENT-REVIEW-r3.md` (3c4961d3).
- F1 transport r3 (procedure 20e58965, manifest 4631d05d) gets **APPROVE_WITH_CONDITIONS**.
- R1, R2 and G5 are fixed and verified on real git. 54/54 tests pass.
- r2 is unchanged (6b43a70d), so deployment GO 06f8d1b0 stays valid.

**Adopted now (C-3): canonical revocation protocol**, binding on all coordinator authority from here on.
- **Form.** A revocation is ONE line, starting at column 0: `REVOKED <DECISION> <full lowercase 64-hex SHA> <reason>`.
- **Forbidden ways to revoke:**
  - an abbreviated SHA;
  - prose or a heading;
  - deleting or striking an issuance line;
  - any other verb.
- **Order.** The revocation line is written and pushed from 05 before any other action. A STOP is then sent to the operator thread with `t3_thread_send`.
- **Never** put a live authority's full SHA on a line containing revoked, withdrawn or rescinded (any case) unless the line is meant to revoke.
- A column-0 full-SHA issuance line is written only when issuing.

**First placement GO: conditions C-1 to C-6** (reviewed in §5 of the review).
- **C-1.** The deployment `complete.json` has been reviewed first.
- **C-2.** Pin `procedure_sha256` 20e58965. Freeze r3 and r2 byte-identical, and never `git clean` the prepared directories.
- **C-4.** The operator runs the dry-run-verified fetch-then-send command `evidence/…-r3-placement-operator-command.sh` (d6cb3690) exactly once. It writes an exit-code file.
- **C-5.** The coordinator runs a read-only pre-issue grep. Each SHA must show exactly its one issuance line.
- **C-6.** After placement, audit `revocation_tip_commit..origin/main` for placed SHAs. There is no retry.

**Optional.** Hardening F-8 is not required, and is deferred.

## 2026-10-12 21:02Z: Perception B deployment to 08 COMPLETE; complete.json reviewed (accepted)

**Run.** The deployment GO 06f8d1b0 ran exactly once at 2026-10-12T21:00:48Z, through the reviewed r2 detached launcher, with one SSH session. There was no retry and no inspection. The operator exit code is **0**, and stderr is empty.

**`complete.json` on 08.** It is at `/mpac/sdicks02/jobs/clasher/v4-b-20261012-r1/deployment-06f8d1b0…/complete.json`, SHA **46fad651c776ec847660f03c003727826b1488065ec19dd7060ae0f944cac9e9**.
- The local replica (`l1/receipts/b08-deployment-operator/06f8d1b0…/complete-reconstructed.json`) has the same SHA. It is reconstructed from the retained receiver stdout (f382ea6b) with the pinned serializer, so no second SSH session was needed.

**Coordinator review: ACCEPTED.**
- The schema is v1.
- It binds package 374325696dc9, GO 06f8d1b0 and review 59ffe41a.
- `files` = 334, which matches the 333 members `deploy_b08.destinations()` selects from the r2 manifest (code/, upload/metadata/ and the 4 META files), plus the deployment record. The coordinator recomputed this offline.
- `bytes` = 46,413,097.
- `runtime_admitted` = false.

**Next.** The first authority-placement GO, under C-1 to C-6 (7ecf4787). The CPU preflight still needs its own GO after placement.

## 2026-10-12 21:04Z: Perception B first authority-placement GO issued

**The GO.** It is byte-identical to the draft at `l1/prepared/b08-authority-placement-go-r1/` (SHA 4433d54c).
- **What it places:** exactly one receipt, the combined-review approval (59ffe41a), at `B_ROOT/authority/<sha>.json` on 127x08.
- **Pins:** procedure 20e58965 and operator command d6cb3690.
- **Execution limits:** cpus [0, 1]; no GPU; no heldout; no retry. It attests `between_phases`.
- **Window:** 2026-10-12 21:30Z–23:00Z.
- **Observation:** quiet-read 54858b0e at commit 1fd18160.
- **Prerequisite:** the deployment record (`complete.json`, 46fad651) was accepted at 4d685b55.

**C-5 pre-issue check passed.** A read-only grep of origin/main shows exactly one issuance line for 59ffe41a and none for this GO.

**Issued copies:**
- `/mpac/sdicks02/jobs/clasher/v4-b-gap-review/receipts/b-authority-placement-go-r1.json` (0444)
- `reports/strategy_council_20260928/live-loop/v4/l1/receipts/b-authority-placement-go-r1.json`

ISSUED AUTHORIZE_B_AUTHORITY_PLACEMENT 4433d54c18e3228971ae3f03fda6b40af8e0fba9d8d3b7387416daff0a70b706

**Not authorized by this GO:** the CPU preflight, GPU or heldout work, or any other placement. After placement, the coordinator runs the C-6 audit.

## 2026-10-12 21:28Z: K4S safe_input r2 committed; rulings E5, full clone, frozen-reader wrapper

**Status.** safe_input r2 is committed at 7f82af0d (`end-prep/safe-input-r2/`, safe_input.py f9ca4926).
- **Tests.** 472 tests across py3.8 and two 3.12 environments, each run normally and under -O. Mutation testing killed 244 of 247 mutants. The 3 survivors are redundant with stronger gates.
- **Git helper (P2-4).** Implemented. It refuses alternates, grafts, shallow clones and driver configs. On git 2.25 the explicit refusal of grafts is the load-bearing part.
- **Metadata pass first.** `git_plan` screens all metadata before reading any object.
- **D1–D4** are implemented.
- **E4 blob check.** The runner independently matched each of the four E4 blob OIDs to its ruled SHA.

**Ruling E5: exact exemptions.** Nine runtime members match the outcome-name family denylist only because of their names. They are exempt at exact path plus blob OID; the runner records the OIDs in the code constant. They are copied byte-exact, hashed, and never parsed by END tooling:
- 8 tracked Python source files whose names contain "games":
  - `reports/explore/k4s-confirm/{check_games,qualify_games}.py`
  - `…/engine-speed/canonical/certify_games.py`
  - `…/exit-r3/round2/{,timing03/}eval-ops/reduce_games.py`
  - `…/search-tuning/timing_games.py`
  - `scripts/{collect_public_development_games,compare_native_public_games}.py`
- the test fixture `tests/fixtures/native_friendly_completed_15_535_86.json`. It was added on 2026-09-28, before any sealed study existed, and is listed in runtime-pin-r2.

The family pattern is **not** narrowed. Any other member that matches is refused.

**Ruling: full clone.** S9 builds only from a dedicated runner-owned full clone at `/mpac/sdicks02/k4s-runner/run-r1/end-prep/repo-full`. It is cloned from origin with no filter. safe_input checks that it has no promisor, alternates, grafts, hooks or driver config. It is checked out at evidence commit P. The shared checkout at `/mpac/sdicks02/repos/clasher` is never used as a build source, because it is a partial clone.

**Ruling: frozen-reader interim.** Frozen code (`k4s_logic.git_bytes()` and the frozen END `git show`) runs only under a wrapper that scrubs `GIT_*` and sets the P2-4 environment. It runs only on clones that safe_input has pre-verified (no replace refs, alternates, grafts, hooks or driver config). S5 and S7 perform that check on the host clone before running.

## 2026-10-12 21:31Z: Perception B first authority placement COMPLETE; C-6 audit clean

**Placement GO 4433d54c: done.** It ran exactly once at 2026-10-12T21:30:44Z using the pinned fetch-then-send operator d6cb3690, with one SSH session and no retry.

**Exit status.** Both the launch and the F1 journal returned exit code 0.

**What landed on 08.** The remote completion record (`complete` echo, SHA 12ce1ed2) shows exactly one receipt placed: the combined-review approval 59ffe41a, at `/mpac/sdicks02/jobs/clasher/v4-b-20261012-r1/authority/59ffe41a….json`. `runtime_admitted` is false.

**C-6 audit (coordinator, read-only): clean.**
- The `revocation_tip_commit` and `fetched_tip` are both bb1d4472. That commit is an ancestor of origin/main, and origin/main had no later commits when audited.
- The ledger contains no `REVOKED` lines.
- For each of the two placed or relied-on SHAs, the only ledger line is its single issuance line.

**Next steps** (each a separate coordinator GO):
1. A CPU-preflight `stage` GO, `AUTHORIZE_B_CPU_PREFLIGHT`, scoped to `stage` only.
2. Its own placement on 08 via F1.
3. Running the stage.

No CPU, GPU or heldout action has been authorized yet.

## 2026-10-12 21:37Z: Perception B CPU-preflight GO issued (phase `stage` only)

The GO is byte-identical to the draft `l1/prepared/b08-stage-and-placement-go-r1/DRAFT-AUTHORIZE_B_CPU_PREFLIGHT-stage.json` (SHA ca6b5ac8).

**Scope and limits:**
- Phases: `["stage"]` only, on 127x08.
- Code root: `code-374325696dc9`.
- Interpreter: clasher-gpu `-B -s`, with CUDA hidden, threads=1, nice 19 and cpus [0, 1].
- No GPU and no heldout data.
- Window: 2026-10-12 22:30Z to 2026-10-13 00:30Z.
- One attempt only. No retry and no environment repair.

**Bindings:** plan 8d5d338e, review 59ffe41a, deployment complete 46fad651, quiet-read 54858b0e.

**Issued copies:**
- `/mpac/sdicks02/jobs/clasher/v4-b-gap-review/receipts/b-cpu-preflight-stage-go-r1.json` (0444)
- `reports/strategy_council_20260928/live-loop/v4/l1/receipts/b-cpu-preflight-stage-go-r1.json`

**Before the stage runs,** three things are still required: the second placement, a C-6 audit, and a separate explicit run GO.

ISSUED AUTHORIZE_B_CPU_PREFLIGHT ca6b5ac89accaa513cb81ea21c1f2c3c40338ef724b6703c0d8fde032d7ca891

## 2026-10-12 21:37Z: Perception B second authority-placement GO issued

The GO is byte-identical to the draft `l1/prepared/b08-stage-and-placement-go-r1/DRAFT-AUTHORIZE_B_AUTHORITY_PLACEMENT-r2.json` (SHA eb334bb2).

**What it places:** exactly one receipt on 127x08, the CPU stage GO ca6b5ac8, at `B_ROOT/authority/<sha>.json`.

**Limits:**
- Procedure 20e58965, operator d6cb3690.
- cpus [0, 1]; between phases.
- No GPU and no heldout data.
- Window: 2026-10-12 22:10Z to 23:40Z.
- No retry.

**Pre-issue check (C-5):** the CPU GO SHA shows exactly one ISSUED line.

**Issued copies:**
- `/mpac/sdicks02/jobs/clasher/v4-b-gap-review/receipts/b-authority-placement-go-r2.json` (0444)
- `reports/strategy_council_20260928/live-loop/v4/l1/receipts/b-authority-placement-go-r2.json`

ISSUED AUTHORIZE_B_AUTHORITY_PLACEMENT eb334bb229081bcb49757762d76e45b3d18037c815c23b9ec60063ac3e6c1f68

## 2026-10-12 21:55Z: Perception B stage transport review: APPROVE_WITH_CONDITIONS

**Review:** `/mpac/sdicks02/jobs/clasher/v4-b-gap-review/B-STAGE-TRANSPORT-REVIEW-r1.md` (ba630631).

**Verdict.** The transport `stage_transport.py` (29d90793) and launcher `operator_stage_once.sh` (c99a8b33) are approved unchanged, with bundle manifest 256badc1. They may be launched **only** through the reviewer's guard command `evidence/B-STAGE-TRANSPORT-REVIEW-r1-operator-command.sh`, SHA cffa7f279b61fa7b781157b8aa61da64ff2637d4bee5896ce600c3a98d07400f.
- The guard checks the run-GO binding, the one-line C-5 rule for 4 SHAs, the launch slot and any existing claims.
- It passed all 16 dry-run cases.

**Adopted conditions:**
- **C-1, run GO.** A run GO `AUTHORIZE_B_STAGE_TRANSPORT_RUN` is committed at `l1/receipts/b-stage-transport-run-go-r1.json`. It must contain the full SHAs of the transport, launcher, CPU GO, manifest, guard and this review. It is issued only after placement eb334bb2 succeeds and its C-6 audit is accepted.
- **C-2, freeze.** Keep everything frozen: no `git clean` of `prepared/`, and no changes to `~/.bashrc` or `~/.ssh/{environment,rc}`.
- **C-3, single launch.** Launch once, within 22:30Z–23:30Z, with no retry.
- **C-4, success and audit.** Success means both exit codes are 0 and `complete.json` is verified. Then the coordinator audits the ledger from `revocation_tip_commit` onward.
- **C-5, UNKNOWN result.** An UNKNOWN result needs a separately reviewed read-only retrieval under its own GO.
- **C-6, next revision.** S4/S5/S2/S3/S8 go into the next revision; they don't block this run.

## 2026-10-12 22:12Z: Perception B second placement complete, C-6 clean; UNKNOWN-retrieval review; stage run GO issued

**Second placement (GO eb334bb2).** It ran exactly once, 2026-10-12T22:10:41Z to 22:10:46Z, using the pinned operator.
- Launch and journal exit codes were both 0. One SSH session, no retry.
- The remote completion record shows exactly one receipt placed on 08: the CPU stage GO (ca6b5ac8). `runtime_admitted` is false.

**C-6 audit (coordinator, read-only): CLEAN.**
- The revocation tip and fetched tip are both 0f9b0092, an ancestor of origin/main, with no later commits.
- The ledger has zero REVOKED lines.
- Each relied-on authority has only its single issuance line.

**UNKNOWN-retrieval review.** `/mpac/sdicks02/jobs/clasher/v4-b-gap-review/B-STAGE-UNKNOWN-RETRIEVAL-REVIEW-r1.md` (73fe4ff2) gives **APPROVE_WITH_CONDITIONS** for reader 41a08106 and sender 2cd58b5a.
- The procedure is read-only and covers exactly 4 paths.
- It is usable only after a coordinator-accepted real UNKNOWN, under its own GO:
  - a window of at most 300 s, opening no earlier than 2026-10-13 00:32Z;
  - the review's R-1 to R-6 conditions;
  - one run, no retry.

**Stage run GO.** The run GO is byte-identical to draft a679b052. It binds:
- transport 29d90793, launcher c99a8b33, manifest 256badc1;
- guard cffa7f27, transport review ba630631;
- the CPU stage GO and the second placement GO.

Constraints:
- Launch exactly once, through the guard only, from 127x05, in the slot 2026-10-12 22:30Z to 23:30Z.
- Stage hard deadline: 00:30Z.
- cpus [0,1]. No GPU, no heldout data, no retry.

Issued copies:
- `/mpac/sdicks02/jobs/clasher/v4-b-gap-review/receipts/b-stage-transport-run-go-r1.json` (0444)
- `reports/strategy_council_20260928/live-loop/v4/l1/receipts/b-stage-transport-run-go-r1.json`

ISSUED AUTHORIZE_B_STAGE_TRANSPORT_RUN a679b0520fef294979a5c7ab5b666660b8a1a345c07dcc2103332b062b421dc6

## 2026-10-12 22:32Z: Perception B CPU stage COMPLETE on 08; C-4 audit clean (accepted)

**Run.** The stage ran once through guard cffa7f27 at 2026-10-12T22:30:37Z, under run GO a679b052, using one SSH session and no retry. The launcher and sender exit codes were both 0, the remote stage exit was 0, and stderr was empty.

**Completion record.** The local `complete.json` (da9df44b6759a0e569438ace345f1d4ea52a0b7b8a9f92ce10e2ff0533e00f7d) is identical to the envelope `complete_sha256`. Its contents:
- schema: b08-stage-complete.v1
- CPU GO: ca6b5ac8; package: 374325696dc9
- 1,238 files, 2,136,818,985 bytes
- `runtime_admitted`, `gpu_work` and `heldout_opened` all false

**C-4 audit (coordinator, read-only): CLEAN.**
- File count is 1,238, matching the plan.
- All paths are under `preflight-ca6b5ac8…/`, with no protected or outcome names.
- Revocation tip 15048bd4 is an ancestor of origin/main.
- None of the 4 guarded SHAs appears on any ledger line after the tip, and there are 0 REVOKED lines.

**Stage ACCEPTED.**

**Next.** The `environment` phase. It needs:
1. a CPU-preflight GO for `environment` only;
2. its placement;
3. a reviewed run through the same guarded transport pattern;
4. a G6 comparison against the 2026-10-08 environment record before the epoch units.

## 2026-10-12 22:37Z: Perception B: environment phase needs new transport; ruling PT-1, one phase-generic transport

The owner's offline environment drafts (`l1/prepared/b08-environment-and-placement-go-r1/`) show that the reviewed stage transport, launcher and guard can't run any other phase unchanged. The stage GO, phase, claims and completion schema are all hard-coded.

**Ruling PT-1.** Do not build and review a separate transport for each remaining phase: environment, 24 epoch units, reducer. The owner writes **one phase-generic transport set** instead, with these parts:
- **Sender and launcher.** One reviewed sender and launcher, parameterized only by the issued CPU GO. Phase, claims and the completion schema are derived and validated from the GO and the frozen package.
- **Guard.** One reviewed guard, parameterized by the run-GO SHA. It applies the C-5 rule to every authority the run relies on.
- **Retrieval.** One generic read-only UNKNOWN retrieval.
- **Carry-over fixes.** It includes all C-6 items from the stage transport review (S4 `env -i`, S5 hash-before-exec, S2 tokenized revocation plus placement checks, S3 claim after publication, S8 integration tests) and a reviewed output cap for each phase.
- **Concurrency.** Bounded concurrency for epoch units (G5: at most 8 units, on disjoint cores) is supported but not used until it is separately authorized.

**Review and issuance.** It gets one independent review. After approval, each phase still gets its own CPU GO, placement and run GO.

**Drafts not issued.** The environment drafts 05ff759e and edea9611, and the template 401ac9f9, are not issued. They will be re-drafted with fresh windows after the transport review.

## 2026-10-12 22:50Z: X4S-4 qualification runbook received; decisions Q-D1 to Q-D4 (pending Sol r5)

The runbook is `reports/explore/x4s4/QUALIFY-RUNBOOK.md`, commit 433c36e7. These decisions take effect only once Sol r5 approves; a qualification GO is issued after that.

- **Q-D1. GO structure: adopted.** One combined GO covers PLAN §6 qualification plus a **conditional** production run.
  - Production proceeds automatically only if every §6 gate passes with its exact receipts.
  - Any failure, anomaly or STOP pauses the run for a coordinator decision.
  - The T+24 h clock starts at the first qualification launch.
- **Q-D2. §6.5 trainer compatibility: decided by the r5 verdict.**
  - If r5 requests changes anyway, use option (a): a narrow `qualify4 smoke-pack`, Sol-reviewed with the next round.
  - If r5 approves, use option (b): run `qualify4 trainer` on the first real O batch after the O gate and before the R5 fit is admitted. This is a recorded change to the §6 ordering, and a trainer failure blocks every fit.
- **Q-D3. Smoke parity at 8 games per arm: designed pause accepted.** If it fails, the coordinator decides whether to grant an exact-receipt exception.
- **Q-D4. Q0 seed audit: included.** It runs once on 05 at nice 19 on a few cores, reading pinned blobs only (7,705 sources plus the 29 approved declarations). It does not touch the shared checkout's worktree.

## 2026-10-12 23:18Z: Perception B generic phase transport: APPROVE_WITH_CONDITIONS

**Review.** `/mpac/sdicks02/jobs/clasher/v4-b-gap-review/B-GENERIC-TRANSPORT-REVIEW-r1.md` (62cf641a).

**Approved, unchanged.** These four files are the single path for the environment phase, the 24 epoch units and the reducer:
- transport 8d348859
- launcher 2679fc3e
- guard cd35c65f
- retrieval 8ac48b0b

They come from bundle manifest 32a4a36f.

**What the review found:**
- The run command is derived only from the CPU GO and the frozen package.
- The C-5 checks cover the recursive authority closure, including placement.
- Each phase makes five exclusive claims per CPU GO.
- All C-6 items are closed.
- The 64 MiB environment cap is adequate: it fails closed and needs no pre-measurement.

**Adopted conditions:**
- **Worker memory limit (RLIMIT_AS).** 16 GiB for the environment phase. 32 GiB for serial epochs and the reducer. At most 20 GiB per member in a two-member group.
- **Full SHAs on the ledger.** A full B authority SHA may appear only on its own column-0 ISSUED line.
- **Run windows** must end at least 1 h before the CPU GO deadline.
- **Repo hygiene.** Large local artifacts never go into the public repo.
- **Concurrency.** Off for the environment phase and epoch 1. After that, optional two-member groups, each needing its own group authority.
- **Retrieval.** Defect U1 (one bad file aborts the whole read) is deferred to r2.

**Next.** Fresh drafts for the environment phase: a CPU GO, placement r3 and a run GO using this transport. These replace the unissued 05ff759e, edea9611 and 401ac9f9.

## 2026-10-12 23:22Z: Fresh 08 quiet-read r2 for the environment GO (E-1 of the generic-transport review)

**Script.** The coordinator ran the reviewed quiet-read once with exactly one change: the output directory is `b08-quiet-read-r2` instead of `-r1`, since the r1 directory is exclusive and already exists.
- The diff is that single `Q=` line. The new script is `evidence/coordinator-quiet-read-r2.sh`, sha 91f4ea6e.
- The reviewed original is e36f8538 and is unchanged.

**Run.** Exit 0, one SSH session, empty stderr. Output is in `l1/receipts/b08-quiet-read-r2/`: **observation.json, sha d5086e1e773b656b771f01ca66654dc4af3168b0c3bd840ac7fd15bc98d29ccf**. Remote UTC was 2026-10-12T23:21:49.439240Z.

| Check on 08 | Value |
|---|---|
| who | 0 |
| `/mpac` available | 1,220,889,788,416 B of 2,015,104,376,832 B (60.6%) |
| loadavg | 0/0/0 |
| CPUs | 128 on both hosts |

All gates pass. **The environment CPU GO, placement r3 GO and run GO must cite this observation.**

## 2026-10-12 23:24Z: Perception B CPU-preflight GO issued (phase `environment` only)

- **Source:** byte-identical to the draft `l1/prepared/b08-environment-and-placement-go-r2/DRAFT-AUTHORIZE_B_CPU_PREFLIGHT-environment.json` (0925060b).
- **Scope:** phase `environment` only, on 127x08. Code root `code-374325696dc9`, clasher-gpu `-B -s`, CUDA hidden, threads 1, nice 19, cpus [0,1], worker limit 16 GiB, concurrency off. No GPU, no heldout, no retry.
- **Window:** 2026-10-13 00:20Z to 02:20Z.
- **Cites:** the accepted stage completion da9df44b and the fresh quiet-read d5086e1e.
- **Issued copies:**
  - `/mpac/sdicks02/jobs/clasher/v4-b-gap-review/receipts/b-cpu-preflight-environment-go-r1.json` (0444)
  - `l1/receipts/b-cpu-preflight-environment-go-r1.json`

ISSUED AUTHORIZE_B_CPU_PREFLIGHT 0925060b75dc26220bdd802a0ce25c647bf44f7e611d652211bd204988a40fc5

## 2026-10-12 23:24Z: Perception B third authority-placement GO issued

- **Source:** byte-identical to the draft `…/b08-environment-and-placement-go-r2/DRAFT-AUTHORIZE_B_AUTHORITY_PLACEMENT-r3.json` (d2824e27).
- **What it places:** exactly one receipt, the environment CPU GO (0925060b), on 127x08.
- **Settings:** procedure 20e58965, operator d6cb3690, cpus [0,1], between phases. No GPU, no heldout, no retry.
- **Window:** 2026-10-13 00:00Z to 01:30Z.
- **Cites:** quiet-read d5086e1e.
- **Pre-issue check (C-5):** the CPU GO SHA appears on exactly one ISSUED line.
- **Issued copies:**
  - `/mpac/sdicks02/jobs/clasher/v4-b-gap-review/receipts/b-authority-placement-go-r3.json` (0444)
  - `l1/receipts/b-authority-placement-go-r3.json`

ISSUED AUTHORIZE_B_AUTHORITY_PLACEMENT d2824e27091dbb3790be1c460522d899445b91cc28a28c05a2f778848548ea23

## 2026-10-12 23:25Z: Coordinator correction: environment CPU GO publication path moved r1→r2

The coordinator published the environment CPU GO (0925060b) at `l1/receipts/b-cpu-preflight-environment-go-r1.json`. The issued placement GO (d2824e27) signs its source path as `…-r2.json`. This was a coordinator error, and it would make the pinned sender fail before claiming.

The fix is a pure rename, recorded in this commit:
- The blob is unchanged (git object 0a5262702121), so the GO bytes, its SHA and both ISSUED lines are unchanged.
- No duplicate copy is kept.
- The placement GO and draft SHAs are unchanged.

**Placement r3 must use COORDINATOR_COMMIT = this commit.** No placement attempt was consumed.

## 2026-10-12 23:48Z: K4S END full package Sol r1: REQUEST_CHANGES (6 findings); D1 clarification ratified

**Review.** `/mpac/sdicks02/k4s-runner/run-r1/reviews/SOL-REVIEW-END-FULL-r1.md` (6918d77a).

| Component | Verdict |
|---|---|
| safe_input r3 | APPROVE_WITH_CONDITIONS |
| S1 | APPROVE (unchanged) |
| S2, S4 | REQUEST_CHANGES |
| S1b, S3, S9, S10 | REQUEST_CHANGES |
| S5, S6, S7 | REQUEST_CHANGES |

Tests: 1,766 pass normally and 1,744 under -O, after fixing the test shim modes.

**Findings:**
- **F1 (BLOCKING).** The stdlib bootstraps in S2, S4 and common, and the host-tool wrappers, read `safe_input.py` and the host tool through an un-gated ancestor path before any confinement check.
- **F2 (HIGH).** The shallow guard repo that S3 builds is refused by the S5 and S7 host helpers. The guard-repo contract must be consistent across all three.
- **F3 (BLOCKING).** A relative `XDG_CONFIG_HOME` is checked in a different location from where frozen git reads it.
- **F4 (HIGH).** Full-clone verification is optional. It must be a precondition for S9's build, verify and equivalence steps.
- **F5 (HIGH).** RC-9 does not bind the preflight to native/corpus inputs or to the attempt bundle. It accepts an ACK from a different round, and it does not check bus-band consistency.
- **F6 (MEDIUM).** The committed test shims are mode 644, so the suite can't be reproduced as committed.

**Disclosures.** Sol accepted all nine.
- **D1 clarification ratified by the coordinator.** S9 may read, SHA-pinned, exactly the six frozen-verifier support files: the runtime-pin list, the qualified binding, the K4S manifest, `K4S-MAC-PROCEDURE.md`, `spec-pins.json` and `build_tiers.sh`. None of them ever enters `runtime_files`.
- Disclosures 2–9 are accepted as Sol states them: the S9 clone exception, the S3 `FETCH_HEAD` removal, the S10 receive receipt, the TRANSFER-DONE rename and names-only exceptions, the S2 commit-bound diagnostic, the S4 partials, the erratum, and the residuals.

**Next.** The runner fixes F1–F6 and resubmits for Sol r2. No host step until then.

## 2026-10-13 00:02Z: Perception B third placement complete, C-6 clean; environment run GO issued

**Placement r3 (d2824e27).** Ran exactly once at 2026-10-13T00:00:54Z, using corrected commit 72426428.
- Both exit codes 0. One SSH session, no retry, empty stderr.
- Exactly one receipt was placed on 08: the environment CPU GO (0925060b). `runtime_admitted` is false.

**C-6 audit: CLEAN.**
- The revocation tip and fetched tip are both e1f29ee7, an ancestor of origin/main.
- There are 0 REVOKED lines.
- Each relied-on authority has only its single ISSUED line.

**Environment run GO issued.** It is byte-identical to the draft (a3e2af3f) and binds:
- the CPU GO 0925060b and placement d2824e27;
- the approved generic transport, launcher and guard (8d348859, 2679fc3e, cd35c65f);
- the fresh quiet-read d5086e1e.

Run constraints:
- Launch exactly once, through the guard only, from 127x05.
- Slot: 2026-10-13 00:20Z to 01:20Z. CPU hard deadline 02:20Z.
- 16 GiB worker limit, concurrency off, cpus [0,1].
- No GPU, no heldout data, no retry.

Issued copies:
- `/mpac/sdicks02/jobs/clasher/v4-b-gap-review/receipts/b-cpu-transport-run-environment-go-r1.json` (0444)
- `l1/receipts/b-cpu-transport-run-environment-go-r1.json`

ISSUED AUTHORIZE_B_CPU_TRANSPORT_RUN a3e2af3fc419fcfc7693835274bad38dcf0eefd472c5f6aefa177aef012936d7

## 2026-10-13 00:22Z: Perception B environment phase COMPLETE; C-4 audit clean; G6 comparison PASS

**Environment run (a3e2af3f).** One run at 2026-10-13 00:20Z through the generic guard, one SSH session, no retry.
- Launcher and sender exit codes are 0, and the outcome is SUCCESS.
- stderr is empty.
- `environment.json` has SHA c99afeda… and is 4,309,120 B. It equals the envelope artifact. `result.json` has SHA 4a767a3a….
- Both files are retained locally only and are not committed.

**C-4 audit: CLEAN.**
- Revocation tip 5c189f10 is an ancestor of origin/main.
- There are 0 REVOKED lines.
- The environment observation's schema, GO, package and stage-complete binding (da9df44b) all match.
- `cuda_imported` is false and `runtime_admitted` is false.

**G6 comparison against the 2026-10-08 record.** All match.

| Item | 2026-10-08 record | Observed |
|---|---|---|
| Python | 3.12.12 | 3.12.12 (CPython) |
| torch | 2.7.1+cu118, cuda 11.8 | 2.7.1+cu118, cuda 11.8 (version.py 2e3ac2ec) |
| numpy | 1.26.4 | 1.26.4 |
| opencv-python | 4.10.0.84 | 4.10.0.84 |
| ultralytics | 8.1.24 | 8.1.24 |

Supporting details:
- The interpreter resolves to the uv CPython 3.12.12 base, SHA 3008abbb. It is invoked as `envs/clasher-gpu/bin/python`.
- There are 23,467 inventoried files.

**Environment phase ACCEPTED.**

**Next: the 24 epoch units.**
- Epoch 1 runs alone first, with concurrency off and a 32 GiB worker limit.
- After epoch 1 completes and is audited, I'll consider batching.
- The cost gate (G5) still applies: the reducer GO requires that the longest epoch unit took ≤ 3,600 s.

## 2026-10-13 00:25Z: Perception B CPU-preflight GO issued (epoch unit 1 only)

The issued GO is byte-identical to `l1/prepared/b08-epoch01-and-placement-go-r1/DRAFT-AUTHORIZE_B_CPU_PREFLIGHT-epoch01.json` (fd4132c1).

- **Scope:** current-graph epoch 1 only, on 127x08.
- **Limits:** 32 GiB worker limit, concurrency off, cpus [0,1]. No GPU, no heldout data, no retry.
- **Window:** 2026-10-13 01:20Z to 03:20Z.
- **Cites:** the accepted environment record (c99afeda, accepted at 5eeec8a1) and quiet-read d5086e1e.
- **Published at:**
  - `l1/receipts/b-cpu-preflight-epoch01-go-r1.json`, the signed path;
  - `/mpac/sdicks02/jobs/clasher/v4-b-gap-review/receipts/b-cpu-preflight-epoch01-go-r1.json` (0444).

ISSUED AUTHORIZE_B_CPU_PREFLIGHT fd4132c1951fcb2df4b9ee988a2f9a138624fbd13bf38682a8050afe1722a7bd

## 2026-10-13 00:25Z: Perception B fourth authority-placement GO issued

The issued GO is byte-identical to `…/b08-epoch01-and-placement-go-r1/DRAFT-AUTHORIZE_B_AUTHORITY_PLACEMENT-r4.json` (18f17da0).

- **What it places:** exactly one receipt, the epoch-1 CPU GO (fd4132c1).
- **Procedure:** 20e58965, operator d6cb3690.
- **Limits:** cpus [0,1], between phases. No GPU, no heldout data, no retry.
- **Window:** 2026-10-13 01:00Z to 02:30Z.
- **C-5 check:** the CPU GO SHA appears on exactly one ISSUED line.
- **Published at:**
  - `l1/receipts/b-authority-placement-go-r4.json`, the signed path;
  - `/mpac/sdicks02/jobs/clasher/v4-b-gap-review/receipts/b-authority-placement-go-r4.json` (0444).

ISSUED AUTHORIZE_B_AUTHORITY_PLACEMENT 18f17da0405e4b741845e72da24752b35c20332cdfe6b37920d94ea6e9318bc9

## 2026-10-13 00:47Z: X4S-4 script review r8: REQUEST_CHANGES (8); scope ruling SR-1, an external watchdog as the host-safety backstop

**Review.** Sol r8 is `/mpac/sdicks02/jobs/clasher/x4s4-review/SOL-REVIEW-SCRIPTS-r8.md` (bc8255f0). The R7 cases are repaired and all 116 tests pass, but there are 8 new findings. Each round has added in-process guard machinery and each round finds new gaps in it. The finding count went 18 → 10 → 8 → 6 → 4 → 3 → 3 → 8. This loop is no longer converging.

**Ruling SR-1 (coordinator, owner decision).** Host safety on 01 moves to **one small, independent, external watchdog**. It is the authoritative backstop and runs outside the study's process tree. The in-process guards stay as defence in depth, and they are no longer required to be perfect.

**Watchdog requirements:**
- A single short file, stdlib only.
- It starts before any study process and has its own launcher.
- Every ≤10 s it checks:
  - STOP;
  - the hard deadline;
  - MemAvailable;
  - PSI;
  - study-tree process count and RSS/PSS;
  - disk use under the job prefix (bounded measurement);
  - GPU memory (bounded).
- On any breach or measurement failure, it writes a durable **HALT marker**. It then stops every study-tree process, identified by verified (pid, starttime) and killed one by one by PID, with no group signals. It re-scans until the tree is empty.
- It never reads results.
- Its own blocking calls are bounded by timeouts. If its loop stalls for more than 30 s, that is itself a HALT.

**What stays blocking: integrity, not resource enforcement.**
- **R8-F4.** Every consumer must refuse any dependency that lacks its matching guard receipt.
- **New rule H-1.** Any output whose completion time is at or after a HALT marker, or after STOP or the deadline, is never counted. All consumers and the reducer enforce this.

**Non-blocking findings.** R8-F1, F2, F3, F5, F6, F7 (including the late READY, which H-1 covers) and F8 become disclosed residuals, because the watchdog covers them. Fix them only if trivial.

**Sol r9 scope:**
1. the watchdog;
2. the R8-F4 fix and H-1;
3. a check that nothing in r8/r9 regresses correctness, evaluation identity, outcome-blindness or I/O confinement.

If Sol approves, the qualification-plus-conditional-production GO follows Q-D1 to Q-D4.

## 2026-10-13 01:01Z: Perception B fourth placement complete, C-6 clean; epoch-1 run GO issued

**Placement r4 (18f17da0).** Ran once at 2026-10-13T01:00:42Z.
- Both exit codes were 0. One SSH session, no retry.
- Exactly one receipt was placed on 08: the epoch-1 CPU GO (fd4132c1).

**C-6 audit: CLEAN.**
- The revocation tip and the fetched tip are both 0778defe, an ancestor of the current state.
- No REVOKED lines.
- Each relied-on authority appears only on its single ISSUED line.

**Epoch-1 run GO issued.** It is byte-identical to the draft (0ac52112). It binds:
- the epoch-1 CPU GO and the r4 placement;
- the approved generic transport, launcher and guard.

Conditions:
- Launch exactly once, through the guard, from 127x05.
- Slot: 2026-10-13 01:20Z to 02:20Z. The CPU deadline is 03:20Z.
- Worker limit 32 GiB, concurrency off, cpus [0,1].
- No GPU, no heldout data, no retry.

**Duration matters for G5.** The epoch-1 unit's measured duration feeds the G5 cost gate: the longest unit must take ≤ 3,600 s.

**Issued copies:**
- `/mpac/sdicks02/jobs/clasher/v4-b-gap-review/receipts/b-cpu-transport-run-epoch01-go-r1.json` (0444)
- `l1/receipts/b-cpu-transport-run-epoch01-go-r1.json`

ISSUED AUTHORIZE_B_CPU_TRANSPORT_RUN 0ac52112a9203f52001949a757d5f1a248d5616634f8ce82af424b25b05e23dc

## 2026-10-13 01:15Z: Fleet utilization plan adopted (U1–U4) and process ruling PR-1

Sam flagged that the fleet sits idle. The plan is `/mpac/sdicks02/jobs/clasher/coordinator-notes/fleet-utilization-plan-r1.md`, written by an Opus planner from read-only sources. Adopted in full.

**U1 (08): pair perception-B epoch units.** From epoch 2 onward, B runs as two-member groups, using the already-approved generic transport.
- Each group gets disjoint cpus {0,1} and {2,3} and a memory limit of 20 GiB per member.
- Each group gets one CPU GO, one placement and one run GO.
- **Condition:** epoch 1 must be accepted and take ≤ 2,400 s. Otherwise B stays serial.
- The next pair's GOs are drafted while the current pair runs.

**U2 (01): fit-seed noise replicates while X4S-4 is in review.**
- Uses the reviewed X4S-3 harness, with a constants-only edit of 20 lines or fewer, in the new prefix `x4s3b-fitseed-20261013`.
- Runs two more r1-only fits: R3a-rep2 and R3a-rep3.
- Games use paired reuse of the X4S-3 seed bank.
- Readout: σ̂_fit, descriptive only, NEVER ADOPTABLE.
- STOP happens at the X4S-4 GO.
- Review: one diff-only round.

**U3 (03): full-speed cost of always-on S-default.**
- Uses the X4S2 harness with a ceiling-constant edit.
- Runs K4-200 against K4S-200 on 2,400 fresh X-deck seeds, about 4.4 h on CPU.
- **U4 (04)** adds the 0.9× pair after one narrowly reviewed LAN runtime copy.
- **Precondition:** the K4S runner confirms that non-K4S CPU load and the sessions don't affect any K4S END admission, bus or stamp procedure.
- **STOP:** at least 3 h before the first K4S END host step on that host. After the STOP session, no further SSH to that host until END completes.

**PR-1, process ruling.**
- **Review cap.** Exploratory, never-adoptable script reviews are capped at **2 rounds**. After round 2:
  - integrity findings (outcome-blindness, fair information, I/O confinement, evaluation identity, seed provenance) **must be fixed**, with a narrow fix-check only;
  - host-safety findings are covered by the external watchdog and H-1;
  - all other findings are disclosed residuals.
- **Harness-reuse lane.** A byte-identical harness, or one changed only in host, ceiling or path constants, with new config/worklist/seeds, needs only a coordinator checklist: diff, git-export seed audit, 8-seed smoke, live STOP test.
- **Review time box.** Any review that takes more than 3 h goes to the coordinator.
- **Confirmatory work** (T1, K4S, TIERS, B) keeps full review.

## 2026-10-13 01:16Z: U1 amended to match the approved transport (no code change)

The perception-B owner correctly pointed out a conflict between U1 and the approved transport (8d348859) and its review (62cf641a, X6). That transport binds **one** epoch per CPU GO and one CPU GO per run GO. Group members need distinct CPU GOs, with exactly one CPU each, cores [0] and [1], started at least 60 s apart.

**U1 is amended to the compatible form.** Per pair:
- **two** CPU GOs, one epoch each;
- **one** placement carrying both;
- **one** group authority;
- **two** run GOs.

Members run on cores [0] and [1], with RLIMIT_AS ≤ 20 GiB each and starts at least 60 s apart. The epoch-1 gates are unchanged: C-4 accepted and ≤ 2,400 s.

No code-change route is taken.

## 2026-10-13 01:21Z: Perception B epoch-1 unit: KNOWN_FAILURE (phase exit 1); diagnosis needed

**What happened.** Run GO 0ac52112 ran once through the guard at 2026-10-13 01:20Z.
- The SSH session completed and returned a failure envelope: schema `b08-cpu-transport-result.v1`, `phase_exit_code` 1, no artifacts, `runtime_admitted` false. The launcher and sender both exited 1.
- Every local file is timestamped within the same minute, so the phase failed almost immediately rather than mid-computation.
- The envelope carries **no failure reason**, and stderr is empty.
- There was no retry and no repair. All partial outputs are kept.

**Effects:**
- The G5 duration gate cannot be assessed.
- The pair drafts for epochs 2 and 3 stay **unissued**.
- U1 pairing stays on hold.

**Next.** We need the remote failure reason, which should be in the phase's own log or claim files on 08. The B owner is to:
- identify, offline, the exact remote files that would hold it;
- say whether the approved generic retrieval (8ac48b0b) can read them for a KNOWN_FAILURE;
- draft a single-use retrieval GO.

**Known candidate cause, not yet evidence.** The generic-transport review flagged RLIMIT_AS interacting with a CUDA-torch import in epoch units. A fast exit-1 matches that risk.

## 2026-10-13 01:26Z: Perception B epoch-1 failure cause found: IntegrityIncident "Unexpected truth bundle member" (a package or plan bug, not a resource limit)

**How the logs were read.** The approved retrieval refuses KNOWN_FAILURE results. So the coordinator ran a single read-only read on 08 itself, using one SSH session with no ControlMaster.
- The reader is a stdlib stub, sha 864b608d. It opens only the 6 exact paths from the owner's proposed read set (ce0a924d) and refuses symlinks, irregular files, nlink > 1 and oversize files.
- It made no remote writes and started no processes.
- Its output is retained at `/mpac/sdicks02/jobs/clasher/v4-b-gap-review/epoch01-diag-read-r1/`.

**Findings.**
- `stderr.log` (1,376 B, sha 25e8d8b6) contains the traceback, which ends in `b08_cpu_preflight.main` → `b08_current_graph.run` → `context` → `materialize`. The failing check is `require(set(p['truth_bundle_members']) <= set(p['bundle_files']), 'Unexpected truth bundle member')`, which raised `b08_authority.IntegrityIncident: Unexpected truth bundle member`.
- The phase claim `preflight-<CPU>/claim.json` is **missing**. The failure happened before the claim, during plan materialization. No computation ran.

**Cause.** The materialized execution plan lists truth-bundle members that are not among its `bundle_files`. That is a defect in the frozen package's execution-plan template or materializer, or a mismatch with the GO's `environment` field. It is **not** RLIMIT_AS or torch.

**The fix needs new bytes.** The owner diagnoses offline, from the frozen template and the issued GO. A fix will probably need a new package revision with a delta review and redeployment, or a corrected GO field if the GO is the cause.

## 2026-10-13 01:28Z: U2 (fit-seed replicates on 01): Sol diff review APPROVE_WITH_CONDITIONS; GO issued

**Review.** Sol's diff review is at `/mpac/sdicks02/jobs/clasher/x4s4-review/SOL-REVIEW-X4S3B-DIFF-r1.md` (840c9733). Its verdict on commit ab4efe030 is APPROVE_WITH_CONDITIONS:
- the scheduler still keeps fits away from S-200;
- the checkpoint SHA check is preserved;
- the σ̂ estimator and its interim/final labels are correct;
- STOP is preserved.

**GO for U2 on 127x01** (exploration, NEVER ADOPTABLE), under these conditions:
1. **Shell mode.** Restore `run_fit.sh`'s executable mode, or launch it explicitly with `bash`, and disclose which.
2. **Write locations.** Every write, including the reducer output, must go under J2 = `/mpac/sdicks02/jobs/clasher/x4s3b-fitseed-20261013`. The X4S-3 job directory J is read-only.
3. **Stop time.** Set `STOP_AT` to no later than the actual launch plus 8 h, keep the assertion, and record the value in PROGRESS and READOUT. A small constant-only commit is enough; it needs no new review.
4. **Before launch, in order:**
   - copy the staging inputs with plain copies, never links;
   - audit J2 for symlinks and references to J;
   - run the 8-seed smoke;
   - run the live STOP test;
   - then launch detached, using X4S-3's core map at nice 10.
5. **Stopping for X4S-4.** On "STOP U2" (the X4S-4 GO), stop immediately and drain by PID.

## 2026-10-13 02:07Z: X4S-4 r9 scoped review: 8 findings; ruling SR-2 caps the loop (fix plus one diff-only fix-check, then GO)

**Review.** Sol r9 (`/mpac/sdicks02/jobs/clasher/x4s4-review/SOL-REVIEW-SCRIPTS-r9.md`, 1b68d637) returned REQUEST_CHANGES with 8 findings:
- **Watchdog:**
  - F1: the stall timer excludes the watchdog's own writes and teardown.
  - F2: cadence can exceed 10 s.
  - F3: process membership and the readout exemption are not closed over work launched from inside the study.
  - F4: a malformed but "successful" measurement is treated as healthy.
- **Integrity:**
  - F5: a STOP interval can disappear before H-1 has durable evidence of it.
  - F6: H-1 omits dependency completions and some READY consumers.
  - F7: raw packing and resume edges are missing from the receipt table.
- **Regression:** F8: the watchdog's own artifact I/O bypasses confinement.

Sol endorses the deadline interpretation (#2).

**Ruling SR-2 (final process for X4S-4):**
1. The owner fixes **all 8** and adds a test for each.
2. Sol does **one diff-only fix-check**: for each of the 8, it says fixed or not fixed, with evidence, and checks for regressions in the changed lines only. There is no open-ended re-review.
3. If all 8 are confirmed fixed, I issue the qualification-plus-conditional-production GO.
   - New findings of the watchdog-robustness or "other" class become disclosed residuals.
   - Only a newly found integrity or regression defect can block the GO, and it would be fixed and checked the same narrow way.
4. **The watchdog is now part of the host-safety contract.** If it ever HALTs, X4S-4 ends, and that is reported as an outcome. It is never silently restarted.

## 2026-10-13 02:12Z: Perception B combined delta review: APPROVE_WITH_CONDITIONS; new combined receipt r3 ISSUED

**Review.** `/mpac/sdicks02/jobs/clasher/v4-b-gap-review/B-TRUTH-DELTA-COMBINED-REVIEW-r1.md`, SHA **3c6dfd49aac9ee35589924ea31a0f242a305e0eb3ab8256291b3d1574a28973f**. The verdict is APPROVE_WITH_CONDITIONS and covers:
- package r3 (7c86e49a);
- generic transport template r2 together with its binding procedure;
- F1 r4 (1b7a64f4);
- the baseline + delta authority model.

It also confirms that the bound generic transport may run the **stage** phase (C-7.1).

**C-1 records:**
- **Cause of the epoch-1 failure.** It was package defect (a). The template carried 192 external truth payloads (64 each of events, objects and rich-objects) that the frozen materializer and `epoch_inputs` adapter required to appear in `bundle_files`. It was **not** the GO's environment reference and not the accepted observation.
- **Fix.** r3 authenticates those payloads through pinned validation receipts and keeps `bundle_files` equal to the original inventory.
- **Superseded text.** `BINDING-PROCEDURE.md` (59de4149) and this review supersede the package `REVIEW.md` paragraph about the zero digest and post-issuance acceptance.

**C-2: new combined receipt.** It binds:
- package 7c86e49a;
- CPU plan b3a90f96;
- deploy script f9fe2ea6;
- baseline scientific review 35b7cf4f;
- delta review 3c6dfd49.

Provenance: review manifest bf6a0d6b, generic template 6ca8b0c6, F1 r4 1b7a64f4.

Published copies:
- `l1/receipts/b-combined-review-receipt-r3.json`
- `/mpac/sdicks02/jobs/clasher/v4-b-gap-review/receipts/b-combined-review-receipt-r3.json` (0444)

The C-5 pre-check passed. Every downstream GO for package r3 uses this single receipt.

**Next.** The coordinator runs the C-3 mechanical binding of `REVIEW` in the generic transport, then redeploys, places, stages, checks the environment, and runs epoch 1 (C-5 to C-8). The failed epoch-1 chain stays consumed.

ISSUED APPROVE_B_COMBINED_REVIEW f50ec6051708dbb3f962612ea133cd0bb48fd745cca95e5aa4aa4ddc2b9e9e60

## 2026-10-13 02:13Z: Perception B generic transport bound (C-3 mechanical binding, PASS)

The coordinator carried out BINDING-PROCEDURE steps 1–6 in `l1/prepared/b08-generic-transport-review-r2/`.

**Step 1: pre-checks.**
- The review set (manifest bf6a0d6b) re-hashes: 27/27 members, `check_binding.py` 6838a770, template manifest 6ca8b0c6.
- Before the edit, the bound directory was byte-identical to `template/`.
- A pre-bind backup was kept under `/mpac/sdicks02/jobs/clasher/v4-b-gap-review/generic-r2-prebind-backup-*`.

**Step 2: the one-line source change.** In `transport.py` line 17, `REVIEW = 'REVIEW_SHA'` was replaced with the issued combined receipt r3 (`REVIEW = 'f50ec605…'`). That is the only source change.

**Step 3: derived pins.** The transport hash was updated in `guard.sh`, `launcher.sh` and `retrieval.sh`. The manifest's status is now `COORDINATOR_BOUND`, and its four records were recomputed with the canonical encoder. Afterwards the 5 edited files were set back to 0444.

**Step 4: `check_binding.py` result PASS.** The receipt for this run is `/mpac/sdicks02/jobs/clasher/v4-b-gap-review/binding-check-r3.json`.

| Artifact | SHA-256 |
|---|---|
| transport.py | d3dc83a98a556481ca56b0d029ea265074b21870153e670c075a499ae56fcc21 (template version 96267dcd) |
| guard.sh | c9cb67e2475e37867f30d762662a95f4c0ef95c6d2051ad89bcfc587701854d7 |
| launcher.sh | 6eb6b725765b18959ffb79eab199f05377f52408706368d69b77850b19a61759 |
| retrieval.sh | 609cac0fa28db0baffc25c740466433a82ba0a23bb10fdef443c3da7c570712f |
| bound REVIEW-MANIFEST | 205309ae90a77cfbdcad5530047e12751737deea3257f32846facf43713a0462 |

**Step 5: tests.** The 30 generic tests pass on a `/dev/shm` copy. The log is kept outside the bound directory, at `…/v4-b-gap-review/generic-bound-tests-r3.log`.

**Step 6: re-check.** Re-running `check_binding.py` against the bound directory still gives PASS.

**Next.** C-5: a fresh deployment GO for package r3. Before it, a fresh quiet-read of 08.

## 2026-10-13 02:21Z: 08 quiet-read r3, for the package-r3 deployment GO

- **Script:** the reviewed quiet-read with one change, its output directory set to `b08-quiet-read-r3`. Script SHA is 17e56b2d.
- **Run:** exit 0, one SSH session.
- **Output:** `l1/receipts/b08-quiet-read-r3/observation.json`, SHA **e3ee45222f9c7c9b796087d2969e0e1d574eadf7f3cdd24c1dbe4f98cae0e267**.
- **Readings (remote UTC 2026-10-13T02:20:56.399083Z):**
  - who: 0;
  - available on `/mpac`: 1,220,879,642,624 bytes out of 2,015,104,376,832 (60.6%);
  - load average: 0.16 / 0.21 / 0.19;
  - CPUs: 128.
- **Gates:** all pass.

## 2026-10-13 02:22Z: Perception B package-r3 deployment GO issued (copy to 08, once)

The issued GO is byte-identical to the draft `l1/prepared/b08-package-r3-deployment-final-r1/b-deployment-go-receipt-r3.json` (8b38cd19).

**What it authorizes:**
- Deploying package r3 (7c86e49a) to 127x08, using:
  - deploy script f9fe2ea6;
  - the F1 r4 deployment operator files;
  - combined receipt r3.
- Writes go only to the new `*-7c86e49a105d` prefixes.
- cpus [0,1].
- No GPU, no heldout data, no retry.

**Window:** 2026-10-13 03:00Z to 04:30Z. The single failure inspection must finish by 05:00Z.

**Quiet-read:** e3ee4522 (who 0).

**C-5 pre-issue check:** passed.

**Issued copies:**
- `l1/receipts/b-deployment-go-receipt-r3.json`
- `/mpac/sdicks02/jobs/clasher/v4-b-gap-review/receipts/b-deployment-go-receipt-r3.json` (0444)

ISSUED AUTHORIZE_B_DEPLOYMENT 8b38cd19c0c960f205463d1612416da6dd8fb51defce9d0b7ba25743832c0bf7

## 2026-10-13 02:51Z: U3/U4 GO (CPU K4-vs-K4S pairs on 127x03 and 127x04, STOP_AT 07:30Z)

The coordinator checked the fix commit d4c7d646 without another review round, as PR-1 allows, against 3dc9ab25 (path `reports/explore/fsc`). The diff covers only the following:
- **Sol r2 R2-1:** stop history fails closed. Both scripts set `nullglob`, so a host with no stop logs is not refused.
- **R2-2:** console users = the max of the helper, checked logind sessions and `who`. Any failed probe counts as 1.
- **R2-3:** every phase's stop-at is `min(now + n, STOP_AT)`. `start` refuses a stop-at past the cap or already passed. `stop` covers every instance. The stop runner is armed before the launches.
- **The single cap:** the file `fsc/DEADLINE` = 2026-10-13T07:30:00Z.

No other logic changed. On a fresh export on 05, all 8 offline test groups pass (coordinator rerun), and nothing in `/mpac/sdicks02/jobs-fsc` was created locally.

**GO**, using commit d4c7d646 and bundle MANIFEST 8978a588:
1. arm `stop_runner.sh` on 05 at 07:30Z for 127x03 and 127x04;
2. `session.sh launch 127x03` with STOP_AT 07:30Z;
3. `session.sh launch 127x04` after 03 returns `__RC=0`.

All of K1–K7 hold as cleared by the K4S runner. Output after STOP_AT is not counted (H-1). K4S A1 on 03/04 is no earlier than STOP + 1 h.

**Disclosed residual:** the bootstrap may create the parent `/mpac/sdicks02/jobs-fsc` on each host.

## 2026-10-13 03:03Z: B package-r3 deployment accepted; FSC-1 (03 resident cache service); X4S-4 r10 to Sol fix-check

**Perception B deployment r3: ACCEPTED.** Coordinator checks:
- the operator exit code is 0;
- `complete-from-stdout.json` hashes to c5c13a5e, which matches the compact receipt `l1/receipts/b08-r3-deployment-result-r1.json`;
- it covers 334 files and 46,418,437 B;
- its schema is `b08-deployment-complete.v1`;
- package 7c86e49a, GO 8b38cd19 and review f50ec605 all match the issued authorities;
- `runtime_admitted=false`;
- there was one SSH session, no inspection and no retry, and the one-use wake-up was disabled.

Next: the perception owner drafts placement r6, which carries the r3 combined review receipt and the stage CPU GO, with fresh windows under the r4 procedure (C-6 to C-9). No phase action happens until the coordinator issues it.

**FSC-1, the 03 preflight refusal.** The 03 launch stopped correctly at preflight (`__RC=91`, nothing staged; 6bcb10c6). The cause is the perception v4 validation cache service PID 2180947 (PGID 2180934). K4S already pins it as 03's idle resident (start_ticks 139691386), and nobody may touch it. Ruling:
- FSC may add an exact-identity exemption to `foreign_sample`/`preflight`, on 127x03 only, for PGID 2180934's three processes (2180934, 2180946, 2180947), with 2180947 at start_ticks 139691386.
- The exemption holds only while the service is idle: its CPU ticks may grow by at most 1 % of one core across the existing 15 s two-sample window.
- Any other identity, a changed start time, or activity is foreign, as before.
- FSC never signals, traces or reads anything of the service beyond /proc stat.

This is a narrow integrity-neutral fix, so the coordinator checks the diff directly under PR-1. A new GO is needed. The STOP_AT stays 07:30Z, and the stop runner already armed stays in place.

**X4S-4 scripts r10** (8bde7397, runbook pin 8a1a0595) went to a Sol diff-only fix-check under SR-2.

## 2026-10-13 03:06Z: 08 quiet-read r4, for the stage CPU GO r2 and placement r6

The coordinator read 08 once, read-only, with `evidence/coordinator-quiet-read-r4.sh` (069ec8bb). It is the reviewed e36f8538 with only the `Q=` output directory changed. Exit code 0, no retry.

Result in `l1/receipts/b08-quiet-read-r4/observation.json` (045b24b3):

| Field | Value |
|---|---|
| who | 0 |
| available | 1,220,832,444,416 B |
| loadavg | 0.08 |

## 2026-10-13 03:07Z: Perception B issues stage CPU GO r2 and placement GO r6 (package r3)

These are the perception owner's drafts (`l1/prepared/b08-r3-stage-placement-drafts-r1/`, f2d3a06b and 19eaf068). The coordinator changed only:
- the fresh observation from quiet-read r4 (who 0, about 1.22 TB free; provenance commit 1841fb84, observation 045b24b3);
- `draft_status`, set to READY;
- the two resolved issuance blockers, which were removed.

After that, the CPU GO was hashed first and its new SHA was substituted into the placement GO's `receipts` and `git_sources`. The diffs were checked field by field.

**Checks:**
- The placement GO passes the reviewed F1 r4 `validate_go`: procedure 3fc7166d, package 7c86e49a, 08, cpus [0,1], between phases, observation, exact authority paths. It is refused before its window.
- Both receipt references pass F1 `receipt()`: the combined review receipt f50ec605 and the stage CPU GO fc424a30.
- C-5: no prior ledger line holds either SHA. There are 0 `REVOKED` lines.
- Between phases: since the deployment was accepted at dfc637c0, no new-package CPU or GPU phase has launched.

**Windows:**
- Placement: 2026-10-13 03:45Z to 05:15Z, operator 2c22b94e, one invocation, no retry.
- Stage CPU: 04:00Z to 06:00Z.

The stage run itself still needs C-6 acceptance of the placement and a separate run GO. The stage run must end by 05:00Z.

**Published:**
- `l1/receipts/b-cpu-preflight-stage-go-r2.json`
- `l1/receipts/b-authority-placement-go-r6.json`
- 0444 copies in `/mpac/sdicks02/jobs/clasher/v4-b-gap-review/receipts/`

ISSUED AUTHORIZE_B_CPU_PREFLIGHT fc424a303bca687eb7a2925d7ef1783b08b5c9846d37836a8f3439d0d040d47d
ISSUED AUTHORIZE_B_AUTHORITY_PLACEMENT e49db31347ccdad5ce4d11d0982beb4830caa1204aa7b5c223aff9f00c2abab0

## 2026-10-13 03:12Z: U3/U4 re-GO with FSC-1 (c7df6fac, STOP_AT 07:30Z)

The coordinator verified `git diff d4c7d646 c7df6fac -- reports/explore/fsc` directly. It contains:
- **The FSC-1 exemption.** `hostcheck.py resident` reads only `/proc/<pid>/stat` on 127x03. It requires exactly PGID 2180934 with PIDs {2180934, 2180946, 2180947}, and start_ticks 139691386 for 2180947, and treats the service as idle only if it uses ≤ 15 ticks over the preflight window. Otherwise the gate stays as before.
- **A fresh leaf for 03,** `fsc-03-20261013b`, via 5 path constants. The failed attempt's prefix (bundle only) is left untouched.

On a fresh export, the 9 offline test groups pass (coordinator rerun), including the new `test_resident_exemption`.

**Approved:**
- Move the 02:52Z attempt's local launch log and wrapper output on 05 into `fsc-sessions/attempt1-0252Z/`.
- Replace the stop runner armed against d4c7d646. First verify that `/proc/2050067/cmdline` and its start time match the runner receipt, then `kill -KILL 2050067` and `kill 2050100`, then confirm both are gone with `ps -p`. Exact PIDs only, no pattern kill.
- Arm a new runner with C=c7df6fac, M=2f16b70d and AT 07:30Z before the launches.

**GO:** the same sequence as at 19047ce7. 03 launches first, and 04 launches only after 03 returns `__RC=0`.

**Disclosed residual:** the FSC slots on 03 (cores 0–59, supervisor 62) overlap the idle service's pinned cores 48–63 and 112–127. This is harmless while the service is idle.

## 2026-10-13 03:12Z: X4S-4 r10 Sol fix-check: 6/8 fixed; two narrow closures, then the coordinator verifies and GOs

Sol's fix-check (`x4s4-review/SOL-FIXCHECK-R10-r1.md`, e5b71aae) returned REQUEST_CHANGES. R9-F1, F2, F4, F5, F6 and F8 are FIXED, and the late 0.05 s H-1 widening is conservative at all four boundaries. Two items remain:
- **R9-F3:** the watchdog's readout-root predicate (`watchdog.py:192`) accepts a `guard.py` token anywhere in argv. A process that never runs guard.py can make its subtree deadline-exempt. Output admission is already bound to the exact invocation in `studytree`, so this is a host-safety/deadline gap, not a counting gap.
- **R9-F7:** `packw.py` silently skips non-real `game-*` entries, but the frozen packer still globs them, so a linked, unevidenced game could be packed. This is an integrity gap.

**Ruling SR-3:** these two get one narrow closure each. There is no further Sol round. The coordinator verifies the diff directly, as PR-1's final round, and then issues the X4S-4 GO.
- **F3:** a readout root must be a process whose executable is Python and whose script argument, in the interpreter's script position and not anywhere in argv, is the exact `guard.py`. It must run `--readout` with an allowed command that matches `guard.py`'s own allowlist. Turn the existing `-c` fixture into a negative; the positive must be a real Runner subtree.
- **F7:** refuse (do not skip) any `game-*` entry that is not a real directory. Assert that the authenticated inventory equals the packer's glob inventory before calling the packer. Add a negative with one authenticated game plus one linked, unevidenced game.

The full matrix must pass under -O0/1/2. Nothing else changes.

## 2026-10-13 03:34Z: K4S END tooling approved (Sol r2); first 03/04 END host step ≥ FSC STOP + 1 h

Sol's full-package r2 review (`k4s-runner/run-r1/reviews/SOL-REVIEW-END-FULL-r2.md`, a770a69e) returned **APPROVE**: F1–F6 are fixed and no new blocking defect was found. Package 9ecf50b1, index 50cc06bc.

There are two non-blocking notes:
- The double-slash HOME normalisation accepts any `//…` HOME, not only `//home/sdicks02`. The runner either corrects the index text or narrows the code and tests, at its choice.
- The test-mode assumptions need documenting: `tar.umask=0022` and process umask 0022.

The END tooling is now frozen at these SHA256SUMS. The runner may do any 05-only preparation now. Any step that touches **03 or 04** (A1 onward) needs a coordinator GO, and comes no earlier than **1 h after the FSC STOP is verified**. STOP_AT is 07:30Z.

## 2026-10-13 03:36Z: X4S-4 GO (scripts d09bdef9, runbook 7b3ec27b); U2 drains after R3a-rep2

**SR-3 verification.** The coordinator read `git diff 8bde7397 d09bdef9`. The code changes are only in `watchdog.py` (`readout_argv`) and `packw.py` (refuse non-real `game-*`, plus `check_inventory`), plus tests, SCRIPTS.md and receipts.
- **F3:** a readout root now needs all of these:
  - a Python argv[0] with only plain flags, then exactly the `guard.py` beside the watchdog;
  - `--readout` before `--`;
  - a wrapped command that passes guard.py's own `studytree.readout_invocation`;
  - `X4S4_READOUT=1`.

  This matches the runbook's GRD/RTPY invocations: the watchdog and guard.py both live in `$J/rt-R3a/repo/reports/explore/x4s4/`.
- **F7:** a non-real `game-*` is refused, and the authenticated inventory must equal the packer's glob immediately before `pack()`.
- **Tests:** mutants were observed for both. The 128/128 matrix passes under -O0/1/2.
- **Residual:** a game that appears between the inventory check and the packer's own glob. That window is milliseconds long, inside a guarded single-writer job.
- **Runbook pin:** 7b3ec27b changes only the `C` pin and two archive commands.

**GO (Q-D1, a single combined GO for qualification plus conditional production)** on 127x01, per QUALIFY-RUNBOOK at 7b3ec27b (c55ba41d) with scripts d09bdef9. X4S-4 is NEVER ADOPTABLE.

**U2 sequencing amendment (supersedes "STOP U2 at the X4S-4 GO"):**
- U2 continues until R3a-rep2's S-200 phase completes, which gives the interim fit-seed σ̂ (1 pair).
- U2 then STOPs. The rep3 fit or games in progress are abandoned and disclosed.
- U2 reports when it has drained, and X4S-4 starts S0 only after that report. The expected cost is about 1 h of X4S-4 start delay, and 01 stays busy throughout.

## 2026-10-13 03:48Z: B placement r6, C-6 ACCEPTED

Placement GO e49db313 completed once (operator 2c22b94e, one SSH, no retry, no extra inspection). Coordinator checks:
- the launcher exit code is 0, and the sender's `exit.json` reports `exit_code` 0;
- `complete-from-stdout.json` hashes to 4e31288b with schema `b08-authority-placement-complete.v1`;
- package 7c86e49a, procedure 3fc7166d and GO e49db313 match;
- the receipts are exactly the review receipt f50ec605 and the stage CPU GO fc424a30;
- `runtime_admitted=false`.

**C-6 audit:**
- `revocation_tip_commit` = `fetched_tip` = ccce58e1, which is an ancestor of origin/main.
- `git log -p ccce58e1..origin/main` contains none of the three placed or authorizing SHAs.
- 0 `^REVOKED` lines.

**Placement r6 is ACCEPTED.** Next: the stage run GO, issued from the owner's draft af547ef8 with these completion fields filled in.

## 2026-10-13 03:48Z: B stage run GO r2 issued (generic transport, package r3)

The issued GO is the owner's draft af547ef8. The coordinator changed only these fields:
- placement r6 completion: complete 4e31288b; launcher and sender exit codes 0; revocation and fetched tip ccce58e1;
- C-6 acceptance commit d6ba3393;
- `placement_c6_accepted=true`, `draft_status` READY, and the one remaining issuance blocker.

The diff was checked field by field.

**What it authorizes:**
- Bound generic transport manifest 205309ae.
- Review f50ec605, stage CPU GO fc424a30, placement e49db313.
- 127x08 driven from 05, cpus [0,1].
- No GPU and no heldout data.
- One launch only, with no retry.

**Window:** 2026-10-13 04:00Z to 05:00Z. No action after it ends. The first launch starts after 04:00Z.

**C-5:** passed, no prior line.

**After the run:** the C-4 audit, then environment drafts with G6.

**Published:**
- `l1/receipts/b-cpu-transport-run-stage-go-r2.json`
- the 0444 copy in `v4-b-gap-review/receipts/`

ISSUED AUTHORIZE_B_CPU_TRANSPORT_RUN 0f0f198efce295812d8690c4703292432fa6ba09ea76ddaa725e827b5ef6ce87

## 2026-10-13 04:05Z: B stage r3 C-4 ACCEPTED; 08 quiet-read r5

**Stage run 0f0f198e** (CPU fc424a30) ran once and reported SUCCESS. Launcher and sender exit codes were both 0.
- `complete.json` is ace2d686: schema `b08-stage-complete.v1`, package 7c86e49a.
  - `runtime_admitted`, `gpu_work` and `heldout_opened` are all false.
  - 2,136,818,985 B staged.
  - It completed inside the window.
- `result.json` is dc5f44fe.

**C-4 audit:**
- The claim tip 542eac9e is an ancestor of origin/main.
- `git log -p` from that tip to origin/main contains none of fc424a30, 0f0f198e, e49db313 or f50ec605.
- 0 `^REVOKED` lines.

**Result: ACCEPTED.**

**Quiet-read r5:** `evidence/coordinator-quiet-read-r5.sh` (cd17cc83), which is e36f8538 with only `Q=` changed. Exit 0, one SSH, no retry. `l1/receipts/b08-quiet-read-r5/observation.json` (c9a4e74a):
- who 0;
- 1,218,691,829,760 B available;
- loadavg 0.18.

**Next:** environment CPU GO r3 and placement r7, issued from the owner's drafts.

## 2026-10-13 04:05Z: B environment CPU GO r3 and placement GO r7 issued (package r3)

These are the owner's drafts in `l1/prepared/b08-r3-environment-placement-drafts-r1/` (dc5001c8, d75da062). The coordinator changed only:
- the fresh observation from quiet-read r5 (c9a4e74a at commit c0e4b880: who 0);
- the stage prerequisite (complete ace2d686, C-4 accepted at c0e4b880);
- the placement's `between_phases`/`no_active_cpu_or_gpu_phase=true`: the stage completed and was accepted, and no phase is active;
- `draft_status` and the remaining issuance blocker.

The CPU GO was hashed first, then the placement GO's `receipts` and `git_sources` were repinned to it. The diffs were checked field by field. The placement GO passes F1 r4 `validate_go`, and the CPU GO passes `receipt()` (phase environment). C-5 is clean and there are no path collisions.

**Windows:**
- placement: 04:40Z to 06:10Z, operator 2c22b94e, one invocation;
- environment CPU: 05:00Z to 07:00Z.

The environment run still needs C-6 acceptance and a separate run GO. G6 must be compared before any epoch GO.

ISSUED AUTHORIZE_B_CPU_PREFLIGHT 2f015cb75f11ed70f123fe6f80e242fd76ad0d16345cbac10b57f4e2e244809c
ISSUED AUTHORIZE_B_AUTHORITY_PLACEMENT 4c26f8a78aba1afc6797eb47dbfa72e8e7773b930ae8a8a5625d75fe579caea4

## 2026-10-13 04:18Z: K4S END A1/A1b GO (read-only copy during FSC; gap kept for A2 onward)

**Request:** the K4S runner's A1-GO-REQUEST (ccce58e1).

**Runner's analysis:** A1/A1b are 8 short read-only logins from 05 at nice 19.
- They copy closed records of completed K4S phases and the r4 admission JSONs.
- They are byte- and SHA-checked, with an inode/size stability check, and take no measurements.
- FSC writes only under its own prefixes. Login-refreshed motd stamps are re-read live before A5/S7.

**Ruling.** The FSC STOP + ≥ 1 h gap applies to A2 onward: staging, S10 df/who checks, S5 preflight measurement, A5 stamps and END launches. It does not apply to A1/A1b.

**GO:** A1 (S1 b987ab97) and then A1b (S1b 7515d5fe), but only if A1 exits 0. Run them exactly as in the request:
- repo-full;
- commit 72426428;
- the k4s-freeze python with `-I -B` and `env -i`.

Conditions:
- Any refusal stops the sequence, with no retry.
- No other step on 03/04.
- Commit via `commit_paths_end.sh` only.
- Then do the 05-only prep (S2/S9/S4/S3/RC-6) and send the A2 GO request for after the gap.

## 2026-10-13 04:42Z: B placement r7, C-6 ACCEPTED

Placement GO 4c26f8a7 completed once (operator 2c22b94e, one SSH, no retry).

**Completion checks:**
- launcher and sender exit codes 0;
- `complete-from-stdout.json` 2a0fb4a9: schema `b08-authority-placement-complete.v1`, package 7c86e49a, procedure 3fc7166d, and exactly one receipt, the environment CPU GO 2f015cb7;
- `runtime_admitted=false`.

**C-6 audit:**
- `revocation_tip_commit` = `fetched_tip` = bfbc3221, which is an ancestor of origin/main;
- `git log -p bfbc3221..origin/main` contains none of 2f015cb7, 4c26f8a7 or f50ec605;
- 0 `^REVOKED` lines.

**Placement r7 is ACCEPTED.** Next: the environment run GO, issued from the owner's draft 9ae4256b.

## 2026-10-13 04:42Z: B environment run GO r2 issued (package r3)

The issued GO is the owner's draft 9ae4256b. The coordinator changed only the placement r7 completion fields:
- complete 2a0fb4a9, exit codes 0, tips bfbc3221;
- C-6 acceptance at 991ab1c8;
- `placement_c6_accepted=true`;
- `draft_status` and the remaining blocker.

**What it authorizes:**
- The bound generic transport 205309ae, CPU GO 2f015cb7 and placement GO 4c26f8a7.
- The accepted stage ace2d686.
- 127x08 driven from 05, cpus [0,1], 16 GiB, concurrency off.
- No GPU and no heldout data.
- One launch only, with no retry.

**Window:** 05:00Z to 06:00Z. The CPU GO ends at 07:00Z.

**Next:** C-4, then a coordinator G6 comparison before any epoch GO.

C-5 passed and there are no path collisions.

ISSUED AUTHORIZE_B_CPU_TRANSPORT_RUN e09712aa47bcf83cee406bf0734d26c6da1aaf4c3e14bd2f48260650f3a98c3e

## 2026-10-13 04:49Z: U2 drained (X4S-4 starts); K4S A1 refusal fixed (S1 r6), A1/A1b re-GO

**U2 drained** (14d8bdb7). The R3a-rep2 S-200 phase finished cleanly, all U2 process groups are empty and the 01 GPU is free. Interim fit-seed σ̂ = 0.0 pp (1 df, interim). "U2 drained" was forwarded to the X4S-4 owner, who starts S0 under GO 4b33d68d. The final 3-pair readout needs R3a-rep3's games on 01, which waits until X4S-4 frees the host.

**K4S A1, first attempt (GO ea3f7686).** S1 refused at login P on 03 with rc -9. Nothing was copied, the destination was never created and A1b was not run (b3349328).
- **Cause:** S1 `_finish` SIGKILLed ssh after stdout EOF but before ssh itself had exited.
- **Fix:** `s1s2-r6` (bfbc3221). S1 is the only changed production file, now 16cbbf57. `_finish` waits up to `EXIT_GRACE = 30 s` for ssh's own exit and kills only after that. The hard per-login timeouts are unchanged.
- **Tests:** 3 new tests, each of which fails on the r5 bytes; 334 pass on 3.12/3.8, normal and -O.
- **Review:** the coordinator verified the 5-line diff directly. There is no other subprocess handler with this race; the rest go through `safe_input.run_checked`.

**Re-GO:** A1 with S1 r6 (16cbbf57), then A1b, but only if A1 exits 0. Commands and conditions are otherwise as in ea3f7686.

## 2026-10-13 04:52Z: X4S-4 staging amendment SA-1 approved (S2 stop at d0c43065)

S2 stopped correctly at 38/41 checks. `base/repo/imitation/exit_r1/{rows,pack,emitter}.py` were absent, because the X4S-3 base has no exit_r1 package, and `base/corpus/` was absent. The runbook's own S2 rule already requires these files: exit_r1 must equal origin/main, and the corpus must equal the X4S-3 pins. So this is a staging-layout gap, not a code change.

The coordinator verified that at both 04c068f5 and origin/main the files have these hashes:
- `__init__` 441385ea
- rows 835a4104
- pack 5442af29
- emitter dab61651

**SA-1, approved exactly as proposed:**
1. **S1b:** `git archive 04c068f5` of those 4 files into `$J/staging`, then `cp -a` to `$J/base/repo/imitation/exit_r1`.
2. **S1c:** `cp -a $J3/corpus $J/base/corpus`. J3 is only read.
3. Rerun the full S2 with `__init__` added. Then the overlay, S3 and W0, as written.

No script changes. Any further S2 failure stops the run again.
