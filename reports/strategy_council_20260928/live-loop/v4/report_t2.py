"""Restated T2 gates, using immutable retained and completion trials."""
from collections import Counter
import json
import numpy as np
from common import HERE,write,sha


def main():
    out=HERE/'actuation'
    inputs=[out/'trials.jsonl',out/'trials-completion-20261007.jsonl']
    rows=[json.loads(l) for p in inputs for l in p.read_text().splitlines()]
    keys=[tuple(r['cell'])+(r['trial'],) for r in rows]
    assert len(keys)==len(set(keys)), 'Duplicate factorial trials'
    counts=Counter(tuple(r['cell']) for r in rows)
    complete=len(counts)==16 and all(n==40 for n in counts.values())
    rep=json.loads((out/'reproduction-completion-20261007.json').read_text())
    result=dict(complete=complete,trials=len(rows),cells={str(k):n for k,n in counts.items()},methods={},misses=[])
    backends={}
    for method in ('grpc','adb-spawn'):
        rr=[r for r in rows if r['cell'][0]==method]
        accepted=[r for r in rr if r['truth_accepted']]
        p50,p99=map(float,np.percentile([r['truth_latency_ms'] for r in accepted],[50,99]))
        timing=dict(samples=len(accepted),p50_ms=p50,p99_ms=p99,p50_ticks=p50/50,p99_ticks=p99/50,tick_ms=50,
                    ticks_semantics='wall-latency equivalents at nominal 20 ticks/s; retained trials lack exact execution ticks')
        backends['offline-renderer-'+method]=timing
        def detected(r):
            return (r['pixel_latency_ms'] is not None and
                    r['pixel_latency_ms']-r['truth_latency_ms']<=600 and r['pixel_latency_ms']<=p99+600)
        positives=sum(detected(r) for r in accepted)
        result['methods'][method]=dict(trials=len(rr),accepted=len(accepted),acceptance=len(accepted)/len(rr),
            two_tap_p95_ms=float(np.percentile([r['tap_ms'] for r in rr],95)),
            detected=positives,sensitivity=positives/len(accepted),timing=timing,
            capture_fps_median=float(np.median([r['capture_fps'] for r in rr])),
            pixel_minus_native_p95_ms=float(np.percentile([r['pixel_latency_ms']-r['truth_latency_ms'] for r in accepted if r['pixel_latency_ms'] is not None],95)))
        if method=='grpc':
            for r in accepted:
                if detected(r):continue
                result['misses'].append(dict(cell=r['cell'],trial=r['trial'],seed=r['seed'],before_tick=r['before_tick'],
                    native_elixir=r['cost']+r['actual_margin'],hud_elixir=r['before_hud']['elixir'],hud_clock=r['before_hud']['clock'],
                    native_acceptance_ms=r['truth_latency_ms'],capture_fps=r['capture_fps'],pixel_latency_ms=r['pixel_latency_ms'],
                    truth_before_sha256=r['truth_before_sha256'],
                    classification='HUD baseline elixir error; likely reader miss. Native acceptance is timely. Raw frame/after-HUD trace was not retained, so short-lived stale pixels versus digit misread cannot be conclusively separated.'))
    write(out/'backend-timing.json',dict(schema='clasher.backend-timing.v1',
        measurement='submission to first observed native acceptance; polling upper bound',
        sources={p.name:sha(p) for p in inputs},backends=backends))
    grpc=result['methods']['grpc'];neg=rep['negatives']
    specificity=sum(not r['pixel_predicted'] for r in neg)/len(neg)
    stale,fixed=rep['stale']
    gates=dict(factorial=complete,acceptance=grpc['acceptance']>=.98,two_tap=grpc['two_tap_p95_ms']<=80,
        sensitivity=grpc['sensitivity']>=.99,specificity=specificity>=.99,
        stale_fix=stale['attempted']==2 and stale['accepted']==1 and fixed['attempted']==1 and fixed['accepted']==1 and fixed['second_command']['reason']=='pending')
    result.update(gates=gates,passed=all(gates.values()),specificity=specificity,negative_windows=len(neg),
        stale_reproduction=[dict(mode=r['mode'],attempted=r['attempted'],accepted=r['accepted'],second_command=r['second_command'],measured_spend=r['measured_spend']) for r in rep['stale']],
        native_ticks_per_second=rep['native_ticks_per_second'])
    lines=['# T2 actuation results','',
        'Verdict: '+('PASS' if result['passed'] else 'FAIL')+' — restated 99% pixel sensitivity gate is not met; actuator remains unqualified for production.','',
        f'All {len(rows)} factorial trials retained; 16 cells × 40. Original 623 rows are untouched; 17 completion rows are in `actuation/trials-completion-20261007.jsonl`. No trials were excluded after outcomes.',
        '', '| Transport | Acceptance | Two-tap p95 | D_b p50 / p99 | Sensitivity |', '|---|---:|---:|---:|---:|']
    for method,m in result['methods'].items():
        t=m['timing']
        lines.append(f"| {method} | {m['accepted']}/{m['trials']} | {m['two_tap_p95_ms']:.2f} ms | {t['p50_ms']:.2f} / {t['p99_ms']:.2f} ms | {m['detected']}/{m['accepted']} ({m['sensitivity']:.2%}) |")
    t=grpc['timing']
    lines += ['',f"Chosen transport remains persistent gRPC with 20 ms inter-tap delay. Its D_b equivalents are {t['p50_ticks']:.3f} / {t['p99_ticks']:.3f} ticks (p50/p99, nominal 50 ms ticks). The retained trials measure first native observation, not exact native execution. Do not present these fractional tick equivalents as exact hook ticks; the unchanged hook's nominal command delay is 22 ticks.",
        '',f"Specificity: {sum(not r['pixel_predicted'] for r in neg)}/{len(neg)} ({specificity:.2%}); 20 no-input and 20 selection-only windows, each {neg[0]['window_seconds']:.3f} seconds. Native hand preservation and nondecreasing elixir corroborate every negative. This is the empirical point gate, not a claim that a 99% population lower confidence bound has been established.",
        '',f"Host GPU, median screenshot delivery {grpc['capture_fps_median']:.2f} FPS; native negative-window stepping {rep['native_ticks_per_second']:.3f} ticks/s. Pixel-minus-native observation p95 {grpc['pixel_minus_native_p95_ms']:.2f} ms.",
        '', '## Each of the four gRPC misses','']
    for m in result['misses']:
        lines.append(f"- Cell {m['cell']}, trial {m['trial']}, seed {m['seed']}, tick {m['before_tick']}: native elixir {m['native_elixir']:.4f}, HUD elixir {m['hud_elixir']:.0f}; acceptance {m['native_acceptance_ms']:.2f} ms; {m['capture_fps']:.2f} FPS; HUD clock {m['hud_clock']:.0f}. No pixel detection before the 1.8 s observation limit. {m['classification']}")
    lines += ['', 'Every miss is Cannon (cost 3). The erroneous baseline of 9 makes the unchanged cost±1 spend predicate seek a post-play HUD near 6 instead of the actual near-zero balance. The HUD clock agrees with the native pre-tap tick at its one-second resolution. All four native acceptances leave more than 600 ms before the 1.8 s trial limit, and capture is roughly 59 FPS: there is no evidence of slow native acceptance or a gross frame-delivery stall. Baseline HUD error is directly recorded; attribution to the digit reader rather than brief stale imagery remains an inference. None is excused from the denominator; sensitivity stays 316/320 = 98.75%. No thresholds or reader were tuned.',
        '', '## Stale re-tap reproduction','']
    for r in result['stale_reproduction']:
        lines.append(f"- {r['mode']}: {r['attempted']} taps attempted, {r['accepted']} accepted, measured spend {r['measured_spend']:.3f}; second command {r['second_command']}.")
    lines += ['', 'Both arms use the same seed and cached pre-tap HUD. The stale arm sends a second command at 700 ms; the ledger arm blocks it as pending and keeps the optimistic spend. This isolates the redundant-command failure mode, not an additional successful double spend. The injected second-play demand is 1/1 in each paired arm; natural planner demand frequency was not measured by this transport bench and remains for simulator/runtime evaluation.',
        '', '## Timing implementation and limits','',
        f"`actuator.py` loads `actuation/backend-timing.json`: verification deadline = most recent submission + measured D_b,p99 + 600 ms; rollback = deadline + 200 ms. For gRPC these are {t['p99_ms']+600:.2f} and {t['p99_ms']+800:.2f} ms. The single retry retains the existing 150 ms wait after the deadline, requires a fresh HUD with the card present and affordable, and starts the same backend-relative window for the retry without a second reservation. No retry is emitted after rollback. Existing fresh-HUD remapping, confirmation predicate, single outstanding command and one-second failure hold remain.",
        '', 'Seven actuator unit tests cover configured deadlines, delayed acceptance, no early retry, one retry, spend preservation and rollback, absent/unaffordable/stale retry blockers, HUD remapping and false confirmations. Collector/storage/converter tests are recorded separately in `validation-20261007-final.log` (the original short synthetic timing failures are retained separately).',
        '', 'Renderer relaunch receipt: `emulator-host/relaunch-20261007/complete.json`; emulator-5584, adb 5042, gRPC 8558, probe 26794, read-only AVD, host GPU, 2 cores / 3 GiB. Pinned attestation SHA256 `864227bf7208aa9c06cd976db3fa0734a32277b0552f92e496ad283a917b4a93`; IPv4 and IPv6 UID REJECT rules rechecked. APK, hook and command age are unchanged. No new attestation was created.',
        '', 'T1 is independent: it uses scheduled native receipts for exact execution labels, not this pixel verifier. T2 failure blocks production P4 qualification; it does not block preregistered T1 acquisition. Delay-aware planner and S-d simulator validation belong to the coordinator’s separate player task.',
        '', 'All raw factorial, stale and specificity rows are preserved under `actuation/`; development trials remain diagnostic only. The retained baseline has no raw screenshot/after-HUD sequence, which limits retrospective miss attribution.']
    report='\n'.join(lines)+'\n'
    (HERE/'T2-RESULTS.md').write_text(report);(out/'RESULTS.md').write_text(report)
    write(out/'metrics.json',result)
    write(out/'candidate-config.json',dict(transport='grpc',backend='offline-renderer-grpc',inter_tap_delay_ms=20,elixir_margin=.1,
        timing_config='backend-timing.json',verification_after_acceptance_ms=600,rollback_after_deadline_ms=200,qualified=result['passed'],reason='Restated sensitivity 316/320 = 98.75% < 99%'))
    print(json.dumps(result,indent=2))

if __name__=='__main__':main()
