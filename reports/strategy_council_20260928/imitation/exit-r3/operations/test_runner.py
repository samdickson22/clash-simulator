import json,resource,subprocess,time,unittest
from pathlib import Path
from exit_r3.test_r3 import R3Tests
start=time.monotonic();r=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(R3Tests));u=resource.getrusage(resource.RUSAGE_SELF)
Path('/mpac/sdicks02/jobs/clasher/exit-r3-20261010-r1/tests.json').write_text(json.dumps(dict(passed=r.wasSuccessful(),tests=r.testsRun,utc=subprocess.check_output(['date','-u','+%FT%TZ'],text=True).strip(),wall_seconds=time.monotonic()-start,cpu_seconds=u.ru_utime+u.ru_stime),indent=2)+'\n')
raise SystemExit(0 if r.wasSuccessful() else 1)
