"""Post-analysis presentation only; no inference or game execution."""
from pathlib import Path
import html,json
HERE=Path(__file__).resolve().parent
r=json.loads((HERE/'result.json').read_text());c=json.loads((HERE/'compute-audit.json').read_text())
labels={'clean-d0':'Clean · d=0', 'clean-d22-unaware':'Clean · d=22 · unaware',
        'clean-d22-aware':'Clean · d=22 · aware',
        'T3-N97-d22-unaware':'Noisy N97 · d=22 · unaware',
        'T3-N97-d22-aware':'Noisy N97 · d=22 · aware'}
def interval(d,signed=False):
    fmt='+.1f' if signed else '.1f'
    return f"[{format(100*d['ci95'][0],fmt)}, {format(100*d['ci95'][1],fmt)}]"
rows=''.join(f'<tr><td>{labels[k]}</td><td>{100*d["point"]:.1f}%</td><td>{interval(d)}</td></tr>' for k,d in r['scores'].items())
contrasts=[]
for key,label in [('primary','Primary · clean aware − unaware'),('secondary','Secondary · noisy aware − unaware'),('latency_cost','Latency cost · clean d=0 − aware d=22')]:
    d=r['contrasts'][key]
    verdict=('PASS' if d['pass'] else 'FAIL') if 'pass' in d else 'descriptive'
    contrasts.append(f'<div class="contrast"><div>{label}<span class="verdict">{verdict}</span></div><strong>{100*d["point"]:+.1f} pp</strong><span class="ci">95% CI {interval(d,True)}</span></div>')
doc='''<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><style>
body{font-family:var(--font-sans,system-ui);color:var(--foreground,#222);margin:0;font-size:14px;line-height:1.5;background:transparent}
p{margin:0 0 14px}.muted,.ci{color:var(--muted-foreground,#666)}
table{border-collapse:collapse;width:100%;font-variant-numeric:tabular-nums;margin-bottom:18px}
td,th{padding:9px 0;border-bottom:1px solid var(--border,#ddd);text-align:right}td:first-child,th:first-child{text-align:left;padding-right:10px}th{font-size:12px;color:var(--muted-foreground,#666);font-weight:500}
.contrast{padding:12px 0;border-bottom:1px solid var(--border,#ddd)}.contrast>div{font-size:13px;margin-bottom:4px}.contrast strong{font-size:20px;margin-right:14px}.verdict{font-size:11px;font-weight:700;margin-left:10px}.ci{white-space:nowrap}
.footer{margin-top:18px;font-size:12px}.hash{font-family:var(--font-mono,monospace);overflow-wrap:anywhere;font-size:11px}.stats{margin-top:16px;font-variant-numeric:tabular-nums}
</style></head><body>'''
doc+=f'<p><strong>S6 completed · {r["games"]:,} games</strong><br><span class="muted">256 per cell · 128 paired worlds · both seats retained</span></p>'
doc+='<table><thead><tr><th>Cell</th><th>Score</th><th>95% CI (%)</th></tr></thead><tbody>'+rows+'</tbody></table>'
doc+=''.join(contrasts)
doc+=f'<p class="stats"><strong>{r["game_cpu_hours"]:.2f}</strong> game CPU hours · <strong>{c["total_metered_cpu_hours"]:.2f}</strong> total metered CPU hours</p>'
doc+='<p class="footer muted">10,000 paired-world bootstrap draws; seed 9781100003. PASS requires the 95% lower bound to exceed zero. Independent recomputation matched. Small transfers and final reporting are unmetered.</p>'
doc+=f'<p class="footer">Manifest<br><span class="hash">{html.escape(r["manifest"])}</span></p></body></html>'
(HERE/'RESULTS-summary.html').write_text(doc)
