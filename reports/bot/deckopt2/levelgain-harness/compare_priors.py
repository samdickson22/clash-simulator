"""Compare frozen14- and23-row populations after the measured run finishes."""
import collections,json
from sam_common import ROOT,OLD,utc,sha,dump

def main():
 assert json.loads((ROOT/'battlelog1850/integrity-audit.json').read_text())['passed']
 from bot.fullpool.cards import engine_name
 gd=json.loads((OLD/'upgrade-source-gamedata.json').read_text());rarity={engine_name(r['name'],strict=False):str(r['rarity']).lower() for r in gd['items']['spells']}
 def read(name):
  path=ROOT/name;rows=[json.loads(s) for s in path.read_text().splitlines()];levels=collections.Counter();counts=collections.defaultdict(collections.Counter);kings=collections.Counter();unknown=0;missing=0
  for row in rows:
   kings[int(row['opp_king_level'])]+=1
   for c,l in zip(row['opp_deck'],row['opp_levels']):
    if l is None:missing+=1;continue
    l=int(l);assert 1<=l<=16;levels[l]+=1
    if c is None:unknown+=1;continue
    counts[rarity[engine_name(c)]][l]+=1
  common=counts['common'];return dict(rows=len(rows),sha256=sha(path),level_counts=dict(levels),rarity_level_counts={k:dict(v) for k,v in counts.items()},king_counts=dict(kings),mean_common=sum(k*n for k,n in common.items())/sum(common.values()),verified_levels=sum(levels.values()),null_name_known_level=unknown,unread_levels=missing),rows
 a,ar=read('input-opponent-decks-20261017-1850.jsonl');b,br=read('input-opponent-decks-20261017-1850-23rows-corrected.jsonl')
 assert a['rows']==14 and b['rows']==23
 support=set(a['king_counts'])|set(b['king_counts']);tv=.5*sum(abs(a['king_counts'].get(k,0)/14-b['king_counts'].get(k,0)/23) for k in support)
 delta=b['mean_common']-a['mean_common'];result=dict(utc=utc(),old=a,new=b,common_mean_delta=delta,common_threshold_trigger=abs(delta)>=.3,king_support_changed=set(a['king_counts'])!=set(b['king_counts']),king_probability_total_variation=tv,king_distribution_changed=tv>0,prefix_level_data_unchanged=all(all(ar[i].get(k)==br[i].get(k) for k in ('opp_levels','opp_king_level','opp_trophies')) for i in range(14)))
 result['prefix_identities_unchanged']=all(ar[i]['opp_deck']==br[i]['opp_deck'] for i in range(14))
 dump(ROOT/'prior-comparison.json',result)
 lines=['# Population update:14 versus23 Battle Log rows',f'Compared after the frozen14-row run completed, {result["utc"]}. The running bank was never modified.','|Quantity|14-row snapshot|23-row snapshot|','|---|---:|---:|',f'|Verified card levels|{a["verified_levels"]}|{b["verified_levels"]}|',f'|Unverified level slots|{a["unread_levels"]}|{b["unread_levels"]}|',f'|Mean identified common level|{a["mean_common"]:.4f}|{b["mean_common"]:.4f}|']
 for level in sorted(set(a['level_counts'])|set(b['level_counts'])):lines.append(f'|Card level{level} count|{a["level_counts"].get(level,0)}|{b["level_counts"].get(level,0)}|')
 for level in sorted(support):lines.append(f'|King{level}|{a["king_counts"].get(level,0)}/14 ({100*a["king_counts"].get(level,0)/14:.2f}%)|{b["king_counts"].get(level,0)}/23 ({100*b["king_counts"].get(level,0)/23:.2f}%)|')
 lines += [f'Common mean change{delta:+.4f}; absolute0.3 threshold triggered: {result["common_threshold_trigger"]}. King support changed: {result["king_support_changed"]}; King mixture total-variation change{100*tv:.2f} percentage points. These descriptive checks do not replace case-level performance confidence intervals.',f'Old SHA `{a["sha256"]}`; new SHA `{b["sha256"]}`. Null identities are never invented; unverified levels remain missing.']
 lines.append('Translator corrections in corrected23 source: s70-m06 slot7 Goblins→GoblinBarrel (common→epic); s70-m03 slot1 Barbarians→GoblinCage, evo form (common→rare). Displayed levels unchanged. Original14 experiment remains frozen; form/confidence metadata retained in the source snapshot, not inferred into the unchanged historical deck bank.')
 (ROOT/'PRIOR-COMPARISON.md').write_text('\n\n'.join(lines).replace('|\n\n|','|\n|')+'\n');print(json.dumps(result))
if __name__=='__main__':main()
