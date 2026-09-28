> ARCHITECTURE CHECKPOINT 2026-09-13: Full simulator-centered pipeline design and implementation handoff now live at /Users/sam/.codex/worktrees/clasher-simulator-fidelity-20260913/PIPELINE_DESIGN.md and HANDOFF.md. User authorized simulator improvement, then asked to finish planning before implementation. Persistent goal and old training remain off. Continue simulator work in the isolated worktree.

> USER PAUSE 2026-09-13: Training and automatic continuation are paused pending comparison with external Clash Royale bots. Do not launch the queued late-continuation probe, further fitting, collection, search, or policy updates. The three-class campaign completed; its artifacts are preserved. A fresh pipeline requires the next user decision.

# Active model goal — September 13

The persistent training goal remains active. No model is accepted. Preserve the public calibration and counterfactual-ranking gates; no search, PPO, policy updates or promotion.

Current work is the supervised three-phase WDL campaign:

- Command: experiments/hog26_three_class_phase/supervise.py --mode run
- Unified exec session:64635; supervisor55200. Verify live state before acting.
- Live state: /Users/sam/Library/Application Support/ClasherMonitor/comparison-status.json
- Logs: reports/hog26_three_class_phase_fit-seed1279501-fold0_20260913.log and corresponding seed/fold logs.
- Pin SHA256:c15412931b138e64f629d4c46e97046bb0d80331f6ffd6dff4ad2f6a78725106
- All ten Python files in experiments/hog26_three_class_phase are frozen.
- Output: reports/hog26_three_class_phase_20260913
- The supervisor fits eight bundles (24 classifiers) sequentially, runs two exact seed reviews concurrently, then scientific comparison. Do not duplicate or pause it.

The fit uses the fixed6,144natural games plus all512marked control views, totaling2,667,560rows. It preserves the original814public features, hard public-clock phases, WDL equal-game/reached-phase weights restricted per phase, and existing hard-margin models. Both views of each physical control share a cluster. Controls remain training-only and are never natural frequency or calibration evidence.

Early/middle heads have actual L/D/W examples; every late head has only L/W. Record that absence explicitly. The actual combined fitting prior has draw mass62/5120=0.012109375; the separate natural prior remains zero. No invented prior mass or outcome balancing is used. The numerical screen can use the unchanged native evaluator for this actual supported combined prior, but it still cannot establish full acceptance.

The largest-phase synthetic memory proof passed at11,082,137,600bytes with the required2GiBheadroom. It used1,272,408×814float64 features, three synthetic classes and two iterations, without real fitting labels or a saved checkpoint. Actual maximum phase fitting counts are1,272,408/803,360/23,940. Public-routing and cross-store materialization tests passed.

The control collection and feature audit are complete.256physical games yielded31draws;512views contain225losses/225wins/62draws and202,408rows. Every feature row reproduced streaming/batch bytes, and rawWDL-to-modelLDW conversion was verified. All control draws ended before the late phase. No earlier collector, feature audit or paused parent remains active.

After the campaign finishes, inspect all exact reviews, native numerical cases, paired natural probability comparisons and control fitting diagnostics. Preserve every unsupported/regressed slice. Control fitting results are not controlled validation. No reserved selection/calibration/final labels have been opened. The preserved ranking rule allows a bounded ranking plan only after all public-state gates pass.

Queued after current fitting/exact/scientific completion: the excluded late-continuation probe in experiments/hog26_late_continuation_feasibility. All five files are frozen, pinSHA f8f245b2e2461eb4eb55157ce9e9514b30d9136d4d0c59c56d491bbe079a6baf. Use lateContinuationEnv with supervise.py --mode run only after the lease is released. Eight fresh mirrored orders each get a real pass prefix to4000or4800ticks, then unchanged frozen-policy continuation. All outcomes and both views retained; extra zero-prefix baseline parity and exact replay required. All probe data remain excluded. This is not ranking or natural calibration; pre-release labels have a modified future policy and cannot become ordinary fitting targets.

The first three-class bundle has complete fitting reports, but exact reviews and other folds remain pending. Do not promote preliminary numbers. Read reports/hog26_scalar_validation_readiness_notes_20260913.md before planning independent validation: the historical protocol is stale as collection authority, and a new scalar source/data protocol is required while preserving its roles and public/ranking gates.

Completed findings:

- Natural training corpus: 6,144 games, 2,465,152 rows, 4,684 losses, 1,460 wins, zero draws.
- More data and hard-phase margins reduced late representative MAE from 0.0274 to 0.0159. Smooth overlap reduced boundary jumps but worsened middle and late representative accuracy.
- All earlier model fits, exact reviews, diagnostics, boundary audits and online feature audits are complete.
- Native numerical gate evaluation refused the zero-draw prior. Preserve that failed screen. The separately tested diagnostic adapter allows zero only for unobserved outcomes and never grants native acceptance.
- The 48-case supported-metrics screen and 32-case existing-WDL screen are complete. Hard margins pass covered numerical margin checks on declared balanced/reactive-defense styles; broad styles retain early bridge-pressure errors. Existing globals/tree WDL have different calibration weaknesses.
- The eight late-only classifier fits and exact reviews are complete. No covered late classification check failed. Both seeds produced identical predictions, not independent replication. Coverage and draw support remain unresolved. See reports/hog26_late_classifier_conclusion_20260913.json.
- The first fixed-order mirror probe gave no draws. A fixed 16-order excluded probe then produced 2 draws, 8 wins and 6 losses; both draws destroyed both kings before the time limit. These 16 games remain excluded from fitting/calibration.
- Paired-view capture passed exact physical-trace and original-seat array parity on one loss and both draw games. Both actual views passed label/action and online-feature checks. All four files in experiments/hog26_scalar_paired_views are frozen.

Read the latest entries in HANDOFF_MODEL_TRAINING_20260913.md and reports/hog26_protocol_reassessment_20260908.md for complete provenance. No older paused process remains. Do not relaunch completed campaigns.

Preserve the dirty tree, failed artifacts, reserved development/calibration/final roles, and all frozen Python directories. Do not edit src/clasher or scripts. Do not commit, reset, clean, stash, merge, push or disturb unrelated work. No subagents are authorized. Python/Ruff/pytest is /Users/sam/Desktop/code/clasher/.venv/bin. Current prefixes:threeClassEnv, mirrorTrainingEnv, mirrorFeaturesEnv, lateClassifierEnv. threeClassEnv prepends the three-class and supported-metrics directories to mirrorFeaturesEnv. The active model code imports both control feature and natural cache authorities.

Latest user steering: compare the Instagram Day50 bot. The comparison was answered in commentary while training continued. See reports/hog26_external_clashai_comparison_20260913.md. Read-only code/data audit found a public252k-replay corpus, but a fixed5k sample has210Hog26base-roster sides and zero exact vanilla matches. No externaldata haveentered fitting; no third-partycode wasexecuted or game runtime acquired. The primary strategic recommendation is to investigate reliable engine/expert-action inputs and real-screen fidelity alongside the critic, not claim superior gameplay from internal metrics. No original training/data gate was changed.
