"""X4S-4 seed-only interval audit (exploration, NEVER ADOPTABLE). r3 after Sol script review r2 (R2-F6).

The X4S-3 audit (declared prior ranges + JSON base/count declarations + a raw 2^52-region literal scan) with a new
source model: NOTHING is read from the working tree. Sources are git blobs of one pinned commit, selected by a
reviewed deterministic rule from tree METADATA alone, and every blob is read by object id and hashed against it
(x4s4io.git_blobs: replace objects disabled, scrubbed environment). Hard links, symlinks, working-tree races and
indirection therefore cannot alias a source to anything else.

Inventory rule (derive_inventory; version x4s4.seed-sources.v1), per tracked entry of the pinned commit:
  * not a regular blob (symlink, gitlink) -> omitted 'not_regular';
  * the study's own directory reports/explore/x4s4/ -> omitted 'own';
  * suffix outside .json/.md/.py/.txt/.yaml/.sh -> omitted 'not_text'; blob > 50 MB -> omitted 'size';
  * an outcome token in ANY component of the full path (result, outcome, complete, readout, verdict, reduc, score,
    loss, release, sealed, games) -> omitted 'outcome_path' (R2-F6: ancestors count, e.g. t1/outcomes/plan.json);
  * inside a sealed tree (reports/explore/t1/, reports/explore/k4s-confirm/, reports/explore/mac-e4-session/,
    reports/strategy_council_20260928/live-loop/, or any component containing 'tiers'): only a seed declaration
    (basename seed-audit*.json, *seed*audit*.json or PREREG*.md) is a source ('sealed_declaration', listed by path and
    blob id in seed-sources.json for review); everything else -> omitted 'sealed';
  * otherwise a 'scan' source; JSON declarations (seed-audit, plan, freeze names and the fixed historical paths) are
    also parsed for base/count ranges;
  * any selected blob whose object id also occurs at an omitted sealed/outcome path -> omitted 'alias_of_excluded'
    (a copy or hard-linked twin of an excluded file is never read).
seed-sources.json (committed, reviewed) pins the commit, the rule version, the SHA-256 of the derived source list,
the per-reason omission counts and the explicit sealed-declaration list; the audit re-derives the list and refuses if
anything differs. Every check is an explicit raise (AuditError); a required source that cannot be read fails.
Commands:  audit_seeds.py inventory --commit <sha>   (writes seed-sources.json; metadata only)
           audit_seeds.py audit                     (writes seed-audit.json)
"""
import argparse, fnmatch, hashlib, json, re, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import x4s4io as io                              # noqa: E402

RULE = 'x4s4.seed-sources.v1'
OFFSETS = (0, 13, 100000, 100001, 100002, 100003, 271828, 271829)
TEXT = ('.json', '.md', '.py', '.txt', '.yaml', '.sh')
SEALED = ('reports/explore/t1/', 'reports/explore/k4s-confirm/', 'reports/explore/mac-e4-session/',
          'reports/strategy_council_20260928/live-loop/')
OUTCOME_TOKENS = ('result', 'outcome', 'complete', 'readout', 'verdict', 'reduc', 'score', 'loss', 'release', 'sealed', 'games')
SEALED_DECL = ('seed-audit*.json', '*seed*audit*.json', 'PREREG*.md')
DECL_JSON = ('seed-audit*.json', '*seed*audit*.json', 'plan*.json', '*freeze*.json', '*FREEZE*.json')
FIXED_DECL = ('reports/strategy_council_20260928/PLAN-NEXT-20261010.md',
              'reports/strategy_council_20260928/imitation/exit-r2/receipts/formula-range-review.json',
              'reports/strategy_council_20260928/imitation/exit-r3/PLAN.md')
