"""Audit seed-only inventories, including every tempo and delay range."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
DEST = Path(__file__).resolve().parent


def numbers(x):
    if isinstance(x, int) and not isinstance(x, bool): yield x
    elif isinstance(x, list):
        for v in x: yield from numbers(v)
    elif isinstance(x, dict):
        for v in x.values(): yield from numbers(v)


def main():
    cfg = json.loads((DEST/'plan.json').read_text())
    paths = [ROOT/'reports/explore/loss-review/seeds.json',
             ROOT/'reports/explore/tempo/exclusions.json']
    paths += sorted((ROOT/'imitation/gates-bc/receipts').glob('**/*seeds.json'))
    paths += sorted((ROOT/'imitation').glob('gate-*/v1/proposed-seeds.json'))
    denied, sources = set(), []
    for path in paths:
        vals = set(numbers(json.loads(path.read_text())))
        denied.update(vals)
        sources.append(dict(path=str(path.relative_to(ROOT)),
                            sha256=hashlib.sha256(path.read_bytes()).hexdigest(), count=len(vals)))
    prior = {}
    for path in (ROOT/'reports/explore/tempo/seed-audit.json',
                 ROOT/'reports/explore/search-ab/seed-audit.json'):
        doc = json.loads(path.read_text())
        for group in ('sets', 'prior_search_sets'):
            for name, spec in doc.get(group, {}).items():
                prior[str(path.relative_to(ROOT))+':'+name] = dict(base=spec['base'], pairs=spec['pairs'])
    for path in sorted((ROOT/'reports/explore').glob('**/seed-audit.json')):
        if path.parent == DEST: continue
        doc = json.loads(path.read_text())
        for group in ('sets', 'prior_search_sets', 'prior_ranges', 'proposed_ranges'):
            for name, spec in doc.get(group, {}).items():
                if isinstance(spec, dict) and 'base' in spec:
                    prior[str(path.relative_to(ROOT))+':'+group+':'+name] = dict(base=spec['base'], pairs=spec.get('pairs',spec.get('count',0)))
    prior['delay-fixes-main-and-lag-controls'] = dict(base=2**48+50000, pairs=1250)
    prior['delay-fixes-preflight'] = dict(base=2**48+59000, pairs=4)
    for spec in prior.values():
        denied.update(spec['base']+i+off for i in range(spec['pairs']) for off in (0,100000,100001,100002,100003,271828,271829))
    checked = {}
    for name, spec in cfg['seed_ranges'].items():
        vals = {spec['base']+i+off for i in range(spec['count']) for off in (0,100000,100001,100002,100003,271828,271829)}
        assert not vals & denied, (name, sorted(vals & denied)[:10])
        assert not any(vals & other for other in checked.values()), name
        checked[name] = vals
    audit = dict(audited_at_utc=__import__('subprocess').check_output(['date','-u','+%Y-%m-%dT%H:%M:%SZ'],text=True).strip(), sources=sources, prior_ranges=prior, denied_count=len(denied),
                 proposed_ranges=cfg['seed_ranges'], helper_offsets=[0,100000,100001,100002,100003,271828,271829],
                 checked_counts={k:len(v) for k,v in checked.items()}, intersections=[])
    (DEST/'seed-audit.json').write_text(json.dumps(audit, indent=2)+'\n')


if __name__ == '__main__': main()
