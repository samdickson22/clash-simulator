import json, glob, random, sys
def load(d):
    out = {}
    for p in glob.glob(d + "/games-*.jsonl"):
        for l in open(p):
            r = json.loads(l)
            if "error" not in r:
                out[(r["opponent"], r["index"])] = r["score"]
    return out
a = load(sys.argv[1]); b = load(sys.argv[2])
for o in sorted({k[0] for k in a}):
    d = [b[k] - a[k] for k in a if k[0] == o and k in b]
    rng = random.Random(0); bs = sorted(sum(rng.choice(d) for _ in d) / len(d) for _ in range(4000))
    print(f"rsim - ours vs {o}: {sum(d)/len(d):+.3f} [{bs[100]:+.3f}, {bs[3899]:+.3f}] n={len(d)}")
