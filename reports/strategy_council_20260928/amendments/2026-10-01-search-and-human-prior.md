# Strategy amendment, 2026-10-01 (user decision; strategy.md itself is unchanged, SHA 2be09f05...)

strategy.md is pinned by digest in every pilot config and in the Tier A admission, so it is not
edited. This file records a user decision that changes priorities relative to it.

Basis: `reports/external_review_20260928/ml-research-20261001.md` (no model-free success in this
game class below ~3e8 decisions; every small-budget success used a search teacher or human data).
The user's instruction (2026-10-01 ~20:07Z): "go ahead and do what you recommended".

Decisions:
1. Oracle planner qualification as a PLAYER starts now (strategy step 2 of "Before distilling the
   oracle": paired-seat screen, then confirmation). No labels are generated and nothing is distilled
   until the strategy's other two conditions hold (prospective admission of the search/candidate
   scope; fresh reference checks on oracle-selected candidates). Output: `oracle-qualification/`.
2. A human-imitation warm start is built from IL_Replay by re-simulation. This is gameplay fitting
   outside the Tier A admitted scope (opponent units outside the 16 pilot cards appear in the
   observations) and uses re-simulated base-form states cut at the first contradiction, which the
   strategy had deferred ("IL_Replay remains action-only until reconstruction is defensible"). The
   user accepted this on 2026-09-30/10-01 ("for a pre-train ... it doesn't matter if the version is
   exactly the same") and again here. First step is the 16-card (P16) human prior; the wide-scope
   pre-train follows if P16 helps. Such checkpoints are research artifacts: they are not Tier A
   admitted pilot arms and carry that label in their metadata. Output: `human-prior-p16/`.
3. The seed-2903 continuation (pilot/v7r2c-launch) is launched as approved.
4. The 3-seed v7r3 pilot (pilot/v7r3-launch) is NOT launched for now; the kit is kept ready. Its CPU
   goes to items 1 and 2.

## Update 2026-10-02 ~24:00Z (user decision)
Human-imitation P16 result (human-prior-p16/README.md): BC 'natural' beat the scripted warm start
40/192 vs 23/192 on fresh seeds. The user chose "PPO from human model": 3 seeds of PPO initialized
from human-prior-p16/checkpoints/human-bc-natural-seed2903.pt (sha 49be1480...), KL anchor 0.05 to
that checkpoint, 60-update critic-only warm-up, otherwise the v7r2 recipe, level 11, nominal then
nominal-league to 5M. Kit pilot/v7r4h-launch (runtime pilot-runtime-v5), being built. It replaces
the held v7r3 run. These runs start from a research artifact and are not Tier A admitted pilot arms.

## Update 2026-10-03 ~04:30Z (user decisions: goal shift to the real game)
Question "is human-level play possible with this setup?" Coordinator answer: not with the 16-card,
level-11, Mac-PPO setup (scope, experience budget, narrow data, no real-client loop). User decisions:
1. Goal: move toward the real game, C56 first (scope-expansion/PLAN.md: engine scope 122 cards,
   actor scope 56 cards, human imitation as the base), then widen to ~120.
2. Compute: Mac mini only. No rented compute.
3. Engine speed: profile first (Python engine vs the existing torch_sim batched simulator), then
   pick the cheaper path to a 30-100x faster simulator.
Coordinator defaults for the plan's open questions (routine; reversible): C56 list as written incl.
the three champions (ability action in contract v5); fresh v5 weights for the primary human arm;
base-form substitution with evo/hero plays at 0.5 weight, L16 observed as nominal L11, tower-troop
matches excluded in v1; Tier A option A (one 32-family attempt per mechanic bundle B1-B4); the frozen
human-prior policy may join the opponent pool and be reported separately; offline BC may run before
the broadened Tier A, but no PPO/league/evaluation claim on C56 cards before their bundle is admitted.
Stage 0 (P16 human prior then PPO) is effectively pilot/v7r4h-launch.

## Update 2026-10-03 ~21:20Z (coordinator decisions; Sam: "You own this project - do not stop to ask me questions")
Evidence: v7r2c s2903 continuation collapsed in the nominal-league phase (fresh-seed paired eval 1M 38/96 holdout
+ 5/96 hog26 -> 2M 20/96 + 0/96, p<0.001; pilot/v7r2c-launch/RESULT-2M-s2903.md). v7r4h (PPO from the human
prior, KL anchor 0.05) at 1M on its own diagnostic seeds: 76/192 (s2901) and 86/192 (s2902) vs the human start
31/192 on the same games (paired p<0.001 both); hog26 25/96 and 34/96.
Decisions:
1. v7r4h: seeds 2901/2902 continue in the league phase only to 2M (direct test: does the anchor prevent the
   league collapse?), then stop (pilot/stop_v7r4h_at_2m.sh); seed 2903 runs --through nominal (1M only).
   Fresh-seed paired evals (human-prior-p16/scripts/run_eval.py; engine/eval code identical in runtimes v4/v5)
   of each 1M and 2M checkpoint. No league beyond 2M until the 2M result is in.
2. Learner fix approved: stored recurrent state + truncated BPTT with burn-in behind a flag (default byte-
   identical), for PPO and BC (learner-tbptt/). New runs only; in-flight runs unchanged.
3. Engine speed: Stage 0 (five Python fixes, opt-in Cython, cheaper script path in srp) then the Stage 1 Rust
   spike with the README's gates (engine-speed/STAGE0.md, STAGE1.md). Python engine stays the identity
   reference. torch_sim frozen (not maintained). New C56 mechanics land in Python first.
4. C56 extraction continues on the 05:23Z engine copy; champion perspectives re-extracted afterwards on a fresh
   copy; BC after that, with TBPTT.
5. Fidelity: the first contradiction in ~47% of perspectives is a simulated tower kill that did not happen in
   the real match; investigation in tower-gap/.
Model routing per ~/.claude/frontier-models.md: implementation on GPT-6-Astra (high), research/decisions on Opus.

## Update 2026-10-03 ~22:30Z (coordinator): tower-clamp cut rule for human replays
tower-gap/README.md: the dominant first contradiction (sim kills a tower standing in the real match) is replay
drift (human defences were played against the real board), concentrated in overtime matches; levels, evo forms,
spells and tower troops explain almost none of it. Decision: replayer rule "clamp the tower at 1 HP, cut only when
accumulated overshoot > 1.0 x tower max HP", rows after the first clamp weighted 0.5, per-row tower_clamped /
overshoot_frac. Projected retention ~74.5% -> ~84%. Applied in C56 extraction v3 together with a refreshed frozen
engine (champion repairs + identity-preserving Stage 0 speed patches); unaffected v2 perspectives reused after a
2% byte-identity re-extraction check. Native checks of Hunter (defending) and Cannon Cart (attacking) queued
for the next emulator window.

## Update 2026-10-03 ~23:00Z (coordinator)
Engine Stage 0 landed (identity 0 mismatches P16+C56, independently re-verified; srp 1.75x; opt-in Cython 1.4x). Rust Stage 1 slice diverges (first divergence ticks 261-669) but raw speed ~73x and clone ~900x: continue to slice parity (Stage 1b) before any Stage 2 commitment. Search-teacher distillation starts now on P16 (srp-dagger/): student = v7r4h 1M, DAgger beta 0.5, KL anchor to the initial student, fresh-seed paired eval vs the student.

## Update 2026-10-04 ~00:00Z (coordinator)
Rust Stage 1b passed all gates (byte-identical 4-card slice; independently re-verified on 8 unseen cases up to 3,278 ticks; 61-78x; clone ~1.4 us). Stage 2 (all 16 pilot cards, full matches, arbitrary placement, mid-game snapshot import) approved; then Stage 3 (native scripts + observations) so srp search runs natively.

## Update 2026-10-04 (coordinator)
Learner fix landed (stored-state TBPTT, T32/B16 3.04x end to end; default byte-identical; equivalence 2e-6). Adopted for new PPO runs and for C56 BC. Learning-quality check: v7r5 = v7r4h recipe + TBPTT, seeds 2901/2902 to 1M, compared on fresh seeds with v7r4h 1M (runtime v6 = v5 + learner files only, so the admitted engine modules are unchanged). C56 extraction v3 running (clamp rule; QA retention 76.3% -> 85.5%).

## Update 2026-10-04 (coordinator)
Rust Stage 2 passed (all 16 pilot cards byte-identical on 64 full games, 2,048 live imports, 8,177 placements; independently re-verified on 16 unseen full matches; ~50x; clone ~1.35 us). Stage 3 approved: native mask, scripted opponents and srp rollouts with decision-identical planner calls, opt-in backend.

## Update 2026-10-04 ~03:40Z (coordinator)
v7r4h 2M: s2901 60->79/192 (p=0.04), s2902 88->59 (p<0.001). Anchored league avoids collapse but is not a dependable improver: no further league training in this form; checkpoint selection by fresh-seed paired evaluation; s2902 1M remains the best policy and the DAgger student. v7r5 (TBPTT) launched at ~44 decisions/s per seed vs ~20 for v7r4h. Rust Stage 3 done: native srp 75.7x, decision-identical on 200 planner calls (end-to-end game check by coordinator in progress).

## Update 2026-10-04 ~04:30Z (coordinator): gamedata drift found
Native and Python srp agree exactly (3 full games, identical outcome/crowns/ticks/calls; ~20-25x whole-game), but
neither reproduced the recorded confirmation games. Bisect: recorded games reproduce exactly under pilot-runtime-v4;
workspace engine files and rl modules overlaid on v4 do not change the game; the workspace gamedata.json does.
The admitted gamedata (v4/v5/native-final-v7) = base 3d99987c + IceSpirits HP 84 (diagnostic override = downloaded
runtime value) and Goblin_Stab damage 49; the workspace has 90 and 47. The P16 identity check missed it (12 scripted
episodes, workspace gamedata in its baseline). Decision: admitted values are canonical for P16; workspace gamedata
patched to them; identity baseline re-recorded from the admitted runtime and broadened (recorded srp game replays +
random-placement episodes); Rust re-verified on canonical data; DAgger labels regenerated on canonical data (native
srp). PPO runs, evaluations and the srp confirmation used the admitted runtimes and are unaffected. The running C56
extraction v3 keeps base gamedata (known difference; tolerable for a human prior; fix on any future re-extraction).
Scripts: engine-speed/coord_replay_recorded_srp.py, coord_e2e_srp_backends.py.

Update 2026-10-04 ~06:20Z: workspace gamedata canonicalized to the admitted values (sha 892fbfa0); broadened identity check passes in all modes; the coordinator reproduced 2 recorded srp confirmation games exactly on the workspace (python and native backends).

## Update 2026-10-04 (coordinator): srp DAgger pilot regressed
Iteration 1 (hard srp labels, CE + 0.1 KL, 40 games, canonical data, native srp at 0.028 core-s/call): student 88 -> 16/192 (p~1e-14). Top-1 agreement unchanged (42.8%), play agreement 0%, CE 5.99 -> 3.51: hard tile labels from a planner whose candidates are mostly random samples flatten the location head. Iteration 2: diagnostics first (label provenance, action-index/tick alignment), then score-softmax targets over the evaluated candidates incl. the student action, loss renormalized over candidates, improvement-margin filter, KL to initial 1.0, LR 5e-6, quick 48-game gate before a full eval.

## Update 2026-10-04 (coordinator): from distillation to run-time search
DAgger it2 (soft candidate targets): 87 vs 88/192 (p=1.0), safe but no gain (filter kept 1.9%). Diagnosis of it1: random-sample candidates supplied 68% of teacher plays; the student learned premature spending (wait-when-playable 94% -> 64%, elixir at play 5.6 -> 2.5); no pipeline bug. srp's strength comes from privileged lookahead at every decision, which a reactive policy cannot copy. With native srp at ~0.028 core-s/call, search fits a live 0.25 s decision budget, so the direction shifts to search AS the player: public-information srp (determinized opponent hidden state, K samples; variant with policy top-N candidates), pre-registered 256-game test + head-to-head vs the best policy (srp-public/). DAgger it3 shelved.

Update 2026-10-04: information rule (Sam): private state the opponent can calculate (exact elixir, hand/cycle once revealed) is fair. Public srp computes it exactly; only unrevealed card identities and RNG are sampled. Policy observations should gain the same derived features.

## Update 2026-10-04 ~10:45Z (coordinator)
- srp-public PASSED its amended pre-registration (fair information: exact derived elixir/hand/cycle; only unrevealed
  cards + RNG sampled; denied-read and invariance tests pass; 0/23,058 elixir errors): srp-pub 0.809, srp-pub-pol
  0.797 vs scripts (holdout 256); head-to-head vs the best policy (s2902 1M) 0.586 / 0.633 [0.547,0.719]; K=1 within
  the 0.25 s live budget (max 0.11 s). Caveat: the unrevealed-card prior is the pilot deck pool; for the real game
  it must come from the human-corpus deck distribution. Hog26 weak (0.41/0.52).
- v7r5 (TBPTT T32/B16) 1M: 47 and 43/192 vs v7r4h 60 and 88 (s2902 p<0.001): stored-state TBPTT as configured hurts
  PPO learning. PPO stays full-prefix; TBPTT BC only after a side-by-side check against full-prefix BC.
- C56 extraction v3 crashed 2026-10-03 21:09 PDT after 270 units (champion bug c56_champions.py:187; one perspective
  killed the pool): repair + champion sweep + per-perspective error isolation + resume on runtime v3b.
- New main line: expert iteration (exit/) — srp-pub-pol acts with the current policy's top-8 proposals, the policy
  learns score-softmax targets over the candidates (weighted by score spread, KL 1.0 to the previous policy), accepted
  per iteration on policy-alone and search-player head-to-head gates.

## Update 2026-10-04 (coordinator): ExIt confirmation failed
Pre-registered 256-game head-to-head: student-proposer search 0.4805 [0.426, 0.531] vs initial proposer (FAIL); vs scripts 104 vs 102/128, hog26 31 vs 30/64. Proposer quality barely matters at this level; the search itself carries the strength. Keep the s2902 1M proposer; stop ExIt in this form. Next: (1) search tuning within the live budget (horizon, K, candidates, rollout opponent models, leaf) by sequential halving + pre-registered confirmation (search-tuning/); (2) Rust Stage 4 (C56 cards + C56 scripts native) — critical path for real-game search.

## Update 2026-10-04 (coordinator): search tuning PASS -> srp-pub-mix is the player
Sequential-halving over 14 profiles within the 0.25 s one-core budget; winner = rollout opponent model as an equal balanced/pressure/defense script mixture (K=1, horizon 160, interval 10, policy top-8 + script top-4 + no-op, balanced own continuation, defense-v2+elixir, terminal +-2). Pre-registered confirmation vs the previous config: 161/256 = 0.629 [0.578, 0.680] PASS; hog26 h2h 0.72; vs scripts holdout 117 vs 102/128, hog26 53 vs 44/64; max wall 147 ms, 0 overruns. Audit: PREREG and launch 10:18, first confirmation game 11:13; reporting amendment (rejected-placement counting only) predates ranking. srp-pub-mix (search-tuning/) is the current best player.

## Update 2026-10-04 (coordinator): live loop
Survey (live-loop/SURVEY.md): no live loop exists; vision stack runs only on recorded spectator video; the native reference is an offline, re-signed private-server (Nulls Royale) client with an injected probe — flagged to the owner as a ToS/IP risk (kept as-is, offline). Plan: L1 perception trained/evaluated on offline rendered frames with exact ground truth; L2 closed loop from pixels on the offline renderer; L3 official client (Training Camp / consenting friendlies, never ladder) only with the owner's explicit go-ahead. L1 started (Astra live-loop-l1-astra-20261004-1).

## Update 2026-10-04 (coordinator): ClashAI evidence
Sam shared that ClashAI (vegetableleaf) reached ~11,074 trophies (PB 11,221) playing on its own. Their recipe (external_review clashai.md): behaviour cloning on the same IL_Replay corpus (252k matches) with a ~1.3M-param entity/patch transformer, half-tile placement head, play/wait gate, all cards incl. forms, observations from the real engine (libg replay loader), and a real-client loop (YOLO vision, later a memory reader) on ladder. Lesson: full-card-scope BC + a working live loop reaches high ladder level; our bottlenecks for the real game are card scope (simulator-limited data) and the live loop, not search/RL sophistication. Action: feasibility of full-corpus replay through our offline native reference (native-corpus/), ideas only — no ClashAI code/data (no license). Ladder play remains off without the owner's explicit go-ahead (ToS).

## Update 2026-10-04 (coordinator): native-corpus no-go; S122 via the Python sim
native-corpus/FEASIBILITY.md: 50/50 matches load but only 28 inject every command; native replay agreement with the real outcome winner 82%, crowns 78%, all tower HP 4% (replay drift exists even in the real engine); 15-64 s per match observed -> 9-39 days for 252k on 8 emulators (RAM-infeasible). Decision: no-go on emulator corpus. Route to a full-card generalist = Python-sim extraction at S122 actor scope (contract v5 already has the 360-token S122 vocabulary; evo/hero as base form at 0.5 weight), launched after the C56 run, disk-budgeted to <=6 GiB via wait subsampling and per-archetype caps; then a generalist BC with ClashAI-inspired heads (half-tile lattice, play/wait gate, wait-for-card), reimplemented from scratch.

## Update 2026-10-04 (owner decision): live play authorized
Sam: "Fully connected, will make a new account for this experiment, so if it gets banned, it's no big deal and run it only inside the emulator on the Mac mini." Coordinator rules: official client only in a dedicated clean AVD on the Mac mini, new throwaway account; offline private-server reference AVD stays separate and never networked; staged Training Camp -> ladder; screen-only fair-information player (no live-client memory reading); no ban/detection-evasion features.
