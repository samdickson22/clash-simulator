"""Synthetic full-fit evidence rejection tests; never load real checkpoints."""
import copy
import json
from selection_guard_v4 import validate_t7_fit
from formal_guard import SPLIT_SHA


def main():
    sha = 'a'*64
    manifest = dict(seed=6108, device='cuda', precision='bf16', compile=False, epochs=24,
                    steps=400, max_matches=0, windows_per_match=32, loader_workers=6,
                    heldout_opened=False, pixel_cache='/synthetic/cache', source_hashes={'source':sha},
                    split_sha256=SPLIT_SHA, training_matches=1, cache_index_sha256={'a':sha},
                    cards=['Knight'], bodies=['Knight'])
    complete = dict(manifest=manifest, steps_completed=9600, heldout_opened=False, checkpoint_sha256=sha)
    inventory = dict(split='train', split_sha256=SPLIT_SHA, cards=['Knight'],
                     matches=[dict(episode='a', split='train', receipt_sha256=sha)])
    rows = [dict(step=i, loss=1.) for i in range(1, 9601)]
    checkpoints = {i:dict(step=i*400, cards=['Knight'], bodies=['Knight'], sha256=sha) for i in range(1,25)}
    def check(m=manifest, c=complete, inv=inventory, logs=rows, ck=checkpoints, admitted=None, sources=None):
        return validate_t7_fit(m,c,inv,logs,checkpoints=ck,
            admitted_train_receipts={'a':sha} if admitted is None else admitted,
            measured_source_hashes={'source':sha} if sources is None else sources)
    result = check()
    assert result['validated'] and not result['selection_seal'] and not result['heldout_opening_authorized']
    checks = 1
    def rejected(fn):
        nonlocal checks
        try: fn()
        except ValueError: checks += 1; return
        raise AssertionError('Invalid selection evidence accepted')
    for key, value in dict(seed=1, epochs=1, steps=128, max_matches=8, loader_workers=8,
                           precision='fp32', compile=True, windows_per_match=16, heldout_opened=True).items():
        m=dict(manifest, **{key:value})
        rejected(lambda:check(m=m,c=dict(complete,manifest=m)))
    rejected(lambda:check(c=dict(complete, steps_completed=128)))
    rejected(lambda:check(c=dict(complete, manifest={})))
    rejected(lambda:check(sources={'source':'b'*64}))
    rejected(lambda:check(admitted={'a':sha,'missing':sha}))
    rejected(lambda:check(admitted={}))
    rejected(lambda:check(inv=dict(inventory,split='heldout')))
    rejected(lambda:check(inv=dict(inventory,matches=inventory['matches']*2)))
    rejected(lambda:check(logs=rows[:-1]))
    rejected(lambda:check(logs=rows[:20]+[rows[19]]+rows[21:]))
    rejected(lambda:check(logs=[dict(rows[0],loss=float('nan'))]+rows[1:]))
    rejected(lambda:check(ck={k:v for k,v in checkpoints.items() if k!=24}))
    bad=copy.deepcopy(checkpoints);bad[24]['step']=128
    rejected(lambda:check(ck=bad))
    bad=copy.deepcopy(checkpoints);bad[1]['bodies']=['Other']
    rejected(lambda:check(ck=bad))
    print(json.dumps(dict(pass_=True, checks=checks, synthetic_only=True, heldout_payloads_opened=False)),flush=True)


if __name__ == '__main__':
    main()
