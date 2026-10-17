"""Passive complete-bank audit and paired level-effect estimates."""
import json
from collections import Counter
import numpy as np
from sam_common import ROOT,OLD,utc,sha,dump
from fullpool_clean import problems
GROUPS={'R3a':('R3a',),'strong opponent':('LIVE-K4CW-r16',),'pooled':('R3a','LIVE-K4CW-r16')}
def analyze(stage):
 d=ROOT/stage;bank=json.loads((d/'validation/bank.json').read_text());meta=json.loads((d/'manifest.json').read_text())
 assert sha(d/'manifest.json')==bank['manifest_sha256']
 assert all(sha(ROOT/n)==v for n,v in meta['helper_sha256'].items())
 rows=[json.loads(p.read_text()) for p in (d/'validation/rows').glob('*.json')]
 expected={(c['id'],n,p) for c in bank['cases'] for n in bank['candidates'] for p in bank['players']}
 lookup={(r['id'],r['candidate'],r['player']):r for r in rows};assert len(lookup)==len(rows) and set(lookup)<=expected
 bad=[r for r in rows if problems(r)];assert not bad,bad[:1]
 text=[f'## {meta["prior"]["label"]}',f'{len(rows)}/{len(expected)} games; genuine flags {len(bad)}. Bank SHA `{sha(d/"validation/bank.json")}`.']
 if set(lookup)!=expected:return text
 searches=0
 for row in rows:
  case=next(c for c in bank['cases'] if c['id']==row['id']);seat=row['seat'];result=row['result'];candidate=row['candidate']
  assert row['bank_sha256']==sha(d/'validation/bank.json')
  for field in ('seed','seat','source_index','opponent','opponent_deck','opponent_levels','own_permutation','opponent_tower_level'):assert row[field]==case[field]
  assert result['terminal'] and row['win']==int(result['winner']==seat)
  assert row['truth_levels'][seat]==meta['candidate_plans'][candidate]['levels']
  assert row['truth_levels'][1-seat]==case['opponent_levels']
  assert row['truth_tower_levels'][seat]==7 and row['truth_tower_levels'][1-seat]==case['opponent_tower_level']
  assert result['decks'][seat]==[meta['candidates'][candidate][i] for i in case['own_permutation']]
  assert result['decks'][1-seat]==case['opponent_deck']
  diag=result['public_diagnostics'][str(seat)];config=diag['start_config']
  assert config['belief_class']=='FullPoolBelief' and config['name']==row['player']
  assert config['fast_path'].endswith('/fits/f1a2/step-001200.pt')
  assert config['native_threads']==1 and config['pool_size']==0 and config['chunks']==4
  assert all(config[k] is None for k in ('deadline_seconds','effective_deadline_seconds','search_deadline_seconds'))
  assert diag['cutoff_hits']==0;searches+=diag['search_decisions']
  if row['opponent']=='LIVE-K4CW-r16':
   strong=result['public_diagnostics'][str(1-seat)]['start_config']
   assert strong['belief_class']=='LiveBelief' and strong['runtime_belief']=='c56'
   assert strong['fast_path'].endswith('/students/it5s2-step001200.pt') and strong['fast_threshold']==.5375
 assert all(len({(r['host'],r['block']['worker_pid']) for r in rows if r['id']==c['id']})==1 for c in bank['cases'])
 assert len({c['seed'] for c in bank['cases']})==len(bank['cases'])
 base=json.loads((ROOT/'base-bank.json').read_text())
 assert [{k:c[k] for k in base['cases'][0]} for c in bank['cases']]==base['cases']
 dump(d/'integrity-audit.json',dict(utc=utc(),passed=True,games=len(rows),cases=len(bank['cases']),search_decisions=searches,bank_sha256=sha(d/'validation/bank.json'),cutoff_hits=0,genuine_failures=0,same_case_one_host_and_worker=True,host_games=dict(Counter(r['host'] for r in rows))))
 text.append(f'Complete-bank integrity audit PASS: {len(rows)} games, {searches} search decisions, zero genuine failures/cutoffs.')
 if meta.get('reference_stage'):
  reference=ROOT/meta['reference_stage'];assert sha(reference/'validation/bank.json')==meta['reference_bank_sha256']
  rb=json.loads((reference/'validation/bank.json').read_text());assert rb['cases']==bank['cases']
  assert json.loads((reference/'integrity-audit.json').read_text())['passed']
  baselines=[json.loads(p.read_text()) for p in (reference/'validation/rows').glob('*.json') if json.loads(p.read_text())['candidate']=='baseline']
  assert len(baselines)==len(bank['cases']) and all(not problems(r) for r in baselines)
  rows+=baselines;lookup.update({(r['id'],r['candidate'],r['player']):r for r in baselines});bank=dict(bank,candidates=['baseline',*bank['candidates']])
  text.append('Paired comparison reuses200 baseline rows from the completed audited shifted bank. Only400 new singleton games; deterministic source/config and cases/opponent levels unchanged. Cached baseline may have run on a different host; no wall deadline.')

 summary=[];player=bank['players'][0]
 for group,policies in GROUPS.items():
  rng=np.random.default_rng(0);boot={n:[] for n in bank['candidates']};wins=Counter();n=0
  for policy in policies:
   cases=[c for c in bank['cases'] if c['opponent']==policy];ix=rng.integers(0,len(cases),(20000,len(cases)))
   for candidate in bank['candidates']:
    v=np.array([lookup[c['id'],candidate,player]['win'] for c in cases],dtype=float)
    boot[candidate].append(v[ix].mean(1));wins[candidate]+=int(v.sum())
   n+=len(cases)
  boot={k:np.mean(v,axis=0) for k,v in boot.items()}
  for candidate in bank['candidates']:
   summary.append(dict(candidate=candidate,group=group,n=n,wins=wins[candidate],baseline_wins=wins['baseline'],delta=(wins[candidate]-wins['baseline'])/n,ci=np.quantile(boot[candidate]-boot['baseline'],[.025,.975]).tolist()))
 dump(d/'validation/summary.json',summary)
 if stage=='battlelog1850':
  import copy_targets
  ranked=copy_targets.rank(summary);dump(d/'validation/singleton-ranking.json',ranked)
  dump(d/'validation/copy-efficiency-ranking.json',sorted(ranked,key=lambda r:r['pp_per_missing_copy'],reverse=True))
  dump(d/'validation/request-efficiency-ranking.json',sorted(ranked,key=lambda r:r['pp_per_request_cycle'],reverse=True))
  import request_order
  order=request_order.priority(ranked,json.loads((ROOT/'affordability-income.json').read_text()));dump(d/'validation/request-priority.json',order)
  first=order[0]
  text += [f'First clan target under the request-only point-estimate heuristic: {first["card"]}, {first["requests_sequential"]} requests, {first["hours_sequential"]}hours if the next request waits7hours. Priority order: '+ ' → '.join(r['card'] for r in order)+'. This is a collection priority, not proof of a unique strongest card or a simulated combined-upgrade plan. Later entries recalculate gaps after shared wilds are allocated once. Wild redemption waits until request grants arrive, using only the copies needed for the upgrade; request rounding can save wilds. Shop offers/chests can change the order.']
  text+=['|Sequential request priority|Missing after remaining wilds|Wilds allocated|Requests / hours|Δ pp per request cycle|','|---|---:|---:|---:|---:|']
  for r in order:text.append(f'|{r["card"]}|{r["missing_copies_sequential"]}|{r["wild_allocated"]}|{r["requests_sequential"]} / {r["hours_sequential"]}|{r["pp_per_request_sequential"]:+.3f}|')
  text+=['','|Singleton pooled point rank|Δ pp [95% CI]|Missing copies after wilds|Δ pp per missing copy [95% CI]|','|---|---:|---:|---:|']
  for r in ranked:
   ci=r['ci'];eff=r['pp_per_missing_copy_ci']
   text.append(f'|{r["card"]}|{100*r["delta"]:+.1f} [{100*ci[0]:+.1f}, {100*ci[1]:+.1f}]|{r["missing_copies"]} {r["rarity"]}|{r["pp_per_missing_copy"]:+.3f} [{eff[0]:+.3f}, {eff[1]:+.3f}]|')
  text+=['Clan request assumptions: one per7hours,2rare or8common copies granted. Shop gold offers/chests may shorten times; no frequency model. No gem deck-copy offers.', '', '|Singleton|Requests|Hours if first request now / after7h|Δ pp per request cycle|','|---|---:|---:|---:|']
  for r in ranked:text.append(f'|{r["card"]}|{r["clan_requests"]}|{r["clan_hours_first_request_now"]} / {r["clan_hours_next_request_in7h"]}|{r["pp_per_request_cycle"]:+.3f}|')
  text+=['Copy-efficiency is a descriptive ratio per missing card copy, with pointwise CIs scaled by the fixed copy gap. It is not gem ROI. Common/rare copies have different supply/prices. Wild allocations compete across cards. Valkyrie9/20 is confirmed. No multiplicity correction or unique best claim.']
 if 'all-plus1' in bank['candidates']:
  pooled=next(r for r in summary if r['candidate']=='all-plus1' and r['group']=='pooled')
  best=max((r for r in summary if r['group']=='pooled' and r['candidate'] not in ('baseline','all-plus1')),key=lambda r:r['delta'])
  text += [f'All eight cards +1: pooled {pooled["baseline_wins"]}/{pooled["n"]} current wins versus {pooled["wins"]}/{pooled["n"]}, paired Δ {100*pooled["delta"]:+.1f} pp [{100*pooled["ci"][0]:+.1f}, {100*pooled["ci"][1]:+.1f}]. Largest singleton point estimate: {best["candidate"]}, {100*best["delta"]:+.1f} pp [{100*best["ci"][0]:+.1f}, {100*best["ci"][1]:+.1f}]. This point ranking does not establish a unique best upgrade. Absolute simulated win rates depend on the assumed population and policies; they are not forecasts of actual ladder win rates.']
 text+=['','|Opponent group|Arm|Wins|Current wins|Paired Δ pp [95% CI]|','|---|---|---:|---:|---|']
 for r in summary:
  text.append(f'|{r["group"]}|{r["candidate"]}|{r["wins"]}/{r["n"]}|{r["baseline_wins"]}/{r["n"]}|{100*r["delta"]:+.1f} [{100*r["ci"][0]:+.1f}, {100*r["ci"][1]:+.1f}]|')
 import diagnostic_metrics as metrics
 old=metrics.GROUPS;metrics.GROUPS=GROUPS
 try:diag=metrics.summarize_metrics(rows,bank['players'],bank['candidates'])
 finally:metrics.GROUPS=old
 dump(d/'validation/metrics-summary.json',diag);text.extend(metrics.markdown(diag))
 text+=['','Prior inputs: '+json.dumps(meta['prior'],sort_keys=True)]
 return text
