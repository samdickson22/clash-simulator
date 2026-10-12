"""X4S-4 seed-only interval audit (copied from X4S-3; the own-echo label differs). r2 after Sol script review r1 (F11, F16).

All frozen/declared banks plus a raw literal scan, with two changes:
  * every check is an explicit raise (AuditError -> exit 1), so -O/-OO cannot remove a gate (Sol F11);
  * a PRE-READ admissibility filter (Sol F16): no file is opened unless admissible(). Symlinks (the file or any
    directory on its path) are never followed or read. Inside the sealed trees (T1, K4S-confirm, the Mac E4 session,
    the live loop / TIERS, and any path component containing 'tiers'), only seed DECLARATIONS are admissible
    (seed-audit*.json, *seed*audit*.json, PREREG*.md, plan*.json) and never a name carrying an outcome token
    (result, outcome, reduc, score, loss, readout, verdict, complete, release, summary, metric, games, win); every
    other file there is skipped unread and counted. Outside the sealed trees the X4S-3 scan is unchanged.
"""
import hashlib, json, os, re, stat, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import confine                                   # noqa: E402

ROOT = HERE.parents[2]; DEST = HERE
OFFSETS = (0, 13, 100000, 100001, 100002, 100003, 271828, 271829)
SEALED = ('reports/explore/t1/', 'reports/explore/k4s-confirm/', 'reports/explore/mac-e4-session/',
          'reports/strategy_council_20260928/live-loop/')
DECLARATION = re.compile(r'^(seed-audit[^/]*\.json|[^/]*seed[^/]*audit[^/]*\.json|PREREG[^/]*\.md|plan[^/]*\.json)$')
OUTCOME = re.compile(r'result|outcome|reduc|score|loss|readout|verdict|complete|release|summary|metric|games|win', re.I)
TEXT = ('.json', '.md', '.py', '.txt', '.yaml', '.sh')


class AuditError(Exception):
    pass


def check(cond, msg):
    if not cond: raise AuditError(msg)


def sealed(rel):
    return rel.startswith(SEALED) or any('tiers' in part.lower() for part in rel.split('/'))


def admissible(path, root):
    """Decided from the path name and lstat only, BEFORE any byte is read."""
    rel = path.relative_to(root).as_posix()
    cur = root
    for part in path.relative_to(root).parts:
        cur = cur/part
        try: st = os.lstat(cur)
        except FileNotFoundError: return False
        if stat.S_ISLNK(st.st_mode): return False
    if not stat.S_ISREG(st.st_mode): return False
    if sealed(rel):
        return bool(DECLARATION.match(path.name)) and not OUTCOME.search(path.name)
    return True


def walk_files(root, dest):
    """All regular files below root, never descending symlinked directories, .git or the study's own directory."""
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        d = Path(dirpath)
        dirnames[:] = sorted(n for n in dirnames if n != '.git' and not os.path.islink(d/n) and d/n != dest)
        for n in sorted(filenames): yield d/n


