"""Admitted home03 synthetic/clock tests and inherited native startup, no games."""
import json,os,resource,subprocess,sys,time
from pathlib import Path
J=Path('/mpac/sdicks02/jobs/clasher/exit-r3-20261010-r2/timing03')
def main():
    from admission import allowed
    assert allowed(J) and os.sched_getaffinity(0)=={55}
    r=dict(passed=False,pid=os.getpid(),pgid=os.getpgrp());t=time.monotonic()
    try:
        subprocess.run([sys.executable,'-B','-m','unittest','discover','-s',str(J/'eval-ops'),'-p','test_*.py','-v'],check=True)
        subprocess.run([sys.executable,'-B','-m','pytest','-q',str(J/'eval-source/reports/explore/e1/test_deadline.py'),'-p','no:cacheprovider'],check=True)
        from imitation.exit_r1 import screen
        e1,policies=screen.initialize(dict(native=str(J/'reporting-native/clasher_core.abi3.so'),checkpoints={'init':str(J/'inputs/main02.pt')}))
        core=e1.make_player(4503602417370496+100000,'W').core
        assert core.arm=='W' and core.config.threads==1 and core.config.horizon==160 and not core.reserve_floor
        import clasher_core
        from admission import sha
        assert sha(clasher_core.__file__)=='f387b2d288ed280de9eeae3164d38f465045685ee53819e279930c2ee10699a8'
        r.update(passed=True,native_startup=True,synthetic_hook_tests=2,protocol_tests=5,proposal_tests=3,deadline_clock_tests=6,no_games=True)
    finally:
        u=resource.getrusage(resource.RUSAGE_SELF);v=resource.getrusage(resource.RUSAGE_CHILDREN);r.update(parent_cpu_seconds=u.ru_utime+u.ru_stime,children_cpu_seconds=v.ru_utime+v.ru_stime,wall_seconds=time.monotonic()-t,utc=subprocess.check_output(['date','-u','+%FT%TZ'],text=True).strip(),accounting='Whole code qualification process/tree once; no simulations')
        (J/'CODE-QUALIFICATION.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r))
if __name__=='__main__':main()
