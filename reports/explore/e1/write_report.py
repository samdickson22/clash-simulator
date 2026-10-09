"""Write public compact summaries from fully audited aggregate E1 results."""
import argparse
import json
from pathlib import Path


def pct(e):
    if e['value'] is None: return 'n/a'
    ci=e['ci95'];return f"{e['value']*100:.2f}% [{ci[0]*100:.2f}, {ci[1]*100:.2f}]" if ci else f"{e['value']*100:.2f}%"


def pp(e):
    if e['value'] is None:return 'n/a'
    ci=e['ci95'];return f"{e['value']*100:+.2f} [{ci[0]*100:+.2f}, {ci[1]*100:+.2f}] pp"


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--results',type=Path,required=True);ap.add_argument('--out',type=Path,required=True)
    a=ap.parse_args();r=json.loads(a.results.read_text());arms=r['arms'];est=r['estimates'];con=r['contrasts'];final='bR' in arms
    labels={'a0':'Deadline baseline vs baseline','aW':'Deadline W vs baseline','b0':'Baseline vs v1','bW':'W vs v1','bR':'W + reserve floor vs v1'}
    lines=['# E1 CPU checks — '+('complete' if final else 'arms 1–4 complete; reserve arm pending'),'',
        f"Exploration lane; frozen plan before games, no PREREG. **{r['terminal_games']:,} terminal games**, {r['paired_seeds']} matched seeds, five train decks / 25 matchups, alternating seats, symmetric d=27 and capacity one. Shared 5,000 paired-seed bootstrap resamples; pointwise 95% percentile CIs. Draws count half for score and separately from losses.",'',
        '| Arm | W/L/D | Loss rate, 95% CI |','| --- | ---: | ---: |']
    for arm in arms:
        o=r['outcomes'][arm];lines.append(f"| {labels[arm]} | {o['wins']}/{o['losses']}/{o['draws']} | {pct(est[arm]['loss'])} |")
    lines+=['',f"**E1a:** deadline W minus deadline baseline loss change **{pp(con['aW_minus_a0']['loss'])}**.",
        f"**E1b:** W minus baseline against v1 loss change **{pp(con['bW_minus_b0']['loss'])}**. W win rate against v1 **{pct(est['bW']['win'])}**; score **{pct(est['bW']['score'])}**.",'',
        '| Deadline arm | Search cutoff hits | v1 fallbacks | Actual wall >200 ms |','| --- | ---: | ---: | ---: |']
    for arm in ('a0','aW'):
        lines.append(f"| {labels[arm]} | {pct(est[arm]['deadline_hit'])} | {pct(est[arm]['fallback'])} | {pct(est[arm]['wall_overrun'])} |")
        lines.append(f"| {labels[arm]}, opponent | {pct(est[arm]['opponent_deadline_hit'])} | {pct(est[arm]['opponent_fallback'])} | {pct(est[arm]['opponent_wall_overrun'])} |")
    lines+=['', 'Every deadline decision includes public observation, cached v1 policy sample, belief, candidates, root reconstruction, scoring and submission. Scoring reserves 8 ms for return. Native cancellation checks each physical tick; only complete roots finished before cutoff are eligible. The actual wall-overrun column exposes OS scheduling/return residuals under SCHED_IDLE; these runs are not hard-real-time OS qualification. Partial/late roots never count. Fallback actions use the sealed v1 player at T=1; search runs on one pinned core.', '',
        '| Arm | Full decision wall p50/p95/p99, ms | CPU p50/p95/p99, ms | W decisions/s/core |','| --- | ---: | ---: | ---: |']
    for arm in arms:
        t=r['latency'][arm];w=t['wall'];c=t['cpu'];rate=r['throughput'][arm]['decisions_per_core_second']
        lines.append(f"| {labels[arm]} | {w['p50_ms']:.1f}/{w['p95_ms']:.1f}/{w['p99_ms']:.1f} | {c['p50_ms']:.1f}/{c['p95_ms']:.1f}/{c['p99_ms']:.1f} | {rate:.3f} |")
    lines+=['', f"**Teacher sizing:** unlimited W against v1 measured **{r['throughput']['bW']['decisions_per_core_second']:.3f} decisions/sec/core**, from summed CPU time for complete own decision calls after each game's first decision. This includes public reconstruction and v1 sampling, and excludes the intermediate five-tick policy maintenance polls and other game work. It is a sampled-state rate, not a guaranteed generation throughput.",'',
        '| Arm | Under-4 arrivals | No affordable defender in hand | Low-minus-high arrival subsequent damage risk |','| --- | ---: | ---: | ---: |']
    for arm in arms:
        lines.append(f"| {labels[arm]} | {pct(est[arm]['arrival_under4_fraction'])} | {pct(est[arm]['no_affordable_defender_in_hand_fraction'])} | {pp(r['associations'][arm]['low_minus_high_damage_risk'])} |")
    if final:
        lines+=['',f"**Reserve intervention:** floor minus W loss change **{pp(con['bR_minus_bW']['loss'])}**; under-4 arrival change **{pp(con['bR_minus_bW']['arrival_under4_fraction'])}**.",
            '', '**Causal finding:** '+r['causality_finding'], '',
            'The intervention forbids non-defensive plays leaving less than four elixir while the public opponent-elixir estimate is at least five. A defensive response is an own-half, same-lane placement within six tiles of a qualifying living public enemy troop (across the bridge or within six tiles of a living own crown tower). WAITs remain eligible. The candidate filter changes no scoring/prior/horizon and defaults OFF. Its causal interpretation applies to this rule against v1; damage-risk and loss-stratified ledger comparisons remain observational. Incursion arrivals and complete eight-second damage windows use the existing loss-review definitions.']
    else:lines+=['','The fifth arm is frozen and runs last. No causal reserve conclusion is reported before it completes.']
    lines+=['', 'Fair inputs: public board, own HUD, accepted public events and independent sampled hidden-model RNG. v1 uses the unmodified sealed gate(c) adapter at five-tick cadence through blocked polls; delayed capacity-one command execution stays outside it. Physical abilities are disabled. All completed games are retained; the separate two-seed smoke is excluded. Per-game telemetry and raw logs remain under `/mpac` on compute hosts.', '',
        'Validation: frozen OFF 250/250 score/action/trace parity; E1 OFF symmetric 125/125; W 125/125 frozen choices/scores; v1 same-state byte/action 250/250; zero-budget native root immutability 125/125; 12 injected-clock/filter tests passed. Library and sealed adapter hashes are pinned in [runtime receipts](receipts/runtime-pin.json).', '',
        f"Freeze commit **`bfb9b107`**; implementation **`47e97277`**. Config SHA256 **`{r['config_sha256']}`**. [Counts, CIs, rate denominators and audits](results.json); [execution progress](PROGRESS.md). Child game CPU: **{r['game_cpu_seconds']/3600:.2f} hours**. E1 ran on03/04 at nice10/SCHED_IDLE, detached setsid, with process/memory supervision; final per-host execution receipts report measured peaks/floors."]
    a.out.write_text('\n'.join(lines)+'\n')
    summary=[f"E1: {r['terminal_games']:,} terminal games /600 paired seeds (symmetric d=27).",
      f"Deadline W loss {pct(est['aW']['loss'])}; baseline {pct(est['a0']['loss'])}; paired change {pp(con['aW_minus_a0']['loss'])}.",
      f"W deadline hits {pct(est['aW']['deadline_hit'])}, v1 fallback {pct(est['aW']['fallback'])}; actual wall overruns {pct(est['aW']['wall_overrun'])}.",
      f"Against v1, W wins {pct(est['bW']['win'])}; W−baseline loss change {pp(con['bW_minus_b0']['loss'])}."]
    if final:summary +=[f"Reserve floor: loss change {pp(con['bR_minus_bW']['loss'])}; under4 change {pp(con['bR_minus_bW']['arrival_under4_fraction'])}.",r['causality_finding']]
    summary +=[f"Unlimited W measured {r['throughput']['bW']['decisions_per_core_second']:.3f} decisions/sec/core. Freeze bfb9b107; implementation47e97277. 95% paired bootstrap CIs; exploration evidence."]
    text='\n\n'.join(summary)+'\n';assert len(text.split())<200,len(text.split())
    (a.out.parent/('SUMMARY.md' if final else 'SUMMARY-arms1-4.md')).write_text(text)

if __name__=='__main__':main()
