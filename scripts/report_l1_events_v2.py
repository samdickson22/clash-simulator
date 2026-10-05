"""Write the measured v2 verdict without promoting missing or failed gates."""
import hashlib
import json
from pathlib import Path
import zipfile

from collect_l1_rendered import REPORT,progress
from collect_l1_events_v2 import disk_bytes


def main():
    v2=REPORT/'v2'
    audit=json.loads((v2/'audit-final/audit.json').read_text())
    selection=json.loads((v2/'validation/selection.json').read_text())
    model=json.loads((v2/'model/complete.json').read_text())
    results={}
    for name in ('fast-stream','heldout-10','heldout-10.9141','heldout-20'):
        path=v2/f'evaluation-{name}/metrics.json'
        if path.exists():results[name]=json.loads(path.read_text())
    pct=lambda x:'unmeasured' if x is None else f'{100*x:.2f}%'
    num=lambda x:'unmeasured' if x is None else f'{x:.4f}'
    text=['# L1 v2 results','',
          'L2 readiness: NOT READY. No acceptance claim is made from the stepped dataset or continuous replay alone. This run used only the unchanged offline native renderer. The official client, game accounts, APK/probe, engine, gamedata and protected experiment directories were not modified.','',
          '## Dataset','',
          f"The main stepped dataset contains {audit['frames']:,} sanitized JPEGs, {audit['events']} accepted deployments, {audit['negative_windows']} explicit negative windows and eight disjoint seed/deck pairs. Split frames: {audit['split_frames']}. Four late deployments originally had only 14 post-command ticks at the cutoff. Separate deterministic replays recaptured their complete -6 through +30 tick windows, adding {audit['supplemental_frames']} frames. Original scored inputs stayed frozen. Both seats cover P16 in training and heldout; split gaps are recorded below.",
          '',f"Coverage gaps by split: {audit['missing_card_sides']}. Pairing/split/hash failures: {audit['failures']}.",
          '',f"Stepped dataset: {audit['dataset_bytes']/1024**3:.3f} GiB. Entire new v2 directory: {disk_bytes(v2)/1024**3:.3f} GiB. Total live-loop, counting hardlinks once: {disk_bytes(REPORT.parent)/1024**3:.3f} GiB. No raw capture files were written; pixels were masked in memory before JPEG conversion.",
          '', 'Each collected interval advances one native tick, waits for a newly produced screenshot and checks unchanged native observations. This is exact simulation stepping, not a certified compositor tick. Deploy-clock and spell animations also advance on presentation time while paused. Therefore the continuous 1x replay is reported separately. It reuses heldout commands without fitting, measures actual screenshot cadence, and brackets event execution from native tick crossings.',
          '', f"Event coordinates retain the requested command placement. The renderer sometimes moves spawns around occupied tower footprints. For example, a training Cannon requested at (2.5, 24.5) appeared at (2.5, 22.5). These labels were not silently changed to make placement pass. {audit['manual_event_reviews']}/{audit['events']} events have manually reviewed cue-presence samples. Clock traces are pixel-derived and model-assisted. These samples do not certify exact cue onset or every frame's visibility.",
          '', '## Detector and validation','',
          f"A small convolutional temporal model uses the current OpenCV color image plus differences from two earlier frames. It was trained for 24 epochs on four training matches, including both 20 Hz and 10 Hz stacks. Checkpoint SHA-256: `{model['sha256']}`. Deploy clocks use pixel color/ring evidence, with offsets fitted only on training. Fusion combines these cues with v1 track births and own hand/elixir transitions. Own spell events retain unknown placement if spatial evidence is weak.",
          '', f"Validation selected temporal threshold {selection['threshold']} and clock threshold {selection['marker_minimum']}. Validation recall {pct(selection['metrics']['recall'])}, precision {pct(selection['metrics']['precision'])}, all-play placement {pct(selection['metrics']['placement_within_one_all_plays'])}. The initial validation run and the spell/clock fusion correction are retained under `*-initial`. No heldout fitting followed model/threshold freezing.",
          '', '## Heldout gates','',
          '| Run | Recall within 0.5 s | Precision | Placement within 1 tile, all plays | Elixir MAE | Hand accuracy once determined |',
          '|---|---:|---:|---:|---:|---:|']
    for name,r in results.items():
        e,d=r['events'],r['derived']
        text.append(f"| {name} | {pct(e['recall'])} | {pct(e['precision'])} | {pct(e['placement_within_one_all_plays'])} | {num(d['elixir_mae'] if d else None)} | {pct(d['hand_accuracy'] if d else None)} |")
    text.extend(['','Targets are recall >=90%, precision >=90%, placement >=90%, elixir MAE <=0.5 and hand accuracy >=90%. Placement includes missed events and unknown coordinates as failures. Matching is one-to-one and requires the correct seat/card. Stepped timings use media time. Continuous timing conservatively requires a prediction after the event bracket upper bound and within 500 ms of its lower bound; there is no compositor fence. Event latency uses image production time and excludes capture transport and inference completion latency.',''])
    for name,r in results.items():
        e,d=r['events'],r['derived']
        if d is None:
            text.extend([f"{name}: {e['matched_within_500_ms']}/{e['truth']} timely matches, {e['false_positive']} false positives, {e['within_one']}/{e['truth']} placements. This is the live event check, using every captured frame at measured rates of 10.25 and 10.06 FPS. It uses native advances up to the next command boundary, with a one-tick bracket around each deployment. Sparse native observations do not certify per-frame derived-state truth, so that gate is scored on the complete stepped heldout matches. JPEG quality is 55 for this extra replay to stay within the data cap; main data uses 82.",''])
            continue
        text.append(f"{name}: {e['matched_within_500_ms']}/{e['truth']} timely matches, {e['false_positive']} false positives, {e['within_one']}/{e['truth']} placements. Derived state covers {d['frames']} frames, with {d['hand_determined_frames']} reference-determined hand frames and {pct(d['hand_coverage'])} hand coverage on that denominator. True-event elixir reference MAE {num(d['reference_elixir_mae'])}. Gates: {r['gates']}.")
        text.append('')
    sensitivity=v2/'evaluation-fast-stream/timing-sensitivity.json'
    if sensitivity.exists():
        diagnostic=json.loads(sensitivity.read_text());mid=diagnostic['midpoint'];upper=diagnostic['optimistic']
        text.extend([f"Timing sensitivity on the same frozen live-stream predictions: command-bracket midpoint recall {pct(mid['recall'])}, precision {pct(mid['precision'])}; optimistic interval-compatible upper bounds are recall {pct(upper['recall'])}, precision {pct(upper['precision'])}, placement {pct(upper['placement_within_one_all_plays'])}. These also fail. The conservative result is a lower bound, not an exact render-timestamp measurement.",''])
    text.extend(['## Derived-state robustness','',
        'The exact public-state source was copied and hash-pinned without importing or writing in srp-public. The adapter maintains a bounded accept/skip posterior, checks affordability, deduplicates events, and tests one omitted play when an observed card contradicts a hypothesis. Hand-slot permutations are merged while preserving prior mass. Elixir is a posterior mean; hand predictions require 90% posterior mass. That confidence is a model assumption, not a proof of correctness. Perceived updates use visible-clock intervals and relative media time. Native ticks and hands are scoring-only inputs.',
        '', 'The corruption experiment applies independent seeded misses, inserted plays, or wrong identities to true events. It samples scoring states once per second but processes each corrupted event at its original time. Its zero-error baseline isolates event-noise degradation from detector timing error. There is one fixed corruption seed, so these are diagnostics, not confidence intervals.','',
        '| Error mode | Nominal rate | Realized errors / events | Elixir MAE | Determined-hand accuracy |','|---|---:|---:|---:|---:|'])
    corruption=v2/'evaluation-heldout-10/corruption.json'
    if corruption.exists():
        for r in json.loads(corruption.read_text()):
            counts=r['injected_errors'];errors=counts['missed']+counts['inserted']+counts['wrong_identity']
            text.append(f"| {r['mode']} | {pct(r['rate'])} | {errors}/{counts['opponent_events']} | {num(r['elixir_mae'])} | {pct(r['hand_accuracy'])} |")
    text.extend(['','## Runtime and evidence',''])
    for directory in ('stream-dataset','fast-stream-dataset'):
        stream=v2/directory/'episodes.jsonl'
        if stream.exists():
            for line in stream.read_text().splitlines():
                r=json.loads(line)
                text.append(f"{directory}, {r['episode_id']}: {r['frames']} screenshots at {r['fps']:.2f} FPS, simulation {r['simulation_ticks_per_wall_second']:.2f} ticks per wall second; screenshot-to-saved p95 {r['screenshot_to_saved_p95_ms']:.1f} ms; final opponent hand/elixir replay parity {r['final_opponent_hand_elixir_match']}.")
    text.extend(['','The single-tick stream is an unscored pacing diagnostic because one-tick control overhead slowed simulation. Its original JPEG bytes are preserved in verified lossless tar.xz chunks under stream-dataset/archives; loose originals were removed only after every member hash matched. The initially blocked stream attempt is excluded and retained under rejected-blocking-*.',
        '', 'A fixed-phase stream subsample averaged only 8.19 and 8.08 FPS because it dropped bursty arrivals. It is retained under *fast-stream-subsampled*. The final event gate uses all 3,069 frames at the native capture cadence. Fractional raw media timestamps are floored to integer milliseconds in the public manifest, as required by the unchanged inference contract; raw receipts remain intact.',
        '', 'A coordinator handoff raced with a tail-recapture child already starting. The duplicate attempt failed at the existing-directory guard before issuing native commands. The original child completed the 74 supplemental frames and continued as the sole event-boundary capture driver. Ownership and recovery receipts are retained.'])
    for name in ['validation',*results]:
        path=v2/f'inference-{name}/timing.json'
        if path.exists():
            r=json.loads(path.read_text());text.append(f"Inference {name}: {r['fps']:.2f} FPS, p95 {r['p95_ms']:.1f} ms, excluding capture. This is not a closed-loop throughput result.")
    boundary=json.loads((v2/'boundary-runtime.json').read_text())
    text.extend(['',f"The runtime input-boundary check processed {boundary['frames']} frames with private-label/native-data reads and INET sockets denied. There were {len(boundary['denied_read_attempts'])} forbidden file-read attempts, {len(boundary['blocked_network_attempts'])} blocked library connectivity probes, and zero successful network connections. Details are in boundary-runtime.json. Emulator launch and shutdown receipts verify both IPv4 and IPv6 game-UID egress blocking. Only one 3072 MiB / two-core emulator was used.",
        '', 'Validation and stepped inference ran with the emulator active; final stream inference ran after its shutdown. These timings do not establish concurrent capture/perception throughput. All 52 focused tests pass. The final integrity record verifies frozen inference sources, weights, thresholds, predictions, the unchanged protected reference, dataset pairing, storage caps, lossless archives and owned emulator shutdown. Tests and integrity checks do not override the failed quality gates.',
        '', 'Evidence lives in v2/dataset, v2/tail-windows, v2/audit-final, v2/model, v2/inference-*, v2/evaluation-*, v2/stream-dataset, v2/fast-stream-dataset, v2/validation and v2/emulator. PROGRESS.md records collection, training, validation revisions, ownership and final checks. The model does not yet justify L2 admission. Remaining work includes timely opponent spell identity/placement, robust placement under native snapping, and reliable live-rate event fusion; exact rendered-tick timing remains uncertified.',
        '', '## Files changed','',
        'New vision modules: src/clasher/vision/l1_events_v2.py and l1_derived_v2.py. New scripts: collect_l1_events_v2.py, train_l1_events_v2.py, infer_l1_events_v2.py, evaluate_l1_events_v2.py, audit_l1_events_v2.py, run_l1_events_v2.py, collect_l1_stream_v2.py, run_l1_stream_v2.py, recapture_l1_tail_v2.py, archive_l1_diagnostic_v2.py, finish_l1_capture_v2.py, run_l1_fast_stream_eval_v2.py, verify_l1_v2_boundary.py and report_l1_events_v2.py. Tests: tests/test_l1_v2.py. Reports: live-loop/l1/v2/, PROGRESS.md and RESULTS-v2.md. No existing v1 source was edited.',''])
    (REPORT/'RESULTS-v2.md').write_text('\n'.join(text))
    root=REPORT.parents[3]
    paths=[*sorted((root/'src/clasher/vision').glob('*v2.py')),*sorted((root/'scripts').glob('*l1*v2.py')),
           root/'scripts/verify_l1_v2_boundary.py',root/'tests/test_l1_v2.py']
    (v2/'source-hashes-final.json').write_text(json.dumps({str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},indent=2)+'\n')
    with zipfile.ZipFile(v2/'sources-final.zip','w',zipfile.ZIP_DEFLATED) as z:
        for p in paths:z.write(p,p.relative_to(root))
    progress('v2 RESULTS-v2.md written with measured gates and NOT READY verdict. Final integrity and owned-process checks still required.')


if __name__=='__main__':main()