MAX_BLOB = 50_000_000
OWN = 'reports/explore/x4s4/'
PRIOR_RANGES = [('K reporting', 4503601407370496, 600), ('K smoke', 4503601417370496, 8), ('X h2h', 4503601507370496, 256),
                ('X paired', 4503601517370496, 600), ('X smoke', 4503601527370496, 32), ('G 04 entire reservation', 4503601607370496, 1000000),
                ('G 01 entire reservation', 4503601609370496, 1000000), ('G 03 entire reservation', 4503601611370496, 1000000),
                ('X dagger conservative full block', 4503601707370496, 10000000), ('K-v2 reporting', 4503601807370496, 600),
                ('K-v2 smoke', 4503601817370496, 8), ('R3 reporting reserved by worker', 4503601907370496, 600),
                ('R3 smoke reserved by worker', 4503601917370496, 8), ('R3 regret replay reserved by worker', 4503601927370496, 65536),
                ('noise-ceiling entire replay reservation', 4503609917370496, 2**18), ('S1 reporting R2', 4503602707370496, 600),
                ('S1 smoke', 4503602617370496, 8), ('S1 invalid R1 reporting (conservative)', 4503602607370496, 600),
                ('past X reassignment', 4503602007370496, 600)]


class AuditError(Exception):
    pass


def check(cond, msg):
    if not cond: raise AuditError(msg)


def sealed(path):
    return path.startswith(SEALED) or any('tiers' in c.lower() for c in path.split('/'))


def outcome_path(path):
    return any(t in c.lower() for c in path.split('/') for t in OUTCOME_TOKENS)


def match(name, pats): return any(fnmatch.fnmatchcase(name, p) for p in pats)


def derive_inventory(entries):
    """Pure: tree metadata -> (sources [[path, oid, kind]], omitted {reason: count}, sealed declarations)."""
    omitted, picked, excluded_oids = {}, [], set()
    def omit(reason): omitted[reason] = omitted.get(reason, 0)+1
    for mode, kind, oid, size, path in sorted(entries, key=lambda e: e[4]):
        name = path.rsplit('/', 1)[-1]
        if kind != 'blob' or mode not in ('100644', '100755'): omit('not_regular'); continue
        if path.startswith(OWN): omit('own'); continue
        if outcome_path(path): omit('outcome_path'); excluded_oids.add(oid); continue
        if sealed(path):
            if match(name, SEALED_DECL) and name.endswith(TEXT):
                if size is not None and size > MAX_BLOB: omit('size'); continue
                picked.append([path, oid, 'sealed_declaration']); continue
            omit('sealed'); excluded_oids.add(oid); continue
        if not name.endswith(TEXT): omit('not_text'); continue
        if size is not None and size > MAX_BLOB: omit('size'); continue
        decl = path.endswith('.json') and match(name, DECL_JSON) or path in FIXED_DECL
        picked.append([path, oid, 'declaration' if decl else 'scan'])
    sources = []
    for path, oid, kind in picked:
        if oid in excluded_oids: omit('alias_of_excluded'); continue
        sources.append([path, oid, kind])
    return sources, omitted, [s for s in sources if s[2] == 'sealed_declaration']


def list_sha(sources): return hashlib.sha256(json.dumps(sources).encode()).hexdigest()


def make_inventory(repo, commit):
    sources, omitted, decls = derive_inventory(io.git_ls_tree(repo, commit))
    return dict(schema=RULE, commit=commit, rule=__doc__.split('Inventory rule')[1].split('seed-sources.json (committed')[0].strip(),
                sources=len(sources), sources_sha256=list_sha(sources), omitted=omitted, sealed_declarations=decls,
                label='X4S-4 seed-audit source inventory (metadata only), exploration, NEVER ADOPTABLE')


