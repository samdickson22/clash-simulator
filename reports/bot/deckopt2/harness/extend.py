"""Budget-stage orchestration. Original current-level screen remains immutable.

A is the frozen held-copy plan. B is reconciled shared-wild/gold allocation.
Do not create a second-screen bank until the original reference is complete.
"""
import argparse,json,shutil
from pathlib import Path
import numpy as np
from bot.deckopt2.run import PLAYERS,utc,sha,dump,bank,summarize,read_rows
from budget import ROOT,candidates,plan
import clean
clean.install()
read_rows=clean.read_rows

HELPERS=('budget.py','instrument.py','execute.py','extend.py','pool.py','clean.py')


def build_B(inventory):
    data=json.loads(inventory.read_text())
    assert data['gold']==8921 and data['cost_reconciliation']['ok'] is True
    counts=data['wild_cards']
    assert all(isinstance(v,int) and v>=0 for v in counts.values())
    a=json.loads((ROOT/'variant-A-copies-only.json').read_text())
    decks=a['candidates'];plans={n:plan(d,counts,data['gold'],Path(data['collection_path'])) for n,d in decks.items()}
    for current in plans.values():
        current['total_gold_from_original']=1400+current['gold']
        current['committed_gold']=1400
        assert current['total_gold_from_original']<=10321
    dump(ROOT/'variant-B-full-budget.json',dict(created_utc=utc(),inventory_sha256=sha(inventory),
         collection_sha256=sha(data['collection_path']),collection_path=data['collection_path'],table_sha256=sha(ROOT/'upgrade-source-gamedata.json'),
         budget=data['gold'],original_budget=10321,committed_gold=1400,committed=data['committed'],source_account_log_sha256=data['source_account_log_sha256'],wild_cards=counts,cost_reconciliation=data['cost_reconciliation'],
         candidates=decks,plans=plans,changed_from_A=[n for n,p in plans.items() if p['levels']!=a['plans'][n]['levels']],
         job_source_sha256={n:sha(ROOT/n) for n in HELPERS}),exclusive=True)
    print('B locked',len(plans),'plans; changed',sum(p['levels']!=a['plans'][n]['levels'] for n,p in plans.items()),flush=True)


def make_meta(variant):
    old=json.loads((ROOT/'manifest.json').read_text())
    base=variant['plans']['baseline']['levels']
    return dict(old,created_utc=utc(),candidates=variant['candidates'],own_levels=base,own_tower=6,
                candidate_plans=variant['plans'],collection_sha256=variant['collection_sha256'],
                resource_variant='B',variant_sha256=sha(ROOT/'variant-B-full-budget.json'),
                wild_cards=variant['wild_cards'],gold_budget=variant['budget'],original_gold_budget=variant['original_budget'],committed_upgrades=variant['committed'],
                job_source_sha256={n:sha(ROOT/n) for n in HELPERS})


def new_screen():
    read_rows(ROOT,'screen',True)
    variant=json.loads((ROOT/'variant-B-full-budget.json').read_text())
    root=ROOT/'new-cards';root.mkdir(exist_ok=True)
    meta=make_meta(variant)
    dump(root/'manifest.json',meta,exclusive=True)
    shutil.copyfile(variant['collection_path'],root/'collection.json')
    from bot.players.runtime import Runtime
    bank(root,Runtime(),meta,'screen',8,list(meta['candidates']))
    p=root/'screen/bank.json';data=json.loads(p.read_text())
    data.update(players=[PLAYERS[1]],candidate_plans_sha256=sha(ROOT/'variant-B-full-budget.json'),
                candidate_levels={n:p['levels'] for n,p in meta['candidate_plans'].items()},gold_budget=8921,
                note='32gold-feasibledecks;resonly;newos.urandombank;notvalidation')
    # No games exist; bank finalization precedes all launch receipts.
    assert not list((root/'screen/rows').glob('*.json'))
    dump(p,data)
    old=json.loads((ROOT/'screen/bank.json').read_text())
    assert not {c['seed'] for c in old['cases']}&{c['seed'] for c in data['cases']}
    print('Final second screen bank',utc(),sha(p),flush=True)


