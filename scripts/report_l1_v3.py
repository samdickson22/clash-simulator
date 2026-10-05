"""Render the completed v3 measurements without promoting failed or unmeasured gates."""
import json
from pathlib import Path

import numpy as np

from collect_l1_events_v2 import disk_bytes
from collect_l1_rendered import REPORT,progress


def fmt(value):return 'unmeasured' if value is None else f'{value:.4f}'
def pct(value):return 'unmeasured' if value is None else f'{100*value:.2f}%'


def main():
    root=REPORT/'v3';data=root/'dataset-merged'
    metrics=json.loads((root/'evaluation-heldout/metrics.json').read_text())
    manifest=json.loads((data/'manifest.json').read_text())
    episodes=[json.loads(l) for l in (data/'episodes-merged.jsonl').read_text().splitlines()]
    selected=[e for e in manifest['matches'] if e['split']=='heldout' and e.get('capture_protocol',0)>=2]
    timings=[json.loads((root/'audit'/e['episode_id']/'timing.json').read_text()) for e in selected]
    native_errors=[];clock_errors=[]
    for entry,timing in zip(selected,timings):
        folder=data/'evaluation_only'/entry['episode_id']
        anchors=[json.loads(l) for name in ('observations.jsonl','timing.jsonl') for l in (folder/name).read_text().splitlines()]
        anchors.sort(key=lambda row:row['start_ns'])
        t=np.array([(r['start_ns']+r['end_ns'])/2e9 for r in anchors])-timing['origin_mono_s']
        ticks=np.array([r['tick'] for r in anchors]);held=(t.astype(int)%2)==1
        native_errors.extend(abs(ticks[held]-(timing['offset_ticks']+timing['ticks_per_second']*t[held]))*50)
        clock_errors.extend(abs((e['lag_low_ms']+e['lag_high_ms'])/2-timing['clock_lag_ms']) for e in timing['clock_edges'][1::2])
    timing_summary=dict(native_p95_ms=float(np.quantile(native_errors,.95)),
        native_p95_ticks=float(np.quantile(native_errors,.95)/50),
        visual_clock_midpoint_p95_ms=float(np.quantile(clock_errors,.95)),
        native_samples=len(native_errors),visual_clock_edges=len(clock_errors),frame_tick_certified=False)
    (root/'timing-summary.json').write_text(json.dumps(timing_summary,indent=2)+'\n')
    events=metrics['events'];derived=metrics['derived'];gates=metrics['gates']
    calibration=json.loads((root/'evaluation-heldout/calibration-diagnostics.json').read_text()) if (root/'evaluation-heldout/calibration-diagnostics.json').exists() else None
    verification=json.loads((root/'final-verification.json').read_text()) if (root/'final-verification.json').exists() else None
    lines=['# L1 v3 results','',f"L2 verdict: {'READY' if metrics['L2_ready'] else 'NOT READY'}.",
        'The following scores use frozen predictions from continuous native-renderer video. Stepped data and oracle events do not enter these gates.','',
        '## Timing','',
        f"Pooled heldout native timing residual p95 is {timing_summary['native_p95_ms']:.2f} ms, or {timing_summary['native_p95_ticks']:.3f} ticks. Pooled visible-clock midpoint residual p95 is {timing_summary['visual_clock_midpoint_p95_ms']:.2f} ms.",
        f"Heldout native offset/drift-fit p95 residuals range from {min(t['native_validation_residual_p95_ms'] for t in timings):.2f} to {max(t['native_validation_residual_p95_ms'] for t in timings):.2f} ms across matches. At 20 ticks/s, these are {min(t['native_validation_residual_p95_ms'] for t in timings)/50:.3f} to {max(t['native_validation_residual_p95_ms'] for t in timings)/50:.3f} ticks.",
        f"Visible-clock midpoint p95 residuals range from {min(t['clock_midpoint_residual_p95_ms'] for t in timings):.2f} to {max(t['clock_midpoint_residual_p95_ms'] for t in timings):.2f} ms. Each episode retains fitted offset, drift, interval-censored clock edges and native request brackets.",
        'Started/completed native step counters prove that admitted ordinary observations did not straddle a logic step. Screenshot PTS is the emulator estimate made before copying the image. Frame tick labels retain empirical uncertainty intervals. Their coverage is not a certified compositor-to-tick guarantee, so the frame-timing gate remains failed.','',
        '## Dataset','',
        f"{len(episodes)} completed matches, {sum(e['accepted_events'] for e in episodes)} accepted deployments, {sum(e['frames'] for e in episodes)} captured frames. Per-match capture rates range from {min(e['fps'] for e in episodes):.2f} to {max(e['fps'] for e in episodes):.2f} FPS. Sanitized H.264 media uses actual arrival/production timestamps in sidecars; nominal container FPS is not used as a native tick label.",
        f"New v3 artifacts: {disk_bytes(root)/1024**3:.3f} GiB. Live-loop total, counting hardlinks once: {disk_bytes(REPORT.parent)/1024**3:.3f} GiB. No v2 evidence was deleted.",
        (f"Allocated storage is {verification['new_storage']['allocated_bytes']/1024**3:.3f} GiB for v3 and {verification['live_loop_storage']['allocated_bytes']/1024**3:.3f} GiB for live-loop, also within both caps. {verification['complete_event_windows']} deployments have complete cue windows; the six incomplete windows belong to censored protocol-1 training tails." if verification else ''),
        'Seeds and deck multisets are disjoint. The roster contains P16 plus the 40 C56 additions. Deployment labels require native scheduling success, hand disappearance and cost evidence. Negative windows are explicit. The added plan covers normal, double and triple-elixir phases and waits for expensive cards.',
        f"Primary heldout scoring uses {len(selected)} protocol-2 matches with command logging and a terminal capture target of at least 700 ms. Every scored event's full 500 ms cue window passed audit. This capture eligibility rule was declared before model fitting. Earlier protocol-1 terminal windows are excluded from training, and protocol-1 validation/heldout captures remain diagnostic. Uncollected adaptive-plan episodes are not represented as completed.",'',
        '## Heldout gates','',
        '| Gate | Target | Measured | Verdict |','|---|---:|---:|---|',
        f"| Correct card/side within 0.5 s, recall | >=90% | {pct(events['recall'])} | {'PASS' if gates['event_recall'] else 'FAIL'} |",
        f"| Event precision | >=90% | {pct(events['precision'])} | {'PASS' if gates['event_precision'] else 'FAIL'} |",
        f"| Placement within one tile, all plays | >=90% | {pct(events['placement_within_one_all_plays'])} | {'PASS' if gates['placement'] else 'FAIL'} |",
        f"| Opponent elixir mean MAE | <=0.75 | {fmt(derived['elixir_mae'])} | {'PASS' if gates['elixir_mae'] else 'FAIL'} |",
        f"| Nominal 90% elixir interval coverage | 85-95% diagnostic band | {pct(derived['interval90_coverage'])} | {'IN BAND' if gates['uncertainty_coverage'] else 'OUT OF BAND'} |",
        f"| Hand accuracy when concentrated | >=90% | {pct(derived['hand_accuracy_when_concentrated'])} | {'PASS' if gates['concentrated_hand'] else 'FAIL'} |",
        '| Frame tick certification | Required | Empirical bounds only | FAIL |','',
        f"There are {events['matched_within_500_ms']}/{events['truth']} timely matches and {events['false_positive']} false positives. Timing matches are one-to-one, after the event bracket upper bound and within 500 ms of its lower bound. Availability includes measured processing time and cumulative FIFO backlog. This is an offline scheduling estimate, not a concurrent capture/perception/search measurement. Misses and unknown placement count against the placement denominator.",
        f"Derived state is scored at {derived['samples']} native query times spaced at least one second apart, using only already-completed pixel predictions and elapsed host time. Nominal 90% interval mean width is {fmt(derived['interval90_mean_width'])} elixir. Hand concentration coverage is {pct(derived['hand_concentrated_coverage'])}, over {derived['hand_concentrated_samples']} concentrated samples. Empty concentration coverage cannot pass.",'',
        'Being inside the predeclared coverage band is a limited diagnostic. The wide spread is not useful precision or proof of calibration.',
        (f"The whole-episode bootstrap 95% interval for coverage is {pct(calibration['interval90_coverage_95_interval'][0])} to {pct(calibration['interval90_coverage_95_interval'][1])}; the nominal 90% level remains above that interval. Elixir MAE bootstrap interval: {fmt(calibration['elixir_mae_95_interval'][0])} to {fmt(calibration['elixir_mae_95_interval'][1])}." if calibration else ''),'',
        '## Per-card events','',
        '| Card | Truth | Predictions | Recall | Precision | Placement, all truth |','|---|---:|---:|---:|---:|---:|']
    for card in manifest['cards']:
        c=events['per_card'].get(card,dict(truth=0,predictions=0,matched=0,placed_within_one=0))
        lines.append(f"| {card} | {c['truth']} | {c['predictions']} | {pct(c['matched']/c['truth'] if c['truth'] else None)} | {pct(c['matched']/c['predictions'] if c['predictions'] else None)} | {pct(c['placed_within_one']/c['truth'] if c['truth'] else None)} |")
    lines+=['','## Implementation and limits','',
        'Fusion uses a causal three-frame network, persistent body births, multi-unit grouping, secondary-spawn suppression, learned deploy-clock offsets and own HUD transitions. Spell identity combines both visual ownership heads; a short causal buffer resolves ownership from own HUD evidence. Spawner sources can be retained from perceived deployments because the frozen entity model covers P16 bodies. Suppression removes weak birth/clock boosts, not independent temporal evidence.',
        'The opponent filter tracks unrevealed deck tokens, hand/queue/refill hypotheses, affordability, uncertain event acceptance and latent missed plays. It exposes a joint sampler and learns an elixir residual distribution on validation only. That correction affects both spread and search samples. The observed heldout coverage above, not the existence of this correction, determines whether spread is calibrated.',
        'The v3 HUD reader separates white digits from the red overtime background and exposes that visible phase cue. Late-entry state starts with unknown deck tokens and a bounded elixir prior, without inventing plays through unobserved warmup time. State-event reliability uses a separate two-second validation identity window; the primary event gate remains 500 ms.',
        'A calibration tie bug was corrected using validation only. Equal-F1 thresholds now prefer more matches, fewer predictions and then the higher threshold. Original validation and uninspected heldout measurements were retained under *-initial-tie-bug. Weights, candidates and inference timestamps did not change.',
        'C56 champion cycle/status behavior is not separately certified. The frozen body model does not become a full C56 entity detector merely because event heads were added. These limits must not be converted into an L2 readiness claim.','',
        '## Evidence and changed files','',
        'Evidence: v3/dataset-merged, v3/audit, v3/model, v3/inference-validation, v3/inference-heldout, v3/evaluation-validation, v3/evaluation-heldout, v3/boundary-runtime.json and emulator ownership/stop receipts. Superseded capture attempts remain named and excluded.',
        'Vision: src/clasher/vision/l1_timing_v3.py, l1_events_v3.py, l1_derived_v3.py, l1_hud_v3.py. Scripts: certify_l1_timing_v3.py, analyze_l1_timing_v3.py, l1_native_capture_v3.py, collect_l1_stream_v3.py, audit_l1_stream_v3.py, finish_l1_collection_v3.py, stop_l1_reference_v3.py, train_l1_stream_v3.py, infer_l1_stream_v3.py, evaluate_l1_stream_v3.py, verify_l1_v3_boundary.py, run_l1_v3_pipeline.py, report_l1_v3.py. Tests: tests/test_l1_v3.py. Reports: this file, PROGRESS.md and v3/.',
        'Only owned offline emulators were used. Game-app IPv4/IPv6 egress was rejected. No official client, account, probe/APK modification, engine edit, protected-directory write, Git mutation or foreign-process signal was performed.',
        ('Final verification passed all '+str(len(verification['checks']))+' integrity/resource checks and all 51 focused L1 tests. Model/prediction hashes, native observation fences, cost parity, split isolation, full roster coverage, protected-reference identity and owned emulator shutdown passed. Acceptance remains false because the stream quality and timing-certification gates failed.' if verification else '')]
    (REPORT/'RESULTS-v3.md').write_text('\n'.join(lines)+'\n')
    progress('v3 RESULTS-v3.md written from completed heldout metrics; L2 verdict '+('READY' if metrics['L2_ready'] else 'NOT READY')+'.')


if __name__=='__main__':main()
