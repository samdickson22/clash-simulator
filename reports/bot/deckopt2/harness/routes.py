"""Write an exclusive deterministic dispatch route for MISSING jobs after drain."""
from pathlib import Path
import argparse,json,random
from bot.deckopt2.run import jobs_for,sha,dump,utc
from clean import read_rows


def main():
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True)
    p.add_argument('--stage',required=True);p.add_argument('--out',type=Path,required=True)
    p.add_argument('--weights',default='h04:28,h03a:4,h03b:4,h01:4')
    a=p.parse_args();data,rows=read_rows(a.root,a.stage)
    jobs=jobs_for(data);lookup={(r['id'],r['candidate'],r['player']):r for r in rows}
    bank_sha=sha(a.root/a.stage/'bank.json')
    assert all(r['bank_sha256']==bank_sha for r in rows)
    pending=[i for i,(c,n,pl) in enumerate(jobs) if (c['id'],n,pl)not in lookup]
    random.Random(20261016).shuffle(pending)
    weights={}
    for item in a.weights.split(','):
        name,n=item.split(':');weights[name]=int(n);assert 1<=int(n)<=40
    wheel=[name for name,n in weights.items() for _ in range(n)]
    routes={n:[] for n in weights}
    for i,index in enumerate(pending):routes[wheel[i%len(wheel)]].append(index)
    flat=[i for indices in routes.values() for i in indices]
    assert len(flat)==len(set(flat))==len(pending) and set(flat)==set(pending)
    dump(a.out,dict(created_utc=utc(),bank_sha256=bank_sha,weights=weights,routes=routes,
                    completed_before=len(rows),pending=len(pending),method='shuffle missing original indices with fixed20261016 dispatch RNG, weighted round robin; no outcome values used',
                    route_source_sha256=sha(__file__)),exclusive=True)
    print(json.dumps(dict(completed=len(rows),pending=len(pending),routes={n:len(ids) for n,ids in routes.items()})))
if __name__=='__main__':main()
