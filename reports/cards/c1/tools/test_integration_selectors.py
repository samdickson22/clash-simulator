"""Pure AST witness controls, no engine/native execution or host access."""
import ast
import copy
from pathlib import Path
from types import SimpleNamespace


def reject(call):
    try: call()
    except AssertionError: return
    raise AssertionError('wrong/unreached selector witness accepted')


def main():
    path=Path(__file__).with_name('probe_integration_selectors.py')
    tree=ast.parse(path.read_text(),filename=str(path))
    namespace=dict(T=SimpleNamespace(watched_row=lambda state,identity:next((row for row in state['entities'] if row['id']==identity),None)))
    for name in ('row','require_witness'):
        node=next(node for node in tree.body if isinstance(node,ast.FunctionDef) and node.name==name)
        exec(compile(ast.Module(body=[node],type_ignores=[]),str(path),'exec'),namespace)
    witness=namespace['require_witness']
    ids=dict(actor=7,primary=8,bandit=9,other=10,chain=11)
    for seat in (0,1):
        for travel in (True,False):
            y=14.5 if seat==0 else 17.5
            bandit=dict(id=9,x=10,y=y,hp=1000 if travel else 900,stun=0 if travel else 0.3,dash=dict(phase='travel' if travel else 'idle'))
            primary=dict(id=8,hp=900); other=dict(id=10,hp=1000)
            base=dict(ids=ids,seat=seat,travel=travel,initial=dict(entities=[dict(id=i,hp=1000) for i in (7,8,9,10)]))
            event=dict(primary=8,reserved=[9],targetable=True,bandit_travel=travel,effect_allowed=not travel)
            rows=dict(bandit=bandit,primary=primary,other=other,actor=dict(id=7,attacked_current=True))
            secondary=dict(base,kind='secondary',reservations=dict(python=[event],clone=[copy.deepcopy(event)]),
                frames=[dict(python_rows=copy.deepcopy(rows),native_rows=copy.deepcopy(rows),native_combat=copy.deepcopy(rows))])
            witness(secondary)
            for mutation in ('missing_reservation','wrong_reserved_id','untargetable','wrong_effect_guard','no_attack','distractor_hit','wrong_bandit_damage'):
                bad=copy.deepcopy(secondary)
                if mutation=='missing_reservation': bad['reservations']['python']=[]
                elif mutation=='wrong_reserved_id':
                    for arm in ('python','clone'): bad['reservations'][arm][0]['reserved']=[10]
                elif mutation=='untargetable':
                    for arm in ('python','clone'): bad['reservations'][arm][0]['targetable']=False
                elif mutation=='wrong_effect_guard':
                    for arm in ('python','clone'): bad['reservations'][arm][0]['effect_allowed']=travel
                elif mutation=='no_attack': bad['frames'][0]['native_combat']['actor']['attacked_current']=False
                elif mutation=='distractor_hit': bad['frames'][0]['native_combat']['other']['hp']=900
                else: bad['frames'][0]['native_combat']['bandit']['hp']=900 if travel else 1000
                reject(lambda:witness(bad))
            chain=dict(id=11,shot_target=9,hit_ids=[8,9],aim=[bandit['x'],bandit['y']],chain_wait=3)
            start=dict(rows,chain=chain)
            finish=dict(rows,chain=None)
            chained=dict(base,kind='chain',frames=[dict(python_rows=copy.deepcopy(start),native_rows=copy.deepcopy(start)),
                dict(python_rows=copy.deepcopy(finish),native_rows=copy.deepcopy(finish))])
            witness(chained)
            for mutation in ('missing_visited','duplicate_visited','wrong_target','wrong_aim','missing_wait','no_impact','wrong_damage','wrong_guard'):
                bad=copy.deepcopy(chained)
                shot=bad['frames'][0]['native_rows']['chain']
                if mutation=='missing_visited': shot['hit_ids']=[8]
                elif mutation=='duplicate_visited': shot['hit_ids']=[8,9,9]
                elif mutation=='wrong_target': shot['shot_target']=10
                elif mutation=='wrong_aim': shot['aim']=[0,0]
                elif mutation=='missing_wait': shot['chain_wait']=0
                elif mutation=='no_impact': bad['frames']=bad['frames'][:1]
                elif mutation=='wrong_damage': bad['frames'][1]['native_rows']['bandit']['hp']=900 if travel else 1000
                elif travel: bad['frames'][1]['native_rows']['bandit']['dash']['phase']='idle'
                else: bad['frames'][1]['native_rows']['bandit']['stun']=0
                reject(lambda:witness(bad))
    print('PASS: both-seat secondary reservation/guard/effect and chain target/visited-ID/multiplicity/aim/impact negative controls; AST/mocks only')


if __name__=='__main__': main()
