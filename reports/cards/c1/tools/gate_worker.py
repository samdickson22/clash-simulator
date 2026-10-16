"""Isolated worker bootstrap; the reviewed driver is its only supported caller."""
import os
from pathlib import Path
import runpy
import signal
import sys


def main():
    # Parent defers cancellation around spawn/PID registration; workers must accept stop signals normally.
    signal.pthread_sigmask(signal.SIG_SETMASK, set())
    capsule, tag, helper, *args = sys.argv[1:]
    capsule = Path(capsule)
    if Path(sys.base_prefix).resolve() != capsule / 'python' or sys.version.split()[0] != '3.12.12':
        raise RuntimeError('Python did not bootstrap from the frozen standalone capsule')
    if sys.flags.hash_randomization or not sys.flags.safe_path or not sys.flags.no_site or not sys.flags.no_user_site:
        raise RuntimeError('worker must preserve seed0 and disable implicit/site/user import paths')
    rt = capsule / ('r1' if tag == 'pinned' else 'total-runtime')
    native = capsule / ('pinned-native' if tag == 'pinned' else 'native')
    std = capsule / 'python/lib/python3.12'
    sys.path[:] = [str(native), str(rt / 'engine-rs'), str(rt / 'src'),
                   str(rt / 'reports/strategy_council_20260928/engine-speed'),
                   str(capsule / 'bot'), str(std / 'site-packages'), str(std),
                   str(std / 'lib-dynload')]
    sys.dont_write_bytecode = True
    os.environ.update(CLASHER_ROOT=str(rt), CLASHER_BOT_RUNTIME=str(rt),
                      CLASHER_DELAY_NATIVE_DIR=str(native), CLASHER_BOT_RUNTIME_PINS='r1',
                      C1_GATE_BOT_ROOT=str(capsule / 'bot'), C1_GATE_FIXTURES=str(capsule / 'fixtures'))
    os.environ.pop('CLASHER_EVAL_RUNTIME_ROOT', None)
    sys.argv = [str(capsule / 'tools' / helper)] + args
    runpy.run_path(sys.argv[0], run_name='__main__')


if __name__ == '__main__':
    main()
