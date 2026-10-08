from pathlib import Path
import json
HERE=Path(__file__).resolve().parent
r=json.loads((HERE/'result.json').read_text());d=json.loads((HERE/'dev-summary-v2.json').read_text());cpu=json.loads((HERE/'compute-audit.json').read_text())
rows=[]
for cell,s in r['scores'].items():
 c=r['contrasts'].get(cell+' - Full');gain='—' if c is None else f"{100*c['point']:+.2f} [{100*c['ci95'][0]:+.2f}, {100*c['ci95'][1]:+.2f}]"
 verdict='Baseline' if c is None else 'Yes' if c['material'] else 'No'
 rows.append(f"<tr><th scope='row'>{cell}</th><td>{100*s['point']:.2f}%</td><td>{100*s['ci95'][0]:.2f}–{100*s['ci95'][1]:.2f}%</td><td>{gain}</td><td class={'pass' if verdict=='Yes' else 'muted'}>{verdict}</td></tr>")
html='''<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><style>
*{box-sizing:border-box}body{font-family:var(--font-sans,system-ui);color:var(--foreground,#202020);font-size:14px;line-height:1.5;margin:0}p{margin:0 0 14px}h3{font-size:16px;margin:22px 0 10px}table{width:100%;border-collapse:collapse;font-variant-numeric:tabular-nums;font-size:13px;margin:8px 0 12px}th,td{padding:7px 5px;border-bottom:1px solid var(--border,#ddd);text-align:right}th:first-child,td:first-child{text-align:left}thead th{font-weight:600;color:var(--muted-foreground,#666)}.muted,small{color:var(--muted-foreground,#666)}.pass{color:var(--success,#18733a);font-weight:600}.scroll{overflow-x:auto}select{font:inherit;background:var(--background,white);color:inherit;border:1px solid var(--border,#ccc);border-radius:6px;padding:5px 8px;margin-left:8px}code{font-size:11px;overflow-wrap:anywhere}.note{font-size:13px}label{font-weight:600}@media(max-width:480px){body{font-size:13px}table{font-size:11px}th,td{padding:7px 3px}}
</style></head><body>
<p><strong>S4 complete: joint repair and ELT are material. Neither isolated repair clears the registered threshold.</strong></p>
<p class="note muted">1,280 games · 128 paired worlds × 2 seats per cell · 10,000 paired-matchup bootstrap draws. Material means the 95% lower bound is strictly positive.</p>
<div class="scroll"><table><thead><tr><th>Cell</th><th>Score</th><th>95% CI</th><th>Gain vs Full, pp [95% CI]</th><th>Material</th></tr></thead><tbody>'''+''.join(rows)+'''</tbody></table></div>
<p class="note">R-elixir’s lower bound is exactly zero. Interaction: <strong>+5.86 pp [−2.34, +14.06]</strong>; the interval includes zero. <strong>No S5 draft:</strong> the R-hand materiality gate was not met.</p>
<h3>Tracker v3 development</h3><p><strong>N97 target met:</strong> 20.63% resolved hands, 91.52% correct among ≥90%-mass hands. The same-trace exact public-derived reference resolves 21.36%. N90/N64 remain largely uninformative at this threshold.</p>
<p class="note muted">28 validation worlds, both observer seats, 12,174 sampled decisions per event level. All 24 recorded perfect-event games pass (23,058 observations, zero errors); 22 unit tests pass. No tracker-v3 strength confirmation was run.</p>
<label for="level">Event level<select id="level"><option value="T2-N97">N97</option><option value="T2-N90">N90</option><option value="T2-N64">N64</option></select></label>
<div class="scroll"><table><thead><tr><th>Tracker</th><th>Resolved ≥90%</th><th>Accuracy</th><th>Elixir MAE</th><th>Coverage</th></tr></thead><tbody id="dev"></tbody></table></div>
<h3>Hand reliability curve, tabulated</h3><p class="note muted">Mean claimed hand mass → observed accuracy (n). Correlated decisions; these are descriptive calibration bins.</p>
<div class="scroll"><table><thead><tr><th>Mass bin</th><th>T3</th><th>T2</th><th>ELT</th></tr></thead><tbody id="curve"></tbody></table></div>
<p class="note">CPU: <strong>29.62 game core-hours</strong>; <strong>≥41.93 total attributable metered core-hours</strong>. Three 04 operational logs duplicated hub logs and were excluded. Game receipts and results are unaffected.</p>
<p class="note muted">Manifest<br><code>'''+r['manifest']+'''</code></p>
<script>const data='''+json.dumps(d['cells'])+''';
const pct=(x,n=2)=>x===null?'n/a':(100*x).toFixed(n)+'%';
function render(){const m=data[document.getElementById('level').value].validation;document.getElementById('dev').innerHTML=['T3','T2','ELT','R-derived'].map(n=>{const x=m[n];return `<tr><th scope="row">${n}</th><td>${pct(x.resolved_rate,3)}</td><td>${pct(x.accuracy)} <small>(${x.resolved})</small></td><td>${x.mae.toFixed(3)}</td><td>${pct(x.coverage)}</td></tr>`}).join('');document.getElementById('curve').innerHTML=m.T3.calibration_curve.map((b,i)=>`<tr><th scope="row">${Math.round(100*b.lower)}–${Math.round(100*b.upper)}%</th>${['T3','T2','ELT'].map(n=>{const c=m[n].calibration_curve[i];return `<td>${c.n?`${pct(c.claimed_mass,1)} → ${pct(c.accuracy,1)} <small>(${c.n})</small>`:'—'}</td>`}).join('')}</tr>`).join('');console.assert(document.querySelectorAll('#dev tr').length===4);console.assert(document.querySelectorAll('#curve tr').length===8)}document.getElementById('level').addEventListener('change',render);render();console.log('S4 tables rendered; 5 strength cells, 4 dev comparators, 8 reliability bins.');</script></body></html>'''
(HERE/'RESULTS-summary.html').write_text(html)
