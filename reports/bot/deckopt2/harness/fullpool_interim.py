"""One descriptive, non-decision read after half the paired case blocks finish."""
import hashlib,json,os,subprocess
from pathlib import Path
import numpy as np
from fullpool_clean import problems
OPS=('R3a','v1','LIVE-K4CW-r16')
GROUPS={'weak pool':OPS[:2],'strong opponent':OPS[2:],'pooled':OPS}
REPS=20000;BOOTSTRAP_SEED=672825

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def utc():return subprocess.check_output(['date','-u','+%Y-%m-%dT%H:%M:%SZ'],text=True).strip()
def save(p,v):p.write_text(json.dumps(v,indent=2))
def maybe(root):
    d=Path(root)/'fullpool';b=d/'validation/bank.json';out=d/'interim-50'
    if not b.exists():return []
    result=out/'result.json'
    if result.exists():return ['Interim descriptive read: fullpool/interim-50/REPORT.md. It does not authorize a deck change; final inference still uses the complete registered bank.\n']
    bank=json.loads(b.read_text());arms=[(n,p) for n in bank['candidates'] for p in bank['players']]
    files=list((d/'validation/rows').glob('*.json'));rows=[json.loads(p.read_text()) for p in files]
    assert all(not problems(r) for r in rows)
    bank_digest=sha(b)
    assert all(r['bank_sha256']==bank_digest for r in rows)
    lookup={(r['id'],r['candidate'],r['player']):r for r in rows};assert len(lookup)==len(rows)
    cases=[c for c in bank['cases'] if all((c['id'],n,p) in lookup for n,p in arms)]
    if len(cases)<len(bank['cases'])/2:return []
    assert all(any(c['opponent']==op for c in cases) for op in OPS)
    out.mkdir(exist_ok=True)
    try:fd=os.open(out/'FREEZE',os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    except FileExistsError:return ['Interim snapshot is being computed; see fullpool/interim-50.\n']
    os.close(fd)
    ids={c['id'] for c in cases};included={p.name:sha(p) for p,r in zip(files,rows) if r['id'] in ids}
    snapshot=dict(utc=utc(),bank_sha256=sha(b),complete_cases=len(cases),registered_cases=len(bank['cases']),
        cases_by_policy={op:sum(c['opponent']==op for c in cases) for op in OPS},case_ids=sorted(ids),
        rows=included,bootstrap_reps=REPS,bootstrap_seed=BOOTSTRAP_SEED,helper_sha256=sha(__file__),
        note='Descriptive interim, not a decision. Complete blocks only; completion-time selection can bias this read. No efficacy stopping, finalist changes or resource-vector changes.')
    save(out/'snapshot.json',snapshot)
    rng=np.random.default_rng(BOOTSTRAP_SEED);case_ids={op:[c['id'] for c in cases if c['opponent']==op] for op in OPS}
    indices={op:rng.integers(0,len(cs),(REPS,len(cs))) for op,cs in case_ids.items()}
    summary=[]
    for player in bank['players']:
        base={op:np.array([lookup[i,'baseline',player]['win'] for i in cs],dtype=float) for op,cs in case_ids.items()}
        for candidate in bank['candidates']:
            values={op:np.array([lookup[i,candidate,player]['win'] for i in cs],dtype=float) for op,cs in case_ids.items()}
            for group,ops in GROUPS.items():
                boot=np.mean([((values[op]-base[op])[indices[op]]).mean(axis=1) for op in ops],axis=0)
                summary.append(dict(player=player,candidate=candidate,group=group,n=sum(len(case_ids[op]) for op in ops),
                    win_rate=float(np.mean([values[op].mean() for op in ops])),baseline_win_rate=float(np.mean([base[op].mean() for op in ops])),
                    delta=float(np.mean([(values[op]-base[op]).mean() for op in ops])),delta_ci=np.quantile(boot,[.025,.975]).tolist()))
    value=dict(snapshot_utc=snapshot['utc'],snapshot_sha256=sha(out/'snapshot.json'),summary=summary,not_a_decision=True)
    save(result,value)
    lines=['# Half-case descriptive interim\n',f"Frozen {snapshot['utc']}: {len(cases)}/{len(bank['cases'])} complete paired cases; policy counts {snapshot['cases_by_policy']}.\n",
        'Not a deck decision. Completion-time selection may bias this read. Every included case has all deck/player arms; unfinished blocks are retained for final validation. Finalists, upgrade vectors, registered sample size and decision rule remain fixed.\n',
        'Wins are primary; draws are nonwins. Twenty thousand paired within-policy bootstrap resamples use the same indices for baseline/candidates and both players. Groups standardize policy weights equally, including when interim counts differ; n is the total actual paired cases. Pointwise95% CIs, no multiplicity adjustment. rext-bc is n/a.\n',
        '|Player|Deck|Group|Paired n|Win%|Upgraded baseline%|Δ pp [95% CI]|','|---|---|---|---:|---:|---:|---|']
    for r in summary:lines.append(f'|{r["player"]}|{r["candidate"]}|{r["group"]}|{r["n"]}|{100*r["win_rate"]:.1f}|{100*r["baseline_win_rate"]:.1f}|{100*r["delta"]:+.1f} [{100*r["delta_ci"][0]:+.1f}, {100*r["delta_ci"][1]:+.1f}]|')
    (out/'REPORT.md').write_text('\n'.join(lines)+'\n')
    short=[f"INTERIM ONLY {snapshot['utc']}, {len(cases)}/450 cases; per-policy counts {snapshot['cases_by_policy']}. Equal-policy-weight paired deltas (pp,95%CI), all vs upgraded baseline; completion-time biased, not a decision."]
    for player in bank['players']:
        tag='res' if player.endswith('-res') else 'base'
        for candidate in bank['candidates']:
            if candidate=='baseline':continue
            terms=[]
            for group in GROUPS:
                r=next(r for r in summary if r['player']==player and r['candidate']==candidate and r['group']==group)
                terms.append(f'{group} {100*r["delta"]:+.1f} [{100*r["delta_ci"][0]:+.1f},{100*r["delta_ci"][1]:+.1f}]')
            short.append(f'{tag} {candidate}: '+', '.join(terms))
    (out/'SUMMARY.txt').write_text('\n'.join(short)+'\n')
    return ['Interim descriptive read is ready: fullpool/interim-50/REPORT.md; no deck-change decision.\n']
