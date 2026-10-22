"""Run the unchanged R34 positive probe plus R33's matrix under the read-only protocol.

Reviewer sources are read only. All adapted fixtures and output stay in this worktree.
The defect assertions are covered by test_lease_supervisor_r34 with fixed expectations.
"""
import contextlib
import io
import json
from pathlib import Path
import runpy
import sys
import unittest

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))
REVIEW = Path('/mpac/sdicks02/scratch/pretrain-v1-dev/review')


def main():
    r34 = runpy.run_path(str(REVIEW/'SOL-R34-probe.py'), run_name='r34_read_only_import')
    r34['independent_contract_checks']()
    # R33 predates the read-only lease design. Retain its 48 stop/deadline cases,
    # updating fixture edits and completion assertions to the current contract.
    source = (REVIEW/'SOL-R33-probe.py').read_text()
    source = source.replace("dir='/mpac/sdicks02/scratch/pretrain-v1-dev/review'",
                            'dir='+repr(str(REPO/'.lease-test-tmp')))
    source = source.replace("['reclaim_origin']==M.iso(EPOCH)", "['trigger_origin']==EPOCH")
    source = source.replace("M.lease_file(str(lease),exclusive=True)", "open(str(lease),'r+')")
    # Cached stopping now checks saved identities before scanning. Give this synthetic
    # fixture the same direct identity oracle as the R34/R35 probes.
    source = source.replace("with mock.patch.object(M,'scan',return_value=procs):",
                            "with mock.patch.object(M,'proc_stat',return_value=('S',1,700001,10,1234)), mock.patch.object(M,'scan',return_value=procs):")
    begin = source.index("            if edit in ('true','false'):")
    end = source.index('        results.append(', begin)
    source = source[:begin]+'''            assert outcome=='ended'
            assert (lease.read_bytes() if lease.exists() else None)==lease_bytes
            receipt=json.loads(Path(st.dir,'ended.json').read_text())
            assert receipt['jobs_drained'] and receipt['owner_lease_updated'] is False
'''+source[end:]
    namespace = {'__name__':'r33_read_only_adaptation'}
    with contextlib.redirect_stdout(io.StringIO()):
        exec(compile(source, str(REVIEW/'SOL-R33-probe.py')+' [contained adaptation]', 'exec'), namespace)
    suite = unittest.defaultTestLoader.loadTestsFromName('bot.pretrain_v1.tests.test_lease_supervisor_r34')
    with contextlib.redirect_stdout(io.StringIO()):
        result = unittest.TextTestRunner(verbosity=1).run(suite)
    summary = dict(runtime=sys.version, r34_positive_groups=len(r34['RESULTS']['independent_passing_checks']),
                   r33_matrix_cases=len(namespace['results']),
                   kill_elapsed_values=sorted(set(r['kill_elapsed'] for r in namespace['results'])),
                   fixed_regressions=result.testsRun, passed=result.wasSuccessful())
    print(json.dumps(summary,indent=2))
    return 0 if result.wasSuccessful() else 1


if __name__ == '__main__':
    raise SystemExit(main())
