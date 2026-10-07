"""Summarize all retained T2 trials without turning missing gates into passes."""
from collections import Counter
import json
import numpy as np
from common import HERE,write

def main():
    out=HERE/'actuation';rows=[json.loads(l) for l in (out/'trials.jsonl').read_text().splitlines()]
    rep=json.loads((out/'reproduction.json').read_text()) if (out/'reproduction.json').exists() else None
    counts=Counter(tuple(r['cell']) for r in rows);complete=len(counts)==16 and all(n==40 for n in counts.values())
    result=dict(complete=complete,trials=len(rows),cells={str(k):n for k,n in counts.items()},methods={},reproduction=rep)
    lines=['# T2 actuation results','','Verdict: blocked on the pinned renderer\'s verification latency.','',
      f'{len(rows)} retained factorial trials; {len(counts)}/16 cells present. Full matrix complete: {complete}.', '',
      '| Method | Trials | First acceptance | Two-tap p95 | Pixel detections <=600 ms |',
      '|---|---:|---:|---:|---:|']
    for method in ['grpc','adb-spawn']:
        x=[r for r in rows if r['cell'][0]==method]
        if not x:continue
        accepted=sum(r['truth_accepted'] for r in x);detected=sum(r['pixel_within_600ms'] for r in x)
        m=dict(trials=len(x),accepted=accepted,acceptance=accepted/len(x),two_tap_p95_ms=float(np.percentile([r['tap_ms'] for r in x],95)),
          pixel_600ms=detected,sensitivity_600ms=detected/max(1,accepted),
          truth_latency_p50_ms=float(np.median([r['truth_latency_ms'] for r in x if r['truth_accepted']])),
          pixel_latency_p95_ms=float(np.percentile([r['pixel_latency_ms'] for r in x if r['pixel_latency_ms'] is not None],95)),
          detected_within_600ms_of_native_observation=sum(r['pixel_latency_ms'] is not None and r['truth_latency_ms'] is not None and r['pixel_latency_ms']-r['truth_latency_ms']<=600 for r in x),
          pixel_minus_native_p95_ms=float(np.percentile([r['pixel_latency_ms']-r['truth_latency_ms'] for r in x if r['pixel_latency_ms'] is not None and r['truth_latency_ms'] is not None],95)),
          median_capture_fps=float(np.median([r['capture_fps'] for r in x])))
        result['methods'][method]=m
        lines.append(f"| {method} | {len(x)} | {accepted}/{len(x)} ({m['acceptance']:.1%}) | {m['two_tap_p95_ms']:.2f} ms | {detected}/{accepted} |")
    for method,m in result['methods'].items():
        lines += ['',f"{method}: {m['detected_within_600ms_of_native_observation']}/{m['accepted']} detections within 600 ms of the probe's first observed acceptance; pixel-minus-native observation p95 {m['pixel_minus_native_p95_ms']:.2f} ms. The probe poll is an observation-time upper bound, not an exact touch execution timestamp."]
    lines += ['', 'The candidate transport is persistent emulator gRPC touch injection, with four RPCs per card-plus-tile action and no per-tap subprocess. The matrix compares 0 and 20 ms inter-tap delays, 3 and 24 native ticks since the previous own deployment, and 0.1 and 1.0 actual elixir margins. Actual margins are measured and checked within 0.06 elixir. The adb baseline starts one host process for each tap. The pinned hook uses the L2 1080x1920 tap map even though screenshots are 1080x2280.', '',
      'No transport is qualified for v4 production. Native acceptance arrives roughly 1.1 seconds after submission. The attested hook formats a touch command at current tick + 2 and adds the 20-tick live-command age. Faster tap delivery does not remove that delay. The 600 ms verifier and 800 ms reservation timeout cannot be admitted against this backend. The coordinator must decide whether to approve a new attested touch shim or amend the renderer-only timing contract. This worker changed neither the APK nor the pinned hook.', '',
      '`actuator.py` implements fresh-HUD slot remapping, one outstanding command, optimistic spend/slot reservation, dual HUD verification, at most one retry after 150 ms, rollback and a one-second card hold. Its unit tests cover stale frames, remapping, false confirmations, retry limits and holds. It must remain unintegrated until the timing mismatch is resolved.', '']
    if rep:
        lines += [f"Native idle-running rate: {rep['native_ticks_per_second']:.3f} ticks/s.",'',f"No-input specificity: {rep['specificity']:.1%} over {len(rep['negatives'])} windows. This does not rescue failed timely sensitivity.", '', '## Stale re-tap reproduction','']
        for r in rep['stale']:lines.append(f"- {r['mode']}: {r['attempted']} attempted, {r['accepted']} accepted; second command {r['second_command']['state']}; measured spend {r['measured_spend']:.3f}.")
        lines += ['', 'This isolates suppression of a cached-frame re-tap at 700 ms. It is not a passing full 600/800 ms actuator lifecycle test.']
    else:lines += ['Stale re-tap and specificity experiment not yet complete.']
    lines += ['', '## Provenance and limitations','',
      'Renderer: host GPU, two cores, 3 GiB, read-only AVD emulator-5584; adb 5042, gRPC 8558, probe 26794. Attestation SHA256 `864227bf7208aa9c06cd976db3fa0734a32277b0552f92e496ad283a917b4a93`. IPv4 and IPv6 app-UID egress rejection was verified. Other projects and Stage 6 jobs remained running.', '',
      'Raw trials are in `actuation/trials.jsonl`; setup schedule receipts and actual elixir margins are retained in each row. Development attempts with an intro overlay and unmanipulated margins remain in separate `development-*-trials.jsonl` files and do not enter the matrix. Later trials reuse a live match during setup and reset at tick 1600 or terminal. Setup uses 4x stepping, measured taps and verification use 1x. Pixel HUD uses the retained v1 reader; v3 weights are not required.']
    write(out/'candidate-config.json',dict(transport='grpc',inter_tap_delay_ms=20,elixir_margin=.1,verification_ms=600,ledger_timeout_ms=800,qualified=False,reason='Pinned touch execution exceeds 600 ms; no production admission'))
    text='\n'.join(lines)+'\n';(HERE/'T2-RESULTS.md').write_text(text);(out/'RESULTS.md').write_text(text);write(out/'metrics.json',result)
if __name__=='__main__':main()
