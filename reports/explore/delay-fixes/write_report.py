"""Render the completed exploration summary; interpretation is supplied separately."""
import argparse
import json
from pathlib import Path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--root', type=Path, required=True)
    a = ap.parse_args()
    result = json.loads((a.root / 'results.json').read_text())
    audit = json.loads((a.root / 'compute-audit.json').read_text())
    def pct(arm, metric):
        if metric not in result['arms'][arm]:return 'unavailable'
        row = result['arms'][arm][metric]
        lo, hi = row['ci95']
        return f"{100*row['value']:.2f}% [{100*lo:.2f}, {100*hi:.2f}]"
    def effect(name, metric):
        if metric not in result['contrasts'][name]['metrics']:return 'unavailable'
        row = result['contrasts'][name]['metrics'][metric]
        lo, hi = row['ci95']
        return f"{100*row['delta']:+.2f} pp [{100*lo:+.2f}, {100*hi:+.2f}]"
    r = result['loss_latency_asymmetry_inflation']
    lines = [
        '# Delay fixes: exploration results', '',
        f"Completed **{result['paired_seeds']:,} paired seeds per original arm**, plus matched-cadence controls, {result['games']:,} terminal games. Non-confirmatory, dev-only simulation; no preregistration or frozen-registration edits.", '',
        (a.root / 'interpretation.md').read_text().strip(), '',
        f"Control completion: {result['control_completion']['status']}; R0/R27 terminal games {result['control_completion']['completed_by_arm']}; common paired controls {result['control_completion']['paired_common']:,}. The target was 1,250 per control arm.", '',
        '## Outcomes', '',
        '| Arm | Win rate, 95% CI | Loss rate, 95% CI | Under-4 arrivals, 95% CI |',
        '|---|---:|---:|---:|',
    ]
    for arm in result['arms']:
        lines.append(f"| {arm} | {pct(arm,'win_fraction')} | {pct(arm,'loss_fraction')} | {pct(arm,'arrival_under4_fraction')} |")
    matched = result['matched_loss_latency_asymmetry_inflation']
    matched_text = (f"The matched-cadence loss-cost difference-in-differences `(R27−R0)−(S27−S0)` is **{100*matched['delta']:+.2f} pp**, 95% CI [{100*matched['ci95'][0]:+.2f}, {100*matched['ci95'][1]:+.2f}], n={matched['paired_seeds']:,} paired seeds." if matched else 'Matched-cadence loss-cost difference-in-differences is unavailable: no common completed control seeds.')
    lines += ['', 'Draws are retained; win rate is not calculated as 1−loss rate.', '',
        '| Paired contrast (treatment − control) | Win change, 95% CI | Loss change, 95% CI | Under-4 change, 95% CI |',
        '|---|---:|---:|---:|']
    for name, row in result['contrasts'].items():
        lines.append(f"| {name}: {row['treatment']} − {row['control']} | {effect(name,'win_fraction')} | {effect(name,'loss_fraction')} | {effect(name,'arrival_under4_fraction')} |")
    lines += ['',
        '| Timing effect | Original vs legacy baseline: win change | Cadence-10 comparison: win change |',
        '|---|---:|---:|',
        f"| Opponent protocol, own d=0 | {effect('opponent_delay_d0','win_fraction')} | {effect('lag_only_d0','win_fraction')} |",
        f"| Opponent protocol, own d=27 | {effect('opponent_delay_d27','win_fraction')} | {effect('lag_only_d27','win_fraction')} |",
        f"| Own d=27 versus d=0, zero-lag opponent | {effect('latency_undelayed','win_fraction')} | {effect('latency_undelayed_matched','win_fraction')} |", '',
        'The left column changes opponent lag plus legacy rollout cadence/path. The right compares the same enabled native path and 10-tick opponent cadence. S0−R0 and S27−R27 isolate decision-to-execution lag. All paired comparisons use the same completed seeds; partial-control comparisons subset the corresponding lagged arm.', '',
        f"The legacy-protocol loss-cost difference-in-differences `(U27−U0)−(S27−S0)` is **{100*r['delta']:+.2f} pp**, 95% CI [{100*r['ci95'][0]:+.2f}, {100*r['ci95'][1]:+.2f}]. A positive value means the zero-lag opponent inflated the measured latency cost in this sample.", '',
        matched_text, '',
        'The historical ledger +7.3 pp and S6 +2.7 pp use different samples/settings. This factorial contrast remeasures the asymmetry; it does not retroactively correct those estimates.', '',
        '[Exported paired-effects figure](paired-effects.svg) ([PNG](paired-effects.png)).', '',
        '## Behavior', '',
        '| Arm | Submission silence | Execution silence | No submission after execution | Pending-blocked polls |',
        '|---|---:|---:|---:|---:|']
    for arm in result['arms']:
        keys = ['post_submission_no_followup_27ticks_fraction','post_execution_no_followup_27ticks_fraction',
                'post_play_no_submission_27ticks_fraction','pending_blocked_decision_fraction']
        lines.append('| '+arm+' | '+' | '.join(pct(arm,k) for k in keys)+' |')
    lines += ['',
        'Silence uses complete 27-tick windows. Submission silence measures the next commitment; execution silence measures the next accepted server-visible play. The third column asks whether a new command was submitted after execution. Under-4 arrivals use the existing loss-review lane-incursion-onset definition and physical HUD elixir; pending-spend reservations are not subtracted from that behavior metric. All behavior ratios pool event numerators/denominators and retain paired-seed uncertainty.', '',
        'Additional loss-review metrics and paired differences are in [results.json](results.json), including capped response latency, affordability, low-reserve win-condition plays, active-threat plays, inter-play gaps, rejections and time at max elixir.', '',
        '## Arms and implementation', '',
        '- U0/U27: our delay 0/27; opponent delay 0, capacity 1.',
        '- S0/S27: our delay 0/27; opponent decision-to-execution lag 22, cadence 10, capacity 4.',
        '- N2/N4: S27 with our outstanding-command capacity 2/4.',
        '- I0/IF: S27 with released-v1 current-state/forward-state imitation proposals.',
        '- R0/R27: enabled S0/S27 native path, opponent lag 0, cadence 10, capacity 4 (nonbinding at zero lag), our delay 0/27.', '',
        'Original U arms retain legacy opponent rollout cadence 3; physical opponent cadence is 10 in every arm. Enabled S/N/I/R rollouts use opponent cadence 10 and own continuation cadence 3. Own physical decision polls are every 10 ticks. The two R controls were added on a code-audit finding before outcomes were inspected, with coordinator approval. [Config](lag-controls-config.json), [timestamp and SHA receipt](receipts/lag-controls-addition.json), [progress](PROGRESS.md).', '',
        'The opponent lag is applied in physical games and native search rollouts. True pending opponent commands live outside BattleState and never enter observation, the accepted-event stream, or the planner root. Rollouts begin without that queue and generate their own hypothetical future commands. This models response lag; it does not shift the observation of a command after execution.', '',
        'Within the fixed-cost C56 card scope, own reservations retain action, card, cost and execution tick individually. Available elixir subtracts all pending costs; occupied slots remain masked. Roots retain the physical unspent own HUD and execute every known pending command at its due tick through the engine exactly once. Completion releases only its reservation. No premature refill, duplicate slot spend or physical refund is introduced.', '',
        'Forward proposals project the planner’s own fair hypothetical root at t+27, including known own pending executions and newly simulated opponent commands. D1 advances using only hypothetical public accepted events. A proposal must also pass the current mask with the same card in the same slot. Both imitation arms use the gate-(b) matched-count replacement pattern: top-8 proposals replace random extras while WAIT, script candidates and the exact baseline candidate count remain available.', '',
        'Flags default off: `symmetric_opponent=False`, `max_outstanding=1`, `forward_prior=False`. Enabled opponent lag/cadence are parameterized as `opponent_delay` / `opponent_interval`. The native method is additive; legacy S6 scoring delegates unchanged when flags are off. The implementation supplies the simulation planner/runtime adapter; the live pixel-verification actuator is not replaced.', '',
        '## Validation and provenance', '',
        '- [24 pytest checks passed](receipts/final-tests-r2.log), including equality of every public observation and confidence field with/without pending opponent commands through tick 22, on both seats. The command becomes visible only when it executes.',
        '- [Native preflight passed on both seats](receipts/pending-preflight.json): flags-off score parity, native single-channel parity, two simultaneous pending commands, four commands at ticks 10/20/27/35, exact elixir/card conservation, root immutability, t+27 endpoint execution, matched legal proposal counts and unchanged current D1.',
        '- Eight-arm smoke completed terminal games; full study checks reject duplicate games, forbidden roles, nonterminal games, seed-exclusion collisions and incomplete original pairing. Two reducer checks verify distinct legacy/matched-cadence effects and correct seed-subsetting for partial controls.', '',
        f"Seed namespace: `2**48 + 50000 + i`; {result['paired_seeds']:,} paired indices. Five train-catalog deck archetypes form 25 matchup cells, seats alternate, and three opponent styles rotate every 25 seeds. Opening decks/shuffle, seat, style and helper seeds match across arms. Own sampled opponent state and rollout RNG remain independent of the physical opponent’s hidden state. Abilities are disabled on both physical sides. The same fixed 160-tick search horizon and candidate budget are used; this is not a general d-sweep and does not duplicate the parallel candidate-coverage/reserve-leaf exploration.", '',
        'Checkpoint: released main02 v1 EMA, SHA256 `d77005d59d6ed40ce7f9bfcfde569b54958bebf056e00653b10dcee3957272ed`; task copy read-only, CPU fp32, in-memory temperature 1. Frozen gate-(b)/(c) artifacts, seeds and driver files are untouched. No training or raw eval/heldout data enter the sims.', '',
        'Provenance limitation: while locating checkpoint provenance, the implementation agent inadvertently opened the first 65 lines of the existing `imitation/RESULTS-v1-offline.md`, which includes summarized gate-(a) heldout outcomes. No raw heldout data were opened or loaded, and those summarized outcomes did not inform arm definitions, checkpoint choice or comparisons. This exploration is not outcome-blinded.', '',
        f"Bootstrap: {result['bootstrap']['draws']:,} shared paired-seed resamples; pooled numerator/denominator ratios; percentile 95% CIs, pointwise and uncorrected. Bootstrap RNG is `2**48 + 59001`. Null estimates and intervals spanning zero are reported as such. Results apply to these train-deck scripted-opponent sims, not human matches or frozen imitation gates.", '',
        '## Compute and practical limits', '',
        '| Host | Games | Maximum pool workers | Worker CPU hours | Mean active cores | Pool utilization incl. pauses/startup/tails | GPU p10/p50/p90 |',
        '|---|---:|---:|---:|---:|---:|---|']
    for host, row in sorted(audit['hosts'].items()):
        gpu = '/'.join(f'{v:.0f}%' for v in row['gpu_p10_p50_p90']) if row['gpu_samples'] else 'unrecorded'
        lines.append(f"| {host} | {row['games']:,} | {row['max_workers']} | {row['worker_cpu_seconds']/3600:.2f} | {row['mean_active_cores_over_shard_wall']:.2f} | {100*row['pool_utilization_over_shard_wall']:.1f}% | {gpu} |")
    lines += ['',
        f"Observed worker CPU totals **{audit['worker_cpu_seconds']/3600:.2f} hours**, a lower bound including verified technical stops. Home 08 throughput guards recorded zero below-95% samples across {audit['hosts']['127x08']['throughput_measured_samples']:,} measured samples; p10/p50/p90 throughput ratios were 0.9899/0.9974/1.0063. Host 16 recorded six below-threshold samples and paused under the new policy; the other leases lack an interval-rate baseline.", '',
        'Leased work used wrapper v2 on the six allowed hosts, whole-job declarations ≤30, 25-seed shards initially, then five-seed original shards after the cap reductions and 25-seed/two-arm control shards and lease-local paths. Refusals and wrapper failures are preserved. An initial PSS refusal on 16 moved its unstarted primary block to home 08. Detached pre-hotfix supervision failed twice; supported foreground admission then worked, and new launches used the coordinator’s repaired wrapper. No cap bypass or wrapper modification. Host 05 only orchestrated and handled compact text/receipts. Coordinator priority updates then closed 13/15 completely; both drained within ten minutes and received no new launches. The later actual 00:10Z update declared 11 down and authorized its lost block to rerun elsewhere. Current caps became 13/15=10, 09/14=15, 16 ≤30 and home 08=12 after draining. 16 used 16 workers following a declared 12 GB PSS stop (13.09GB peak), then 26 workers with 18 GB declared PSS after the throughput-policy update; its 103 completed games were preserved and only verified orphan workers cleaned up. A technical guard restart and the cap reductions preserved completed games and schedules. An earlier 16 restart was refused for an existing Clasher process below the nice minimum; that refusal was accepted, and later coordinator-authorized admission succeeded.', '',
        'The final 16 lane also accepted an aggregate-PSS admission refusal and retired; its unstarted seeds were requeued on the remaining hosts. Later nice-minimum admissions refused 09/15; both main lanes retired with no owner process altered. After the coordinator fixed the tempo-horizon exec-nice cause and explicitly authorized conditional re-admission, read-only checks cleared 09/15 for controls. Every leased control admission first checks for any Clasher process below nice 10; failed checks wait without attempting admission. The wrapper retains its own admission checks. The compute total is a lower bound: it includes stopped-attempt CPU, while the down 11 second attempt is unavailable and successful initialization/build/test CPU is excluded. Utilization uses the sum of workers×attempt wall time across changing caps. Early shards used the original utilization guard, which the perf audit found ineffective. Following the coordinator’s 00:46Z authorization, the shared guard samples every two seconds and can pause only for a fresh GPU-job interval throughput more than 5% below an explicitly measured baseline. Idle GPUs and missing/stale metrics are exempt; GPU utilization is receipt-only. New shards use SCHED_IDLE and refresh their affinity away from observed active GPU-job/feeder cores and SMT siblings. The A/B owner measured 30-minute coexistence on 08, while this task kept 08 drained through the qualification. Lease v4 capture logs supplied no interval fps or measured baseline, so those shards rely on idle scheduling/affinity and do not claim validated throughput protection. Continuous GPU utilization ≥80% is not claimed. [compute-audit.json](compute-audit.json) records below-threshold samples, monitor-reported paused worker-seconds, stopped attempts, utilization and completed shards. Brief verified idle-GPU drains on 13/15 can overstate monitor-reported paused time. The coordinator ordered an early lease drain at 03:00Z; all leased launch caps were set to zero at 03:00:44Z. The named 09/p1050 and 14/p0925 reservations finished naturally and were verified absent at 03:04:53Z. The final leased shard exited successfully at 03:06:04Z; registry and process checks at 03:06:50Z confirmed zero own reservations/workers on all five leased hosts ([receipt](receipts/early-leases-clear.json)). Remaining controls ran on home 08 with at most 12 pool workers; new home 03/01 allowances were unnecessary. All controls completed by 03:14:25Z; home 08 sim/reduction work was verified clear at 03:19:49Z ([completion receipt](receipts/completion.json)), before its 04:55Z handover, and the leased 04:30Z hard exit remains binding.', '',
        'The A/B owner’s sequential 08 coexistence qualification measured 237.66→233.99 fresh interval rows/s with 16 idle sims, a 1.55% slowdown; 5,000 three-step moving-block bootstrap ratio CI [0.9794, 0.9898], 25 fresh steps per phase. This is a small measured loss within 5% tolerance, not zero loss. It recorded 0/410 paused samples and 350 completed qualification games; background rsync traffic occurred in both phases. Qualification receipt: [../search-ab/receipts/coexistence-summary.json](../search-ab/receipts/coexistence-summary.json). The qualification used the A/B native runtime; our isolated native binary differs, so it does not certify our exact binary. Following confirmed treatment drain, this task resumed 08 with 12 workers and a three-step median guard using the measured 237.66 rows/s baseline.', '',
        'On 16, the own-sim-drained T11 control measured 12,147.40 interval rows/s from 40 fresh steps over 38 seconds; the guard compares 10-step medians against 95% of that baseline. The baseline and its source field are retained in [receipts/throughput-baseline16.json](receipts/throughput-baseline16.json). Measured throughput ratios and guard coverage are retained in compute-audit.json; missing metrics on the other leases are disclosed rather than treated as successful protection.', '',
        'New-shard decision latency uses an atomic shared active-wall clock that removes completed and ongoing GPU pauses; raw wall and process CPU are retained. Legacy pause-inflated wall times are separated and cannot be retrospectively corrected exactly. Fixed-work outcomes have no wall-clock deadline. The A/B owner handles opt-in CPU-time decision-budget producer/consumer changes in its own simulator/search files. CPU quantiles cover all games, while active-wall quantiles cover only corrected-clock games in results.json. These timings do not establish compliance with a live 200ms deadline or validate multi-command pixel verification.', '',
        'Full reduced per-game files, schedules and game hashes remain under `reports/explore/delay-fixes/` on home 08; shard copies and the isolated build remain lease-local. Compact results, source hashes, validation and wrapper receipts are retained here. See [README.md](README.md) for methods, [launch.json](launch.json) for initial accounting and [launch-throughput-v5.json](launch-throughput-v5.json) for the original controller and [launch-lag-controls.json](launch-lag-controls.json) for the controls. [source-hashes.json](source-hashes.json) identifies the isolated binary/source snapshot. Prior unstarted offsets are superseded by the final manifest.', '',
        '## Recommended L2-v4 amendments', '',
        (a.root / 'amendments.md').read_text().strip(), '',
    ]
    (a.root / 'RESULTS.md').write_text('\n'.join(lines))


if __name__ == '__main__':
    main()
