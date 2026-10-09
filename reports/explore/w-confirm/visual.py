"""Self-contained results chart for the coordinator; no external assets."""
import json
from pathlib import Path

root=Path(__file__).resolve().parent
data=dict(outcomes=json.loads((root/'results.json').read_text()),
          latency=json.loads((root/'latency-results.json').read_text()))
template='''<!doctype html><html><head><meta charset="utf-8"><style>
body{font-family:var(--font-sans,system-ui);color:var(--foreground,#222);margin:0}
h3{font-size:16px;margin:18px 0 10px}p{font-size:12px;color:var(--muted-foreground,#666);line-height:1.5}
svg{display:block;width:100%;height:240px;overflow:visible}button,select{font:inherit;font-size:12px;color:inherit;background:var(--secondary,#eee);border:1px solid var(--border,#ccc);border-radius:6px;padding:6px 9px}
.controls{display:flex;gap:10px;flex-wrap:wrap;align-items:center;font-size:12px}.stat{font-size:13px;margin:10px 0}.legend{font-size:11px;color:var(--muted-foreground,#666)}
table{width:100%;border-collapse:collapse;font-size:12px;margin-top:10px}th,td{text-align:left;padding:7px 4px;border-bottom:1px solid var(--border,#ddd)}td.num,th.num{text-align:right}
.tip{min-height:32px;font-size:12px;color:var(--muted-foreground,#666)}
</style></head><body>
<h3>W against baseline search · symmetric d=27</h3>
<svg id="loss" role="img" aria-label="Loss rates with bootstrap confidence intervals"></svg>
<div class="stat" id="delta"></div>
<p>600 paired fresh seeds per main arm; 25 deck matchups, alternating seats. 95% paired bootstrap CIs. W-vs-W: 100 descriptive seeds.</p>
<h3>Decision agreement versus p95 latency</h3>
<div class="controls"><select id="mode" aria-label="Opponent model"><option value="original">Original W · immediate rollout opponent</option><option value="symmetric">Symmetric d=27 W</option></select><label><input type="checkbox" id="four"> Show four-core runs</label></div>
<svg id="tradeoff" role="img" aria-label="Action agreement versus p95 latency"></svg>
<div class="tip" id="tip">Select a point for its measurements.</div>
<div class="legend">● Complete scoring / exact reuse &nbsp; ● Approximate reductions &nbsp; ◆ Four cores &nbsp; Dashed line: 200 ms</div>
<table><thead><tr><th>Complete scorer</th><th class="num">Agreement</th><th class="num">p50 / p95 ms</th></tr></thead><tbody id="rows"></tbody></table>
<p id="scope"></p>
<script>
const D=__DATA__,N='http://www.w3.org/2000/svg',C=['var(--chart-1,#3377aa)','var(--chart-2,#22aa77)','var(--chart-3,#bb8844)'];
function node(s,tag,attrs,text){const e=document.createElementNS(N,tag);Object.entries(attrs).forEach(([k,v])=>e.setAttribute(k,v));if(text!==undefined)e.textContent=text;s.appendChild(e);return e}
function axes(s,w){s.setAttribute('viewBox','0 0 '+w+' 240');s.innerHTML=''}
const pct=x=>(x*100).toFixed(1)+'%';
function losses(){const s=document.querySelector('#loss'),w=640;axes(s,w);let max=Math.max(...Object.values(D.outcomes.estimates).map(e=>e.game_loss_fraction.ci95[1]))*1.18;max=Math.max(max,.1);const x=v=>110+v/max*460;
for(let i=0;i<5;i++){let v=max*i/4;node(s,'line',{x1:x(v),x2:x(v),y1:10,y2:203,stroke:'var(--border,#ddd)'});node(s,'text',{x:x(v),y:225,'text-anchor':'middle','font-size':11,fill:'currentColor'},pct(v))}
['0','W','H16','WW'].forEach((a,i)=>{const e=D.outcomes.estimates[a].game_loss_fraction,y=30+i*48;node(s,'text',{x:3,y:y+5,'font-size':12,fill:'currentColor'},a==='WW'?'W vs W':a+' vs 0');node(s,'line',{x1:x(0),x2:x(e.value),y1:y,y2:y,stroke:C[i%3],'stroke-width':16,opacity:.4});node(s,'line',{x1:x(e.ci95[0]),x2:x(e.ci95[1]),y1:y,y2:y,stroke:C[i%3],'stroke-width':2});node(s,'circle',{cx:x(e.value),cy:y,r:5,fill:C[i%3]});node(s,'text',{x:585,y:y+4,'font-size':12,fill:'currentColor'},pct(e.value))});
const e=D.outcomes.paired_contrasts.W.game_loss_fraction;document.querySelector('#delta').textContent='W − control: '+(100*e.difference).toFixed(2)+' percentage points · 95% CI ['+(100*e.ci95[0]).toFixed(2)+', '+(100*e.ci95[1]).toFixed(2)+']';}
function plot(){const mode=document.querySelector('#mode').value,four=document.querySelector('#four').checked,all=D.latency.results[mode],entries=Object.entries(all).filter(([n,r])=>four||r.budget==='one core');const s=document.querySelector('#tradeoff'),w=640;axes(s,w);let xmax=Math.max(210,...entries.map(([n,r])=>r.wall.p95_ms))*1.1,ymin=Math.min(.9,...entries.map(([n,r])=>r.exact_action_agreement))-.02;const x=v=>58+v/xmax*550,y=v=>195-(v-ymin)/(1-ymin)*160;
for(let i=0;i<5;i++){let v=xmax*i/4;node(s,'line',{x1:x(v),x2:x(v),y1:27,y2:195,stroke:'var(--border,#ddd)'});node(s,'text',{x:x(v),y:217,'text-anchor':'middle','font-size':10,fill:'currentColor'},v.toFixed(0))}for(let i=0;i<4;i++){let v=ymin+(1-ymin)*i/3;node(s,'line',{x1:58,x2:610,y1:y(v),y2:y(v),stroke:'var(--border,#ddd)'});node(s,'text',{x:50,y:y(v)+3,'text-anchor':'end','font-size':10,fill:'currentColor'},pct(v))}
node(s,'line',{x1:x(200),x2:x(200),y1:27,y2:195,stroke:'var(--warning,#cc9900)','stroke-dasharray':'5 4'});node(s,'text',{x:330,y:239,'text-anchor':'middle','font-size':11,fill:'currentColor'},'p95 milliseconds · candidate generation + public root + scoring');
entries.forEach(([name,r])=>{let exact=!/wait[12]|gate/.test(name),color=exact?C[0]:C[2],xx=x(r.wall.p95_ms),yy=y(r.exact_action_agreement),e=r.budget==='four cores'?node(s,'polygon',{points:`${xx},${yy-6} ${xx+6},${yy} ${xx},${yy+6} ${xx-6},${yy}`,fill:color}):node(s,'circle',{cx:xx,cy:yy,r:5,fill:color});e.setAttribute('tabindex','0');e.style.cursor='pointer';const text=name+' · '+r.agreement_count+'/'+r.states+' exact actions · p50 '+r.wall.p50_ms.toFixed(1)+' / p95 '+r.wall.p95_ms.toFixed(1)+' ms · '+r.budget;node(e,'title',{},text);e.onclick=e.onfocus=()=>document.querySelector('#tip').textContent=text});
const names=mode==='original'?['full','native-full','native-dedup']:['full','dedup'];document.querySelector('#rows').innerHTML=names.map(n=>{let r=all[n];return '<tr><td>'+n+'</td><td class="num">'+r.agreement_count+'/'+r.states+'</td><td class="num">'+r.wall.p50_ms.toFixed(1)+' / '+r.wall.p95_ms.toFixed(1)+'</td></tr>'}).join('');document.querySelector('#scope').textContent=D.latency.state_count+' fixed public states · three repeats · 3990X. Prepared sensor input and sampled beliefs; image parsing, belief inference and actuator/network excluded. No win-rate claim for reduced scorers; no live deadline guarantee.';}
document.querySelector('#mode').onchange=plot;document.querySelector('#four').onchange=plot;losses();plot();console.log('charts:',document.querySelectorAll('svg').length,'states:',D.latency.state_count);
</script></body></html>'''
(root/'summary.html').write_text(template.replace('__DATA__',json.dumps(data)))
