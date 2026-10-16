"""Local source/AST witness controls only; no engine or native import."""
import ast
import copy
from pathlib import Path

path=Path(__file__).with_name('probe_dash_clock.py')
namespace={}
tree=ast.parse(path.read_text())
for name in ('row','require_witness'):
    node=next(node for node in tree.body if isinstance(node,ast.FunctionDef) and node.name==name)
    exec(compile(ast.Module(body=[node],type_ignores=[]),str(path),'exec'),namespace)


def reject(result):
    try: namespace['require_witness'](result)
    except (AssertionError,TypeError,KeyError): return
    raise AssertionError('bad dash-clock witness accepted')


def sample(mode,seat):
    loaded=mode.startswith('loaded'); hit=mode not in ('miss','missing')
    equal=mode.endswith('equal'); zero=mode=='cold_zero'
    initial=dict(id=7,clock_initialized=loaded,clock_reseed=None,force_due=zero,
        cooldown=0 if zero else 1 if equal else 0.4,
        clock=dict(interval=1000,load=600,timeline=0,remaining=600 if equal else 0,finish=0),dash=dict(phase='travel'))
    after=copy.deepcopy(initial); after['dash']['phase']='idle'
    if hit:
        after['cooldown']=1
        if not loaded: after['clock']['remaining']=600; after['force_due']=False
        elif not equal: after['clock_reseed']=1000
    hp=None if mode=='missing' else 10
    frames=[]
    for offset in range(40):
        actor=copy.deepcopy(initial if offset<5 else after)
        if hit and offset>5: actor['clock_initialized']=True
        frames.append(dict(offset=offset,before=copy.deepcopy(initial if offset<=5 else after),
            python=copy.deepcopy(actor),native=copy.deepcopy(actor),target_before=hp,
            target_python=hp if not hit else 10 if offset<5 else 8 if offset==5 else 7,
            target_native=hp if not hit else 10 if offset<5 else 8 if offset==5 else 7))
    return dict(seat=seat,mode=mode,ticks=40,initial=dict(entities=[initial]),actor_id=7,
        differences=[],errors=[],frames=frames,dash_damage=2)


def main():
    modes=('cold_zero','cold_equal','loaded_changed','loaded_equal','miss','missing')
    for seat in (0,1):
        for mode in modes:
            result=sample(mode,seat); namespace['require_witness'](result)
            for label in ('python','native'):
                bad=copy.deepcopy(result); bad['frames'][5][label]['clock_initialized']=not mode.startswith('loaded'); reject(bad)
                bad=copy.deepcopy(result); bad['frames'][5][label]['clock']['finish']=1; reject(bad)
                bad=copy.deepcopy(result); bad['frames'][5][label]['clock_reseed']=777; reject(bad)
                if mode.startswith('cold'):
                    # Exact old native failure and a stale force-due flag.
                    bad=copy.deepcopy(result); bad['frames'][5][label]['clock']['remaining']=0
                    bad['frames'][5][label]['clock_reseed']=1000; reject(bad)
                    bad=copy.deepcopy(result); bad['frames'][5][label]['force_due']=True; reject(bad)
                if mode in ('miss','missing'):
                    bad=copy.deepcopy(result); bad['frames'][5][label]['cooldown']=1; reject(bad)
            bad=copy.deepcopy(result); bad['frames']=bad['frames'][:-1]; reject(bad)
            bad=copy.deepcopy(result); bad['frames'][5]['python']['dash']['phase']='travel'; reject(bad)
            bad=copy.deepcopy(result); bad['errors']=[dict(error='partial run')]; reject(bad)
            if mode not in ('miss','missing'):
                bad=copy.deepcopy(result)
                for frame in bad['frames'][6:]: frame['target_python']=frame['target_native']=8
                reject(bad)
    print('PASS: both-seat cold-zero/full, loaded changed/equal and miss/missing witness controls; old captured seed/remaining split, eager-init, finish/seed/force drift, incomplete/absent landing and missing ordinary resume rejected; AST only')


if __name__=='__main__': main()
