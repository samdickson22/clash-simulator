"""Read-only plumbing analysis. Deliberately never consumes winners or scores."""
import argparse
import hashlib
import json
from pathlib import Path


def percentile(values, q):
    x = sorted(values)
    i = (len(x)-1)*q
    a = int(i); b = min(a+1, len(x)-1)
    return x[a]+(x[b]-x[a])*(i-a)


def search_summary(folder, expected):
    paths = sorted(folder.glob('game-*.json'))
    rows = [json.loads(p.read_text()) for p in paths]
    assert len(rows) == expected and all(r['terminal'] and r['plumbing_only'] for r in rows)
    t = [v for row in rows for v in row['timings_ms']]
    proposal = [v for row in rows for v in row['proposal_ms'] if v > .1]
    return dict(games=len(rows), decisions=len(t), p50_ms=percentile(t,.5), p99_ms=percentile(t,.99),
                max_ms=max(t), over_250_ms=sum(v>250 for v in t),
                candidate_illegal=sum(r['illegal'][r['seat']] for r in rows),
                script_illegal=sum(r['illegal'][1-r['seat']] for r in rows),
                candidate_rejected=sum(r['rejected'][r['seat']] for r in rows),
                script_rejected=sum(r['rejected'][1-r['seat']] for r in rows),
                skew_rows=sum(r['skew_checks'] for r in rows),
                proposal_p99_ms=percentile(proposal,.99) if proposal else None,
                snapshot_hashes=sorted({r['snapshot_tree_sha256'] for r in rows}),
                checkpoint_hashes=sorted({r['checkpoint_sha256'] for r in rows}))


def p16_summary(folder, fixed):
    path=folder/'holdout-nominal-balanced'
    receipt=json.loads(Path(str(path)+'.adapter.json').read_text())
    assert receipt['returncode']==0 and receipt['plumbing_only'] and receipt['fixed_world']==fixed
    audits=json.loads(Path(str(path)+'.legality.json').read_text())
    games=json.loads(Path(str(path)+'.games.json').read_text())
    assert len(audits)==len(games)==4
    assert all(r['terminal'] for r in audits)
    assert all(r['terminated'] and r['plumbing_only'] for r in games)
    for a,b in zip(games[::2],games[1::2]):
        assert a['matchup_seed']==b['matchup_seed'] and a['candidate_player']==0 and b['candidate_player']==1
        assert a['candidate_deck']==b['opponent_deck' if fixed else 'candidate_deck']
        assert a['opponent_deck']==b['candidate_deck' if fixed else 'opponent_deck']
    return dict(games=4, terminal=4, candidate_illegal=sum(r['illegal_candidate'] for r in audits),
                candidate_rejected=sum(r['rejected'][r['candidate_seat']] for r in audits),
                opponent_rejected=sum(r['rejected'][1-r['candidate_seat']] for r in audits),
                decisions=sum(r['decisions'] for r in audits), pairing_exact=True,
                snapshot_hash=receipt['snapshot_tree_sha256'], mask_asymmetry='imitation v5 / comparator v4')


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--search',type=Path,required=True)
    ap.add_argument('--standalone',type=Path,required=True);ap.add_argument('--output',type=Path,required=True)
    args=ap.parse_args()
    search=search_summary(args.search,20)
    c56=search_summary(args.standalone/'c56',4)
    p16=p16_summary(args.standalone/'p16',False)
    h2h=p16_summary(args.standalone/'h2h',True)
    hashes=set(search['snapshot_hashes']+c56['snapshot_hashes']+[p16['snapshot_hash'],h2h['snapshot_hash']])
    assert len(hashes)==1
    result=dict(plumbing_only=True,search=search,c56=c56,p16=p16,h2h=h2h,
                snapshot_tree_sha256=hashes.pop(),
                qualification_passed=search['over_250_ms']==0 and all(
                    r['candidate_illegal']==r['candidate_rejected']==0 for r in (search,c56,p16,h2h)))
    with open(args.output,'x') as f:json.dump(result,f,indent=2)
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
