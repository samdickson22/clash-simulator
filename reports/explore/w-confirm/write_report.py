"""Write the final report from complete reductions, never partial outcomes."""
import json
from pathlib import Path

DEST=Path(__file__).resolve().parent


def pct(v): return '—' if v is None else f'{100*v:.2f}%'
def interval(e,percent=True):
    if e['value'] is None:return '—'
    scale=100 if percent else 1
    return f"{e['value']*scale:.2f} [{e['ci95'][0]*scale:.2f}, {e['ci95'][1]*scale:.2f}]"


def main():
    r=json.loads((DEST/'results.json').read_text())
    l=json.loads((DEST/'latency-results.json').read_text())
    compute=json.loads((DEST/'receipts/compute.json').read_text())
    assert r['paired_seeds']==600 and all(r['validation'].values())
    arms=['0','W','H16','WW'];e=r['estimates']
    lines=['# W confirmation and latency — 2026-10-09','',
        '**Frozen exploration lane; 600 paired fresh seeds per main arm.** '
        'Search opponents on both sides, d=27 on both sides, five train decks / 25 matchups, '
        'alternating seats. Supplementary W-vs-W uses the first 100 paired seeds. '
        'No tuning on reporting seeds; all 1,900 games are terminal.','',
        '| Focal vs opponent | Wins / losses / draws | Loss %, paired-bootstrap 95% CI | Loss change vs control, pp |',
        '|---|---:|---:|---:|']
    for arm in arms:
        o=r['outcomes'][arm];diff=r['paired_contrasts'].get(arm,{}).get('game_loss_fraction')
        d='—' if not diff else f"{100*diff['difference']:+.2f} [{100*diff['ci95'][0]:+.2f}, {100*diff['ci95'][1]:+.2f}]"
        lines.append(f"| {('W vs W' if arm=='WW' else arm+' vs 0')} | {o['wins']} / {o['losses']} / {o['draws']} | {interval(e[arm]['game_loss_fraction'])} | {d} |")
    lines+=['','Bootstrap: 5,000 shared seed resamples across main arms and every pooled metric; '
        'pointwise percentile 95% intervals, unadjusted. WW has a separate descriptive 100-seed '
        'bootstrap and is not a 600-seed confirmation. Draws remain separate. '
        'Paired main-arm contrasts, numerators and denominators are in [results.json](results.json).','',
        '## Tempo loss-review metrics','',
        '| Metric | 0 vs 0 | W vs 0 | H16 vs 0 | W vs W |','|---|---:|---:|---:|---:|']
    for m in ('arrival_under4_fraction','no_affordable_defender_in_hand_fraction',
              'defender_not_in_hand_fraction','time_at_max_fraction','leaked_elixir_lower_bound_per_minute'):
        if m not in e['0']:continue
        percent=not m.endswith('per_minute')
        lines.append('| '+m+' | '+' | '.join(interval(e[a][m],percent) for a in arms)+' |')
    lines+=['','| Arm / expensive card | In-hand opportunities | Affordable %, 95% CI | Accepted plays / deck-minute, 95% CI |',
            '|---|---:|---:|---:|']
    for arm in arms:
        for c in ('Xbow','Giant','Rocket','Fireball'):
            afford=e[arm]['affordable_hand_fraction:'+c]
            plays=e[arm].get('card_per_deck_minute:'+c)
            lines.append(f"| {arm} / {c} | {int(afford['denominator'])} | {interval(afford)} | {interval(plays,False) if plays else '—'} |")
    lines+=['','Affordability is measured at decision opportunities; timed WAIT reduces those opportunities. '
        'Accepted plays include zero-use deck games. Arrival is the ledger’s lane-incursion onset, '
        'and defender availability is its generic non-spell/non-win-condition hand proxy. '
        'Leaked elixir is a conservative cap-interval lower bound, omitting partial approaches to cap '
        'and collector overflow. Humans’ historical 16–19% under-4 reference is descriptive, not an objective.','',
        '## Decision latency in confirmation games','',
        '| Arm | Wall p50 / p95 / p99, ms | CPU p50 / p95, ms | Wall >200 ms |',
        '|---|---:|---:|---:|']
    for arm in arms:
        wall=r['latency'][arm]['wall'];cpu=r['latency'][arm]['cpu']
        lines.append(f"| {arm} | {wall['p50_ms']:.1f} / {wall['p95_ms']:.1f} / {wall['p99_ms']:.1f} | {cpu['p50_ms']:.1f} / {cpu['p95_ms']:.1f} | {pct(wall['over200_fraction'])} |")
    lines+=['','These full-decision timings include observation, belief update, candidate generation, '
        'public reconstruction, all three styles and submission. They come from a loaded, idle-scheduled '
        '50-worker simulation, not a live latency guarantee. Confirmation uses the private native WAIT '
        'extension with full work; it does not use reduced styles, gating or deduplication.','',
        '## Fixed-state agreement versus latency','',
        f"Separate frozen corpus: **{l['state_count']} public decision states**, all 25 matchups, both seats, "
        'ticks 90/300/600/1200/2400 on disjoint seeds. Three repeats/state; all candidate lists and public '
        'roots regenerate exactly. Inputs and sampled public beliefs are fixed before timing. Warmup/profile '
        'samples are excluded, execution order alternates. Scores/actions below compare to the full W '
        'reference in the same opponent-delay model; no reduced variant has a win-rate claim.','',
        'Primary budget: one physical 3990X core on 03, Torch/BLAS/Rayon=1. Four threads get four physical '
        'cores and **exceed this budget**. Timing includes candidate generation, public root reconstruction '
        'and scoring from a prepared public input; image/sensor parsing, belief inference and actuator/network '
        'are excluded. The p95 target below is empirical for this fixed-state scope, not end-to-end live admission.','']
    for mode,title in (('original','Original tempo W: immediate hypothetical opponent'),
                       ('symmetric','Confirmation W: symmetric d=27 hypothetical opponent')):
        lines+=[f'### {title}','','| Variant | Exact action agreement | Play/WAIT agreement | Wall p50 / p95, ms | CPU p95, ms | Core budget |',
                '|---|---:|---:|---:|---:|---|']
        for name,s in l['results'][mode].items():
            lines.append(f"| {name} | {s['agreement_count']}/{s['states']} ({pct(s['exact_action_agreement'])}) | {pct(s['play_wait_agreement'])} | {s['wall']['p50_ms']:.1f} / {s['wall']['p95_ms']:.1f} | {s['cpu']['p95_ms']:.1f} | {s['budget']} |")
        lines+=['']
    lines+=['`dedup` reuses original WAIT’s rollout for the identical 10-tick WAIT, preserving score addition '
        'and tie order. This is exact shared work; general branching prefixes were not implemented because '
        'continuation must retain both queues, phase and RNG. `wait1/2` uses one/two styles only for the three '
        'timed waits; immediate plays and original WAIT retain all three styles. `gateX` omits timed waits at '
        'elixir ≥X. `native-*` moves original W’s unchanged cadence/command schedule into the existing Rust '
        'command path with opponent_delay=0. Symmetric W already uses that native path. `threads4` uses '
        'GIL release with independent private mutable roots. Exact agreement retains action IDs/durations. '
        'Reference-score regret and exact score-vector counts are in [latency-results.json](latency-results.json).','',
        '### Why W increased the historical median','',
        'Appending timed WAIT candidates turns formerly single-WAIT decisions into full root reconstruction '
        'and nine extra style/candidate rollouts, even when no card is affordable. The original W adapter '
        'also runs each delayed rollout through Python/native calls at every cadence/execution boundary. '
        'Deduplicating original WAIT and 10-tick WAIT removes three redundant rollouts; moving the command '
        'loop into Rust removes this repeated Python orchestration while retaining complete candidate/style '
        'coverage. These mechanisms explain the historical median jump; current fixed-state numbers use '
        'a different state distribution, so they do not claim to reproduce the old 330 ms median.','',
        '| Full original-W profile function | Calls | Self profiled seconds | Cumulative seconds |',
        '|---|---:|---:|---:|']
    for row in l['profiles']['original'][:12]:
        label=row['function'].replace(str(DEST.parents[2]),'repo')
        lines.append(f"| `{label}` | {row['calls']} | {row['own_seconds']:.3f} | {row['cumulative_seconds']:.3f} |")
    lines+=['','cProfile covers eight serial decisions; cumulative rows overlap and must not be added.','',
        '## Recommendation','']
    delta=r['paired_contrasts']['W']['game_loss_fraction']
    if delta['ci95'][1]<0:
        lines.append('W retains a loss-rate advantage against the baseline search opponent under symmetric delay. '
            'Keep it as the exploration candidate for a separately qualified live test.')
    elif delta['ci95'][0]>0:
        lines.append('W loses more often in this stronger symmetric-delay comparison. Do not promote it based on the scripted-opponent result.')
    else:
        lines.append('This stronger comparison does not resolve W’s loss-rate advantage. Keep the result uncertain; do not promote it on the scripted-opponent result alone.')
    best=l['results']['original']['native-dedup']
    lines.append(f"Prefer the complete native command loop plus exact WAIT deduplication before approximate reductions: "
        f"original-W agreement is {best['agreement_count']}/{best['states']}, one-core p95 {best['wall']['p95_ms']:.1f} ms. "
        'Repeat prospective live deadline and completed-candidate qualification; these games and prepared-state timings do not authorize a production change.')
    lines+=['','## Reproducibility, validation and compute','',
        'Freeze [PLAN.md](PLAN.md), config SHA256 `414ecf5235f899c41e874e9c03465c2a944de2f5372f25747b0159bfcaea42a8`, '
        'committed/pushed before games in `e006fdba`. See [AMENDMENTS.md](AMENDMENTS.md), '
        '[seed-audit.json](seed-audit.json), [runtime pin](receipts/runtime-pin.json), '
        '[qualification](receipts/qualification.json), [ordinary parity](receipts/ordinary-parity.json), '
        '[state manifest](receipts/state-manifest.json), and [compute](receipts/compute.json).','',
        'All arms share build48 combat semantics. The private native binary adds timed waits only to the '
        'existing delay-command path and uses GIL-release/v3; ordinary actions have exact score/trace/digest '
        'parity with the supplied build48 quickwins binary. This matched comparison is not an engine-parity '
        'claim to historical tempo’s build46. Fair inputs remain public board/own HUD, accepted enemy card '
        'events, independent sampled hidden-state/RNG and the train-only prior. Physical opponent search '
        'is stronger than scripts but its rollout futures still use scripts and a public reconstruction model.','',
        f"Compute: 03 only, nice 10 / SCHED_IDLE, detached via setsid; peak own processes "
        f"**{compute['peak_own']}**, peak combined Clasher **{compute['peak_combined']}**. "
        f"Completed reporting game CPU: **{r['completed_game_cpu_seconds']/3600:.2f} core-hours**; "
        'startup, profiler and technical attempts are outside that subtotal. No leased/GPU-reserved host '
        'or heavy 05 work. Raw game/state/profile/build artifacts and caches stay on 03 under '
        '`/mpac/sdicks02/jobs/clasher/w-confirm-20261009-r1/`; no raw games are committed. '
        'The reducer validates full paired coverage, terminal games, identical seed/seat/shuffled decks, '
        'capacity one, no rejected commands and queue conservation on both sides.']
    (DEST/'RESULTS.md').write_text('\n'.join(lines)+'\n')


if __name__=='__main__':main()
