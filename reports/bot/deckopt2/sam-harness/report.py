"""Light-only paired analysis; the upgrade decision precedes play comparisons."""
from collections import Counter
import json
import numpy as np
from sam_common import ROOT,OLD,utc,sha,dump
from fullpool_clean import problems
GROUPS={'weak pool':('R3a','v1'),'strong opponent':('LIVE-K4CW-r16',),'pooled':('R3a','v1','LIVE-K4CW-r16')}
def summarize(bank,rows):
 lookup={(r['id'],r['candidate'],r['player']):r for r in rows};out=[]
 for player in bank['players']:
  for group,policies in GROUPS.items():
   rng=np.random.default_rng(0);means={n:[] for n in bank['candidates']};wins=Counter();n=0
   for policy in policies:
    cases=[c for c in bank['cases'] if c['opponent']==policy]
    ix=rng.integers(0,len(cases),(20000,len(cases)))
    for candidate in bank['candidates']:
     values=np.array([lookup[c['id'],candidate,player]['win'] for c in cases],dtype=float)
     means[candidate].append(values[ix].mean(1));wins[candidate]+=int(values.sum())
    n+=len(cases)
   means={candidate:np.mean(parts,axis=0) for candidate,parts in means.items()}
   for candidate in bank['candidates']:
    for reference in bank['candidates']:
     out.append(dict(player=player,candidate=candidate,reference=reference,group=group,n=n,wins=wins[candidate],reference_wins=wins[reference],win_rate=wins[candidate]/n,reference_win_rate=wins[reference]/n,delta=(wins[candidate]-wins[reference])/n,delta_ci=np.quantile(means[candidate]-means[reference],[.025,.975]).tolist()))
 return out
def spending(bank,summary):
 variants=json.loads((ROOT/'upgrade-variants.json').read_text());reserve=next(p for p in bank['players'] if p.endswith('-res'))
 strong=[r for r in summary if r['player']==reserve and r['group']=='strong opponent' and r['reference']=='baseline']
 ranking=sorted(strong,key=lambda r:(-r['win_rate'],variants['plans'][r['candidate']]['gold'],r['candidate']))
 best=ranking[0]['candidate'];comparisons=[r for r in summary if r['player']==reserve and r['group']=='strong opponent' and r['candidate']==best and r['reference']!=best]
 separated=all(r['delta_ci'][0]>0 for r in comparisons)
 chosen=best if separated else variants['fallback']
 result=dict(frozen_utc=utc(),chosen=chosen,strong_res_point_leader=best,separated=separated,
  reason='Strong reserve leader separated from all alternatives by positive paired lower95%CI.' if separated else 'Paired strong-reserve intervals overlap zero; use the approved MiniPekka+Cannon fallback.',
  plan=variants['plans'][chosen],strong_res_ranking=ranking,leader_pairwise_strong_res=comparisons,
  bank_sha256=sha(ROOT/'upgrades/validation/bank.json'),collection_sha256=variants['collection_sha256'],gems_spent=0,
  execution_warning='Resources are the frozen pre-spend snapshot. If LIVE LEAD already applied the fallback, do not repeat spending; use the ranking as counterfactual information.')
 dump(ROOT/'SPENDING-PLAN.json',result)
 lines=['# Final spending plan',result['reason'],'',result['execution_warning'],'','|Order|Card|Level|Gold|Held copies|Wild cards|','|---:|---|---|---:|---:|---|']
 for i,s in enumerate(result['plan']['upgrade_order'],1):lines.append(f'|{i}|{s["card"]}|{s["from_level"]}→{s["to_level"]}|{s["gold"]}|{s["held_copies"]}|{s["wild_cards"]} {s["rarity"]}|')
 plan=result['plan'];lines += [f'\nTotal {plan["gold"]} gold; remaining {plan["gold_left"]}. Wild cards left {plan["wild_cards_left"]}. Gems unchanged at410; no gems spent.\n']
 lines += ['\nFull strong-opponent ranking (reserve point estimates first; overlapping intervals do not establish an ordering):\n',
           '|Rank|Plan|Reserve wins|Reserve Δ pp vs fallback [95% CI]|Base wins|Remaining gold spend|',
           '|---:|---|---:|---|---:|---:|']
 for i,r in enumerate(ranking,1):
  base=next(s for s in summary if s['player']!=reserve and s['candidate']==r['candidate'] and s['reference']=='baseline' and s['group']=='strong opponent')
  lines.append(f'|{i}|{r["candidate"]}|{r["wins"]}/{r["n"]}|{100*r["delta"]:+.1f} [{100*r["delta_ci"][0]:+.1f}, {100*r["delta_ci"][1]:+.1f}]|{base["wins"]}/{base["n"]}|{variants["plans"][r["candidate"]]["gold"]}|')
 (ROOT/'SPENDING-PLAN.md').write_text('\n'.join(lines))
 return lines
