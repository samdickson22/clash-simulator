"""Reuse the shared evaluation cells with the explicitly requested workspace engine."""
import importlib.util
import json
import sys
import resource
import time
from kit import COUNCIL, ROOT, HERE, write_json, check_data_pins, sources_match

path = COUNCIL / 'human-prior-p16/scripts/run_eval.py'
spec = importlib.util.spec_from_file_location('shared_run_eval', path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
module.RUNTIME = ROOT
if __name__ == '__main__':
    pins = json.loads((HERE/'preflight.json').read_text())
    check_data_pins(pins)
    if not sources_match(pins['sources']):
        raise RuntimeError('unreviewed workspace source drift before evaluation')
    started = time.perf_counter()
    cpu_started = time.process_time()
    children_before = resource.getrusage(resource.RUSAGE_CHILDREN)
    module.main()
    children_after = resource.getrusage(resource.RUSAGE_CHILDREN)
    cost_name = 'initial' if 'srp-dagger-initial-s2902' in sys.argv else 'final'
    write_json(HERE/f'evaluation-cost-{cost_name}.json', dict(arguments=sys.argv[1:],
        wall_s=time.perf_counter()-started,
        cpu_s=time.process_time()-cpu_started + children_after.ru_utime + children_after.ru_stime
              - children_before.ru_utime - children_before.ru_stime))