def audit(root=ROOT, dest=DEST):
    root, dest = Path(root), Path(dest)
    skipped = dict(sealed_unread=0, symlink_or_irregular=0)
    def take(p):
        if dest == p or dest in p.parents: return False
        ok = admissible(p, root)
        if not ok:
            rel = p.relative_to(root).as_posix()
            skipped['sealed_unread' if sealed(rel) else 'symlink_or_irregular'] += 1
        return ok
    paths = [root/'reports/strategy_council_20260928/PLAN-NEXT-20261010.md']
    paths += sorted((root/'reports/explore').glob('**/seed-audit.json'))
    paths += sorted((root/'reports/strategy_council_20260928/imitation/exit-g-topup').glob('*.json'))
    for pat in ('**/*FREEZE*.json', '**/*freeze*.json', '**/*seed-audit.json'):
        paths += sorted((root/'reports/strategy_council_20260928/imitation').glob(pat))
    paths.append(root/'reports/strategy_council_20260928/imitation/exit-r2/receipts/formula-range-review.json')
    for pat in ('**/*seed*audit*.json', '**/*freeze*.json'):
        paths += sorted((root/'reports/strategy_council_20260928/imitation/exit-r3').glob(pat))
    for top in ('reports', 'imitation'):
        for pat in ('**/*seed*audit*.json', '**/*FREEZE*.json', '**/*freeze*.json'):
            paths += sorted((root/top).glob(pat))
    paths.append(root/'reports/strategy_council_20260928/imitation/exit-r3/PLAN.md')
    paths += sorted((root/'reports/explore').glob('**/plan.json'))
    ranges = [('K reporting', 4503601407370496, 600), ('K smoke', 4503601417370496, 8), ('X h2h', 4503601507370496, 256), ('X paired', 4503601517370496, 600),
              ('X smoke', 4503601527370496, 32), ('G 04 entire reservation', 4503601607370496, 1000000), ('G 01 entire reservation', 4503601609370496, 1000000),
              ('G 03 entire reservation', 4503601611370496, 1000000), ('X dagger conservative full block', 4503601707370496, 10000000),
              ('K-v2 reporting', 4503601807370496, 600), ('K-v2 smoke', 4503601817370496, 8), ('R3 reporting reserved by worker', 4503601907370496, 600),
              ('R3 smoke reserved by worker', 4503601917370496, 8), ('R3 regret replay reserved by worker', 4503601927370496, 65536),
              ('noise-ceiling entire replay reservation', 4503609917370496, 2**18)]
    ranges += [('S1 reporting R2', 4503602707370496, 600), ('S1 smoke', 4503602617370496, 8), ('S1 invalid R1 reporting (conservative)', 4503602607370496, 600),
               ('past X reassignment', 4503602007370496, 600)]
    cfg = json.loads((dest/'plan.json').read_text())
    own_intervals = {(v['base']+off, v['count']) for v in cfg['seed_ranges'].values() for off in OFFSETS}
    sources, echoes = [], []
    def walk(x, label):
        if isinstance(x, dict):
            if isinstance(x.get('base'), int):
                count = x.get('count', x.get('pairs', 0))
                if isinstance(count, int) and count > 0:
                    declared = x.get('name', '')
                    if not declared and isinstance(x.get('source_names'), list): declared = '; '.join(x['source_names'])
                    own_echo = (declared.startswith('X4S-4') or 'reports/explore/x4s4/' in declared) and (x['base'], count) in own_intervals
                    if own_echo: echoes.append(dict(source=label, declaration=declared, base=x['base'], count=count,
                                                    reason='peer audit echoes this new reservation, not historical usage'))
                    else: ranges.append((label, x['base'], count))
            for k, v in x.items(): walk(v, label+':'+k)
        elif isinstance(x, list):
            for i, v in enumerate(x): walk(v, label+':'+str(i))
    for path in sorted(set(paths)):
        if not os.path.lexists(path) or not take(path): continue
        raw = path.read_bytes(); label = str(path.relative_to(root))
        sources.append(dict(path=label, sha256=hashlib.sha256(raw).hexdigest()))
        if path.suffix == '.json': walk(json.loads(raw), label)
    checks = []
    for name, spec in cfg['seed_ranges'].items():
        for off in OFFSETS:
            lo = spec['base']+off; hi = lo+spec['count']
            for label, base, count in ranges:
                for oldoff in OFFSETS:
                    a = base+oldoff; b = a+count
                    check(hi <= a or b <= lo, f'bank {name}+{off} intersects {label}+{oldoff}')
            checks.append(dict(range=name, offset=off, start=lo, stop_exclusive=hi))
    srt = sorted(cfg['seed_ranges'].values(), key=lambda x: x['base'])
    for a, b in zip(srt, srt[1:]): check(a['base']+a['count']+max(OFFSETS) < b['base'], f'own banks {a} and {b} overlap within the helper offsets')
    literals, scanned = set(), 0
    for p in walk_files(root, dest):
        if p.suffix in TEXT and take(p) and p.stat().st_size < 50_000_000:
            try: literals.update(int(m) for m in re.findall(rb'45036[0-9]{11}', p.read_bytes())); scanned += 1
            except OSError: pass
    lo = min(v['base'] for v in cfg['seed_ranges'].values()); hi = max(v['base']+v['count'] for v in cfg['seed_ranges'].values())+max(OFFSETS)
    hits = sorted(x for x in literals if lo <= x < hi)
    check(not hits, f'raw literals inside the new banks: {hits[:10]}')
    raw_scan = dict(files_scanned=scanned, literal_count=len(literals), window=[lo, hi], hits=hits, skipped_unread=skipped,
                    sealed_trees=list(SEALED)+['any path component containing "tiers"'],
                    nearest_below=max([x for x in literals if x < lo], default=None), nearest_above=min([x for x in literals if x >= hi], default=None))
    out = dict(utc=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), sources=sources, prior_ranges=[dict(name=n, base=b, count=c) for n, b, c in ranges],
               proposed_ranges=cfg['seed_ranges'], helper_offsets=OFFSETS, checks=checks, intersections=[], own_reservation_echoes=echoes,
               raw_literal_scan=raw_scan, reservation=cfg.get('seed_reservation'),
               open_ended_dagger='4503601707370496 <= seed < 4503601807370496 reserved; helpers included; future allocation beyond that requires a new audit')
    unique = {}
    for entry in out['prior_ranges']: unique.setdefault((entry['base'], entry['count']), set()).add(entry['name'])
    out['prior_ranges'] = [dict(base=b, count=c, source_names=sorted(labels)) for (b, c), labels in sorted(unique.items())]
    return out


def main():
    try:
        out = audit()
    except AuditError as e:
        raise SystemExit(f'audit_seeds.py: FAILED: {e}')
    target = confine.writable(str(DEST/'seed-audit.json'), roles=('seed-audit.json',), roots=[confine.REPORT_ROOT])
    target.write_text(json.dumps(out, indent=2)+'\n')
    print(json.dumps(dict(sources=len(out['sources']), prior_ranges=len(out['prior_ranges']), literals=out['raw_literal_scan']['literal_count'],
                          skipped_unread=out['raw_literal_scan']['skipped_unread'], intersections=0)))


if __name__ == '__main__':
    main()
