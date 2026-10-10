"""Render only after complete paired outcomes and execution/GC audits."""
import html,json
from pathlib import Path
D=Path(__file__).resolve().parent

def interval(point,ci,scale=1):
    return f'{point*scale:.2f} [{ci[0]*scale:.2f}, {ci[1]*scale:.2f}]'

def main():
    r=json.loads((D/'results.json').read_text());g=json.loads((D/'gc-maintenance.json').read_text());e=json.loads((D/'receipts/execution.json').read_text());pin=json.loads((D/'receipts/runtime-pin.json').read_text())
    assert r['checks']['games']==1800 and r['paired_seeds']==600 and e['complete']
    retention=r['retention'];pct=None if retention['point'] is None else retention['point']*100
    if retention['point'] is None:
        verdict='Retention is undefined because the paired K4 gain is nonpositive.'
    elif retention['lower_ci_target_met']:
        verdict='K2 retains at least 80% of K4’s gain, supported by the paired 95% interval.'
    elif retention['upper_ci_below_target']:
        verdict='K2 falls below the 80% retention target; the paired 95% interval also lies below it.'
    elif retention['point_target_met']:
        verdict='K2 meets the 80% retention target at the point estimate, but the paired 95% interval does not establish it.'
    else:
        verdict='K2 misses the 80% target at the point estimate; the paired 95% interval leaves the target uncertain.'
    text=f'# K2 two-thread anytime W\n\nCompleted {r["utc"]}. **{verdict}**\n\n'
    if pct is not None:text+=f'**Retention: {interval(retention["point"],retention["ci95"],100)}%.** Numerator (K0−K2) {retention["numerator_loss_pp"]:.2f} pp; paired reference denominator (K0−K4) {retention["denominator_loss_pp"]:.2f} pp. Historical K4/K0 losses 19.3%/46.5% provide context only; this study uses its own paired K4 anchor.\n\n'
    text+='Exploration only: 1,800 terminal games, 600 fresh paired seeds across K2-200/K0-200/K4-200, sealed v1 opponent, symmetric d=27/capacity1, five decks/25 matchups/alternating seat. No Mac, live or heldout access.\n\n'
    text+='| Arm | W/L/D | Loss %, 95% CI | Loss change vs K0, pp, 95% CI | Cutoff %, 95% CI | Latency p50/p95/p99/max, ms |\n|---|---:|---:|---:|---:|---:|\n'
    for arm,v in r['arms'].items():
        w=v['wall_ms'];text+=f'| {arm} | {v["wins"]}/{v["losses"]}/{v["draws"]} | {interval(v["loss_pct"],v["loss_ci_pct"])} | {interval(v["loss_change_pp"],v["loss_change_ci_pp"])} | {interval(v["cutoff_pct"],v["cutoff_ci_pct"])} | {w["p50"]:.1f}/{w["p95"]:.1f}/{w["p99"]:.1f}/{w["max"]:.1f} |\n'
    c=r['paired_K2_minus_K4'];text+=f'\nK2−K4 loss difference: {interval(c["loss_change_pp"],c["ci95_pp"])} pp. Paired 80%-target contrast: {interval(retention["target_contrast_pp"],retention["target_contrast_ci_pp"])} pp; positive favors retaining ≥80%.\n\n'
    text+='| Arm | Decisions | >200 ms count / % | Positive overrun p50/p95/p99/max, ms | Extra-delay tick counts | Cut returns >208 ms | CPU hours |\n|---|---:|---:|---:|---|---:|---:|\n'
    for arm,v in r['arms'].items():
        w=v['positive_overrun_ms'];text+=f'| {arm} | {v["decisions"]} | {v["overrun_count"]} / {v["overrun_pct"]:.3f}% | {w["p50"]:.3f}/{w["p95"]:.3f}/{w["p99"]:.3f}/{w["max"]:.3f} | {json.dumps(v["overrun_ticks_hist"],sort_keys=True)} | {v["cut_past_deadline_plus_reserve_count"]} | {v["game_cpu_hours"]:.2f} |\n'
    text+='\nAll positive wall overruns are retained and charged as ceil(overrun×20) extra ticks to command due time, own availability and timed waits. Timer includes public observation, v1 fallback, belief, candidates, public root, scoring and submission; scoring cutoff192 ms reserves8 ms. Partial/late roots never count; the frozen collector returns without draining. Latencies cover own decision calls; intermediate policy/maintenance polls are excluded.\n\n'
    text+='| Arm | GC count (generation counts) | GC p50/p95/p99/max, ms | GC >50/250/500 ms counts | GC ms per game minute | During decision |\n|---|---:|---:|---:|---:|---:|\n'
    for arm,v in g['arms'].items():
        w=v['pause_ms'];counts='/'.join(str(v['count_above_ms'][str(x)]) for x in (50,250,500));text+=f'| {arm} | {v["count"]} ({json.dumps(v["generation_counts"],sort_keys=True)}) | {w["p50"]:.3f}/{w["p95"]:.3f}/{w["p99"]:.3f}/{w["max"]:.3f} | {counts} | {v["pause_ms_per_game_minute"]:.2f} | {v["during_decision_window_count"]} |\n'
    text+='\nGC maintenance is in whole-game wall/CPU, but does not advance simulated ticks or incur decision lateness. Frozen instrumentation lacks pause timestamps and opportunity/channel traces: **live poll overlap and the resulting loss penalty are unknown**. Zero collections inside a decision does not establish zero delayed live polls. A deployment still needs loaded Mac full-pipeline timing, timestamped maintenance/poll gaps, warmup GC freeze/threshold experiments with retained-memory/equality checks, and three available cores for K2 (two search workers plus main). No Mac-core sufficiency or distillation retirement follows automatically.\n\n'
    text+=f'Statistics: {r["bootstrap"]["reps"]:,} shared paired-seed percentile bootstrap resamples, RNG{r["bootstrap"]["seed"]}; unadjusted pointwise95% CIs. Loss means opponent wins; draws remain separate. Retention=(K0−K2)/(K0−K4); {retention["valid_bootstrap_replicas"]:,} valid replicas, {retention["nonpositive_denominator_replicas"]} nonpositive-denominator replicas omitted from ratio CI. Cutoff/overrun-rate intervals resample per-game numerator/denominator totals. Each matchup/seat has12 paired seeds.\n\n'
    q=json.loads((D/'receipts/qualification.json').read_text());b=json.loads((D/'receipts/belief-qualification.json').read_text())
    text+=f'Qualification: 1/2/4 threads each exact screen8 actions/candidates/scores125/125; one/two/four equality125/125; zero-budget root immutability125/125. {b["histories"]} public histories match frozen belief arrays/ledger/samples/RNG with deadline ON/OFF. Injected-clock, two/four-thread no-drain/reuse/late-score, lateness and GC tests pass; see [test receipt](receipts/tests.txt). Excluded24-game smoke is terminal/audited.\n\n'
    text+=f'Source: K-v2 freezes e546e181/75e2513d/dd692ef9; K2 freeze {pin["freeze_commit"]}. Scorer only widens accepted thread counts. Native SHA44874fd6, immutable sealed checkpoint/v1 adapter and combat source retained. Reporting seeds4503602307370496+[0,600), excluded smoke4503602317370496+[0,8); [seed audit](seed-audit.json) proves disjointness from K/K-v2/X/G/R3 and noise-ceiling reservations including helper offsets. [Plan](plan.json), [qualification](receipts/qualification.json), [raw-result hashes/statistics](results.json), [GC supplement](gc-maintenance.json), [source/process exit audit](receipts/execution.json), [runtime pin](receipts/runtime-pin.json), [progress/release](PROGRESS-K2.md).\n\n'
    text+=f'Fleet:03 only,nice10/SCHED_OTHER,11 nonoverlapping five-core slots0–54 (8 if console user), narrowed per game to K2=3,K0=1,K4=5 physical cores; supervisor59. Qualification alone on60. No timing on60–63/SMT, no cache/controller changes, G STOP-03 retained. Minimum observed available memory {e["min_memavailable_GiB"]:.2f} GiB; all owned reporting PGIDs{e["fully_vacated_pgids"]} fully exited, no pauses/source mismatches. Raw games/logs remain03:/mpac/sdicks02/jobs/clasher/k2-20261010-r1/reporting. Release requires all other owned qualification/smoke/reduction processes also absent.\n'
    (D/'RESULTS.md').write_text(text)
    # Self-contained final visual uses the same audited summary; no network assets.
    rows=''.join(f'<tr><td>{html.escape(a)}</td><td>{v["loss_pct"]:.2f}% [{v["loss_ci_pct"][0]:.2f}, {v["loss_ci_pct"][1]:.2f}]</td><td>{v["loss_change_pp"]:.2f} pp</td><td>{v["cutoff_pct"]:.2f}%</td><td>{v["wall_ms"]["p99"]:.1f} ms</td></tr>' for a,v in r['arms'].items())
    retained='undefined' if pct is None else interval(retention['point'],retention['ci95'],100)+'%'
    (D/'results.html').write_text(f'''<!doctype html><html><meta charset="utf-8"><title>K2 paired strength retention</title><style>body{{font:17px system-ui;background:#101827;color:#e2e8f0;margin:0;padding:34px}}main{{max-width:940px;margin:auto}}h1{{font-size:32px}}.metric{{font-size:40px;color:#7dd3fc}}p{{line-height:1.5}}table{{width:100%;border-collapse:collapse;margin:24px 0}}td,th{{padding:12px;text-align:left;border-bottom:1px solid #334155}}small{{color:#94a3b8}}</style><main><h1>K2: two search workers, 200 ms</h1><div class="metric">Retention {html.escape(retained)}</div><p>{html.escape(verdict)}</p><table><tr><th>Arm</th><th>Loss / paired 95% CI</th><th>Change vs K0</th><th>Cutoffs</th><th>Latency p99</th></tr>{rows}</table><p>600 shared seeds per arm · v1 opponent · symmetric delay27 · honest overrun delays · nice10/SCHED_OTHER on03.</p><small>Exploration on fleet CPUs. K2 uses3 physical cores total. Mac full-pipeline timing and live GC maintenance penalties remain unqualified.</small></main></html>''')
    print(verdict)
if __name__=='__main__':main()
