# External review: vegetableleaf/ClashAI vs Clasher

Date: 2026-09-28. Reviewer: read-only subagent. Scope: evidence-based comparison. No code, weights or data were copied into Clasher, nothing in Clasher was modified except this report, and no package was installed.

- **ClashAI clone:** shallow, at `/Users/sam/Desktop/code/external/ClashAI`. HEAD `61e372d5d0655d7b54deb888f7cf5331df9b3c0a` (2026-09-26, "L68be: HANDOFF -- live lag root cause ..."). About 1.9 GB and 7,710 files. Repo created 2026-07-25; 171 stars at review time.
- **Clasher reference state:** `docs/history/HANDOFF_NEW_THREAD_20260928.md` ("Current continuation state") and `reports/strategy_council_20260928/strategy.md` (approved SHA `2be09f05...`).
- **Citations:** ClashAI paths are relative to the clone root. Clasher paths are relative to `/Users/sam/Desktop/code/clasher` unless given as absolute `~/.cache/...` paths.
- **ClashAI's own journal:** `HANDOFF.md` is a roughly 5,000-line journal. Line numbers refer to that file at the HEAD above.

Labels used below:
- **(measured by them)**: the number is in their journal, not reproduced here.
- **(verified here)**: I read the code or data myself.
- **(inference)**: my own reasoning.

---

## 0. Executive summary

1. **License: none.** There is no LICENSE file anywhere in the repo, and GitHub reports `license: null`. All rights are reserved by default, so **ideas only**: no code, models, data or documentation can be copied. The third-party pieces ClashAI depends on have their own licenses and are *not* part of ClashAI:
   - IMAX9D/cr-native-sandbox: MIT
   - RoyaleGym/RoyaleSim: MIT
   - Ultralytics: AGPL-3.0
   - The HF `VanguardX101/IL_Replay` dataset states no license.
