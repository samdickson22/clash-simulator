"""Concurrent aggregate reservations; run under the home fleet wrapper."""
from concurrent.futures import ProcessPoolExecutor
from multiprocessing import Manager
import json
from build_cache import claim_bytes


def attempt(args):
    ledger,lock,size=args
    try:claim_bytes(ledger,lock,size)
    except RuntimeError:return 0
    return size


def main():
    checks=0
    with Manager() as manager:
        ledger=manager.Value('q',1000);lock=manager.Lock()
        # A compressibility outlier may use the unused share of another match.
        claim_bytes(ledger,lock,750);claim_bytes(ledger,lock,200)
        assert ledger.value==50;checks+=1
        assert attempt((ledger,lock,51))==0 and ledger.value==50;checks+=1
        claim_bytes(ledger,lock,50);assert ledger.value==0;checks+=1
        try:claim_bytes(ledger,lock,-1)
        except ValueError:checks+=1
        else:raise AssertionError('Negative allocation accepted')
        assert ledger.value==0;checks+=1
        ledger.value=1003
        with ProcessPoolExecutor(8) as pool:
            used=sum(pool.map(attempt,[(ledger,lock,7)]*200))
        assert used==1001 and ledger.value==2;checks+=1
        # Previously written partial files remain charged across fresh runs:
        # the parent computes its initial ledger from physical used_bytes.
        ledger.value=1000-350
        assert attempt((ledger,lock,651))==0 and ledger.value==650;checks+=1
    print(json.dumps(dict(pass_=True,checks=checks,synthetic_only=True)),flush=True)


if __name__=='__main__':main()