def main():
 text=['# Sam deck follow-up',f'Updated {utc()}. Information-only deck comparison; Sam chooses his live deck. Spending uses reachable account levels. No account actions from this harness.\n']
 if (ROOT/'SPENDING-PLAN.json').exists():text += [(ROOT/'SPENDING-PLAN.md').read_text()]
 statuses=[]
 for stage in ('upgrades','max','current'):
  bank=json.loads((ROOT/stage/'validation/bank.json').read_text());meta=json.loads((ROOT/stage/'manifest.json').read_text())
  rows=[json.loads(p.read_text()) for p in (ROOT/stage/'validation/rows').glob('*.json')];expected=len(bank['cases'])*len(bank['candidates'])*len(bank['players'])
  bad=[r for r in rows if problems(r)];keys=[(r['id'],r['candidate'],r['player']) for r in rows];assert len(keys)==len(set(keys))
  assert all(r['bank_sha256']==sha(ROOT/stage/'validation/bank.json') for r in rows)
  statuses.append(dict(stage=stage,rows=len(rows),expected=expected,flags=len(bad)))
  title={'upgrades':'Six reachable upgrade plans (priority)','max':'Primary PLAY: all cards and towers L16','current':'Secondary: frozen pre-spend account cards, towers L7'}[stage]
  text += ['## '+title,f'{len(rows)}/{expected} games, {len(bad)} genuine flags. Bank {bank["created_utc"]}, SHA `{sha(ROOT/stage/"validation/bank.json")}`.\n']
  if stage=='upgrades':
   text.append('Here baseline means the approved MiniPekka+Cannon plan, not the old live deck. All six arms use Sam\'s eight cards. Inventory frozen before spending:28,668gold,98common/24rare wilds,410gems. If LIVE LEAD applies the fallback before this result, do not repeat its spending; treat alternative arms as counterfactuals against this snapshot.\n')
  else:
   text.append('Here baseline means the old live eight-card deck. Sam and inferno are the two comparison decks. Levels below are truth inputs; planner level handling remains deployed.\n')
   if stage=='current':text.append('This is the02:51–02:55Z pre-spend snapshot. LIVE LEAD later executed MiniPekka6→7 at04:49:50Z and Cannon6→7 at04:51:38Z, after this bank began; those purchases do not change its frozen arms. It does not measure the later upgraded live account.\n')
   for name,deck in meta['candidates'].items():text.append(name+': '+', '.join(f'{c} L{meta["candidate_plans"][name]["levels"][c]}' for c in deck)+'.\n')
  if bad or len(rows)!=expected:
   text.append('Incomplete: no frozen inference or spending decision from partial results.\n');continue
  expected_keys={(c['id'],n,p) for c in bank['cases'] for n in bank['candidates'] for p in bank['players']};assert set(keys)==expected_keys
  audit_path=ROOT/stage/'integrity-audit.json'
  if audit_path.exists():
   receipt=json.loads(audit_path.read_text())
   assert receipt['passed'] and receipt['complete'] and receipt['games']==expected and receipt['bank_sha256']==sha(ROOT/stage/'validation/bank.json')
   text.append(f'Final integrity audit PASS at {receipt["utc"]}: {receipt["games"]} games, {receipt["search_decisions"]} search decisions, zero genuine failures and zero cutoffs. All case arms stayed on one host and worker; inputs, truth levels, scoped players and disjoint seeds were checked.\n')
  summary=summarize(bank,rows);dump(ROOT/stage/'validation/summary.json',summary)
  if stage=='upgrades' and not (ROOT/'SPENDING-PLAN.json').exists():text += spending(bank,summary)
  if stage!='upgrades':
   text += ['|Player|Opponent policy|Old live wins|Sam wins|Inferno wins|',
            '|---|---|---:|---:|---:|']
   for player in bank['players']:
    for policy in meta['opponents']:
     values=[]
     for candidate in ('baseline','sam','inferno'):
      part=[r for r in rows if r['player']==player and r['candidate']==candidate and r['opponent']==policy]
      values.append(f'{sum(r["win"] for r in part)}/{len(part)}')
     text.append('|'+ '|'.join(['reserve' if player.endswith('-res') else 'base',policy,*values])+'|')
   text.append('')
  text += ['|Player|Candidate|Reference|Group|Paired n|Win%|Reference%|Δ pp [95% CI]|','|---|---|---|---|---:|---:|---:|---|']
  for r in summary:
   show=(r['reference']=='baseline' and r['candidate']!='baseline') or (stage!='upgrades' and r['candidate']=='sam' and r['reference']=='inferno')
   if show:text.append(f'|{"reserve" if r["player"].endswith("-res") else "base"}|{r["candidate"]}|{r["reference"]}|{r["group"]}|{r["n"]}|{100*r["win_rate"]:.1f}|{100*r["reference_win_rate"]:.1f}|{100*r["delta"]:+.1f} [{100*r["delta_ci"][0]:+.1f}, {100*r["delta_ci"][1]:+.1f}]|')
  import diagnostic_metrics as metrics
  saved=metrics.GROUPS;metrics.GROUPS=GROUPS
  try:diag=metrics.summarize_metrics(rows,bank['players'],bank['candidates'])
  finally:metrics.GROUPS=saved
  dump(ROOT/stage/'validation/metrics-summary.json',diag);text.extend(metrics.markdown(diag))
 text += ['## Protocol and limits\n','True Battle Log decks: all91 rows uniformly sampled; no C56 opponent projection. Opponent card levels in account-level scenarios are independently sampled from the prior population, never per-match truth. The rows contain no opponent King levels: opponent King7 is an assumption; our account King7 is confirmed. MAX truth is L16 for all cards and both towers, independently checked against L15 to rule out clamping.\n',
 'The account-level prior uses observed common-level counts L2:7, L3:17, L4:61, L5:110, L6:53, L7:2. For a non-common card, subtract one from the common draw and clamp to its rarity floor (rare3, epic6, legendary9, champion11). This rarity adjustment is a scenario assumption, not an observed rare-card level. Cards are drawn independently. The account-level upgrade test is heavily saturated and may overstate performance if current opponents exceed this historical prior; MAX has no such level-prior sampling.\n',
 'Before any secondary game or claim, the newer full ACCOUNT-LOG read03:05:29Z corrected non-Sam cards to Musketeer5, Minions6 and Goblins2 (Skeletons remains7). The secondary input amendment preserved all cases, seeds and dispatch; archived original inputs and current-level-correction.json record both hashes. Sam\'s eight, the upgrade bank and the MAX bank were unchanged.\n',
 'Both players retain deployed all-L11/root/belief planning. Our scoped FullPoolBelief/f1a2 and the strong C56 LiveBelief/it5s2 use separate Runtimes. Serial configuration: deadlineNone in search, LivePlayer and Recorder; native1, pool0, chunks4. Zero cutoffs are by construction, not a claim about live wall200 latency. No ExactLevelRoot is installed. rext-bc n/a.\n',
 'Base/reserve labels denote FP-LD-K4L-R-gs-rw-fc-c4-mk1a1 and its -res variant. They are built from the corresponding LIVE-K4L-R-gs-rw-fc-w200-t4-p4-mk1a1 bundles, then configured as the approved serial c4 twin of p4 with all deadlines cleared. The explicit fallback default is f1a2, whereas the named K4L-R-gs-rw-fc-c4-mk1a1 player defaults to R3a; no wall cutoff is active here. Wall200 rows were not run on these shared hosts. The extra full-game L16 replay matched twice: command SHA256 2d20983bf75f3332447a0bc4a7e18220e1dff9438afd4798b936d1c905b1024f, state hash4982442046507175223.\n',
 'All case arms share one worker/host with randomized arm order. Actual wins are primary and draws are nonwins. Paired percentile bootstrap:20,000 within-policy resamples, identical case indices for all candidates/references; policy weights equal. Intervals are pointwise, with no multiplicity adjustment. Saturated all-win samples can give degenerate intervals; they do not prove equivalence or100% true performance. Opponent-level-prior and simulator/planner uncertainty are outside these intervals. Upgrade ranking uses strong reserve first; overlapping paired intervals invoke the pre-approved fallback. These tests do not choose Sam\'s live deck.\n',
 'Clean rule: opponent refusals are ordinary policy behavior; our refusals, native failures, live errors and nonterminal games flag the case. Raw counters/rows retained; the predeclared SpearGoblin_Dummy garrison sprite is the sole expected unmapped exception. Every raw result retains per-side start configuration and truth card/tower levels.\n',
 'Source: frozen1a65dcd1a00c5e3f891228df878d3bbebe4de187; planning live16402b-r3/native de11f12401da396b309cd2e5d3ea422cfa1c94f462a4e3250fd51d89a62887b1. Truth RoyaleSim0.1.34/client16.402, binary97e03055332faeb986c91a12aa64c6e22ca65948b68351803d914e0a84eb43bb. Official live16402c cost/rarity gamedata SHAa7de3e93eb4320c48775da97cd0e5113fb793ea57782ba0eb006af0bd6eb0ccb. Account snapshot and complete per-stage manifests/banks remain in this job directory, outside git.\n']
 (ROOT/'REPORT.md').write_text('\n'.join(text).rstrip()+'\n');dump(ROOT/'analysis-status.json',dict(utc=utc(),stages=statuses));print(json.dumps(statuses))
if __name__=='__main__':main()
