"""Post-analysis presentation only; renders the independently audited results."""
from pathlib import Path
import json,html
s=Path('/mpac/sdicks02/repos/clasher/reports/strategy_council_20260928/search-noise-s5')
r=json.loads((s/'result.json').read_text());a=json.loads((s/'completion-audit.json').read_text());cpu=json.loads((s/'compute-audit.json').read_text())
assert a['independent_scores_and_all_bootstrap_intervals_match'] and r['games']==1536
esc=html.escape
pct=lambda x:f'{100*x:.2f}%'
ci=lambda d:f"[{100*d['ci95'][0]:.2f}, {100*d['ci95'][1]:.2f}]"
primary=r['contrasts']['primary'];verdict='PASS' if primary['pass'] else 'FAIL'
scores=''.join(f"<tr><th>{esc(c)}</th><td>{pct(d['point'])}</td><td>{ci(d)}</td></tr>" for c,d in r['scores'].items())
labels={'primary':'Primary · T3-N97 − Full-N97','secondary_elt':'Secondary · T3-N97 − ELT-N97','secondary_n90':'Secondary · T3-N90 − Full-N90','ceiling_gap':'Ceiling gap · R-derived − T3-N97'}
contrasts=''.join(f"<tr><th>{esc(labels[k])}</th><td>{100*d['point']:+.3f}</td><td>{ci(d)}</td><td>{('PASS' if d['pass'] else 'FAIL') if 'pass' in d else 'Descriptive'}</td></tr>" for k,d in r['contrasts'].items())
diag=''
for c,d in r['diagnostics'].items():
 accuracy=pct(d['hand90_accuracy']) if d['hand90_accuracy'] is not None else 'n/a'
 diag+=f"<tr><th>{esc(c)}</th><td>{pct(d['coverage'])}</td><td>{d['width']:.3f}</td><td>{d['mae']:.3f}</td><td>{pct(d['hand90_fraction'])}</td><td>{accuracy}</td><td>{pct(d['unanimity_fraction'])}</td></tr>"
post=' · '.join(f"{esc(c)} {pct(d['post_error_coverage'])}" for c,d in r['diagnostics'].items())
page=f'''<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>S5 — tracker v3 confirmation</title><style>
body{{font-family:var(--font-sans,system-ui);color:var(--foreground,#20252a);margin:0;font-size:14px;line-height:1.5}}h1{{font-size:25px;line-height:1.2;margin:0 0 12px}}h2{{font-size:18px;margin:25px 0 8px}}p{{margin:8px 0 14px}}.muted,small{{color:var(--muted-foreground,#697078)}}.hero{{font-size:19px}}.table{{overflow:auto}}table{{border-collapse:collapse;width:100%;font-variant-numeric:tabular-nums;font-size:13px}}th,td{{text-align:right;padding:9px 7px;border-bottom:1px solid var(--border,#ccc);white-space:nowrap}}th:first-child{{text-align:left;padding-left:0;font-weight:500}}thead th{{color:var(--muted-foreground,#697078);font-weight:500;font-size:12px}}code{{font-family:var(--font-mono,monospace);font-size:11px;overflow-wrap:anywhere}}.stats{{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin:18px 0}}.stat{{background:var(--secondary,#f2f3f4);padding:16px;border-radius:var(--radius,8px)}}.stat b{{display:block;font-size:21px}}.stat span{{font-size:12px}}.foot{{font-size:12px}}@media(max-width:480px){{h1{{font-size:22px}}.stats{{grid-template-columns:1fr}}th,td{{padding:7px 5px}}}}
</style></head><body><h1>S5 · Frozen tracker v3 confirmation</h1>
<p class="hero"><strong>Primary {verdict}</strong> · T3-N97 − Full-N97: <strong>{100*primary['point']:+.3f} pp</strong>, 95% CI {ci(primary)}.</p>
<p class="muted">1,536 games · 128 paired worlds × two seats × six cells. The S4 tracker remained unchanged. PASS requires a strictly positive 95% lower bound.</p>
<h2>Scores against the fixed C56 opponent protocol</h2><div class="table"><table><thead><tr><th>Cell</th><th>Score</th><th>95% CI (%)</th></tr></thead><tbody>{scores}</tbody></table></div>
<h2>Registered contrasts</h2><div class="table"><table><thead><tr><th>Comparison</th><th>Gain (pp)</th><th>95% CI (pp)</th><th>Verdict</th></tr></thead><tbody>{contrasts}</tbody></table></div>
<p class="foot muted">10,000 paired-matchup bootstrap resamples, retaining both seats and all cells; seed {r['bootstrap_seed']}. Win = 1, draw = ½, loss = 0. No multiplicity adjustment.</p>
<h2>Tracker diagnostics</h2><div class="table"><table><thead><tr><th>Cell</th><th>Elixir<br>coverage</th><th>Width</th><th>MAE</th><th>Hand mass<br>≥90% rate</th><th>Accuracy<br>when resolved</th><th>Old<br>unanimity</th></tr></thead><tbody>{diag}</tbody></table></div>
<p class="foot muted">T3-N90’s 100% hand accuracy is only 13 resolved samples out of 59,537; it cannot establish broad calibration. Width and MAE are in elixir units. Diagnostics are descriptive, correlated decision samples. Old unanimity is computed separately from v3’s ≥90%-mass hand field.</p>
<p class="foot"><strong>Post-error elixir coverage:</strong> {post}.</p>
<h2>Compute and audit</h2><div class="stats"><div class="stat"><b>{r['game_cpu_hours']:.2f}</b><span>game CPU core-hours</span></div><div class="stat"><b>{cpu['total_metered_cpu_hours']:.2f}</b><span>{'at least · ' if cpu['total_is_lower_bound'] else ''}total metered core-hours</span></div><div class="stat"><b>{a['wall_span_minutes']:.1f} min</b><span>confirmation wall span</span></div></div>
<p class="foot">Supervisor/worker CPU: {cpu['confirmation_supervisors_and_workers_cpu_hours']:.3f} core-hours. Totals overlap; do not add them. Six verified mirrored hub-log copies are excluded. Small copying and finalization operations are unmetered.</p>
<p class="foot">All 1,536 terminal receipts, 152 successful partitions and both supervisor successes existed before analysis. Independent aggregation matched every score and bootstrap interval. Final frozen-file audits passed on 01/04/08. No confirmation reruns or exclusions.</p>
<p class="foot">Both historical seed audits passed with no detected collisions. They list 726 unavailable historical paths, so absolute disjointness from unavailable history cannot be established. Games ran only on 04/08, nice 10, one native/BLAS thread; 01 collected and analyzed. No engine/gamedata changes or commits.</p>
<p class="foot"><strong>Manifest SHA256</strong><br><code>{r['manifest']}</code></p><p class="foot"><strong>Receipt aggregate SHA256</strong><br><code>{r['receipt_aggregate']}</code></p>
</body></html>'''
(s/'RESULTS-summary.html').write_text(page)
print(json.dumps({'path':str(s/'RESULTS-summary.html'),'bytes':len(page.encode())}))
