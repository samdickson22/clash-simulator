"""Passive copy shortfalls and singleton copy-efficiency; never spends currency."""
import json,math
from sam_common import ROOT,utc,sha,dump

def snapshot():
 original=json.loads((ROOT/'affordability.json').read_text());data=dict(original)
 data.update(utc=utc(),gold=28518,gems=425,source='BOT LEAD account update, read02:51–08:53Z; ACCOUNT-LOG snapshot',account_log_sha256=sha(ROOT/'input-ACCOUNT-LOG-0909.md'),gem_authorization='Sam approved deck-card copies; LIVE LEAD decides, no worker spend',display_risk='Valkyrie9/20 now confirmed by LIVE LEAD; previous discrepancy resolved',copy_income='No deck-copy gem offers. Clan requests assumed1/7h,2rare or8common as granted; shop gold offers/chests opportunistic, no frequency assumed')
 data['rows']=[dict(r) for r in original['rows']]
 held={'Valkyrie':9,'Cannon':110}
 for r in data['rows']:
  r['held_copies']=held.get(r['card'],r['held_copies']);r['extra_copies_needed']=max(0,r['needed']-r['held_copies']-r['wild_available'])
 dump(ROOT/'affordability-0909.json',data,True)
 lines=['# Current copy targets',f'Account update recorded {data["utc"]}: gold28,518; gems425; wild24common/4rare. King7. No immediate upgrade affordable with held copies and wilds alone. No gem offers for deck-card copies. LIVE LEAD makes spending decisions. No purchases or requests executed here.','Each row allocates the entire relevant wild-card stock to that one card. These are competing alternatives, not simultaneous reservations.','|Card|Upgrade|Held / needed|Wilds|Missing copies|Gold|','|---|---|---:|---:|---:|---:|']
 for r in data['rows']:lines.append(f'|{r["card"]}|{r["from_level"]}→{r["to_level"]}|{r["held_copies"]}/{r["needed"]}|{r["wild_available"]} {r["rarity"].lower()}|{r["extra_copies_needed"]}|{r["gold"]:,}|')
 lines += ['Valkyrie9/20 is confirmed. Clan income assumed one request every7hours, granting2rare or8common. Time is7hours×ceil(missing/grant), or7hours less if the first request is ready now. Daily gold shop offers and chests may shorten this; their arrival rates are unknown. Copies of common and rare cards have different availability and price. The pp-per-copy ranking is not gem ROI.']
 (ROOT/'COPY-TARGETS.md').write_text('\n\n'.join(lines)+'\n')

def rank(summary):
 data=json.loads((ROOT/'affordability-income.json').read_text());by={r['card'].lower()+'-plus1':r for r in data['rows']};out=[]
 for row in summary:
  if row['group']!='pooled' or row['candidate'] not in by:continue
  r=by[row['candidate']];gap=r['extra_copies_needed'];requests=math.ceil(gap/(2 if r['rarity']=='Rare' else 8));out.append(dict(row,card=r['card'],missing_copies=gap,rarity=r['rarity'],gold=r['gold'],clan_requests=requests,clan_hours_next_request_in7h=7*requests,clan_hours_first_request_now=7*(requests-1),pp_per_request_cycle=100*row['delta']/requests,pp_per_missing_copy=100*row['delta']/gap,pp_per_missing_copy_ci=[100*v/gap for v in row['ci']]))
 return sorted(out,key=lambda r:r['delta'],reverse=True)
if __name__=='__main__':snapshot()
