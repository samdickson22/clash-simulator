"""Render RESULTS.md from results.json (X4S, exploration, NEVER ADOPTABLE)."""
import json, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
BUDGETS = (200, 160, 140, 120)


def f(x): return f'{x:.2f}'
def c(v): return f'[{v[0]:.2f}, {v[1]:.2f}]'


def main():
    d = json.loads((HERE/'results.json').read_text())
    ops = json.loads((HERE/'receipts/execution.json').read_text()) if (HERE/'receipts/execution.json').exists() else {}
    A = d['arms']; C = d['contrasts']; n = d['paired_seeds']
    L = []
    L.append('# X4S: R3a cutoff default (S-default) inside K4 at slower-core budgets\n')
    L.append(f"**Exploration only, NEVER ADOPTABLE.** Reduced {d['utc']}; {n} complete paired seeds "
             f"(all nine arms) from 4503604807370496+[0,600), hosts {d['hosts']}. Opponent: the exact S1/K2 v1 policy. "
             "Honest lateness, d=27/capacity 1, five decks, alternating seats. "
             "Budgets emulate ≈1.0/0.8/0.7/0.6× fleet core speed (budget equivalence, not real underclocking).\n")
    L.append('## Loss vs v1 (paired-seed 95% CIs)\n')
    L.append('| Budget | K4 loss % | K4S loss % | K4S − K4, pp | K4 cutoff % | K4S cutoff % | K4S student-default % of decisions |')
    L.append('|---|---:|---:|---:|---:|---:|---:|')
    for b in BUDGETS:
        k, s = A[f'K4-{b}'], A[f'K4S-{b}']; ct = C[f'K4S-{b} minus K4-{b}']
        L.append(f"| {b} ms | {f(k['loss_pct'])} {c(k['loss_ci_pct'])} | {f(s['loss_pct'])} {c(s['loss_ci_pct'])} | "
                 f"{f(ct['loss_change_pp'])} {c(ct['ci95_pp'])} | {f(k['cutoff_pct'])} {c(k['cutoff_ci_pct'])} | "
                 f"{f(s['cutoff_pct'])} {c(s['cutoff_ci_pct'])} | {f(s['student_default_pct'])} {c(s['student_default_ci_pct'])} |")
    k0 = A['K0c-200']
    L.append(f"\nAnchor K0c-200 (S1 one-core cached-v1 coarse-first): loss {f(k0['loss_pct'])} {c(k0['loss_ci_pct'])}, "
             f"cutoff {f(k0['cutoff_pct'])}%.\n")
    L.append('## Paired contrasts (pp, 95% CI)\n')
    L.append('| Contrast | pp | 95% CI |'); L.append('|---|---:|---:|')
    for name, v in C.items():
        L.append(f"| {name} | {f(v['loss_change_pp'])} | {c(v['ci95_pp'])} |")
    L.append('\n## Readings (pre-declared, descriptive)\n')
    L.append('"Rescues" = upper CI(K4S-b − K4-b) < 0. "Holds" = upper CI(K4S-b − K4-200) ≤ +5 pp (S1 margin).\n')
    L.append('| Budget | Rescues K4 | Holds within 5 pp of K4-200 |'); L.append('|---|---|---|')
    for b in BUDGETS:
        r = d['readings'][str(b)]
        L.append(f"| {b} ms | {r['rescues_K4']} | {r['holds_within_5pp_of_K4_200']} |")
    L.append('\n## Timing and defaults\n')
    L.append('| Arm | W/L/D | Decisions | Fallback % | Overrun % | Wall p50/p95/p99/max ms | Overrun p50/p99/max ms | Cut returns > budget+8 ms | Prep cutoffs | Game CPU h |')
    L.append('|---|---:|---:|---:|---:|---|---|---:|---|---:|')
    for arm, v in A.items():
        w, o = v['wall_ms'], v['positive_overrun_ms']
        L.append(f"| {arm} | {v['wins']}/{v['losses']}/{v['draws']} | {v['decisions']} | {f(v['fallback_pct'])} | {f(v['overrun_pct'])} | "
                 f"{w['p50']:.1f}/{w['p95']:.1f}/{w['p99']:.1f}/{w['max']:.1f} | {o['p50']:.1f}/{o['p99']:.1f}/{o['max']:.1f} | "
                 f"{v['cut_returns_past_deadline_plus_reserve']} | {json.dumps(v['preparation_cutoffs'])} | {v['game_cpu_hours']:.2f} |")
    L.append('')
    L.extend(sys.argv[1:])
    (HERE/'RESULTS.md').write_text('\n'.join(L)+'\n')


if __name__ == '__main__':
    main()
