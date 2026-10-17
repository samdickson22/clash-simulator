"""Collection priority under explicit request income, using singleton point estimates."""
import math

def priority(ranked,inventory):
 # Gold offers/chests have no measured arrival model; no gem-copy offers.
 # This is a request-only priority heuristic, not a simulated combined plan.
 wild=dict(inventory['wild_cards']);remaining={r['card']:dict(r) for r in ranked};by={r['card']:r for r in inventory['rows']};order=[]
 while remaining:
  options=[]
  for card,r in remaining.items():
   account=by[card];rar=account['rarity'].lower();raw_gap=max(0,account['needed']-account['held_copies']);grant=2 if rar=='rare' else 8
   gap=max(0,raw_gap-wild[rar]);requests=math.ceil(gap/grant)
   # Delay wild redemption until copies arrive: use only what unlocks this level.
   used=max(0,raw_gap-requests*grant);assert used<=wild[rar]
   eff=100*r['delta']/max(1,requests)
   options.append(dict(r,missing_copies_sequential=gap,wild_allocated=used,requests_sequential=requests,hours_sequential=7*requests,pp_per_request_sequential=eff))
  positive=[r for r in options if r['delta']>0]
  chosen=max(positive,key=lambda r:(r['pp_per_request_sequential'],r['delta'],-r['requests_sequential'])) if positive else min(options,key=lambda r:r['requests_sequential'])
  chosen['selection_basis']='largest positive pooled point delta/request cycle' if positive else 'no positive singleton point remains; closest unlock only, no inferred benefit'
  order.append(chosen);wild[chosen['rarity'].lower()]-=chosen['wild_allocated'];remaining.pop(chosen['card'])
 return order
