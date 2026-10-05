"""Write the L1 v1 gate report from completed, frozen artifacts."""
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
REPORT=ROOT/'reports/strategy_council_20260928/live-loop/l1'
V1=REPORT/'v1'


def main():
    load=lambda p:json.loads((V1/p).read_text())
    audit=load('dataset-merged/audit.json');m=load('evaluation/metrics.json')
    timing=load('inference/timing.json');capture=load('stream-timing.json');train=load('model/training_manifest.json')
    pct=lambda x:'unmeasured' if x is None else f'{100*x:.2f}%'
    num=lambda x:'unmeasured' if x is None else f'{x:.4f}'
    verdict=lambda value:'PASS' if value else 'FAIL'
    seen=set();data_bytes=model_bytes=0
    for path in REPORT.rglob('*'):
        if not path.is_file():continue
        stat=path.stat();key=(stat.st_dev,stat.st_ino)
        if key in seen:continue
        seen.add(key)
        if path.suffix in ('.pt','.npz'):model_bytes+=stat.st_size
        else:data_bytes+=stat.st_size
    weight_sha=hashlib.sha256((V1/'model/detector/weights/best.pt').read_bytes()).hexdigest()
    resume=load('model/resume_manifest.json') if (V1/'model/resume_manifest.json').exists() else None
    batch_description=(f"initial batch {train['batch']}, resumed batch {resume['batch']}" if resume else f"batch {train['batch']}")
    gates=m['gates_v1'];events=m['events_v1'];hp=m['non_tower_hp'];derived=m['derived']
    reference=m['perfect_event_reference']
    body=[v for k,v in m['entities']['per_card_v1'].items() if k not in ('Tower','KingTower')]
    body_truth=sum(x['truth'] for x in body);body_one=sum(x['within_one'] for x in body)
    gate_rows=[
        ('Dataset','10k–20k frames',str(audit['frames']),10000<=audit['frames']<=20000),
        ('L1 data/storage','<3 GiB data; <1 GiB models',f'{data_bytes/1024**3:.3f} GiB data; {model_bytes/1024**3:.3f} GiB models',data_bytes<3*1024**3 and model_bytes<1024**3),
        ('Entity position, all truth','>=90% within one tile',pct(m['entities']['within_one_tile_all_truth']),gates['entities']),
        ('Non-tower position, all truth','>=90% within one tile',pct(body_one/max(1,body_truth)),body_one/max(1,body_truth)>=.9),
        ('Both-side plays','>=90% correct card within 500 ms',pct(events['recall']),gates['events']),
        ('Play placement, all plays','>=90% within one tile',pct(events['placement_within_one_all_plays']),gates['placement']),
        ('Non-tower HP, certified visible','>=60% coverage; MAE <=0.10',f"{pct(hp['visible_coverage'])}; {num(hp['visible_mae'])}",gates['hp']),
        ('Clock','MAE <=1 second',num(m['clock']['mae_seconds'])+' s',gates['clock']),
        ('Derived opponent elixir','MAE <=0.5 with full coverage',f"{num(derived['elixir_mae'])}; coverage {pct(derived['coverage'])}",gates['derived_elixir']),
        ('Derived opponent hand','>=90% once determined',f"{pct(reference['perceived_hand_accuracy_on_determined_frames'])} over {reference['hand_determined_frames']} reference-determined frames",gates['derived_hand']),
        ('Streaming capture','>=10 FPS sustained',num(capture['fps'])+' FPS',capture['fps_gate']),
        ('Render-tick latency','p95 <=150 ms','Uncertified; no render-tick fence',False),
        ('Perception throughput','>=10 FPS',num(timing['fps'])+' FPS',timing['fps']>=10),
        ('Public status/lifecycle','Required before L2','Not implemented',False)]
    lines=['# L1 v1 results','',
        'L2 readiness: NOT READY. The report below separates measured failures from unverified gates. Only the unchanged offline native renderer was used. No official client, account, game-app network, native-probe/APK modification, or engine edit was part of this work.','',
        '## Gates','', '| Gate | Target | Result | Verdict |','|---|---|---|---|']
    lines.extend(f'| {name} | {target} | {result} | {verdict(ok)} |' for name,target,result,ok in gate_rows)
    lines += ['', '## Dataset and pairing','',
        f"{audit['frames']} JPEG frames, {audit['jpeg_bytes']:,} bytes, {audit['distinct_seeds']} seeds and {audit['distinct_decks']} distinct decks. Split counts: {audit['split_frames']}. Seeds and decks are disjoint across splits, and all v0 decks were excluded. Both shards are retained; the merged dataset uses hardlinks, so it does not duplicate JPEG storage.",'',
        'Collection advances continuously for 2, 4, 6 or 8 ticks, then pauses, waits for a fresh gRPC image, and observes again. Four placement styles cover balanced, bridge, backline and spread play. The intro advances at 1x without actions until the public HUD is visible. Native state must remain equal across capture; every admitted frame also agrees with the frozen v0 clock reader. This clock-conditioned sample is not an unfiltered live-clock test. All images are masked at source resolution before downscaling to 540x1140. No raw video or screenshot files are retained.','',
        f"All {audit['pairing_passed']} hash/pairing receipts pass. Visibility assessments: {audit['visibility_counts']}. Projected-box overlap and possible Tesla retraction are recorded per label. Uncertain labels are retained in conservative all-object metrics. There is no independently certified visible-unit denominator, so the visible-HP gate cannot pass. Ground-anchor boxes remain weak sprite extents. Paused state equality and clock agreement do not establish an exact compositor tick.",'',
        'The H.264 pilot delivered 28.9 FPS but failed freshness: tick 344 still showed 2:44 while a fresh screenshot showed 2:43. Its 30 frames are excluded. A separate 40-frame gRPC smoke passed all visible-clock checks and is also excluded from the scored dataset.','',
        '## Detector and public readings','',
        f"YOLOv8n was retrained from the local v0 checkpoint for {train['epochs']} epochs at {train['imgsz']} pixels, {batch_description}, on MPS. JPEG compression and blur augment the training images; colour, translation and scale augmentation run during training. No heldout images enter model or HUD fitting. Stable hand windows and bounded per-value templates keep dense sampling from inflating HUD memory.",'',
        f"Selected checkpoint SHA-256: `{weight_sha}`. Validation uses CPU NMS without a time cutoff so late images in a batch cannot be silently skipped. Model selection uses validation only.",'',
        f"Entity precision {pct(m['entities']['precision'])}, recall {pct(m['entities']['recall'])}. Non-tower position within one tile, including misses: {body_one}/{body_truth}. HP readings cover {hp['readings']}/{hp['truth']} non-tower labels, or {pct(hp['coverage'])}, with MAE {num(hp['mae'])}. This denominator includes visibility-uncertain labels.",'',
        f"Own hand slot accuracy {pct(m['hud']['hand_slot_accuracy'])}; whole-hand accuracy {pct(m['hud']['full_hand_accuracy'])}; next card {pct(m['hud']['next_accuracy'])}. Displayed own elixir accuracy {pct(m['hud']['own_elixir_integer_accuracy'])}, MAE {num(m['hud']['own_elixir_mae'])}. Clock missing on {m['clock']['missing']} frames. No additional own-HUD acceptance threshold was invented.",'',
        '| Card | Truth | Predictions | Precision | Recall | Mean position error, tiles | p95 position error | Within 1 tile, all truth |',
        '|---|---:|---:|---:|---:|---:|---:|---:|']
    for card,c in sorted(m['entities']['per_card_v1'].items()):
        lines.append(f"| {card} | {c['truth']} | {c['predictions']} | {pct(c['precision'])} | {pct(c['recall'])} | {num(c['position_mean_tiles'])} | {num(c['position_p95_tiles'])} | {pct(c['within_one_all_truth'])} |")
    lines += ['', 'Position errors are conditional on identity/owner matching within three tiles. The final column counts unmatched truth as failure.','',
        '## Deployments and derived state','',
        f"Strict events: {events['matched_within_500_ms']} matched, {events['missed']} missed, {events['false_positive']} false positives; precision {pct(events['precision'])}. Placement within one tile is {pct(events['placement_within_one_detected'])} among timely detected plays and {pct(events['placement_within_one_all_plays'])} across all plays. Unknown placement is a miss. Mean timely event delay {num(events['mean_delay_ms'])} ms; this excludes real capture and inference delay.",'',
        'Persistent tracks survive brief detection gaps. New same-card units are clustered near legal deployment zones. Own plays additionally require a hand transition with a visible elixir spend or a confident refill; submitted actions never count as perception. HUD-only spell events retain unknown placement. Opponent spell-effect recognition remains unimplemented, so the event work is incomplete.','',
        f"The unmodified srp-public/derived_public_state.py was run on perceived opponent plays and the perceived clock, using a monotonically clamped interval midpoint. The frozen prior is a uniform deck population without episode assignments. Opponent elixir MAE {num(derived['elixir_mae'])} on {derived['valid_frames']}/{m['frames']} frames. Opponent hand resolved on {derived['hand_resolved']} frames, conditional accuracy {pct(derived['hand_accuracy_when_resolved'])}, exact recovery over all frames {pct(derived['hand_exact_recovery_rate'])}. Posterior collapses: {derived['posterior_collapses']}.",'',
        f"Event-spend diagnostic: {m['event_error_propagation']}. Misses leave too much derived elixir until the cap; false or wrong plays can reduce it and make the hand/order posterior inconsistent. Posterior failures stop derivation; no truth repair is applied.",'',
        f"Evaluation-only true-event reference: elixir MAE {num(reference['elixir_mae'])} on {reference['valid_frames']} frames. The reference determines the opponent hand on {reference['hand_determined_frames']} frames, with accuracy {pct(reference['oracle_hand_accuracy'])}. Perceived-event hand accuracy on those same frames is {pct(reference['perceived_hand_accuracy_on_determined_frames'])}, counting abstentions and collapsed states as misses. These native labels and ticks are used only for scoring; they never repair or feed the pixel model.",'',
        '## Capture and latency','',
        f"1x capture with short controller pauses between ten-second segments: {capture['frames']} frames over {capture['seconds']:.2f} seconds, {capture['fps']:.2f} FPS. The authenticated gRPC endpoint is loopback-only. Emulator screenshot-production timestamp to sanitized host receipt: mean {capture['screenshot_production_to_sanitized_receipt_mean_ms']:.2f} ms, p95 {capture['screenshot_production_to_sanitized_receipt_p95_ms']:.2f} ms, p99 {capture['screenshot_production_to_sanitized_receipt_p99_ms']:.2f} ms. This is a screenshot-transport measurement, not certified render-tick latency. The latter remains unmeasured because the unchanged renderer supplies no per-frame tick fence.",'',
        f"JPEG-to-public-frame perception: {timing['fps']:.2f} FPS, p95 {timing['p95_ms']:.2f} ms, synchronized batch-1 MPS. Capture, search and action execution are excluded; capture and perception rates must not be added together as a closed-loop result.",'',
        '## Evidence and remaining work','',
        'Artifacts: v1/dataset-merged/audit.json, v1/model/training_manifest.json, v1/inference/frames.jsonl, v1/inference/timing.json, v1/evaluation/metrics.json, v1/evaluation/derived.jsonl, v1/stream-timing.json, v1/producer-sources.json and v1/producer-sources.zip. Emulator launch, attestation, firewall and stop receipts are in v1/emulator-grpc-auth2 and v1/emulator-second.','',
        'Before L2, close the failed perception gates, implement opponent spell cues and public status/lifecycle handling, establish visible-unit labels for HP scoring, and obtain defensible render-tick latency evidence without changing the prohibited native probe/APK. No offline closed-loop search/control acceptance run was performed.','']
    lines += ['## Changed files','',
        'Vision: src/clasher/vision/l1_perception.py, l1_stream.py, l1_temporal.py, l1_hp.py, l1_training.py.','',
        'Scripts: scripts/collect_l1_rendered.py, audit_l1_dataset.py, train_l1_perception.py, resume_l1_training.py, infer_l1_perception.py, evaluate_l1_perception.py, evaluate_l1_v1.py, benchmark_l1_stream.py, launch_l1_reference.py, run_l1_v1_pipeline.py, report_l1_v1.py.','',
        'Tests: tests/test_l1_v1.py. Reports and generated artifacts: this L1 directory, primarily v1/, PROGRESS.md and RESULTS-v1.md.','']
    if resume:
        lines += ['## Resource restart','',
            'Host pressure reached 6.7 GiB free disk and 9.6 GiB swap during epoch 2. Only the owned trainer was stopped. The completed epoch-1 checkpoint retained optimizer state; the incomplete second epoch was discarded. scripts/resume_l1_training.py resumed the fit at batch 8. After epoch 2 completed, validation box matching and retained statistics moved to CPU, and a second restart discarded a short partial epoch 3. The input data and HUD model stayed unchanged. Both completed checkpoints, initial producer archives, checkpoint hashes, and resume source hashes are retained.','',
            'A later free-disk guard stopped an incomplete epoch 5. The final two epochs used separate processes, releasing MPS caches after each saved checkpoint and requiring at least 8 GiB free disk before the next process started. Only completed epochs count toward the reported fit.','',
            'The resumed process uses MPS high/low allocator ratios of 0.4/0.25 and clears unused MPS cache every 25 batches and at epoch/validation boundaries. These controls follow the [PyTorch allocator documentation](https://docs.pytorch.org/docs/stable/mps_environment_variables.html). Actual driver allocation, swap and free disk are logged in v1/model/mps-memory.jsonl. Foreign jobs were never signalled.','']
    if (V1/'final-verification.json').exists():
        lines += ['## Final verification','',
            'All 42 focused L1 and existing contract/privacy tests pass. The canonical live-inference CLI reproduces every exported contract metric and gate exactly; its exit code is 1 because acceptance fails. Frozen prediction and training-label hashes were rechecked. The upstream derived-state source hash matches v0. All owned emulators and long-running L1 jobs are stopped.','',
            'Four fixed heldout samples were visually inspected in v1/heldout-qa.jpg. Ground-anchor predictions align with the native labels, while dense troop groups show extra detections. This is a spot check, not per-label visibility certification. Heldout traces contain no Tesla bodies, so Tesla recall remains unmeasured despite training support. No tuning followed heldout inspection.','']
    (REPORT/'RESULTS-v1.md').write_text('\n'.join(lines))
    print(str(REPORT/'RESULTS-v1.md'))


if __name__=='__main__':main()
