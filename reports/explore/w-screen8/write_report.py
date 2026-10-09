"""Render aggregate paired results; raw games remain outside the repository."""
import json
from pathlib import Path
import sys

p=Path(sys.argv[1]);r=json.loads((p/'results.json').read_text())
labels={'0':'Baseline','W':'Full W','S8':'Screen8'}
def ci(x,scale=100):
    if x['value'] is None or x['ci95'] is None:return 'unavailable'
    v=x['value']*scale;lo,hi=[a*scale for a in x['ci95']]
    return f'{v:.2f} [{lo:.2f}, {hi:.2f}]'
def diff(x):
    v=x['difference']*100;lo,hi=[a*100 for a in x['ci95']]
    return f'{v:+.2f} [{lo:+.2f}, {hi:+.2f}]'
main=['# W-screen8 fresh paired outcome check','',
    '600 fresh paired seeds; symmetric d=27; 5 decks/25 matchups; alternating seats; 1,800 terminal games.',
    '', '| Arm | W/L/D | Loss %, paired 95% CI |', '|---|---:|---:|']
for a in r['arms']:
    o=r['outcomes'][a];main.append(f"| {labels[a]} | {o['wins']}/{o['losses']}/{o['draws']} | {ci(r['estimates'][a]['game_loss_fraction'])} |")
main += ['',f"Loss changes, pp (paired 95% CI): screen8−baseline **{diff(r['paired_contrasts']['S8']['game_loss_fraction'])}**; full W−baseline **{diff(r['paired_contrasts']['W']['game_loss_fraction'])}**; screen8−full W **{diff(r['paired_contrasts']['S8_minus_W']['game_loss_fraction'])}**.",
    '',f"**{'PASS' if r['pass_criterion_met'] else 'FAIL'}:** screen8−full W upper CI {'≤' if r['pass_criterion_met'] else '>'} +3 pp; 5,000 paired-bootstrap resamples.",
    '', '| Full-decision wall latency, ms | p50 | p95 | p99 |', '|---|---:|---:|---:|']
for a in r['arms']:
    t=r['latency'][a]['wall'];main.append(f"| {labels[a]} | {t['p50_ms']:.1f} | {t['p95_ms']:.1f} | {t['p99_ms']:.1f} |")
main += ['', 'Full-decision timings include observation through submission under fleet load; no live qualification.',
    '', '[Metrics/CPU latency](METRICS.md); [counts/CIs](results.json).',
    '', 'Default OFF. Parity: OFF 250/250 score/action/trace; ON 125/125 choices/retained scores; 54 tests. Runtime patch: none.',
    '', 'Commits: freeze `d0e9dc2f`; baseline `f9d3b454`; implementation `59454e1a`/`62044189`; report SHA in PROGRESS.']
(p/'RESULTS.md').write_text('\n'.join(main)+'\n')
metrics=['# Paired loss-review metrics','', 'Pooled ratios resampled by paired seed; 5,000 shared bootstrap resamples. Percentages except leakage (elixir/minute). Exact numerators/denominators, expensive-card opportunity counts and all arm contrasts are in results.json.',
    '', '| Metric | Baseline | Full W | Screen8 |', '|---|---:|---:|---:|']
for m in ('arrival_under4_fraction','no_affordable_defender_in_hand_fraction','defender_not_in_hand_fraction','time_at_max_fraction','leaked_elixir_lower_bound_per_minute','rejected_play_fraction'):
    scale=1 if m=='leaked_elixir_lower_bound_per_minute' else 100
    metrics.append('| '+m+' | '+' | '.join(ci(r['estimates'][a][m],scale) for a in r['arms'])+' |')
metrics += ['', '| Arm / card | Affordable at in-hand opportunity %, 95% CI | Accepted plays / deck-minute, 95% CI |', '|---|---:|---:|']
for a in r['arms']:
    for c in ('Xbow','Giant','Rocket','Fireball','Log'):
        metrics.append(f"| {labels[a]} / {c} | {ci(r['estimates'][a]['affordable_hand_fraction:'+c])} | {ci(r['estimates'][a]['card_per_deck_minute:'+c],1)} |")
metrics += ['', '| Arm | Full-decision wall p50 / p95 / p99, ms | CPU p50 / p95 / p99, ms | Wall >200 ms, % | Decisions |', '|---|---:|---:|---:|---:|']
for a in r['arms']:
    w=r['latency'][a]['wall'];c=r['latency'][a]['cpu']
    metrics.append(f"| {labels[a]} | {w['p50_ms']:.1f} / {w['p95_ms']:.1f} / {w['p99_ms']:.1f} | {c['p50_ms']:.1f} / {c['p95_ms']:.1f} / {c['p99_ms']:.1f} | {w['over200_fraction']*100:.2f} | {w['decisions']} |")
metrics += ['', 'Affordability is measured at decision opportunities, which timed WAIT reduces. Accepted plays include zero-use deck games. Arrival is lane-incursion onset; defender availability is the generic non-spell/non-win-condition hand proxy. Leakage is a conservative cap-interval lower bound. Scored opportunities include the balanced scan for every initial candidate, including plays omitted from full refinement. The reference screen adapter does not tally wait_counts; its empty tally is not zero WAITs.',
    '', f"Completed reporting game CPU: {r['completed_game_cpu_seconds']/3600:.2f} core-hours. Startup, builds and qualification are outside this subtotal.",
    '', 'The study uses the frozen w-confirm screen8 adapter and private WAIT native binary; the production batch implementation is separately proven exact on the frozen 125-state corpus. Games use sampled public roots and scripted rollout futures, with a physical baseline search opponent. No reporting-seed tuning or game replacement. Loaded SCHED_IDLE timing is descriptive; no image/sensor/network live admission is claimed.']
(p/'METRICS.md').write_text('\n'.join(metrics)+'\n')
print('Aggregate report written; RESULTS words:',len((p/'RESULTS.md').read_text().split()),flush=True)
