"""Fit-host only: metered unit and unchanged injected-clock qualifications."""
import ast,hashlib,importlib.util,json,os,resource,socket,subprocess,sys,time,unittest
from pathlib import Path

def main():
    j=Path(sys.argv[1]);assert socket.gethostname().split('.')[0]=='127x09'
    assert os.getpriority(os.PRIO_PROCESS,0)>=10 and os.sched_getaffinity(0)=={126}
    started=time.monotonic();ops=j/'eval-ops';frozen=j/'frozen-x'
    sys.path[:0]=[str(ops),str(frozen),str(j/'qualification-runtime/k-anytime'),str(j/'qualification-runtime/e1')]
    parsed=[]
    for path in list(ops.glob('*.py'))+list(frozen.glob('*.py')):
        ast.parse(path.read_text(),filename=str(path));parsed.append(path.name)
    harness=json.loads((j/'stage3-sdefault-addendum.json').read_text())
    for name in ('sdefault.py','k_stage3_sdefault.py','test_sdefault.py'):
        assert hashlib.sha256((frozen/name).read_bytes()).hexdigest()==harness['files']['ops/'+name]
    suite=unittest.TestSuite()
    for name in ('test_proposals','test_admission'):
        suite.addTests(unittest.defaultTestLoader.loadTestsFromName(name))
    result=unittest.TextTestRunner(verbosity=2).run(suite);assert result.wasSuccessful() and result.testsRun==5
    import test_sdefault
    clocks=[]
    for name in sorted(vars(test_sdefault)):
        if name.startswith('test_'):getattr(test_sdefault,name)();clocks.append(name)
    assert len(clocks)==7
    u=resource.getrusage(resource.RUSAGE_SELF)
    receipt=dict(passed=True,unit_tests=result.testsRun,frozen_clock_tests=clocks,ast_files=parsed,cpu_seconds=u.ru_utime+u.ru_stime,wall_seconds=time.monotonic()-started,utc=subprocess.check_output(['date','-u','+%FT%TZ'],text=True).strip(),host=socket.gethostname().split('.')[0],nice=os.getpriority(os.PRIO_PROCESS,0),affinity=sorted(os.sched_getaffinity(0)),accounting='Whole qualification process once; earlier unmetered five-test dry runs disclosed separately.')
    (j/'evaluation-tests.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt))
if __name__=='__main__':main()
