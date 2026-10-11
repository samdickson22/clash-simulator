"""Render RESULTS-tables.md from results.json (X4S2, exploration, NEVER ADOPTABLE). The narrative RESULTS.md
is written by hand around these tables."""
import json, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def f(x, d=1): return '–' if x is None else f'{x:.{d}f}'
def c(v): return '–' if not v else f'[{v[0]:.1f}, {v[1]:.1f}]'


def main():
    src = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE/'results.json'
    dst = Path(sys.argv[2]) if len(sys.argv) > 2 else HERE/'RESULTS-tables.md'
    d = json.loads(src.read_text())
    A, C = d['arms'], d['contrasts']
    L = [f"# X4S2 tables (generated {d['utc']} from results.json; exploration, NEVER ADOPTABLE)\n"]
    for pop, title in (('X', 'X population (X4S five decks, X4S seeds; `x4s:` = X4S games)'),
                       ('G', 'G population (L2-v4 own decks vs held-out guard decks, fresh seeds)')):
        L.append(f'## Arms: {title}\n')
        L.append('| Arm | Seeds | Loss % [95% CI] | Cutoff % | Student-default % | Coarse complete at cutoff % | Play % | Poll ms | Scale sleep ms | Prep ms | Wall p50/p95 ms |')
        L.append('|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---|')
        for key, s in sorted(A.items()):
            if not key.startswith(pop+':'): continue
            L.append(f"| {key[2:]} | {s['seeds']} | {f(s['loss_pct'])} {c(s['loss_ci_pct'])} | {f(s['cutoff_pct'])} | "
                     f"{f(s['student_default_pct'])} | {f(s['coarse_complete_at_cutoff_pct'])} | {f(s['play_rate_pct'])} | "
                     f"{f(s['poll_ms'])} | {f(s['scale_sleep_ms'])} | {f(s['prep_ms'])} | {f(s['wall_ms']['p50'])}/{f(s['wall_ms']['p95'])} |")
        L.append('')
    L.append('## Paired contrasts (loss pp, paired-seed bootstrap 95% CI, unadjusted)\n')
    L.append('| Contrast | Seeds | pp | 95% CI |')
    L.append('|---|---:|---:|---|')
    for k, v in C.items():
        L.append(f"| {k} | {v['seeds']} | {v['loss_change_pp']:+.1f} | {c(v['ci95_pp'])} |")
    L.append('')
    if d.get('pooled'):
        L.append('## Pooled X + G (bootstrap stratified by population)\n')
        L.append('| Contrast | Seeds X / G | pp | 95% CI |')
        L.append('|---|---:|---:|---|')
        for k, v in d['pooled'].items():
            L.append(f"| {k} | {v['seeds_X']} / {v['seeds_G']} | {v['loss_change_pp']:+.1f} | {c(v['ci95_pp'])} |")
        L.append('')
    L.append(f"Blocks per phase: {d['blocks_per_phase']}; blocks per host: {d['hosts_games']}; "
             f"excluded interrupted blocks: {len(d['excluded_interrupted'])}.")
    dst.write_text('\n'.join(L)+'\n')


if __name__ == '__main__':
    main()
