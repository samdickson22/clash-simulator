"""Opt-in deterministic size balancing; never changes per-case seeds."""
from collections import defaultdict

def cost_key(case):
    return '|'.join((str(case[2]), str(case[5]), ','.join(sorted(case[3])), ','.join(sorted(case[4])), str(case[6] if len(case)>6 else '0')))

def longest_first(cases, costs):
    return sorted(cases, key=lambda c: -float(costs.get(cost_key(c), costs.get(str(c[-1]), 1.))))

def balanced_shards(cases, count, costs):
    if count<1:raise ValueError('positive shard count required')
    shards=[[] for _ in range(count)];loads=[0.]*count
    # Keep all treatments for each seed together.
    pairs=defaultdict(list)
    for c in cases:pairs[c[0]].append(c)
    groups=sorted(pairs.values(),key=lambda g:-sum(float(costs.get(cost_key(c),1.)) for c in g))
    for group in groups:
        lane=min(range(count),key=lambda i:(loads[i],i))
        shards[lane].extend(group)
        loads[lane]+=sum(float(costs.get(cost_key(c),1.)) for c in group)
    return shards,loads

def lane_failed(failures,host,*,admission_refused=False):
    """Admission refusals retire immediately; other failures get three tries."""
    failures[host]=failures.get(host,0)+1
    return admission_refused or failures[host]>=3