def audit(repo, inventory, plan):
    """Audit the pinned sources. Returns the audit document; raises AuditError on any failure."""
    check(inventory.get('schema') == RULE, 'inventory rule version')
    sources, omitted, decls = derive_inventory(io.git_ls_tree(repo, inventory['commit']))
    check(list_sha(sources) == inventory['sources_sha256'] and omitted == inventory['omitted'] and decls == inventory['sealed_declarations'],
          'derived source list differs from the reviewed seed-sources.json')
    blobs = io.git_blobs(repo, [o for _, o, _ in sources])
    check(set(blobs) == {o for _, o, _ in sources}, 'a required source blob could not be read')
    ranges = list(PRIOR_RANGES)
    own_intervals = {(v['base']+off, v['count']) for v in plan['seed_ranges'].values() for off in OFFSETS}
    echoes = []
    def walk(x, label):
        if isinstance(x, dict):
            if isinstance(x.get('base'), int):
                count = x.get('count', x.get('pairs', 0))
                if isinstance(count, int) and count > 0:
                    declared = x.get('name', '')
                    if not declared and isinstance(x.get('source_names'), list): declared = '; '.join(x['source_names'])
                    if (declared.startswith('X4S-4') or OWN in declared) and (x['base'], count) in own_intervals:
                        echoes.append(dict(source=label, base=x['base'], count=count))
                    else: ranges.append((label, x['base'], count))
            for k, v in x.items(): walk(v, label+':'+k)
        elif isinstance(x, list):
            for i, v in enumerate(x): walk(v, label+':'+str(i))
    parsed = 0
    for path, oid, kind in sources:
        if kind in ('declaration', 'sealed_declaration') and path.endswith('.json'):
            try: doc = io.loads_strict(blobs[oid], path)
            except io.Refusal as e: raise AuditError(f'declaration {path} is not strict JSON: {e}')
            walk(doc, path); parsed += 1
    checks = []
    for name, spec in plan['seed_ranges'].items():
        for off in OFFSETS:
            lo = spec['base']+off; hi = lo+spec['count']
            for label, base, count in ranges:
                for oldoff in OFFSETS:
                    a = base+oldoff; b = a+count
                    check(hi <= a or b <= lo, f'bank {name}+{off} intersects {label}+{oldoff}')
            checks.append(dict(range=name, offset=off, start=lo, stop_exclusive=hi))
    srt = sorted(plan['seed_ranges'].values(), key=lambda x: x['base'])
    for a, b in zip(srt, srt[1:]): check(a['base']+a['count']+max(OFFSETS) < b['base'], f'own banks {a} and {b} overlap within the helper offsets')
    literals = set()
    for path, oid, kind in sources: literals.update(int(m) for m in re.findall(rb'45036[0-9]{11}', blobs[oid]))
    lo = min(v['base'] for v in plan['seed_ranges'].values()); hi = max(v['base']+v['count'] for v in plan['seed_ranges'].values())+max(OFFSETS)
    hits = sorted(x for x in literals if lo <= x < hi)
    check(not hits, f'raw literals inside the new banks: {hits[:10]}')
    unique = {}
    for n, b, c in ranges: unique.setdefault((b, c), set()).add(n)
    return dict(utc=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), commit=inventory['commit'], rule=RULE,
                sources=len(sources), sources_sha256=inventory['sources_sha256'], declarations_parsed=parsed, omitted=omitted,
                prior_ranges=[dict(base=b, count=c, source_names=sorted(n)) for (b, c), n in sorted(unique.items())],
                proposed_ranges=plan['seed_ranges'], helper_offsets=OFFSETS, checks=checks, intersections=[], own_reservation_echoes=echoes,
                raw_literal_scan=dict(literal_count=len(literals), window=[lo, hi], hits=hits,
                                      nearest_below=max([x for x in literals if x < lo], default=None),
                                      nearest_above=min([x for x in literals if x >= hi], default=None)),
                reservation=plan.get('seed_reservation'),
                completeness='historical reservations = the declared prior ranges + every base/count found in the parsed declarations; '
                             'literal coverage = every selected source; omissions are counted per reason above')


def main(argv=None):
    ap = argparse.ArgumentParser(); sub = ap.add_subparsers(dest='cmd', required=True)
    i = sub.add_parser('inventory'); i.add_argument('--commit', required=True)
    sub.add_parser('audit')
    a = ap.parse_args(argv)
    if a.cmd == 'inventory':
        io.replace_json(io.REPORT_ROOT+'/seed-sources.json', make_inventory(io.REPO, a.commit), report=True)
        return
    try:
        inv = io.read_json(io.REPORT_ROOT+'/seed-sources.json', 64 << 20)
        plan = io.read_json(io.REPORT_ROOT+'/plan.json', 16 << 20)
        out = audit(io.REPO, inv, plan)
    except (AuditError, io.Refusal) as e:
        raise SystemExit(f'audit_seeds.py: FAILED: {e}')
    io.replace_json(io.REPORT_ROOT+'/seed-audit.json', out, report=True)
    print(json.dumps(dict(sources=out['sources'], omitted=out['omitted'], literals=out['raw_literal_scan']['literal_count'], intersections=0)))


if __name__ == '__main__':
    main()