def select():
    old_data,old_rows=read_rows(ROOT,'screen',True)
    new_root=ROOT/'new-cards'
    new_data,new_rows=read_rows(new_root,'screen',True)
    old_summary=summarize(ROOT,'screen',True)
    new_summary=summarize(new_root,'screen',True)
    def score(summary,n):
        rows=[r for r in summary if r['candidate']==n and r['group']=='pooled']
        return sum(r['delta'] for r in rows)/len(rows)
    old_names=[n for n in old_data['candidates'] if n!='baseline']
    new_names=[n for n in new_data['candidates'] if n!='baseline']
    winner_old=max(old_names,key=lambda n:(score(old_summary,n),n))
    ranking=sorted(new_names,key=lambda n:(-score(new_summary,n),n))
    chosen=ranking[:3]
    if winner_old not in chosen:chosen.append(winner_old)
    else:
        third,fourth=ranking[2:4]
        lookup={(r['id'],r['candidate']):r['win'] for r in new_rows}
        diffs=np.array([lookup[c['id'],third]-lookup[c['id'],fourth] for c in new_data['cases']],dtype=float)
        se=float(diffs.std(ddof=1)/np.sqrt(len(diffs)))
        if score(new_summary,third)-score(new_summary,fourth)<=se:chosen.append(fourth)
    selected=['baseline']+chosen
    selection=dict(created_utc=utc(),rule='top3 newbudget resscreen bypooled pairedwindelta; include originalscreen meanbothplayers winner ifabsent; elsefourth ifwithin1SE ofthird',
                   selected=selected,original_winner=winner_old,
                   original_ranking=sorted([(n,score(old_summary,n)) for n in old_names],key=lambda x:(-x[1],x[0])),
                   budget_ranking=[(n,score(new_summary,n)) for n in ranking],
                   screen_bank_sha256=[sha(ROOT/'screen/bank.json'),sha(new_root/'screen/bank.json')],
                   variant_sha256=sha(ROOT/'variant-B-full-budget.json'))
    dump(ROOT/'selection.json',selection,exclusive=True)
    vroot=ROOT/'final-validation';vroot.mkdir(exist_ok=True)
    variant=json.loads((ROOT/'variant-B-full-budget.json').read_text())
    meta=make_meta(variant)
    dump(vroot/'manifest.json',meta,exclusive=True)
    shutil.copyfile(ROOT/'selection.json',vroot/'selection.json')
    (vroot/'screen').mkdir(exist_ok=True)
    shutil.copyfile(ROOT/'screen/bank.json',vroot/'screen/bank.json')
    from bot.players.runtime import Runtime
    bank(vroot,Runtime(),meta,'validation',150,selected)
    p=vroot/'validation/bank.json';data=json.loads(p.read_text())
    data.update(candidate_levels={n:meta['candidate_plans'][n]['levels'] for n in selected},gold_budget=8921,
                candidate_plans_sha256=sha(ROOT/'variant-B-full-budget.json'))
    assert not list((vroot/'validation/rows').glob('*.json'))
    dump(p,data)
    used={c['seed'] for b in (old_data,new_data) for c in b['cases']}
    assert not used&{c['seed'] for c in data['cases']}
    print('Fresh validation bank',utc(),sha(p),'decks',selected,flush=True)


def main():
    p=argparse.ArgumentParser();p.add_argument('command',choices=['build-B','new-screen','select']);p.add_argument('--inventory',type=Path)
    args=p.parse_args()
    if args.command=='build-B':build_B(args.inventory)
    elif args.command=='new-screen':new_screen()
    else:select()
if __name__=='__main__':main()