def main():
 lines=['# Sam deck: current affordability and +1-level sizing',f'Updated {utc()}. Hypothetical level gains; no spending or live deck changes.',(ROOT/'COPY-TARGETS.md').read_text()]
 ranking=ROOT/'battlelog1850/validation/request-priority.json'
 if ranking.exists():
  first=json.loads(ranking.read_text())[0]
  lines.insert(1,f'First clan target: **{first["card"]}**. Pooled paired Δ **{100*first["delta"]:+.1f} pp [{100*first["ci"][0]:+.1f}, {100*first["ci"][1]:+.1f}]**,100cases per opponent policy. Request-income collection order: Valkyrie → Cannon → MiniPekka → Giant; Fireball/Bats deferred on this evidence. The corrected23-row distribution agrees; no re-run, as directed.')
 budget=json.loads((ROOT/'affordability-0909.json').read_text())
 common=sum(r['needed']-r['held_copies'] for r in budget['rows'] if r['rarity']=='Common')-budget['wild_cards']['common']
 rare=sum(r['needed']-r['held_copies'] for r in budget['rows'] if r['rarity']=='Rare')-budget['wild_cards']['rare']
 lines += [f'The all-eight +1 counterfactual costs {sum(r["gold"] for r in budget["rows"]):,} gold if copies are obtained. At this snapshot it still lacks {common} common and {rare} rare copies after using the shared wild-card stocks once. It is not an executable spending plan.']
 if (ROOT/'preflight/receipt.json').exists():
  receipt=json.loads((ROOT/'preflight/receipt.json').read_text());assert receipt['passed']
  lines += [f'Unscored serial replay passed {receipt["utc"]}: identical command SHA `{receipt["command_sha256"]}` and state hash{receipt["state_hash"]}, ourKing7/opponentKing8. The first import attempt failed before any game because the frozen runtime was read-only for Numba caching; the corrected launch uses a writable cache inside this job. No runtime files or scored rows were changed.']
 for stage in ('battlelog1850','shifted','shifted-extra'):
  if (ROOT/stage/'NOT-RUN.json').exists():lines += ['## Optional shifted Valkyrie/Fireball follow-up','Registered400games but not launched;0newgames. BOT LEAD requested final publication and resource release after the measured result. No claim is made from this unrun extension.']
  elif (ROOT/stage/'validation/bank.json').exists():lines+=analyze(stage)
  elif stage=='battlelog1850':lines += ['## 1,850 Battle Log prior','Waiting for the new population file; not run yet.']
 if (ROOT/'PRIOR-COMPARISON.md').exists():lines += [(ROOT/'PRIOR-COMPARISON.md').read_text()]
 lines+=['## Protocol and limits',
 'Shifted row: six arms, current account levels, all eight cards +1, and single +1 on Giant, MiniPekka, Cannon or Bats. Measured row: eight arms, adding Valkyrie and Fireball singletons. Our King stays7 in every arm. Current levels are Valkyrie6/Archers8/Bats7/Cannon7/Fireball6/Zap6/MiniPekka7/Giant7. These hypothetical upgrades need not be affordable.',
 'One reserve serial full-pool twin: FP-LD-K4L-R-gs-rw-fc-c4-mk1a1-res. Deployed all-L11 planner handling retained, no ExactLevelRoot. Explicit f1a2 fallback; native1/pool0/chunks4, no deadlines in search/LivePlayer/Recorder. Zero cutoffs follow from no-wall construction, not live latency. Strong opponent remains C56 LiveBelief plus it5s2@0.5375 in a separate Runtime; process-wide belief/fast env does not leak between seats.',
 'One fresh bank of200 cases (100 per R3a/strong policy), six shifted/eight measured arms and randomized arm order. All arms of a case stay on one host/worker. The empirical-prior variant retains seeds, opponent decks, seats and own permutations; only opponent card/tower population draws change. No level input is treated as per-match knowledge. Opponent decks remain the original91 true Battle Log decks uniformly sampled; this is a level-prior sensitivity, not a new deck-frequency sample.',
 'Paired win-rate differences:20,000 percentile bootstrap resamples within policy, identical case indices across arms; pooled weights the two policies equally. Draws are nonwins. Intervals are pointwise, no multiplicity adjustment. They exclude prior/simulator/planner uncertainty; saturated samples can produce degenerate intervals and do not establish equivalence.',
 'The all-eight improvement must not be divided by eight or assumed to equal the sum of singleton effects. It also includes Archers and Zap, which are not singleton arms. Valkyrie and Fireball singletons were added only in the measured-prior row. No unique singleton ranking or immediate purchase is established by the largest point estimate.',
 'The shifted row extrapolates far beyond observed trophies66–841 to1,850. Common-level shift is+4.542 with stochastic integer rounding, mean9.306. Opponent King8 is assumed per BOT LEAD; our King7. Non-common levels use common draw minus1 clamped to rarity floor. The later empirical level/tower population is reported separately. A duplicate King7 row would add1,200 games and is omitted in favor of the fresh-prior row.',
 'Clean rule: opponent policy refusals are normal. Our refusals, native failures, live errors and nonterminal games flag the case. The predeclared cosmetic SpearGoblin_Dummy garrison sprite is the sole unmapped exception; raw counters retained.',
 'Frozen source1a65dcd1a00c5e3f891228df878d3bbebe4de187, live16402b-r3 native SHAde11f12401da396b309cd2e5d3ea422cfa1c94f462a4e3250fd51d89a62887b1. Truth RoyaleSim0.1.34/client16.402, binarySHA97e03055332faeb986c91a12aa64c6e22ca65948b68351803d914e0a84eb43bb. Official live16402c cost gamedata SHAa7de3e93eb4320c48775da97cd0e5113fb793ea57782ba0eb006af0bd6eb0ccb. Private bank/manifests, raw rows and immutable model/source receipts remain outside git.']
 (ROOT/'REPORT.md').write_text('\n\n'.join(lines).replace('|\n\n|','|\n|')+'\n')
if __name__=='__main__':main()
