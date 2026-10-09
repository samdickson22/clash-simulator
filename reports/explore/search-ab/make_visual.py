"""Small, theme-aware presentation of the completed compact report."""
import html,json
from pathlib import Path
root=Path(__file__).resolve().parent;d=json.loads((root/'results.json').read_text());p=d['primary'];rows=[]
for a,label in [('0','Baseline'),('C','Coverage'),('R','Reserve'),('CR','Both')]:
 s=p['estimates'][a];loss=s['game_loss_fraction'];ci=loss['ci95'];change=p['paired_contrasts'].get(a+'-0',{}).get('game_loss_fraction');delta='Reference'
 if change:
  lo,hi=change['ci95'];color='var(--destructive)' if lo>0 else 'var(--success)' if hi<0 else 'var(--foreground)'
  delta=f'<span style="color:{color}">{100*change["difference"]:+.2f} pp</span><small>[{100*lo:+.2f}, {100*hi:+.2f}]</small>'
 rows.append(f'<tr><td><b>{a}</b><small>{label}</small></td><td>{int(loss["numerator"]):,} / 2,000<small>{100*loss["value"]:.2f}% [{100*ci[0]:.2f}, {100*ci[1]:.2f}]</small></td><td>{delta}</td></tr>')
q=d.get('budget_check');n=sum(q['latency'][a]['wall']['n'] for a in ['0','C','R','CR']);over=sum(q['latency'][a]['wall']['over200'] for a in ['0','C','R','CR']);maximum=max(q['latency'][a]['wall']['max'] for a in ['0','C','R','CR'])
qualification=d.get('throughput_qualification')
coexist=''
if qualification:
 coexist=f'<p class="foot">30-minute GRU coexistence check: {qualification["baseline_rate"]:.2f} → {qualification["treatment_rate"]:.2f} rows/s ({100*(qualification["ratio"]-1):+.2f}%). {qualification["paused_samples"]} paused samples. Idle scheduling and GPU-core/SMT exclusions.</p>'
content='''<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><style>
body{font-family:var(--font-sans,system-ui);color:var(--foreground);margin:0}h3{font-size:18px;margin:0 0 8px}p{line-height:1.5;margin:8px 0;color:var(--muted-foreground)}table{width:100%;border-collapse:collapse;font-size:14px}th{text-align:left;font-size:12px;font-weight:600;color:var(--muted-foreground);padding:10px 6px;border-bottom:1px solid var(--border)}td{padding:12px 6px;vertical-align:top;border-bottom:1px solid var(--border)}th:first-child,td:first-child{padding-left:0}small{display:block;color:var(--muted-foreground);font-size:12px;margin-top:3px}.note{margin-top:14px;padding:16px;border-radius:var(--radius,8px);background:var(--warning-surface);color:var(--warning-foreground);font-size:13px;line-height:1.5}.foot{font-size:12px;margin-top:12px}@media(max-width:450px){table{font-size:12px}small{font-size:11px}th,td{padding-right:3px;padding-left:3px}}
</style></head><body><h3>d=27 search A/B</h3><p>2,000 paired seeds per arm · exploration only</p><table><thead><tr><th>Arm</th><th>Losses · rate [95% CI]</th><th>Paired loss change [95% CI]</th></tr></thead><tbody>'''+''.join(rows)+f'''</tbody></table><div class="note"><b>200 ms budget unmet.</b> The exact S6 arms overrun. A separate cutoff check still recorded {over:,} overruns in {n:,} full decisions, maximum {maximum*1000:.0f} ms.</div><p class="foot">Shared seed bootstrap; positive change means more losses. Single reserve weight fixed from separate tuning seeds. These are simulator research results, with pointwise intervals and no confirmatory interpretation.</p>{coexist}</body></html>'''
(root/'comparison.html').write_text(content)
