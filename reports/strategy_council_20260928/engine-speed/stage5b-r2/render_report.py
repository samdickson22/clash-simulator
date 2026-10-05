"""Render final evidence without altering the frozen analysis."""
import json
from pathlib import Path
HERE=Path(__file__).resolve().parent
r=json.loads((HERE/'result.json').read_text());assert r['complete']
h=r['head_to_head'];c=r['scripts'];t=r['timing'];b=r['baseline_timing']
text=f'''# Stage 5b: {'PASS' if r['pass'] else 'NO-GO'}

The deadline player completed all 384 preregistered terminal games. Strength gate {'PASS' if h['pass_strength'] else 'FAIL'}; strict 250 ms wall gate {'PASS' if t['overruns']==0 else 'FAIL'}.

## Implementation

The Stage 5 public model, scripts, engine, prior and candidate set are unchanged. The live adapter in stage5b-r2/deadline_player.py uses a configurable 200 ms wall deadline and two Rust candidate workers. The driver starts the clock before public sensor conversion. Work follows the existing candidate priority: script top choice, no-op, script ranks, ability/policy proposals, then samples. Each candidate requires all three opponent-style rollouts; incomplete scores are discarded. Workers check the deadline between ticks and continuation decisions and join before return. If no candidate finishes, the first public-legal script candidate is returned. The Stage 5 sequential path remains available with deadline_seconds=None and threads=1.

Results reduce in original priority order with the original 1e-9 tie tolerance. For a fixed completed candidate set, results do not depend on thread completion order. Scheduling can change which candidates finish before the deadline. This cooperative cutoff is not an operating-system realtime guarantee under arbitrary preemption.

## Tests

All 200 Stage 5 roots reproduce the exact recorded action, ordered candidate scores, continuation digests and full MT state trace hashes with 1, 2 and 4 workers. The six focused tests pass, including the Stage 5 stunned-push regression, expired-budget legal fallback, mid-rollout cancellation, partial-result exclusion, priority ties and thread invariance. The parity receipt is stage5b/parity.json. The Python engine, public scripts and gamedata entry hashes pass preservation checks.

## Preregistered results

PREREG-C56-deadline-r2.md, schedule.json, seed-audit.json and evaluation-manifest.json precede every evaluation game. Primary head-to-head: {h['wins']} wins, {h['draws']} draws, {h['games']} games; score {h['score']:.6f}, paired-matchup 95% CI [{h['ci'][0]:.6f}, {h['ci'][1]:.6f}]. Required score >=0.47 and lower bound >0.42. Continuity against C56 scripts: {c['wins']} wins, {c['draws']} draws, {c['games']} games; score {c['score']:.6f}, CI [{c['ci'][0]:.6f}, {c['ci'][1]:.6f}]. Confidence intervals use 10,000 percentile bootstrap resamples of paired means, RNG 40404043. Human decks follow the same role-held-out eval/eval_ood planning and train opponent catalogs as Stage 5, restricted to deck identities supported by its train-only prior; this is not deck-identity holdout. No interim strength analysis, exclusions or player retuning. The first attempt stopped with 59 terminal receipts when the unchanged Stage 5 baseline rejected an unsupported held-out opponent deck on pair 27. Its receipts and source pins remain in stage5b/. The replacement registration used entirely fresh seeds and restricted deck identities before any replacement game; the first attempt is not acceptance evidence.

## Timing and host load

All 384 games: {t['decisions']} candidate decisions, p99 {t['p99']*1000:.3f} ms, searched p99 {t['search_p99']*1000:.3f} ms, max {t['max']*1000:.3f} ms; {t['overruns']} decisions above 250 ms. Deadline-truncated decisions: {r['truncations']}; no-complete-candidate fallbacks: {r['fallbacks']}. Baseline timing is separate: p99 {b['p99']*1000:.3f} ms, max {b['max']*1000:.3f} ms, overruns {b['overruns']}.

Three nice-10 evaluation processes ran concurrently, with up to two native search workers per process. Host launch snapshots in stage5b-r2/host-worker*.txt and per-game load/nice records document other work. C56 extraction and live-loop training were active during preparation; no unrelated job was stopped or modified. All-decision timing includes sensor conversion, public history, candidates, root reconstruction and native search; only pregame initialization/warmup is excluded.

Public-state verifier checks: {r['derived_checks']}. Rejected candidate/opponent commands: {r['rejected']}. All results are retained. The public combat model remains approximate, so public-legal candidates can occasionally fail engine application, as in Stage 5.

Manifest SHA256: {r['manifest']}. Receipt aggregate SHA256: {r['receipts_sha256']}. Every worker exits zero; the analyzer requires all 192 paired matchups and unchanged source pins.

## Files and scope

Changed runtime sources: src/clasher/rl/c56_rollout_planner.py and engine-rs/src/scripts.rs. Added engine-rs/test_stage5b_deadline.py. Added engine-speed/PREREG-C56-deadline.md, STAGE5B.md and stage5b-r2/ adapter, build/run drivers, registration, audit, parity, evaluation, analysis and receipts. Updated engine-speed/PROGRESS.md. Stage 5 evidence and its private extension remain unchanged. No forbidden Git operation or protected data/runtime directory was changed. Owned cargo intermediates are cleaned only while idle; outputs remain below 500 MB.
'''
(HERE.parent/'STAGE5B.md').write_text(text)
print(text)
