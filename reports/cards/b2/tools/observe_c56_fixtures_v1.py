"""Observe native exceptions while executing canonical parity_fixtures unchanged.

No additional native call, state mutation, action or RNG read. A proxy forwards
each call and records/re-raises every native exception, including exceptions the
canonical producer catches and otherwise hides inside trajectory chains.
"""
import hashlib
import importlib.util
import json
from multiprocessing import Pool, get_start_method
import os
from pathlib import Path
import sys

if not __debug__ or sys.flags.optimize:
    raise SystemExit('optimized fixture observation forbidden')

ORIGINAL_ONE=None
EVENTS=None
AUDIT=None
NATIVE_SHA=None


def call_observed(name,callback,*args,**kwargs):
    EVENTS['calls'][name]=EVENTS['calls'].get(name,0)+1
    try:
        return callback(*args,**kwargs)
    except BaseException as error:
        EVENTS['errors'].append(dict(method=name,type=type(error).__name__,message=str(error)[:300]))
        raise


class NativeProxy:
    def __init__(self,actual):self._actual=actual
    def __getattr__(self,name):
        value=getattr(self._actual,name)
        if not callable(value):return value
        def invoke(*args,**kwargs):return call_observed(name,value,*args,**kwargs)
        return invoke


def install(audit_directory):
    global AUDIT,NATIVE_SHA
    import clasher_core
    NATIVE_SHA=hashlib.sha256(Path(clasher_core.__file__).read_bytes()).hexdigest()
    AUDIT=(Path(audit_directory)/f'worker-{os.getpid()}.jsonl').open('x')
    original=clasher_core.BattleState
    def constructor(*args,**kwargs):
        return NativeProxy(call_observed('constructor',original,*args,**kwargs))
    clasher_core.BattleState=constructor


def observed_one(episode):
    global EVENTS
    EVENTS=dict(episode=episode,calls={},errors=[],native_sha256=NATIVE_SHA,optimized=sys.flags.optimize)
    try:
        return ORIGINAL_ONE(episode)
    finally:
        AUDIT.write(json.dumps(EVENTS,sort_keys=True)+'\n');AUDIT.flush()


def main(canonical_path,audit_directory,args):
    global ORIGINAL_ONE
    # Canonical Linux fixture Pool already uses fork; keep that execution model.
    if get_start_method()!='fork':raise RuntimeError('reviewed fixture observation requires fork')
    audit_directory.mkdir()
    spec=importlib.util.spec_from_file_location('b2_c56_canonical_fixtures',canonical_path)
    module=importlib.util.module_from_spec(spec);sys.modules[spec.name]=module;spec.loader.exec_module(module)
    ORIGINAL_ONE=module.one
    module.one=observed_one
    def pool(workers):return Pool(workers,initializer=install,initargs=(str(audit_directory),))
    module.Pool=pool
    sys.argv=[str(canonical_path)]+args
    module.main()


if __name__=='__main__':main(Path(sys.argv[1]),Path(sys.argv[2]),sys.argv[3:])
