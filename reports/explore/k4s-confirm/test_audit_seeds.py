"""audit_seeds.py tests: self-declaration skip, own-output exclusion, helper-offset declaration windows, F-4 bounds,
exit codes, and a synthetic foreign collision that must still FAIL.

End-to-end cases run the tool in a throwaway `git clone --shared` of this worktree's HEAD; synthetic commits are written
only to the clone. No in-window seed literal is written in this file: every value is derived from plan.json.
"""
import json, os, shutil, subprocess, sys
from pathlib import Path
import pytest
import audit_seeds as A

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
REL = 'reports/explore/k4s-confirm/'
PY = '/bin/python3' if Path('/bin/python3').exists() else sys.executable
PLAN = json.loads((HERE/'plan.json').read_text())['seed_ranges']
K = {k: dict(base=v['base'], count=v['count'], stop=v['base']+v['count']) for k, v in PLAN.items()}
TOP = max(A.OFFSETS)


def test_declared_window_is_base_through_last_seed_plus_largest_offset():
    for r in K.values():
        assert A.k4s_declared(r['base'], K) and A.k4s_declared(r['stop']-1+TOP, K)
    hi = max(r['stop']-1+TOP for r in K.values())
    assert not A.k4s_declared(hi+1, K) and not A.k4s_declared(min(r['base'] for r in K.values())-1, K)


def test_classify_k4s_docs_only():
    v = K['primary']['base']+1  # the test_reduce.py:105 shape: an in-range seed that is not a base
    assert A.classify(REL+'test_reduce.py', v, K) == 'EXCLUDED_K4S_DECLARATION'
    assert A.classify(A.LIVE_V4+'PREREG-K4S-DRAFT-r3.md', K['reserve']['stop']-1+TOP, K) == 'EXCLUDED_K4S_DECLARATION'
    assert A.classify('reports/explore/other/plan.json', v, K) == 'FAIL'
    assert A.classify(REL+'notes.md', max(r['stop']-1+TOP for r in K.values())+1, K) == 'FAIL'


def test_window_bounds_include_both_f4_bounds():
    assert A.WINDOW_BOUNDS == {A.SCAN_TASK[0], A.SCAN_TASK[1], A.SCAN_F4[0], A.SCAN_F4[1]}
    for b in A.SCAN_F4:
        assert A.SCAN_LO <= b <= A.SCAN_HI and not A.k4s_declared(b, K)
        assert A.classify(REL+'K4S-SPEC.md', b, K) == 'WINDOW_BOUND_TEXT'
        assert A.classify('reports/explore/other/NOTES.md', b, K) == 'FAIL'


def git(cwd, *a, **kw):
    return subprocess.run(['git', *a], cwd=cwd, check=True, capture_output=True, **kw).stdout.decode().strip()


@pytest.fixture
def clone(tmp_path):
    """Shared, index-only clone of HEAD with the files the tool reads from the worktree checked out."""
    dst = tmp_path/'repo'
    head = git(ROOT, 'rev-parse', 'HEAD')
    git(tmp_path, 'clone', '-q', '--shared', '--no-checkout', str(ROOT), str(dst))
    git(dst, 'update-ref', '--no-deref', 'HEAD', head)
    git(dst, 'update-ref', 'refs/heads/main', git(ROOT, 'rev-parse', 'main'))
    git(dst, 'read-tree', head)
    git(dst, 'checkout', head, '--', REL+'plan.json', A.PREREG_R3, A.CONFORMANCE)
    tool = dst/REL/'audit_seeds.py'
    shutil.copyfile(HERE/'audit_seeds.py', tool)  # the tool under test, even before it is committed
    return dst


def commit(dst, files):
    """Commit `files` {path: text} on top of HEAD in the clone only (plumbing; nothing is checked out)."""
    for path, text in files.items():
        blob = subprocess.run(['git', 'hash-object', '-w', '--stdin'], cwd=dst, input=text.encode(), check=True, capture_output=True).stdout.decode().strip()
        git(dst, 'update-index', '--add', '--cacheinfo', f'100644,{blob},{path}')
    tree = git(dst, 'write-tree')
    env = dict(os.environ, GIT_AUTHOR_NAME='t', GIT_AUTHOR_EMAIL='t@t', GIT_COMMITTER_NAME='t', GIT_COMMITTER_EMAIL='t@t')
    c = subprocess.run(['git', 'commit-tree', tree, '-p', 'HEAD', '-m', 'synthetic'], cwd=dst, env=env, check=True, capture_output=True).stdout.decode().strip()
    git(dst, 'update-ref', '--no-deref', 'HEAD', c)


def run(dst):
    r = subprocess.run([PY, str(dst/REL/'audit_seeds.py')], cwd=dst, capture_output=True)
    return r.returncode, json.loads((dst/REL/'seed-audit.json').read_text())


def test_clean_head_passes_and_skips_self(clone):
    rc, out = run(clone)
    assert (rc, out['status'], out['violations']) == (0, 'PASS', [])
    note = next(n for n in out['notes'] if 'own-declaration files' in n)
    assert REL+'plan.json' in note
    assert not any(s.startswith(REL) for p in out['prior_intervals'] for s in p['sources'])
    hits = out['literal_scan']['in_window_hits']
    assert not any(h['path'] in A.OWN_OUTPUTS for h in hits)
    assert any('excluded from the literal scan' in n for n in out['notes'])
    assert all(h['classification'] != 'FAIL' for h in hits)


def test_own_outputs_with_foreign_values_are_not_scanned(clone):
    far = max(r['stop']-1+TOP for r in K.values())+1000
    commit(clone, {p: f'{far}\n' for p in A.OWN_OUTPUTS})
    rc, out = run(clone)
    assert (rc, out['status']) == (0, 'PASS')


def test_synthetic_foreign_collision_still_fails(clone):
    v = K['primary']['base']+10
    commit(clone, {'reports/explore/zz-foreign/plan.json': json.dumps(dict(seed_ranges=dict(x=dict(base=v, count=5)))),
                   'reports/explore/zz-foreign/NOTES.md': f'seed {v}\nbound {A.SCAN_F4[0]}\n'})
    rc, out = run(clone)
    assert (rc, out['status']) == (1, 'FAIL')
    assert any(x.startswith('overlap primary offset 0') for x in out['violations'])
    assert f'in-window literal {v} at reports/explore/zz-foreign/NOTES.md:1' in out['violations']
    assert f'in-window literal {A.SCAN_F4[0]} at reports/explore/zz-foreign/NOTES.md:2' in out['violations']
    assert any('reports/explore/zz-foreign/plan.json' in s for p in out['prior_intervals'] for s in p['sources'])


def test_undeclared_literal_in_k4s_doc_still_fails(clone):
    v = max(r['stop']-1+TOP for r in K.values())+1
    commit(clone, {REL+'zz-notes.md': f'{v}\n', REL+'plan-zz.json': json.dumps(dict(base=v, count=1))})
    rc, out = run(clone)
    assert (rc, out['status']) == (1, 'FAIL')
    assert sorted(out['violations']) == sorted([f'in-window literal {v} at {REL}zz-notes.md:1', f'in-window literal {v} at {REL}plan-zz.json:1'])
    assert REL+'plan-zz.json' in next(n for n in out['notes'] if 'own-declaration files' in n)
