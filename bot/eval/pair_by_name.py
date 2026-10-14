import json, glob, random, sys
def load(dirs, cand):
    out = {}
    for d in dirs.split(','):
        for p in glob.glob(d + '/games-*.jsonl'):
            for l in open(p):
                r = json.loads(l)
                if 'error' not in r and r['candidate'] == cand:
                    out[(r['opponent'], r['index'])] = r['score']
    return out
A = load(sys.argv[1], sys.argv[2]); B = load(sys.argv[3], sys.argv[4])
allp = []
for o in sorted({k[0] for k in A}):
    d = [B[k] - A[k] for k in A if k[0] == o and k in B]
    if not d: continue
    allp.append(d)
    rng = random.Random(0); bs = sorted(sum(rng.choice(d) for _ in d) / len(d) for _ in range(4000))
    print(f"B-A vs {o}: {sum(d)/len(d):+.3f} [{bs[100]:+.3f}, {bs[3899]:+.3f}] n={len(d)}")