2. **Engine.** ClashAI's "real engine" is IMAX9D/cr-native-sandbox: the original **x86_64 `libg.so` from client 15.535.29**, run headless under a stub JNI host in an Android AVD and driven over JSON-over-TCP. It is deterministic (211/211 byte-identical re-drives) and has **no snapshot op**, so every branch re-drives the prefix. Even so, a full recorded match takes **~2.5 s** on a Linux/KVM slot, and 4 slots in one AVD give **3,400 matches/h**.
3. **Our native branches are ~50-80× slower per decision.** The ~25 min per branch comes from the read path, not from game time. Our v6 branches took 2.11 s per decision; ClashAI's closed loop, with policy inference, takes ~26-35 ms. The biggest overhead is the per-decision out-of-process ADB `dd` level read, plus per-command TCP connections and redundant observes.
4. **Biggest throughput finding: our probe already supports snapshots.** Our injected probe is FirstLight commit `28d66cc`. It already implements and **attests `snapshot_restore: true`** on our 15.535.86 runtime (`snapshot-create` / `restore H`, using the engine's own StateSnapshot serializer with digest verification). It also has resident multi-match slots and persistent sessions. None of these are used by our readiness runner. Fix the read path first, then branch from snapshots; that plausibly takes a branch from minutes to well under a minute (inference, §2.6).
5. **Search teacher.** The engine search teacher (S3: greedy one-shot placement search, hand-written tower-damage score, card teacher-forced, argmax target) **failed its gate in all five configurations**. The gate itself (exact-cell agreement with pros) was a questionable instrument. The more relevant lesson comes from their Python-sim experiment:
   - Rollout search over the student's own shortlist gave a large paired gain (11/12 wins, n=12, replicated on a disjoint slice).
   - **Distilling its argmax actions made the student play worse.** It copied the teacher's play-rate marginal without its judgement (the privileged-teacher gap).
   - This directly supports our soft `kl_regularized_candidate_target` design, and argues for extra controls in our oracle qualification.
6. **Model.** An entity-token + patch-token transformer with a factorised **half-tile 36×64 per-cell head**, a card head, a state-conditioned play/wait gate, "wait for card X", and a crown-difference value head. It has no recurrence and only a 3-play history. Their data shows human placements sit on a **500-unit (half-tile) lattice**, which is relevant to our 576-tile-centre action space for 2×2 buildings (Cannon, Tesla).
7. **Evaluation.** Engine win rates are against **non-reacting "ghosts"** (recorded human command timelines). Their own measurements show these are inflated:
   - 29% of engine matches outlive the scripted opponent, and 27 of those 29 are wins.
   - An engine 74% became **35.1% live** (13W-22L-2D, n=37, CI 21.8-51.2%).
   - Every RL attempt, including a 22.5k-match self-play league, was null.
   - The journal is admirably self-critical. Some README claims are stale or do not match the code (S3 "Gumbel-top-k over student proposals" is not what `pipeline/s3_teacher.py` implements).
8. **Vision.** YOLO11s, 230 classes, presence recall 0.855 / precision 0.886 on 241 images / 820 boxes. **No weights are published**, the Roboflow sources are undocumented, and Ultralytics is AGPL. Not reusable as an artifact. The ideas are reusable: the measured `degrade()` error model, the foot-offset correction, and team-by-colour with a tracker. They later bypassed vision entirely with a live-client memory reader, which we must not adopt.

---

## 1. License

| Item | Finding | Evidence |
|---|---|---|
| ClashAI repo | **No license.** No LICENSE, COPYING or NOTICE file (verified via `find`); GitHub API `license: null`. Only `.github/FUNDING.yml`. The README calls it "open-source" (README.md "Sponsors" section), but that is not a license grant. | `gh api repos/vegetableleaf/ClashAI` |
| What that permits | Under default copyright (and GitHub ToS §D.5, which lets users view and fork on GitHub), we may **read the code and learn ideas**. We may **not copy, adapt or redistribute code, docs, figures, configs, trained weights or datasets**, and "reimplementation" must not be a transliteration. | (legal default) |
| cr-native-sandbox (their engine host; lives in gitignored `research/ext/cr-native-sandbox`, not in the repo) | Upstream IMAX9D/cr-native-sandbox is **MIT** (GitHub API; 8 stars; last push 2026-09-15). The code is MIT. Game APKs and `libg.so` are *not* included and are "legally obtained by the user" only; the upstream README says the repo contains no game files, weights or private data. | upstream README; `research/CR_NATIVE_SANDBOX_ASSESSMENT.md:8,79-81` |
| RoyaleGym family (RoyaleSim Rust engine, RoyaleGym, RoyaleLearn, RoyaleImitate, RoyaleViser) | All **MIT** (RoyaleSim shows `NOASSERTION` in the API, but its LICENSE file is MIT text). Used by ClashAI in gitignored `research/ext/Royale/`. | `gh api repos/RoyaleGym/*` |
| Detector stack | `ultralytics>=8.4.107` (`icebow/requirements.txt:9`) is **AGPL-3.0**. Any YOLO weights they published would be AGPL-entangled. No weights are published (`.gitignore` excludes `*.pt`, `runs/`, `data/`; no LFS). | agent read |
| KataCR detection dataset | Cited as "github.com/wty-yy/Clash-Royale-Detection-Dataset, MIT", and used only for sprites (`icebow/src/clashrl/katacr_segments.py:3-4`). Verify upstream before relying on it. | |
| Roboflow datasets | Fetched through a private API key (`hogeq/tools/roboflow_fetch.py:1-5,45-54`). **Dataset names and licenses are not recorded anywhere.** | |
| HF `VanguardX101/IL_Replay` | "FirstLight anonymized battle replays": 252,238 matches, 17.8 M actions (`tools/hf_manifest.json:1-30`; `tools/hf_download.py:32`). The HF card metadata has **no license field** (checked via the HF API: not gated, no license tag). This is the *same* IL_Replay our strategy already treats as action-only. | |
| ToS | Their README says automating Clash Royale violates Supercell's ToS (README.md:10). Their own assessment flags running `libg.so` outside the client as reverse engineering the ToS prohibits (`research/CR_NATIVE_SANDBOX_ASSESSMENT.md:79-81`). This is not a copyright license question, but it bears on anything touching live clients. | |

**Verdict:** ClashAI's code cannot be copied; ideas only. Anything we build must be written independently in Clasher.

**Side note on Clasher provenance (not ClashAI):** our own probe `libcrprobe.so` is compiled from FirstLight source commit `28d66cc` (`~/.cache/clasher-native-reference/probe-build-20260914/receipt.json`). This review did not assess the FirstLight license. It matters for recommendations R1-R3, which modify or exercise that probe, and should be confirmed separately.

---

## 2. Real-engine setup and throughput

### 2.1 What ClashAI runs

- **Engine and build.** The original Clash Royale **x86_64 `libg.so`, client 15.535.29**, loaded headless by cr-native-sandbox's stub JNI host (`JniHost`). It runs inside a rooted API-31 x86_64 AVD (`-no-window -gpu swiftshader_indirect`, 4 vCPU / 4 GB). Around 60 hard-coded RVAs, and it fails closed on any other build (`research/CR_NATIVE_SANDBOX_ASSESSMENT.md:18-20,43-52`).
- **Renderer and observation.** The renderer is NOP'd; there are no pixels (`:21-22,72-73`). Observation reads process memory (`/proc/self/mem`), exposing entities, elixir, hands, cycle, towers, RNG state and a `state_hash` (`:62-64`).
- **API.** `reset(replay_json)` builds a battle through the client's own replay loader. `step(n)` runs the engine update at a fixed 0.05 s per tick with no sleeps. `act(side, deck_index, x, y)` issues the client's own `DoSpellCommand`, and libg's verdict is authoritative. `joint_transition` applies both sides' actions and steps in one round trip (`:53-61`). `probe_grid` returns libg's own deploy mask, which `pipeline/s3_teacher.py:232-247` uses.
- **Slots and hosting.** One BattleGameState per service ("slot"). 2-4 slots per AVD, reached over adb-forwarded ports 37031+/38031+. They later moved to a GCP Linux VM with nested KVM (`HANDOFF.md:4284-4300`, §5cs.84).

### 2.2 Determinism

- **Measured by them:** 211/211 replays re-driven twice produce byte-identical final state hashes (`HANDOFF.md:2333`).
- The driver checks determinism explicitly with `--runs 2` (`research/sandbox_tools/replay_drive.py:500-520`).
- This matches our finding of zero within-engine floors in the v6 paired repetition.

### 2.3 Branching / snapshot

- **None.** "The engine protocol has no save/restore op (checked: reset, load_replay, act, ability, step, step_trace, observe, joint_*, probe_grid), so every candidate is evaluated by re-driving the replay from reset to the branch tick" (`pipeline/s3_teacher.py:18-21`; also `HANDOFF.md:3314`, `README.md:101`).
- `drive_to()` re-drives every prefix play for each candidate (`pipeline/s3_teacher.py:110-132`). For K futures it re-drives once per future per candidate (`:385-398`).

### 2.4 Throughput (measured by them)

| Measurement | Value | Source |
|---|---|---|
| Full replay re-drive with a compact observation every 20 ticks, Windows/WHPX box | 12.52 s/match | `HANDOFF.md:4278-4281` |
| Same work, Linux/KVM VM, 1 slot | **2.48 s/match** (1,452/h/slot) | `HANDOFF.md:4278-4281` |
| 4 slots in one AVD (`-cores 4`) | 3.58-3.67 s/slot, **3,400 matches/h**, 2.68× | `HANDOFF.md:4266-4271` |
| Pilot drive of 17,853 HF replays on 4 VM slots | **7,192 replays/h** (6,281/h mid-run); 11,415 ok / 6,438 failed (all Elite-Barbarians evolution) | `HANDOFF.md:170` |
| Per-branch cost in S3 (24 candidates, horizon 120) | ~22 s/state/slot, i.e. ~0.9 s per candidate, each a full prefix re-drive plus rollout | `HANDOFF.md:4233` |
| Closed-loop S1 policy vs ghost, decision every 10 ticks | 20.3-21.9 s/match/slot (a 15.9 s figure was a 2-match smoke) → ~35 ms per decision including inference | `HANDOFF.md:3127,3153` |
| Upstream sandbox: batched stepping between commands | 9,738-10,552 ticks/s | upstream `docs/HOST_LITE_READ_CACHE.zh-CN.md:37` |
| Upstream: joint action + step + full state every 4 ticks | 1,207-1,255 ticks/s, i.e. ~3.3 ms per decision round trip | same file, `:38` |
| Upstream Linux resident scaling | 48 workers / 16 cores → 8,162 aggregate ticks/s; 64 workers was slower | upstream `docs/LINUX_HEADLESS_MULTICONCURRENCY_RESEARCH_20260910.zh-CN.md:37-43` |
| Upstream per-call cost breakdown | `step_jni` 3.30 ms, `observe_jni` 0.36 ms, Java JSON parse 1.5-5.6 ms | same, `:49-54` |

Lessons they learned the hard way:
- WHPX vs KVM was a 5× hypervisor effect (`HANDOFF.md:4281`).
- "A throughput number is meaningless until you confirm both sides produced the same artifact." Their first VM number omitted recording and read 1.43 s (`HANDOFF.md:4283`).

### 2.5 Our native reference, for comparison (from a read-only audit of Clasher)

- **Runtime and probe.** Null's 15.535.86 in an arm64 AVD, host GPU, `-no-window`. The probe is FirstLight `cr_replay_probe.cpp` (8,561 lines), built as `libcrprobe.so` with sha `2ea5e10d...` (`~/.cache/clasher-native-reference/probe-build-20260914/receipt.json`). Live attestation reports `content_version 15.535.86`, `libg_build_id 90e6f351...`, capabilities `headless`, `native_render`, **`snapshot_restore: true`**, `structured_observation`, `two_sided_actions` (`reports/strategy_council_20260928/m0/readiness/native-startup-resumed-20260928/attestation.json`).
- **Readiness already runs headless and faster than real time.** `configure` builds a GameStateManager from replay JSON. A dedicated worker thread steps it in a tight loop gated only by the step budget (`cr_replay_probe.cpp:8001,8190,7873`). `step N` only adds budget (`:6052-6079,7040`). Engine stepping cost is negligible.
- **How a branch is built.** `scripts/run_readiness_v2.py:316-364`: attest, status, configure, then replay the whole recorded prefix from tick 0 (`observe` + `step` + `replay-schedule-card` per command), then compare the root frame against the archive. The prefix collector does the same (`src/clasher/rl/readiness_prefix.py`).
- **Unused probe features.** No Python code sends `snapshot-create`/`restore`, uses `session-v1`/`batch-*-v1`, or sends `render off`. A grep of `scripts/`, `src/` and `reports/` finds no uses.
- **Decision cadence.** Every 5 ticks (`src/clasher/rl/readiness_execution.py:247-250`). A tick-90 root to tick 6001 is ~1,183 decisions. v6 native branches ended at tick 3600 with 703 decisions in **1,486.5 s / 1,487.7 s** → **2.11 s per decision** (SwiftShader, per-read attestation; `m0/readiness/paired-repetition-run-v6-verification.json`).
- **Per-decision requests.** Roughly 8-10 probe requests, each on a new TCP connection (`scripts/run_readiness_v2.py:391-526`, `scripts/smoke_reference_battle.py:11-22`), plus one level read.
- **Level read.** Out-of-process, `adb shell` → `dd if=/proc/PID/mem` (`scripts/read_native_public_levels.py:114-120,316-468`). It measured 1.44-1.97 s per read under the old reader, **~79% of branch time** (`m0/native-throughput-profile/README.md`). With verified sessions and host GPU the median read is **0.338 s** (`m0/native-throughput/hostgpu-read-profile.json`). That still projects to ~6-7 min for a 703-decision branch or ~10-12 min for a full game. Full-game throughput on host GPU has not been measured.

### 2.6 What could make our native branches much faster (ranked)

| # | Change | Evidence it helps | Expected effect (inference) | Cost / risk |
|---|---|---|---|---|
| T1 | **One in-probe atomic read per decision.** Add public levels to the probe's `observe-atomic`, or add a level-read command that walks the same structures in-process. Use one persistent `session-v1` connection. Delete redundant `observe` calls. | ClashAI/upstream decision round trips take 3-35 ms with in-process `/proc/self/mem` reads. Ours are 338 ms+ via ADB `dd` plus ~8 connections. | 0.34-2.1 s → roughly 20-80 ms per decision, a **5-30×** branch speed-up. Tier A's 512 native branches would drop from ~200 h (at 25 min) or ~55 h (at 6.5 min) to a few hours on one AVD. | Needs a probe rebuild (NDK restore, 10-30 min per `cleanup-20260925.json`), which gives a new probe sha, a new attestation pin and new identical-execution floors. Needs a dual-read equivalence study against the current reader on archived and development frames. The "no cached body/level values" rule stays intact (still a per-frame read, just in-process). Must land **before** the next immutable runtime freeze (handoff next action 3), or wait until after Tier A. |
| T2 | **Branch from snapshots.** Configure, replay the prefix once to the root, `snapshot-create`, then `restore H` per branch (4 candidates × 4 continuations = 16 branches per family). | ClashAI's entire S3 cost was prefix re-drive (`s3_teacher.py:18-21`, `HANDOFF.md:4233`). Our probe already attests `snapshot_restore: true` and verifies digests on restore (`cr_replay_probe.cpp:640-660,2536-2600,6804-6870`). | Removes the prefix replay per branch (tens of seconds today, larger for late roots). More important later: makes any native candidate evaluation (oracle qualification, Tier B, reference checks) cost O(horizon) instead of O(prefix + horizon). | Needs a restore-validity study on development roots: restored vs from-zero branch outcomes, full frame equality at the first post-restore decision and terminal equality. Check whether the "read-only instance" definition in `start_local_reference.py` permits probe-side snapshot state. Not usable for the current `m0-native-prefix-development-v2` attempt without a new declaration. |
| T3 | **Resident multi-slot** (`batch-fast-v1` / `resident_multimatch.inc`, up to 16 live GameStateManagers per process) or several probe ports per AVD, instead of a second AVD. | ClashAI measured 4 slots/AVD at 2.68× (`HANDOFF.md:4266-4271`). Upstream warns of cross-slot contamination risk and requires an A/B isolation test ("reset A must not change B") (`LINUX_HEADLESS...zh-CN.md:141-160`). | 2-3× per AVD, possibly more than the planned two read-only AVDs. | Isolation tests. The single libg execution lane is shared, so gains come from amortising host overhead, not from CPU parallelism. |
| T4 | **Suppress UI rendering / idle scene cost** (`render off`), since readiness uses the headless manager. | The idle client burned ~7 cores under SwiftShader vs ~110% on host GPU (`m0/native-throughput/emulator-idle-suspend.json`). | Frees CPU for T3; small direct effect on host GPU. | Low. Attestation and capture of the attested state need rechecking. |
| T5 | Linux/KVM host for emulators if remote compute is used. | 5× WHPX→KVM (`HANDOFF.md:4281`). | Not applicable to the Mac mini (Hypervisor.framework); relevant only if the grant is used. | |

T1 is the single largest lever: the dominant cost is the read path, not game time or prefix replay. T2 is the structural lever for any later native search. Neither changes game semantics. Both change the *instrument*, so they must be frozen into a prospective protocol before any fresh capture, never swapped in mid-attempt.

---

## 3. Search teacher (S3) vs our optional oracle arm

### 3.1 What ClashAI actually built (verified in code)

`pipeline/s3_teacher.py`:
- **State.** A pro replay state is reached by deterministic re-drive (`drive_to`, `:110-132`).
- **Card.** Teacher-forced to the pro's slot (`:11-13`).
- **Candidates.** The engine legal mask (`probe_grid`) projected onto the model's 36×64 half-tile lattice, then **2-D stratified** subsampling to `--max-candidates 24` (`:232-288`), then a stage-B refine over all cells within ±2 of the best coarse cell (`:419-430`).
- **Rollout.** Horizon H ticks (120-2400 tested). The opponent is either inert or replays its *recorded* future plays, optionally with K jittered "common futures" seeded per (state, k), not per candidate (`:156-203`). Our own side's future is never replayed except in a diagnostic mode.
- **Score.** v2 = enemy tower HP lost − own tower HP lost + ⅛ × enemy unit HP destroyed (`:206-229`). v1 counted own surviving HP and rewarded "hiding".
- **Selection.** Hard argmax with reservoir random tie-break (`:406-416`). About 40% of candidates tied at the maximum, and "first wins" had resolved every tie to the back row (`HANDOFF.md:4165`).
- **Output.** One target cell per state. No soft distribution, no value target, no uncertainty.

**This does not match the README's description** ("Gumbel-top-k over its top 8-16 proposals + wait", README.md:82). The original proposal (`HANDOFF.md:2340`) was never implemented in the engine.

- **Compute (measured by them).** ~22 s/state/slot at 24 candidates, H=120; 46 min for 497 states on 4 slots. ~75 min with refinement at H=400 (`HANDOFF.md:4233,4138`).
- **Result.** The gate was "teacher exact-cell agreement with pros ≥ student". Teacher 0.00% vs student 21.9-23.9%, mean distance 9.5 vs 3.4 tiles (`HANDOFF.md:4138-4146`). An oracle check showed a near-pro candidate (1.68 tiles) was evaluated and rejected (`:4148-4154`). Five follow-up hypotheses (unit term, opponent model, horizon, sequencing, common futures) all came back null (`:4006-4027`). Spells were the exception: the objective ranked Log and Tornado near the top.
- **Critique (inference).**
  - The gate measured agreement with pros, not teacher strength. "Teacher beats frozen student ≥ 60%" was pre-registered (`HANDOFF.md:2340`) but **never run**.
  - A one-shot, card-forced, horizon-limited placement search under a hand-written damage score is not a reasonable test of search-based policy improvement.
  - The recorded opponent does not react to the candidate (acknowledged at `s3_teacher.py:164-166`).
  - The negative result is real for that objective and nothing broader. The authors say so (`HANDOFF.md:4023`).

### 3.2 The more relevant ClashAI evidence: search over the student in their Python sim

Code: `scratchpad/gauntlet/L67/student_search.py`, fork via `copy.deepcopy((eng, opponent))` in `icebow/src/clashrl/sim/rollout_search.py:308-320`.

- **Setup.** Candidates = WAIT + the student's top-4 affordable cards × top-3 cells. 12 s rollouts on a **privileged** sim fork, scored by their sim Scorer.
- **Controls.** `force_play` (top candidate, no rollout), `random` (from the same shortlist) and `never`.
- **Search result (measured by them, n=12 per slice).** Paired Δtower **+1.71 ± 0.42 (t=4.08), 11/12 wins**, replicated on a disjoint seed slice at +1.46 ± 0.34. The controls were null or negative (`HANDOFF.md:2586-2618`). Most of the gain survived with cell search removed, i.e. gate plus card only (`HANDOFF.md:2620-2632`).
- **Distillation result (measured by them).** 18,218 decisions from 120 matches, fine-tuning the gate and card heads on the teacher's argmax:

  | Metric | Before | After |
  |---|---|---|
  | Teacher agreement (balanced gate) | 0.58 | 0.65 |
  | Teacher agreement (card) | 69% | 87% |
  | Plays per match | ~50 | 21-27 |
  | Pro card agreement | 63% | 49% (−14.5 pp) |

  Sim outcome got **worse** on both slices (−0.54, −0.39, not significant at n=12). Their diagnosis: "the teacher's restraint without its judgement". The student learned the marginal play rate, not the state-conditional evaluation, which is a privileged-teacher gap (`HANDOFF.md:2639-2654`). A later "value reranker" also failed from the same gap (`HANDOFF.md:3318`).

### 3.3 Comparison with our oracle arm

| Aspect | ClashAI S3 (engine) | ClashAI sim search | Clasher optional oracle |
|---|---|---|---|
| Planner | Greedy one-shot placement argmax | Shortlist rollout, argmax | `FixedDepthThompsonOracle` (`src/clasher/rl/oracle_planner.py`): Thompson-sampled bandit over sampled action subsets, fixed depth, stable root candidates, reward-model win probability |
| Candidates | Engine-legal lattice sample, card forced | Student top-K cards × top-C cells + wait | Sampled action subsets; strategy Tier A roles; `stable_root_candidates` |
| State access | Privileged engine state | Privileged sim fork | Privileged scalar sim (critic-side); labels via `imitation.py::_collect_oracle_shard` (`:213-300`) with behaviour mixing |
| Target | Hard argmax cell | Hard argmax action | **Soft** `kl_regularized_candidate_target`: π_old(a)·exp(V(a)/β) over candidates, requires behaviour support (`src/clasher/rl/counterfactual_policy_iteration.py:75-122`) |
| Qualification | Pro agreement (failed) | Paired sim outcome (passed); distillation failed | Tier A teacher-search admission, 64-game screen + 256-game confirmation at ≥0.05 match score, fresh reference checks (strategy.md:65-71) |
| Cost per decision | ~22 s/slot (24 cands, full re-drive each) | Sim fork, cheap | Scalar sim; native only for reference checks |

**Implications for us (inference):**
1. Their distillation failure is exactly the failure our soft target is designed to reduce. π_old·exp(V/β) keeps the student's prior mass and shifts it by value margins. It does not collapse onto the teacher's argmax marginal.
   - This does not solve hidden-information contradictions; our strategy already says so (strategy.md:71).
   - Add explicit **marginal-drift diagnostics** to oracle-student qualification: play/wait rate per elixir bucket and phase, per-card play share, and the teacher vs student situation-conditional gate curve. ClashAI's failure showed up first as plays per match falling 50→21-27.
2. Include ClashAI's three controls in the oracle's 64-game screen:
   - **force-play** (top actor candidate, no search)
   - **random-from-candidate-set**
   - **never-play/wait-only**

   They separate "search chooses well" from "search changes the play rate". They cost one extra arm each at screen scale.
3. **Tie handling and coverage.** 40% maxima ties and two separate candidate-sampler bugs decided their answers twice (`HANDOFF.md:4180-4193,4165`). Our Tier A already specifies pessimistic ties and consequential-coverage accounting. Also dump per-candidate scores for the teacher substage.
4. **Use common random futures across candidates** (seeded per state and future, not per candidate). ClashAI did this correctly (`s3_teacher.py:172-176`), and it is cheap variance reduction for our oracle's rollouts.
5. Compute: on native, per-candidate evaluation is dominated by prefix replay unless T2 (snapshots) is adopted. On scalar, forking is already cheap.

---

## 4. Model and action space

### 4.1 ClashAI S1 (verified in code, `pipeline/model_v3.py`)

- **Entity tokens** (`:109-115`): vocab embedding + 13 features + 32 Fourier coordinate features. Up to 64 tokens, truncated by distance to the river (`pipeline/obs_contract.py:599-612`).
- **Patch tokens** (`:117-120`): 9×16 grid of 2-tile patches, each a learned position + Fourier coords + scatter-sum of the entity embeddings inside it.
- **Global token** (`:122-125`): from 70 scalars plus the last 3 own plays.
- **Trunk:** 4-layer, d=128 pre-norm transformer (`:80-93`). About 1.3 M parameters in the generalist (`HANDOFF.md:166`).
- **Cell head** (`:139-146`): full 36×64 = 2,304 half-tile cells. The logit is ⟨key(patch_out[cell's patch]) + key(cell_emb[cell]), query(g, card)⟩ + bias. The [B,2304,d] tensor is never materialised.
- **Other heads:** card over the 8 deck slots (hand-masked), state-conditioned gate (play/wait), "wait for card X" over deck slots, and a 7-way categorical value over crown difference.
- **Generalist variant** (`pipeline/model_gen.py:1-17`): card identity plus form embeddings, an order-invariant pooled hand/deck, a pointer card head over the 4 hand positions, and a "wait for card X" pointer.
- **No recurrence.** Memory is 3 past own plays, plus optional per-entity age.
- **Mirror augmentation** (`:164-173`).

### 4.2 Observation and hidden information

`BoardState` (`pipeline/obs_contract.py:112-150`) contains:
- units and spells with class, side (mine / enemy / unknown), x, y, hp_frac (engine exact; live None), deploying, age, conf
- 6 towers with hp_frac, known and alive flags
- clock and phase flags
- own elixir, plus an exact flag
- `opp_elixir` (engine **exact**, live None or estimate)
- own hand and next card as deck slots

Hidden-information handling is **weaker than our contract**:
- Engine-trained rows fed exact opponent elixir and exact unit HP to the actor.
- The live path later fed an elixir estimate. That suppressed the gate and was then turned off (`HANDOFF.md:2570-2572`, item J.1).
- They eventually built a public-events opponent-elixir counter, which recovered the measured 9-14 pp cost of hiding opponent elixir against ghosts (`HANDOFF.md:166`, "OPP-ELIXIR COUNTER").

This mirrors our "beliefs from observations" rule (strategy.md:45) and is empirical support for it. Their data showed **0 spell tokens in 1.43 M training rows**, while 19.5% of live frames carry one (`HANDOFF.md:2582`).

### 4.3 Versus Clasher

| | ClashAI S1 / generalist | Clasher `ClasherPolicy` (strategy.md:29-45) |
|---|---|---|
| Encoder | Entity + patch tokens, transformer 4×128 | Entity attention 4 layers × 128, 4 heads; separate privileged critic |
| Memory | None (3 past plays) | LSTM 256, 4 history slots, 8 seen-card slots |
| Action | Gate → card (8 slots / 4-hand pointer) → cell (2,304 half-tiles) | Categorical slot hierarchy: 4 slots × 576 tile centres + wait + ability |
| Wait semantics | Supervised gate + "wait for card X" | Wait action, reconsidered next observation |
| Value | 7-way crown-difference classifier | Privileged critic |
| Hidden info | Exact opponent elixir/HP in engine training rows | Strict public actor, masked, confidence/missingness |

**Resolution evidence.** Their crawl shows every placement coordinate is 500k or 500k−1 units, i.e. the **half-tile lattice**, with tile centres at odd k (`HANDOFF.md:4583-4584`). They measured +1.3 pp exact-cell from fixing a floor-vs-round convention at lattice boundaries (§5cs.70-71, `HANDOFF.md:4581-4588`).

For us (inference): even-sized buildings (Cannon and Tesla, both 2×2 and both in our 16-card pilot) are plausibly anchored on tile corners, not tile centres. **Recommendation R7:** during the M0 coordinate round-trip audit (strategy.md:49), measure what fraction of native-accepted and human placements lie on even-k (tile-edge) lattice points per card class. That decides whether the "constrained sub-tile residual" is needed, without any gameplay fitting.

**Label-noise trap to check in our data (R8):** in their datasets, wait rows on a side's own play tick carried the post-play hand with gate 0. That was **15.07%** of wait rows (`HANDOFF.md:166`, "ALSO FOUND"). Our scripted complete-game demonstration adapter should be tested for the equivalent off-by-one: a decision row recorded after an accepted play but labelled wait. This is a contract test, allowed before Tier A.

---

## 5. Data

### 5.1 ClashAI's data

- **Sources.**
  - RoyaleAPI web replays, scraped with a session cookie and Cloudflare clearance by an out-of-repo crawler (`scratchpad/gauntlet/L59/il_audit.md:23`). The 429 limit is per IP; ~6.4 replays/min after a backoff fix (`HANDOFF.md:4532-4536`).
  - The HF `VanguardX101/IL_Replay` dump (252,238 matches; `tools/hf_manifest.json`).
- **Reconstruction** (`research/sandbox_tools/replay_drive.py`):
  1. Feed the 20 Hz command timeline (engine units, 1000 per tile) into libg tick by tick.
  2. Infer the opening hand and queue from each side's play sequence (8C4 × 4! = 1,680 candidates, `:185-205`). Check whether dealing is position-based by resetting with two deck orders, then permute the deck to realise the inferred deal (`:14-19`; `s3_teacher.py:90-104`).
  3. Levels fixed at 11 (the crawl has none). Tower troops not modelled.
  4. Retry "not enough elixir" rejections for a few ticks (`:416-421`).
  5. Grade: accepted plays / total, final crowns vs record, and the determinism hash.
- **Fidelity (measured by them).**
  - 99.2% of pro plays accepted; crowns match 77.7% (211 replays), versus 26.1% for their earlier hand-written sim (`HANDOFF.md:2333`).
  - corpus_v3 icebow 76.9%; HF extras 78.4%.
  - Hog decks diverge more, likely from level sensitivity (`HANDOFF.md:2497`).
- **Sizes.**
  - S1 icebow 78,277 rows (21,687 play / 56,590 wait); hogeq 33,218.
  - Generalist `gen_dataset_v1`: 3,745,692 rows (928k play) from 14,661 replays across 4,283 decks (`HANDOFF.md:168`, agent).
  - Split by replay tag, crc32 % 100 < 15 (`pipeline/dataset.py:107`).
- **Scaling (measured by them).** About +1.5-1.7 pp exact cell per corpus doubling on the own-deck crawl. The HF foreign corpus did **not** extend the line for placement (+0.11 pp vs +0.7 predicted) but helped card choice (+1.96 pp; `HANDOFF.md:3957`). In the generalist, placement is flat across per-deck data volume while card choice rises (+6.7 pp; `HANDOFF.md:166`, T3).

### 5.2 Usability for Clasher

- **Their corpora are not in the repo** (`data/` is gitignored). Even if obtained, they would need permission; there is no license.
- **IL_Replay is already known to us.** Our audit found zero two-sided base/level-11 matches in 5,000, all placement forms unknown, and abilities unattributed (strategy.md:79; `m0/human-audit/README.md`).
  - ClashAI's engine *does* model evolutions and heroes; ours (15.535.86 plus a 16-base-card sim) does not.
  - Their evolved-Elite-Barbarians gap alone failed 36% of a slice (`HANDOFF.md:170`).
  - Re-driving IL_Replay under our runtime would admit only matches whose full card and form sets exist in 15.535.86, at unknown levels and tower troops, graded by acceptance and crowns.
- **What their method demonstrates, which we can reimplement independently (R6).** A deterministic native re-drive with deal-order inference plus an acceptance/crowns/hash fidelity grade turns action-only replays into graded native state sequences. For us this is at most:
  1. a held-out **human-observation evaluation** source (legal masks, public-state alignment, action distributions), and
  2. a behaviour-diversity diagnostic.

  It is not training data before Tier A, and not a source of human-expert labels for base-card forms.
- **Licensing and ToS status.** IL_Replay has no stated license, and RoyaleAPI's terms were not examined by ClashAI. Treat both as unresolved.
- **Comparison with our human audit.** Our KataCR/TV-Royale route gets public-state observations from video, which is our real deployment modality. ClashAI's route gets exact engine states for pro actions, but never public observations. The two are complementary. ClashAI's own conclusion was that anonymous video mining was "not worth continuing" for *their* scaling goal (`HANDOFF.md:4247-4262`); that does not apply to our held-out, public-observation audit purpose.

---

## 6. Vision

- **Detector.** Ultralytics YOLO11s @ imgsz 960, 230 classes (165 troop / 19 building / 46 spell), with no team in the class name (`hogeq/config/detect_classes.yaml:1-11`; `HANDOFF.md:2406-2410`). The pinned run is `board-24-5` (`icebow/config/config.yaml:1497`). Training uses Albumentations "status effect" augmentation (`hogeq/tools/detect/train.py:39-77`).
- **Training data.**
  - Own recorded frames, with auto-labelling of own freshly spawned troops (`icebow/src/clashrl/detect.py:1-19`).
  - A synthetic sprite bank: 40,412 own crops + 3,701 KataCR crops, and 5,000 synthetic images.
  - Later a 12,359-image Roboflow import (`HANDOFF.md:1476-1485`). The pinned model predates the Roboflow import. The later `board-26`, trained on ~50% Roboflow data, was rejected (`HANDOFF.md:1111-1133`).
- **Accuracy (measured by them).**
  - Frozen live gate on **241 images / 820 boxes**: presence recall 0.855, precision 0.886, whitelist identity recall 0.823 (`HANDOFF_ARCHIVE.md:2862-2875`).
  - 69/230 classes have zero validation instances (`GAUNTLET_LOG.md:245`). Box position error was not measured in that gate.
  - The own-click test gave placed-unit recall 0.81 strict / 0.97 any; hogeq 0.55 (`HANDOFF.md:2479`).
  - Team: unknown 0.25; wrong 0.15 for troops/buildings and 0.40 for own spells (`pipeline/obs_contract.py:497-499`).
- **Other readers.** Hand and next card by template matching (262/276 plays identified). Elixir by an HSV bar read, integer only, with no accuracy figure. Tower HP by a digit CNN (~92% per digit, then a consensus filter). Clock from wall time since match start.
- **Effect on play (measured by them, vs 100 held-out ghosts).**

  | Condition | Win rate |
  |---|---|
  | Live-like view | 52% |
  | Trained on `degrade()` rows | 74% |
  | Clean observations | 92% |

  Source: `HANDOFF.md:3316`. They also found `degrade()` over-predicted the live gate shift. Live gate p>0.5 was 24.8-32.5%, the engine gave 29.4-29.8%, and degrade gave 44.6-52.4% (`HANDOFF.md:182`, `HANDOFF.md:3930`, §5cs.97). A modelled error distribution can be wrong on the axes that matter.
- **`degrade()` error model** (`pipeline/obs_contract.py:509-558`):
  - keep units with p = recall
  - false positives at rate (1−precision)/precision, with same-kind random class and 1-tile jitter (the jitter is unmeasured)
  - position noise σ = 0.45 tiles
  - unknown and wrong team rates as above
  - confidence redrawn from a measured mixture
  - unit HP, deploying, age, king HP and opponent elixir set to None; elixir floored
  - foot correction for troop boxes, `TROOP_FOOT_K=0.25` (`:490-495`)
- **Weights and license.** Weights are not published, the Roboflow provenance is unknown, and Ultralytics is AGPL. **Not reusable as an artifact.**
- **Pivot we must not follow.** By 2026-09-24 their live path uses a read-only **memory reader of the live client** (MuMu, "training camp only"). An AI safety classifier denied parts of that work (`HANDOFF.md:164`). This is hidden-information-capable and ToS-hostile. It conflicts with our public-information actor principle and is out of scope.
- **Fit to our `PublicVisionFrame`** (`src/clasher/rl/live_inference_contract.py:195-217`). Their output maps onto `VisionEntity` (card, kind, player_id with an unknown option, x/y tiles, confidence, hp None) and our hand, next-card, elixir and clock fields with confidences. Their design ideas align with our missingness rules: unknown team as a third state, not guessed; HP None rather than a fabricated 1.0 (they note live had filled 1.0, `HANDOFF.md:3155`). Our contract additionally requires `play_events`, accepted own plays and levels with confidence, which their stack does not produce.
- **Recommendation (later, R5):** reuse the *measurement protocol*:
  - an own-click test to calibrate recall, precision, position σ and team error
  - a label-free team audit
  - live-vs-engine gate comparison as a check of the noise model

  Do this when we build our perception augmentation, before real deployment (strategy.md:177). Do not reuse their model or data.

---

## 7. Evaluation methodology and honest assessment

**Strengths:**
- Pre-registered gates, 3 seeds, paired designs, McNemar tests, replay-clustered bootstrap.
- Explicit retractions (e.g. `HANDOFF.md:3153`, `:4210-4214`).
- Rules such as "never compare two instruments" and "quote play rate beside agreement".
- A good trap catalogue. The deterministic-replay trap is notable: with deterministic ghosts and clean observations, k seeds replayed identical matches, so the effective n was 58, not 174 (`HANDOFF.md:166`, "CORRECTION").

**Weaknesses and caveats:**
1. **The primary offline metric is exact-cell agreement with pros**, conditional on a play. Their pro-pair ceiling was ~27.5% exact / 31.6% within one tile (`HANDOFF.md:2568`, §H). It is a proxy for imitation fidelity, not strength, yet they used it to gate the search teacher.
2. **Engine win rates are against non-reacting ghosts.**
   - Artifact: 29% of engine matches outlive the scripted opponent, and 27 of 29 are wins (`HANDOFF.md:3842`).
   - Clean-observation screens saturate at 0.86-0.97.
   - The FirstLight comparison notes ghost exploits (296 of 306 wins vs ≤3-card opponents, `HANDOFF.md:3127`).
3. **Live:** 35.1% over 37 matches (CI 21.8-51.2%), with no trophy-band control, against an engine 74% for the same checkpoint (`HANDOFF.md:3827-3852`). 81% of the owner's matches went to overtime.
4. **RL:**
   - Engine PPO from a CNN BC init: flat with a KL leash, collapsed without one (`HANDOFF.md:31-37`).
   - RoyaleSim PPO: nulls, then −11.5 pp at u89 (`HANDOFF.md:168,172,176`).
   - A 16 h / 22.5k-match self-play league: no measurable improvement on 299 train-split ghosts; the held-out screen gain was selection noise (`HANDOFF.md:166`, "league1 RESULT").
   - Their candidate explanations: thin win/loss signal, no critic baseline, a gate-only KL leash that never engaged.
   - **None of their RL runs used a recurrent actor, a privileged critic, reacting scripted opponents or potential-based shaping**, so their nulls are not direct evidence against our recipe (inference).
5. **README vs code drift.** S3 is described as Gumbel-top-k over student proposals, which is not implemented. The header block "Last updated 2026-09-23" is older than the §3 entries. The README says S3 "made play worse"; that refers to *distilling* the sim search, not the engine teacher.

**Net:** a careful hobby project with good measurement hygiene and genuine negative results. Its demonstrated strength is imitation of pros on one or two decks, plus a generalist that matches the specialist on agreement. Beyond-imitation learning is unproven. Live play is below 50% at small n. Its most transferable assets are the engine-throughput facts, the distillation failure mode and the trap catalogue.

---

## 8. Recommendations (ranked)

Strategy fit keys: **M0** = allowed now (contract tests, instrumentation, no gameplay fitting); **pre-freeze** = must land before the new immutable runtime / fresh Tier A bank is frozen; **post-A** = after Tier A admission; **pilot**; **later** = post-pilot / pre-deployment.

| Rank | Recommendation | Benefit | Cost | License feasibility | Fit | Admission-rule conflicts |
|---|---|---|---|---|---|---|
| R1 | **Native read-path rewrite (T1):** in-probe public level read inside the atomic observation, one persistent `session-v1` connection, drop redundant `observe`/`observe-rich` calls. | 5-30× native branch throughput (0.34-2.1 s → ~20-80 ms per decision, inference based on ClashAI and upstream round-trip measurements). Makes 512-branch Tier A plus Tier B feasible on the Mac mini in hours, not days. | Medium: C++ probe change and rebuild (restore NDK), new attestation pin, dual-read equivalence study, new same-engine floors. | Our own code; independently written. Confirm the FirstLight probe license. | **pre-freeze** (or defer until after Tier A) | None in substance. Never swap mid-attempt; keep the per-frame read (no level caching) unless separately approved. |
| R2 | **Snapshot branching (T2):** `snapshot-create` at root, `restore` per branch/candidate; validate restored ≡ replayed. | Removes prefix replay; turns native candidate evaluation into O(horizon). Prerequisite for any affordable native teacher-qualification or reference check. | Low-medium: already compiled and attested; needs a validation study and runner support. | Own code. | Development validation in **M0**; production use **pre-freeze** via the protocol; heavy use **post-A** (teacher substage) | Must be declared in the prospective protocol. Opened development roots only for the validation. |
| R3 | **Resident multi-slot / multi-port per AVD (T3)** plus `render off` (T4), as an alternative to or complement of the planned two read-only AVDs. | ~2-3× per emulator (ClashAI 2.68× at 4 slots); frees CPU. | Medium: cross-slot isolation tests (reset A ⇒ B unchanged; interleaved = solo traces). | Own code. | **pre-freeze** or **post-A** | None if isolation is proven and recorded. |
| R4 | **Oracle-qualification hardening from ClashAI's distillation failure:** keep soft `kl_regularized_candidate_target`; add force-play, random-from-candidates and wait-only controls to the 64-game screen; add marginal-drift diagnostics (play rate by elixir/phase, card shares, gate curves) for the distilled student; per-candidate score dumps; common random futures across candidates; pessimistic/random tie handling. | Avoids the "teacher's restraint without its judgement" failure; cheap discrimination of real search gains. | Low: extra screen arms and logging. | Ideas only. | **post-A** (teacher-search admission substage); design notes can go into the M0 protocol text | None; strengthens rules. |
| R5 | **Perception-noise measurement protocol:** own-click calibration (recall, precision, position σ, team error, confidence distribution), label-free team audit, and live-vs-reference gate comparison to validate any augmentation model. | Avoids ClashAI's 39-point engine→live gap and its mis-specified `degrade()`. | Medium, when a live adapter exists. | Ideas only; no weights or data. | **later** (pre-deployment, per strategy.md:177) | Must keep missingness/confidence; no fabricated HP/levels. |
| R6 | **Native re-drive of action-only human replays** (deal-order inference + acceptance/crowns/hash grading) to build a *held-out human-observation evaluation* set. | Gives graded native state sequences for human actions; helps judge mask/legality and behaviour coverage. | High, and limited by 15.535.86 card/form coverage, unknown levels/tower troops, and IL_Replay/RoyaleAPI licensing. | Method reimplementable; **data license unresolved**. | **later**, low priority | Not training data before Tier A; not relabelling modern forms as base cards (strategy.md:79). |
| R7 | **Half-tile placement audit:** fraction of native-accepted and human placements on tile-edge lattice points per card class (esp. Cannon/Tesla 2×2), and round-trip error through our 576-tile projection. | Evidence-based decision on the sub-tile residual. | Low. | Idea only. | **M0** (coordinate audit, strategy.md:49) | None; no fitting. |
| R8 | **Wait-label off-by-one test** in the scripted demonstration adapter and any human adapter (post-play hand labelled wait). | Prevents a 15%-scale gate label-noise bias like ClashAI's. | Low. | Idea only. | **M0** (data/contract tests) | None. |
| R9 | **Tap-to-execution latency and extrapolation** as a measured deployment condition: ClashAI measured 24-27 ticks (1.20-1.35 s) tap→land on their client, costing 2-16 pp against ghosts; extrapolation recovered some of it (`HANDOFF.md:166`, "ACTION DELAY"/"EXTRAPOLATION"). | Prior for our control-latency modelling. | Low to note; medium to implement. | Idea only. | **later** (pre-deployment) | Latency must be measured on our own path; their number is only a prior. |
| R10 | **RoyaleSim (MIT Rust engine) as an optional cross-check backend.** | Independent, fast, deterministic integer engine. | Medium-high; ClashAI hit harness breakers (units ×18, deal order, overtime 60→120; `HANDOFF.md:178`), and it lacks Tornado/evos at points. | MIT. | **later / optional** | Not admitted; no substitution for Null's reference; any use needs its own parity checks. |

**Explicitly not recommended:**
- Copying any ClashAI code, weights or data (no license).
- Using non-reacting recorded "ghost" opponents as strength evidence. They are acceptable at most as a diagnostic stress slice; our fixed reacting pool remains the evaluation.
- Pro-agreement as a teacher gate.
- Hand-written tower-damage one-shot rollouts as a teacher objective.
- Feeding exact opponent elixir or unit HP to the actor. This conflicts with the public-information actor rule.
- Live-client memory readers. They conflict with the public-information principle and ToS.
- Their detector artifacts (AGPL, unknown data provenance, unpublished).

---

## 9. Single biggest idea for native-branch throughput

**Fix the per-decision read path, then branch from snapshots. Both are already within reach of our existing probe.**

ClashAI shows a native Clash Royale engine can re-drive a complete recorded match in ~2.5 s and run a policy-in-the-loop decision in ~26-35 ms, even though its engine has *no* snapshot support. Our engine already steps headlessly faster than real time. Our 2.11 s per decision (0.34 s or more on host GPU) is therefore almost entirely instrument overhead:
- an out-of-process ADB `dd` level read on every decision
- about 8-10 fresh TCP connections per decision
- redundant observes

Moving the public level read into the probe's atomic observation and using a single persistent session should give a 5-30× speed-up (inference). Our probe also already attests `snapshot_restore: true` on 15.535.86 (`snapshot-create` / `restore H` with digest verification). Using it removes prefix replay per branch and makes native candidate evaluation affordable. Both are instrument changes: validate them on development roots and freeze them into the prospective protocol before any fresh capture.
