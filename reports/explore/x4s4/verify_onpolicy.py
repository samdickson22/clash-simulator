"""X4S-4 (exploration, NEVER ADOPTABLE): verify, seal and gate packed training/diagnostic sets.

Modes (fixed roots and gates under <job>/data):
  O        onpolicy/          -> O-VERIFIED.json        bank C indices < 3500; every row a supervised scored root;
                                 recorded_outcome 0; 300,000 <= rows <= 450,000; per arm K4S-120 <= 200,000 and
                                 S-200 <= 250,000; rows == the passed O label receipts' rows (digest-mismatch rate
                                 <= 0.1%, complete).
  holdout  onpolicy-holdout/  -> HOLDOUT-VERIFIED.json  bank C indices >= 3500 (never trained on); root-only; outcome 0;
                                 rows == the passed holdout label receipts' rows.
  OW       onpolicy-w/        -> OW-VERIFIED.json       PLAN r3 E11: bank C' only (no seed in C or E); emitter
                                 shards (all rows); every selected game sealed and SHA-verified; source games == the
                                 contiguous selected prefix exactly; scored-root count (RootTeacherStore rule) ==
                                 the selection's selected_roots, within [|O|, |O| + last selected game's roots];
                                 no dedup; single-candidate root share reported.
Every mode: no seed of the evaluation bank E. Safety primitives are those of x4s3/verify_g.py r3: explicit
raises (valid under -O), lstat ancestor chain, link-free scandir inventory, O_NOFOLLOW|O_NONBLOCK reads with
fstat, single-link regular files, exact seal inventory, mandatory fd-based sealing re-checked before success,
O_EXCL receipt and gate.
"""
import argparse, hashlib, json, os, stat, subprocess, sys, time
from pathlib import Path, PurePosixPath
import numpy as np

JOB = Path('/mpac/sdicks02/jobs/clasher/x4s4-onpolicy')
MODES = {'O': ('onpolicy', 'O-VERIFIED.json'), 'holdout': ('onpolicy-holdout', 'HOLDOUT-VERIFIED.json'),
         'OW': ('onpolicy-w', 'OW-VERIFIED.json')}
RECEIPT = 'VERIFY-RECEIPT.json'
OPERATIONAL = {'pack-log.txt'}
SCHEMA = 'clasher.exit-r1.teacher-v6.v1'
O_MIN, O_MAX = 300_000, 450_000
ARM_CAPS = {'K4S-120': 200_000, 'S-200': 250_000}
HOLDOUT_MIN_INDEX = 3500
MISMATCH_LIMIT = 0.001


class ValidationError(Exception):
    pass


def check(cond, msg):
    if not cond: raise ValidationError(msg)


def real_dir_chain(path):
    check(path.is_absolute(), f'not absolute: {path}')
    cur = Path('/')
    for part in path.parts[1:]:
        cur = cur/part
        try: st = os.lstat(cur)
        except FileNotFoundError: raise ValidationError(f'missing: {cur}')
        check(stat.S_ISDIR(st.st_mode) and not stat.S_ISLNK(st.st_mode), f'not a real directory: {cur}')


def open_regular(path):
    try: fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except OSError as e: raise ValidationError(f'cannot open without following links: {path}: {e!r}')
    st = os.fstat(fd)
    if not stat.S_ISREG(st.st_mode) or st.st_nlink != 1:
        os.close(fd); raise ValidationError(f'not a single-link regular file: {path}')
    return fd


def read_regular(path):
    fd = open_regular(path)
    with os.fdopen(fd, 'rb') as f: data = f.read()
    return data, hashlib.sha256(data).hexdigest()


def sha(path):
    fd = open_regular(path); h = hashlib.sha256()
    with os.fdopen(fd, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''): h.update(b)
    return h.hexdigest()


def scan(top):
    files, dirs, stack = set(), set(), ['']
    while stack:
        rel = stack.pop()
        with os.scandir(top/rel if rel else top) as it:
            for e in it:
                r = f'{rel}/{e.name}' if rel else e.name
                if e.is_symlink(): raise ValidationError(f'symlink: {top/r}')
                if e.is_dir(follow_symlinks=False): dirs.add(r); stack.append(r)
                elif e.is_file(follow_symlinks=False):
                    check(e.stat(follow_symlinks=False).st_nlink == 1, f'multiply-linked file: {top/r}'); files.add(r)
                else: raise ValidationError(f'special file: {top/r}')
    return files, dirs


def safe_key(k):
    p = PurePosixPath(k)
    check(isinstance(k, str) and k and not p.is_absolute() and '..' not in p.parts and '.' not in p.parts and str(p) == k,
          f'unsafe seal key: {k!r}')


