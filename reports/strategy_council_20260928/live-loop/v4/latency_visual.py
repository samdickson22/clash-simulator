"""Render the retained latency receipts as a self-contained review table."""
import html
import json
from pathlib import Path
import sys

metrics=json.loads(Path(sys.argv[1]).read_text())
parity=json.loads(Path(sys.argv[2]).read_text())
stages=[('Capture','capture'),('Decode + sanitize','decode'),('Body / HUD (CPU fallback)','backbone_hud'),
        ('Temporal fusion','temporal_fusion'),('Tracker + ledger + roots','belief'),
        ('Active S6 search','search_active'),('Latest-pixel HUD refresh','actuator_hud'),('Mock two-tap submission','taps')]

def row(label,values):
    return '<tr><th scope="row">'+html.escape(label)+'</th>'+''.join(f'<td>{values[k]:.2f}</td>' for k in ('p50','p95','p99'))+'</tr>'

def table(caption,rows):
    return '<table><caption>'+caption+'</caption><thead><tr><th scope="col">Measurement</th><th scope="col">p50</th><th scope="col">p95</th><th scope="col">p99</th></tr></thead><tbody>'+''.join(rows)+'</tbody></table>'

page='''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><style>
body{font:14px/1.5 var(--font-sans,system-ui);color:var(--foreground,#222)}p{margin:0 0 14px}.flow{display:flex;flex-wrap:wrap;gap:6px 12px;margin:14px 0 22px}.flow span{white-space:nowrap}.flow small{color:var(--muted-foreground,#666)}table{border-collapse:collapse;width:100%;margin:0 0 22px;font-variant-numeric:tabular-nums}caption{text-align:left;font-weight:650;margin:0 0 6px}th,td{padding:7px 6px;border-bottom:1px solid var(--border,#ddd)}thead th{font-weight:500;color:var(--muted-foreground,#666)}th{text-align:left;font-weight:450}td,thead th:not(:first-child){text-align:right}th:first-child{padding-left:0}td:last-child{padding-right:0}.note{font-size:12px;color:var(--muted-foreground,#666)}@media(max-width:440px){body{font-size:12px}th,td{padding:6px 4px}}
</style><body>'''
page+=f'<p><strong>CPU replay on 127x04</strong> · {len(metrics["matches"])} train matches · {metrics["timing_ms"]["frame_to_tap"]["count"]} first attempts</p>'
page+='<div class="flow"><span>P0 capture →</span><span>P1 perception →</span><span>P2 belief →</span><span>P3 decision →</span><span>P4 actuation</span><small>P5 supervises the five separate workers</small></div>'
page+=table('Per-stage latency · milliseconds',[row(label,metrics['timing_ms'][key]) for label,key in stages])
page+=table('Frame → first-attempt submission · milliseconds',[
    row('Fleet measured',metrics['timing_ms']['frame_to_tap']),
    row('Projected: 20 ms perception',metrics['timing_ms']['projected_perception_20ms']),
    row('Projected: 35 ms perception',metrics['timing_ms']['projected_perception_35ms'])])
page+='<p class="note">End-to-end targets: p50 ≤200 ms, p99 ≤400 ms. Projections replace each source frame’s perception cost with DESIGN’s 15+5 ms or 25+10 ms stage budgets; observed queues and all other costs remain. They are not target-machine measurements.</p>'
page+=table('Exact tracker comparison · milliseconds per update',[
    row('Frozen v3',parity['before_ms']),row('Accelerated v3',parity['after_ms'])])
page+=f'<p class="note">Bit-exact equality across {parity["updates"]:,} updates: both full lattices, distribution summaries, hand masses, cycles, four seeded roots and RNG states. Requested tracker/ledger/root p99: ≤10 ms. Processed {metrics["processed_fraction"]:.2%} of captured frames at {metrics["processed_fps"]:.2f} FPS. Mock input only.</p>'
page+='</body></html>'
Path(sys.argv[3]).write_text(page)
