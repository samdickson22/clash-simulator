"""Regenerate the small report from receipts; never label partial runs complete."""
from pathlib import Path
import argparse
import json
import math
import statistics

ROOT = Path(__file__).resolve().parent


def read_run(label):
    path = ROOT/'runs'/label
    records = [json.loads(line) for line in (path/'monitor.jsonl').read_text().splitlines()] if (path/'monitor.jsonl').exists() else []
    receipt = json.loads((path/'completion.json').read_text()) if (path/'completion.json').exists() else None
    return records, receipt


def window(rows):
    games = sum(r['wins']+r['losses']+r['draws'] for r in rows)
    tokens = sum(r['transitions'] for r in rows)
    return dict(decisions=tokens, games=games, wins=sum(r['wins'] for r in rows),
        win_rate=sum(r['wins'] for r in rows)/games if games else None,
        **{key:sum(r[key]*r['transitions'] for r in rows)/tokens if tokens else None
           for key in ('mean_reward','entropy','value_loss','approx_kl','clip_fraction','grad_norm','explained_variance')})


def main(require_complete=False):
    summaries = {}
    lines = ['\n## Benchmark receipts\n', '| Mode | Decisions | Update ms/decision | End-to-end decisions/s | Speedup |', '|---|---:|---:|---:|---:|']
    fixed_labels = ('bench-full-pinned','bench-t32-fixed','bench-t64-fixed')
    pinned = all((ROOT/'runs'/label/'completion.json').exists() for label in fixed_labels)
    labels = fixed_labels if pinned else ('bench-full','bench-t32','bench-t64')
    _, baseline = read_run(labels[0])
    for label in labels:
        rows, receipt = read_run(label)
        summaries[label] = receipt
        if receipt and receipt['completed']:
            lines.append(f"| {label} | {receipt['decisions']} | {receipt['update_ms_per_decision']:.2f} | {receipt['decisions_per_second']:.2f} | {receipt['decisions_per_second']/baseline['decisions_per_second']:.2f}× |")
        else:
            lines.append(f'| {label} | pending | | | |')
    lines += [f'\nSource pinning: {pinned}. '+('Full/T64 use the first 4096 decisions of the pinned A/B runs; T32 is a separate 4096-decision run against the corrected source; only tbptt.py differs from the full-prefix source, whose default behavior is byte-identical.' if pinned else 'Original benchmark source drift prevents a clean isolated speedup claim.'),
              '\nCompare the table with the ≤2 ms/decision and approximately 3× targets. This comparison includes entity-padding cropping, changed collection recurrence, differing KL early stops and shared-host contention. It does not isolate prefix replay cost.\n', '## A/B monitor summary\n']
    complete = True
    for label in ('ab-full-pinned','ab-t64-fixed'):
        rows, receipt = read_run(label)
        done = bool(receipt and receipt['completed'] and receipt['decisions'] >= 150000)
        complete &= done
        finite = all(math.isfinite(v) for row in rows for v in row.values() if isinstance(v,(int,float)))
        early = [r for r in rows if r['decisions'] <= 25000]
        late = [r for r in rows if r['decisions'] > 125000]
        summary = dict(receipt=receipt, completed=done, last_decisions=rows[-1]['decisions'] if rows else 0,
                       all_monitor_values_finite=finite, early=window(early), late=window(late), overall=window(rows))
        summaries[label] = summary
        lines.append(f"### {label}\n\nStatus: {'complete' if done else 'INCOMPLETE'}, {summary['last_decisions']} decisions. Monitor values finite: {finite}.\n")
        lines += ['| Window | Decisions | Games | Wins | Mean reward | Entropy | Value loss | KL | Clip fraction | Gradient norm | Explained variance |', '|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|']
        for name in ('early','late','overall'):
            w=summary[name]
            fmt=lambda key: 'n/a' if w[key] is None else f'{w[key]:.5g}'
            lines.append(f"| {name} | {w['decisions']} | {w['games']} | {w['wins']} | " + ' | '.join(fmt(k) for k in ('mean_reward','entropy','value_loss','approx_kl','clip_fraction','grad_norm','explained_variance'))+' |')
        lines.append('')
    lines += ['Early and late windows use update endpoints ≤25k and >125k decisions. Metrics are weighted by collected decisions; individual minibatch statistics retain the learner\'s existing aggregation. Terminal outcomes and training reward are noisy and are not a held-out strength evaluation.\n']
    if not complete:
        lines.append('A/B acceptance remains open until both 150k receipts and monitor curves are reviewed.\n')
    else:
        lines.append('Both runs completed. The final assessment above distinguishes numerical sanity from the unresolved learning-quality gate. No superiority claim is supported by this single-seed comparison.\n')
    (ROOT/'results/summary.json').write_text(json.dumps(summaries,indent=2,allow_nan=False)+'\n')
    readme=ROOT/'README.md'
    readme.write_text(readme.read_text().split('<!-- measured-results -->')[0]+'<!-- measured-results -->\n'+'\n'.join(lines))
    print(json.dumps({k: v.get('last_decisions',v.get('decisions')) if v else None for k,v in summaries.items()}))
    if require_complete and not complete:
        raise SystemExit('A/B incomplete')


def plot_curves():
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(3, 2, figsize=(12, 10), constrained_layout=True)
    keys = ('mean_reward','entropy','value_loss','approx_kl','grad_norm','cumulative_win_rate')
    for label in ('ab-full-pinned','ab-t64-fixed'):
        rows, _ = read_run(label)
        if not rows:
            continue
        x = [r['decisions'] for r in rows]
        for ax, key in zip(axes.flat, keys):
            # Trailing eight-update smoothing retains startup and end windows.
            y = [statistics.mean(r[key] for r in rows[max(0,i-7):i+1]) for i in range(len(rows))]
            ax.plot(x,y,label=label)
            ax.set_title(key.replace('_',' '))
            ax.set_xlabel('Collected decisions')
            ax.grid(alpha=.2)
    axes.flat[0].legend()
    fig.suptitle('Training monitors: trailing 8-update means; no held-out evaluation')
    fig.savefig(ROOT/'results/ab-monitor-curves.png',dpi=140)
    plt.close(fig)


if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--require-complete',action='store_true')
    parser.add_argument('--plot',action='store_true')
    args=parser.parse_args()
    main(args.require_complete)
    if args.plot:
        plot_curves()