def verify(mode, root, plan, label_receipts, selection, o_gate, result):
    banks = plan['seed_ranges']
    E = banks['reporting']
    B = banks['collection_w'] if mode == 'OW' else banks['collection']
    lo, hi = B['base'], B['base']+B['count']
    if mode == 'O': hi = B['base']+HOLDOUT_MIN_INDEX
    if mode == 'holdout': lo = B['base']+HOLDOUT_MIN_INDEX
    real_dir_chain(root)
    entries = {}
    with os.scandir(root) as it:
        for e in it:
            check(not e.is_symlink(), f'symlink at root: {e.name}')
            entries[e.name] = 'dir' if e.is_dir(follow_symlinks=False) else 'file' if e.is_file(follow_symlinks=False) else 'special'
    special = sorted(n for n, t in entries.items() if t == 'special')
    check(not special, f'special root entries: {special}')
    check(RECEIPT not in entries, 'receipt already exists')
    batches = sorted(n for n, t in entries.items() if t == 'dir')
    check(batches and all(n.startswith('batch-') and n[6:].isdigit() and len(n) == 10 for n in batches), f'root directories {batches}')
    extra = {n for n, t in entries.items() if t == 'file'} - OPERATIONAL
    check(not extra, f'unexpected root entries: {sorted(extra)}')
    for n in sorted(OPERATIONAL & set(entries)):
        st = os.lstat(root/n); check(stat.S_ISREG(st.st_mode) and st.st_nlink == 1, f'operational file {n} not single-link regular')
    total_rows, total_roots, per_arm, corpus_files, out, games, single = 0, 0, {}, [], [], [], 0
    for name in batches:
        d = root/name
        raw, digest = read_regular(d/'manifest.json'); seal = json.loads(raw)
        check(seal.get('schema') == SCHEMA and seal.get('complete') is True and seal.get('packed') is True, f'{name} seal')
        keys = set(seal['files']); [safe_key(k) for k in keys]
        files, dirs = scan(d)
        check(files - {'manifest.json'} == keys and 'manifest.json' in files, f'{name} inventory differs from seal')
        needed = {str(PurePosixPath(k).parents[i]) for k in keys for i in range(len(PurePosixPath(k).parents)-1)}
        check(dirs == needed, f'{name} unexpected directories {sorted(dirs-needed)}')
        for k, want in seal['files'].items(): check(sha(d/k) == want, f'{name}/{k} SHA')
        a = {k: np.load(d/'train'/f'{k}.npy', mmap_mode='r') for k in ('teacher_root', 'teacher_wait_kind',
             'expert_action_supervision_valid', 'root_offsets', 'root_valid', 'perspective_ids', 'recorded_outcome')}
        n = len(a['teacher_root'])
        check(n == int(seal['rows']) and n > 0, f'{name} row count')
        sizes = np.diff(np.asarray(a['root_offsets']))
        roots = np.asarray(a['teacher_root']).astype(bool) & (np.asarray(a['teacher_wait_kind']) == 0) \
            & np.asarray(a['expert_action_supervision_valid']).astype(bool) & (sizes > 0)
        if mode in ('O', 'holdout'):
            check(bool(roots.all()), f'{name} non-root rows present')
            check(bool((np.asarray(a['recorded_outcome']) == 0).all()), f'{name} outcome stored')
        offs = np.asarray(a['root_offsets'])
        valid = np.asarray(a['root_valid'])
        ridx = np.flatnonzero(roots)
        check(all(bool(valid[offs[i]:offs[i+1]].any()) for i in ridx), f'{name} root without a valid score')
        seeds = np.asarray(a['perspective_ids'])
        check(bool(((seeds >= lo) & (seeds < hi)).all()), f'{name} seed outside its bank range')
        check(not bool(((seeds >= E['base']) & (seeds < E['base']+E['count'])).any()), f'{name} evaluation-bank seed present')
        if mode == 'OW':
            Cb = banks['collection']
            check(not bool(((seeds >= Cb['base']) & (seeds < Cb['base']+Cb['count'])).any()), f'{name} collection-bank C seed in O_W')
        single += int((sizes[ridx] == 1).sum())
        src = json.loads(read_regular(d/'sources.json')[0])
        for g in src['games']:
            arm = Path(g['path']).parent.name; per_arm[arm] = per_arm.get(arm, 0)+int(g['rows'])
            games.append(Path(g['path']).name)
        total_rows += n; total_roots += int(roots.sum()); corpus_files += [d/'manifest.json'] + [d/k for k in keys]
        out.append(dict(name=name, manifest_sha256=digest, rows=n, roots=int(roots.sum()), games=len(src['games'])))
    if mode in ('O', 'holdout'):
        check(all(r.get('passed') is True and r.get('set') == mode and r.get('digest_mismatch_rate', 1) <= MISMATCH_LIMIT
                  for r in label_receipts) and label_receipts, 'label receipts not passed for this set')
        labeled = sum(int(r['rows']) for r in label_receipts)
        check(total_rows == labeled, f'packed rows {total_rows} != label receipts rows {labeled}')
        check(set(per_arm) <= set(ARM_CAPS), f'unknown arms {sorted(per_arm)}')
    if mode == 'O':
        check(O_MIN <= total_rows <= O_MAX, f'O rows {total_rows} outside [{O_MIN}, {O_MAX}]')
        check(all(per_arm.get(k, 0) <= v for k, v in ARM_CAPS.items()), f'per-arm caps exceeded {per_arm}')
    if mode == 'OW':
        check(selection.get('reached') is True, 'O_W selection did not reach its target')
        check(selection['target_roots'] == o_gate['rows'], 'O_W target != |O|')
        check(total_roots == selection['selected_roots'], f'O_W roots {total_roots} != selection {selection["selected_roots"]}')
        check(o_gate['rows'] <= total_roots <= o_gate['rows']+int(selection['last_game_roots']),
              f'O_W roots {total_roots} outside [|O|, |O| + last game roots]')
        check(sorted(games) == [f'game-{g:05d}' for g in selection['selected_games']], 'O_W sources != selected prefix')
    for p in corpus_files:
        fd = open_regular(p)
        try: os.fchmod(fd, stat.S_IMODE(os.fstat(fd).st_mode) & ~0o222)
        finally: os.close(fd)
    for p in corpus_files:
        st = os.lstat(p); check(stat.S_ISREG(st.st_mode) and st.st_nlink == 1 and not (st.st_mode & 0o222), f'still writable: {p}')
    result.update(batches=out, rows=total_rows, roots=total_roots, rows_per_arm=per_arm, sealed_files=len(corpus_files), sealed=True,
                  single_candidate_roots=single, single_candidate_root_share=single/max(1, total_roots))


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--mode', choices=sorted(MODES), required=True)
    ap.add_argument('--plan', type=Path, required=True)                 # x4s4 plan.json (banks)
    ap.add_argument('--label-receipts', type=Path, nargs='*', default=[])
    ap.add_argument('--selection', type=Path)                            # OW only
    a = ap.parse_args(argv)
    root = JOB/'data'/MODES[a.mode][0]; gate = JOB/'data'/MODES[a.mode][1]
    t0 = time.monotonic()
    result = dict(passed=False, sealed=False, mode=a.mode, root=str(root), label='X4S-4 exploration, NEVER ADOPTABLE',
                  python_optimize=sys.flags.optimize)
    try:
        check(not os.path.lexists(gate), 'gate already exists')
        plan = json.loads(read_regular(a.plan)[0])
        receipts = [json.loads(read_regular(p)[0]) for p in a.label_receipts]
        selection = o_gate = None
        if a.mode == 'OW':
            check(a.selection is not None, '--selection required for OW')
            selection = json.loads(read_regular(a.selection)[0])
            o_gate = json.loads(read_regular(JOB/'data'/MODES['O'][1])[0])
        else:
            check(a.selection is None, '--selection only for OW')
        verify(a.mode, root, plan, receipts, selection, o_gate, result)
        result['passed'] = True
    except Exception as e:
        result['error'] = repr(e)
    result.update(utc=subprocess.check_output(['date', '-u', '+%FT%TZ'], text=True).strip(), wall_seconds=time.monotonic()-t0)
    real_dir_chain(root)
    fd = os.open(root/RECEIPT, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o644)
    with os.fdopen(fd, 'w') as f: f.write(json.dumps(result, indent=2)+'\n')
    if result['passed']:
        gate_body = dict(utc=result['utc'], mode=a.mode, batches=result['batches'], rows=result['rows'], roots=result['roots'],
                         rows_per_arm=result['rows_per_arm'], single_candidate_root_share=result['single_candidate_root_share'], receipt_sha256=hashlib.sha256((root/RECEIPT).read_bytes()).hexdigest(),
                         label='X4S-4 %s, exploration, NEVER ADOPTABLE' % a.mode)
        fd = os.open(gate, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o444)
        with os.fdopen(fd, 'w') as f: f.write(json.dumps(gate_body, indent=2)+'\n')
    print(json.dumps({k: v for k, v in result.items() if k != 'batches'}), flush=True)
    return 0 if result['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
