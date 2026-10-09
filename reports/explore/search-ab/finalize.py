"""Seed-paired, game-cluster bootstrap and compact exploration report."""
import argparse,hashlib,json
from pathlib import Path
from collections import Counter,defaultdict
import numpy as np
from clasher.analysis.loss_review.summarize import bootstrap_matrix
from clasher.analysis.loss_review.human import write
ARMS=['0','C','R','CR']
CARDS=['Xbow','Giant','Fireball','Rocket','Log']

def summarize(paths,expected,reps):
 rows={a:{} for a in ARMS};receipts=[];catalog=json.loads((paths[0]/'catalog.json').read_text())
 for path in paths:
  receipt=json.loads((path/'receipt.json').read_text());assert receipt['terminal']==receipt['games']
  receipts.append({k:v for k,v in receipt.items() if k!='results'})
  for p in (path/'games').glob('*.json'):
   r=json.loads(p.read_text());arm=r['cohort'];seed=r['metadata']['seed']
   assert arm in ARMS and seed not in rows[arm] and r['role']=='exploration'
   rows[arm][seed]=r
 assert all(len(rows[a])==expected and rows[a].keys()==rows['0'].keys() for a in ARMS)
 keys=sorted(rows['0'])
 assert keys==list(range(keys[0],keys[0]+expected))
 for seed in keys:
  reference=rows['0'][seed]['metadata']
  for a in ARMS:
   row=rows[a][seed];meta=row['metadata'];ab=row['search_ab']
   assert all(meta[k]==reference[k] for k in ('own_deck','opponent_deck','seat','style','delay_ticks'))
   assert ab['arm']==a and ab['reserve_weight']==(1 if 'R' in a else 0)
 for a in ('C','CR'):
  assert all(v.get('final_absent',0)==0 for row in rows[a].values() for v in row['search_ab']['attrition'].values())
 metrics=sorted({m for a in ARMS for r in rows[a].values() for m in r['stats']['all']})
 spells=sorted({n for a in ARMS for r in rows[a].values() for n in r['metadata']['own_deck'] if catalog['cards'].get(n,{}).get('spell')})
 metrics+=['game_loss_fraction','game_win_fraction','game_draw_fraction']+['spell_mix:'+s for s in spells]
 matrix=np.zeros((expected,len(metrics)*4,2));latency={};attrition={};counts={};channels={};budget={}
 for ai,a in enumerate(ARMS):
  lat=[];cpu=[];attr=defaultdict(Counter);cc=Counter();ch=Counter();bc=Counter()
  for i,seed in enumerate(keys):
   r=rows[a][seed];s=dict(r['stats']['all']);meta=r['metadata'];ab=r['search_ab']
   assert meta['delay_ticks']==27 and meta['terminal']
   own=meta['winner']==meta['seat'];draw=meta['winner'] is None
   s.update(game_loss_fraction=[r['loss'],1],game_win_fraction=[own,1],game_draw_fraction=[draw,1])
   spell_counts={n:s.get('card_per_deck_minute:'+n,[0,0])[0] for n in spells};total=sum(spell_counts.values())
   for n in spells:s['spell_mix:'+n]=[spell_counts[n],total]
   for j,m in enumerate(metrics):matrix[i,ai*len(metrics)+j]=s.get(m,[0,0])
   lat+=ab['latency_seconds'];cpu+=ab['cpu_latency_seconds']
   for name,v in ab['attrition'].items():attr[name].update(v)
   cc.update({int(k):v for k,v in ab['candidate_counts'].items()});ch.update(meta['channel']);bc.update(ab['budget_counts'])
  def times(xs):return dict(n=len(xs),median=float(np.median(xs)),p95=float(np.quantile(xs,.95)),p99=float(np.quantile(xs,.99)),max=float(max(xs)),over200=sum(x>.2 for x in xs),over200_fraction=float(np.mean(np.array(xs)>.2)))
  latency[a]=dict(wall=times(lat),cpu=times(cpu));attrition[a]=dict(attr);counts[a]=dict(cc);channels[a]=dict(ch);budget[a]=dict(bc)
 point,boot,total=bootstrap_matrix(matrix,8091008,reps);est={};contrasts={}
 for ai,a in enumerate(ARMS):
  est[a]={}
  for j,m in enumerate(metrics):
   k=ai*len(metrics)+j
   if not np.isfinite(point[k]):continue
   good=boot[:,k][np.isfinite(boot[:,k])]
   est[a][m]=dict(value=float(point[k]),ci95=np.quantile(good,[.025,.975]).tolist(),numerator=float(total[k,0]),denominator=float(total[k,1]),supported_games=int(np.sum(matrix[:,k,1]>0)))
 for ai,a in enumerate(ARMS[1:],1):
  contrasts[a+'-0']={}
  for j,m in enumerate(metrics):
   diff=boot[:,ai*len(metrics)+j]-boot[:,j];good=diff[np.isfinite(diff)]
   if not len(good):continue
   contrasts[a+'-0'][m]=dict(difference=float(point[ai*len(metrics)+j]-point[j]),ci95=np.quantile(good,[.025,.975]).tolist(),paired_seeds=expected)
 interaction={}
 for j,m in enumerate(metrics):
  effect=boot[:,3*len(metrics)+j]-boot[:,len(metrics)+j]-boot[:,2*len(metrics)+j]+boot[:,j]
  good=effect[np.isfinite(effect)]
  if len(good):interaction[m]=dict(difference=float(point[3*len(metrics)+j]-point[len(metrics)+j]-point[2*len(metrics)+j]+point[j]),ci95=np.quantile(good,[.025,.975]).tolist())
 coverage_changes={a:sum(rows[a][s]['search_ab']['attrition'].get(n,{}).get('baseline_absent',0) for s in keys for n in rows[a][s]['metadata']['own_deck']) for a in ARMS}
 exact_pairs=sum(rows['0'][s]['loss']==rows['C'][s]['loss'] and rows['0'][s]['stats']==rows['C'][s]['stats'] for s in keys)
 return dict(latency_scopes=sorted({r['search_ab']['decision_scope'] for a in ARMS for r in rows[a].values()}),paired_seeds=expected,seed_range=[keys[0],keys[-1]],estimates=est,paired_contrasts=contrasts,factorial_interaction=interaction,latency=latency,attrition=attrition,candidate_counts=counts,channels=channels,budget=budget,receipts=receipts,baseline_missing_card_opportunities=coverage_changes,baseline_C_identical_reductions=exact_pairs)

