"""Offline injected reader/hold failures; the actual driver receives fake capture and fake ADB only."""
import importlib.abc
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
mode = os.environ['LL_PROBE']
if mode == 'rollback':
    class NoHandUI(importlib.abc.MetaPathFinder):
        def find_spec(self, name, path=None, target=None):
            if name in ('handui', 'handsync'):
                raise ImportError('rollback must not import ' + name)
    sys.meta_path.insert(0, NoHandUI())

import drive

def fail(frame):
    raise RuntimeError('injected pixel failure: ' + mode)

if mode == 'screens':
    drive.screen_kind = fail
elif mode == 'handui':
    import handui
    handui.slot_ui = fail
elif mode == 'hold':
    new_session = drive.new_session
    def held(rt, player, deck):
        s = new_session(rt, player, deck)
        def step(record):
            s.hold_reason = 'test_opening_unreliable'
            return None
        s.step = step
        return s
    drive.new_session = held

raise SystemExit(drive.main())