def reproduction(root):
 rows=[json.loads(p.read_text()) for p in (root/'reproduction-original/games').glob('*.json')];old={p.stem:json.loads(p.read_text()) for p in (root/'ledger-games').glob('*-d27.json')}
 assert len(rows)==len(old)==150
 losses=sum(r['loss'] for r in rows);differences=[];strict_differences=0;common=0
 for r in rows:
  ref=old[r['identity']]
  if r['loss']!=ref['loss']:differences.append(r['identity']+':loss')
  for scope,stats in ref['stats'].items():
   for m,v in stats.items():
    if m not in r['stats'].get(scope,{}):continue
    common+=1
    if not np.allclose(v,r['stats'][scope][m],rtol=1e-12,atol=1e-12):strict_differences+=1
    if not np.allclose(v,r['stats'][scope][m],rtol=1e-6,atol=1e-5):differences.append(r['identity']+':'+scope+':'+m)
 result=dict(games=150,losses=losses,compared_metric_pairs=common,differences=differences,within_float32_reduction_tolerance=not differences,strict_float_differences=strict_differences,note='Ledger JSON trace re-reduction promotes float32 sensor values to float64; discrete events and game losses match exactly.')
 assert losses==22 and not differences
 return result

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--root',type=Path,required=True);ap.add_argument('--reps',type=int,default=2000);ap.add_argument('--budget',action='store_true');args=ap.parse_args();root=args.root
 result=dict(lane='exploration',not_gate_evidence=True,confirmatory=False,bootstrap_reps=args.reps,bootstrap_unit='paired simulator seed; all arm ratios share multinomial draws',tuning=json.loads((root/'tuning.json').read_text()),seed_audit=json.loads((root/'seed-audit.json').read_text()),baseline_reproduction=reproduction(root),primary=summarize(sorted((root/'shards').glob('p*')),2000,args.reps))
 if args.budget:result['budget_check']=summarize([root/'budget-full-127x04'],100,args.reps)
 result['alias_smoke']=json.loads((root/'receipts/alias-check.json').read_text())
 assert all(h['represented'] for h in result['alias_smoke']['hand'] if h['legal_tiles'])
 result['required_latency_budget_met']=not any(result['primary']['latency'][a]['wall']['over200'] for a in ARMS)
 result['primary']['latency_clock']='legacy_raw_wall_including_external_pauses'
 if (root/'receipts/coexistence-summary.json').exists():result['throughput_qualification']=json.loads((root/'receipts/coexistence-summary.json').read_text())
 result['pause_parity']=json.loads((root/'receipts/pause-parity.json').read_text())
 result['startup_check']=json.loads((root/'receipts/startup-check.json').read_text())
 result['balancing_check']=json.loads((root/'receipts/balancing-check.json').read_text())
 result['preparation_profile']=json.loads((root/'receipts/belief-profile.json').read_text())
 result['operations']=json.loads((root/'receipts/lease-scheduler.json').read_text())
 result['runtime_pins']={str(p.relative_to(root)):json.loads(p.read_text()) for p in (root/'receipts').rglob('*pin.json')}
 pins=list(result['runtime_pins'].values());differences={n:sorted({d['files'][n] for d in pins}) for n in pins[0]['files'] if len({d['files'][n] for d in pins})>1}
 assert set(differences)<= {'src/clasher/analysis/loss_review/simulate.py'}
 result['runtime_consistency']=dict(differing_files=differences,note='Only optional full-decision timing metadata was added after primary staging; fixed-search action logic, native binary, public reconstruction, prior and both treatment implementations have identical hashes.')
 result['limitations']=['Exploration only; pointwise CIs without multiplicity correction.','Empirical zero rates have degenerate bootstrap intervals; these are not population upper bounds.','Exact ledger S6 fixed-budget search violates the 200ms budget, including baseline.','Reserve is a heuristic against a generic defender proxy, not a causal diagnosis.','Scripted simulator matchups do not establish human/live/gate performance.','The ledger catalog does not identify internal BlowdartGoblin in this schedule; generic defender and per-card diagnostics preserve that existing alias limitation. Coverage still protects every mask-legal slot.','Budget check uses a changed anytime search and separate fresh seeds; wall scheduling is not hard real time.','No eval, heldout data, registration changes or git commits.']
 primary=result['primary'];result['interpretation']={}
 for arm in ('C','R','CR'):
  effect=primary['paired_contrasts'][arm+'-0']['game_loss_fraction'];lo,hi=effect['ci95']
  result['interpretation'][arm]=dict(loss_change_pp=100*effect['difference'],loss_change_ci95_pp=[100*lo,100*hi],description=('more losses in this simulator sample, with pointwise CI above zero' if lo>0 else 'fewer losses in this simulator sample, with pointwise CI below zero' if hi<0 else 'loss difference uncertain; pointwise CI includes zero'))
 result['source_sha256']={str(p.relative_to(root.parents[2])):hashlib.sha256(p.read_bytes()).hexdigest() for p in [root/'finalize.py',root/'select_weight.py',root.parents[2]/'src/clasher/analysis/loss_review/search_ab.py',root.parents[2]/'src/clasher/analysis/loss_review/simulate.py']}
 write(root/'results.json',result)
 def pct(x):return f'{100*x:.2f}%'
 def effect(v):return f"{100*v['difference']:+.2f} pp [{100*v['ci95'][0]:+.2f}, {100*v['ci95'][1]:+.2f}]"
 p=result['primary'];lines=['# d27 search A/B exploration — 2026-10-08','', '**Exploration lane. Research guidance only; no pre-registration or eval/heldout access.**','',f"2,000 paired seeds per arm (8,000 terminal games). Exact S6 ledger harness, five decks, 25 matchups, three scripted opponents, alternating seats and d=27. Reporting seeds `2**48 + 10_000 + i`, i=0..1999. Single reserve weight selected: **{result['tuning']['selected_weight']}** on 150 separate tuning seeds.",'','**The exact-harness arms fail the 200 ms decision requirement, including Arm 0.** Results below are fixed-budget simulator research, not approval to deploy. The supplementary anytime check is reported separately.','', '| Arm | Wins / losses / draws | Loss rate, 95% CI | Paired loss change vs 0 |','|---|---:|---:|---:|']
 for a in ARMS:
  s=p['estimates'][a];loss=s['game_loss_fraction'];ci=loss['ci95'];w=int(s['game_win_fraction']['numerator']);l=int(loss['numerator']);d=int(s['game_draw_fraction']['numerator']);diff='—' if a=='0' else effect(p['paired_contrasts'][a+'-0']['game_loss_fraction'])
  lines.append(f"| {a} | {w} / {l} / {d} | {pct(loss['value'])} [{pct(ci[0])}, {pct(ci[1])}] | {diff} |")
 lines+=['','Measured interpretation: '+ '; '.join(a+' — '+result['interpretation'][a]['description'] for a in ('C','R','CR'))+'. These are exploratory, pointwise intervals. The tuning advantage is not assumed to generalize to reporting seeds.','', 'Arm definitions: 0 = original planner; C = candidate coverage; R = public reserve leaf term; CR = both. One selected reserve weight is held fixed across reporting arms.','', 'Paired percentile bootstrap: 2,000 seed resamples, shared draws across all arms and metrics. Rates pool event/exposure numerators and denominators rather than averaging per-game ratios. All estimates, denominators, paired CIs and the CR−C−R+0 interaction are in `results.json`.','', '| Metric | 0 | C | R | CR |','|---|---:|---:|---:|---:|']
 for m in ['arrival_under4_fraction','no_affordable_defender_in_hand_fraction']+['card_per_deck_minute:'+n for n in CARDS]+[k for k in p['estimates']['0'] if k.startswith('spell_mix:')]:
  cells=[pct(p['estimates'][a][m]['value']) if 'fraction' in m or 'spell_mix:' in m else f"{p['estimates'][a][m]['value']:.4f}" for a in ARMS]
  lines.append('| '+m+' | '+' | '.join(cells)+' |')
 lines+=['','Card rates are accepted plays per minute in games containing that card, including zero-use games. Spell mix is each spell’s share of all accepted spell casts. Defender availability is the existing loss-review generic non-spell, non-win-condition hand proxy. A zero empirical rate and [0,0] bootstrap interval are not population upper bounds or proof of no missed opportunity.','', '## Where expensive cards die','', '| Arm / card | Hand opportunities | Unaffordable | Affordable | Fully masked | Generator absent | Reduction absent | Final absent | Selected / offered |','|---|---:|---:|---:|---:|---:|---:|---:|---:|']
 for a in ARMS:
  for n in CARDS[:-1]:
   s=p['attrition'][a].get(n,{});v=[s.get(k,0) for k in ['in_hand','unaffordable','affordable','masked_all','generation_dropped','reduction_dropped','final_absent']]
   lines.append(f"| {a} / {n} | "+' | '.join(map(str,v))+f" | {s.get('selected',0)} / {s.get('scored_opportunities',0)} |")
 lines+=['','Instrumentation is per decision with no outstanding command. Fully masked is conditional on affordability; generator absence is conditional on legal tiles; reduction absence means present in exhaustive script ranking but absent in the original fixed pool. Coverage repairs only missing legal hand slots by replacing the lowest-prior unprotected extra; WAIT and one existing best-prior representative per covered slot are protected. Original candidate count is preserved. Expensive-card opportunities after the affordability gate are small; zero attrition is not evidence of healthy resource planning.', '', '## Reserve value and tuning','', 'Leaf value adds `−weight * 0.005 * max(0, defender_target − own_leaf_elixir)` only when a visible living enemy troop is at canonical y≤18. The defender target is the cheapest generic defender affordable in the root public own hand; if none is affordable, use the cheapest defender in that hand as a savings target. This fixed reference avoids the tautology of requiring a leaf-affordable card and then testing a deficit. It uses native `public_view`: visible bodies and own elixir only. No opponent hand, deck order, live RNG, snapshots or privileged hidden clocks enter this term. Terminal ±2 values are preserved. One weight is shared by R and CR. The inherited loss-review card catalog lacks the internal BlowdartGoblin alias in this schedule; it is excluded from the generic defender/card diagnostic proxy. Candidate coverage itself operates on every legal hand slot, independently of catalog identity. The public/native alias smoke shows BlowdartGoblin remains affordable, has 222 legal tiles and is represented under C; the catalog limitation affects reserve/diagnostic classification, not candidate coverage.','', 'Tuning seeds: `2**48 + 30_000 + i`, i=0..149. Grid: 0, 1, 4, 16, 64. Select minimum tuning losses, breaking ties toward lower weight. No reporting games were read before selection.','', '| Weight | Tuning losses / 150 |','|---:|---:|']
 for r in result['tuning']['weights']:lines.append(f"| {r['weight']} | {int(r['losses'])} |")
 lines+=['','## Decision latency','', '| Arm | Wall median / p95 / p99 / max (ms) | >200 ms | CPU p95 (ms) |','|---|---:|---:|---:|']
 for a in ARMS:
  w=p['latency'][a]['wall'];c=p['latency'][a]['cpu'];lines.append(f"| {a} | "+' / '.join(f"{1000*w[k]:.1f}" for k in ['median','p95','p99','max'])+f" | {w['over200']} / {w['n']} ({pct(w['over200_fraction'])}) | {1000*c['p95']:.1f} |")
 lines+=['','All arms include the same candidate attrition instrumentation, which adds an exhaustive prior ranking pass; absolute times include this diagnostic cost. Primary latency starts at candidate generation/instrumentation and includes public root reconstruction, scoring and submission; public observation and belief update precede this boundary, so it is a lower bound on full decision latency. CPU timing distinguishes compute cost from scheduling. Command execution delay remains 27 ticks. The ledger uses fixed work rather than a deadline and reproduces its behavior; these results cannot satisfy a hard 200 ms wall budget.','']
 if 'budget_check' in result:
  q=result['budget_check'];lines+=['## Supplementary budget check','', 'Separate 100 paired fresh seeds per arm at `2**48 + 50_000 + i`. Same selected weight, decks and matchup schedule; an opt-in 180 ms search cutoff starts before public observation, belief update, candidate generation and root construction, with another 8 ms return cushion. Cancellation occurs between native calls and 10-tick rollout chunks. Only completed three-style candidate scores count; no completed score means WAIT. This changes the baseline planner and is not the exact ledger Arm 0.','', '| Arm | Wins / losses / draws | Paired loss change vs budgeted 0 | Wall p95 / max (ms) | >200 ms |','|---|---:|---:|---:|---:|']
  for a in ARMS:
   s=q['estimates'][a];w=q['latency'][a]['wall'];diff='—' if a=='0' else effect(q['paired_contrasts'][a+'-0']['game_loss_fraction']);lines.append(f"| {a} | {int(s['game_win_fraction']['numerator'])} / {int(s['game_loss_fraction']['numerator'])} / {int(s['game_draw_fraction']['numerator'])} | {diff} | {w['p95']*1000:.1f} / {w['max']*1000:.1f} | {w['over200']} / {w['n']} |")
  lines+=['','The full-boundary check records 51 overruns in 121,959 decisions, mostly at early public conditioning calls. A separate train-prior-only profile conditions 4,914,000 posterior states down to 1,498,560 on one public Log event: update plus sampling took about 415 ms. The earlier BarbLog profile took about 160 ms and is also retained. This identifies a preparation cost the rollout cutoff cannot interrupt. Profile code and receipt are retained; no prior-conditioning rewrite was introduced during reporting.','', 'Any measured >200 ms event means this cooperative cutoff does not provide a hard real-time guarantee. Truncation, completed-candidate and fallback counts are retained in JSON. Budget sensitivity is exploratory and selected without reporting-seed tuning.','']
 lines+=['## Reproduction, seeds, tests and compute','', f"The unmodified S6 reproduction matches within float32 reduction tolerance all {result['baseline_reproduction']['compared_metric_pairs']:,} common metric numerator/denominator pairs in all 150 ledger d27 games, plus every game loss. Aggregate losses 22/150; under-4 91.03%; no affordable defender 65.34%; X-Bow 0.123608, Giant 0.056545, Fireball 0.112252, Rocket 0, Log 3.000536 per deck-minute.",'', 'Seed audit checks game/shuffle and all player-helper seed offsets 0, 100000, 100001, 100002 against the ledger’s read-only 4,356 gate/helper seed inventory and 19,294 historical values. Reporting, tuning, budget-check, public/native smoke and ledger sets have zero intersections. No gate outcomes, eval data or frozen registrations were opened. `seed-audit.json` includes exclusion hashes and exact ranges.','', '33 A/B, guard and loss-review unit tests passed, including loss-review reduction/bootstrap tests and new coverage, public reserve, parity, cutoff and resume tests. Final tests and native parity receipts are retained under `receipts/`. Default behavior is unchanged: experiment flags are required; no live-player files were modified. No git commits.','', '| Run / host | Workers | Fresh / reused games | Wall seconds | Fresh games/s | Fresh worker CPU seconds | Reserved CPUs |','|---|---:|---:|---:|---:|---:|---:|']
 for label,data in [('primary',p)]+([('budget',result['budget_check'])] if 'budget_check' in result else []):
  for r in data['receipts']:lines.append(f"| {label} / {r['host']} | {r['workers']} | {r.get('new_games',r['games'])} / {r.get('resumed_games',0)} | {r['wall_seconds']:.1f} | {r.get('new_games',r['games'])/r['wall_seconds']:.3f} | {r.get('new_worker_cpu_seconds',r['worker_cpu_seconds']):.1f} | {128-len(r['affinity'])} |")
 lines+=['','Simulations ran detached through fleet_run.sh on authorized home hosts or lease wrapper v2, with nice ≥10. Initial 96/96/80-worker tuning allocations were reduced following coordinator corrections. The early 96-worker 04 batch tripped perception’s process guard; it was stopped and completed games retained. Final primary shards used 04≤40, 08≤16, and leased09/14≤18. 01 and 03 remained off after their reservations; no simulator started on03 because the handoff file existed before launch. 11 became unreachable and its incomplete shard was replayed elsewhere. 13/15 drained and were vacated. 16 admission refusals on PSS were honored. Leased staging used rsync -c from04 into isolated lease-local paths. No work on02, roader paths, tailscale or crontab; no pkill. 05 only authored code and read compact artifacts. First baseline throughput was 0.98 games/s on96 workers; first-ten-minute measurements and subsequent affinity receipts are retained.','', 'The primary dataset was produced with the historical GPU-utilization guard. Its wall-latency arrays include external SIGSTOP time and remain labeled legacy raw wall; they are not retrospectively corrected. Successful-game CPU sums exclude abandoned partial-game compute. A later audit showed the utilization guard caused unnecessary pauses; the separate versioned throughput qualification uses fresh GPU-job interval rows/s, a measured baseline, idle scheduling, observed active GPU-job core/SMT exclusions, pause-aware wall telemetry and CPU-clock decision deadlines. The primary fixed-work behavior was preserved.','', 'All16 primary shards completed, 8,000 terminal games. The old lease worker’s14-minute wall limit caused retries; completed games were retained. The new worker counts only active time toward its840-second shard limit and retains an absolute lease exit deadline. Fixed-work action hashes and winners matched across all4arms with3forced pauses and permuted LPT dispatch. The scheduling replay preserves all8,000 cases and their paired clusters in20balanced100-pair shards. Measured initialize startup was28.90s cold and25.79s after external bytecode warming; source hashes were unchanged. New leased starts stop at04:15Z and all our leased work exits by04:30Z. Full admissions, process/PSS peaks, pauses, retries and original commands are retained.','',
 'Primary runtime pins agree on the native binary, train prior, public reconstruction, fixed S6 planner and both treatment implementations. The sole difference among primary pins is optional full-decision timing metadata in simulate.py; its flag was off in primary games. Later pause-clock/throughput changes are staged separately for qualification and their source hashes are recorded independently.','', 'Reproduction flags: `--arms 0 --pairs 150 --seed-base 281474976710656 --delays 27 --reserve-weight 0 --allow-ledger-seeds`. Reporting flags: `--arms 0 C R CR --pairs 125 --pair-offset OFFSET --seed-base $((281474976710656 + 10000 + OFFSET)) --delays 27 --reserve-weight 1 --resume`, with the shared exclusions JSON and an authorized worker cap. Each shard’s complete deck/opponent/seat schedule is retained in schedule.json; receipts retain exact launch commands. Omitting --arms preserves the original simulator/player behavior.','', 'Full per-game reductions, latency arrays, schedules and receipts were collected on 04 under this report directory; leased copies remain in the isolated lease-local runtime. Compact JSON and source hashes accompany this report. Pointwise exploration intervals carry no confirmatory interpretation.']
 if 'throughput_qualification' in result:
  q=result['throughput_qualification'];lines+=['','## Throughput guard qualification','',q['report_text'],'','Details and phase samples are retained in receipts/coexistence-summary.json. This sequential exploration check is research guidance; it does not prove a population guarantee. Legacy primary wall times remain unchanged.']
 (root/'RESULTS.md').write_text('\n'.join(lines)+'\n')
 print(json.dumps(dict(primary_losses={a:p['estimates'][a]['game_loss_fraction'] for a in ARMS},tuning=result['tuning'],budget_losses={a:result.get('budget_check',{}).get('estimates',{}).get(a,{}).get('game_loss_fraction') for a in ARMS})))
if __name__=='__main__':main()
