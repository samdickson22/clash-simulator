"""Run short real-driver/fake-I/O probes sequentially. No Mac, model training, or remote host access."""
import ast
import json
import os
import shlex
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
TREE = HERE.parents[2]
VPY = '/mpac/sdicks02/scratch/live-loop/venv/bin/python'
BPY = '/mpac/sdicks02/repos/clasher-bot/.venv/bin/python'
root = Path(tempfile.mkdtemp(prefix='handsync-r2-driver-'))
env = dict(os.environ, PYTHONPATH=f'{TREE}:{TREE}/src:{TREE}/live/perception:/mpac/sdicks02/scratch/live-loop/pydeps',
           OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1', MKL_NUM_THREADS='1', NUMEXPR_NUM_THREADS='1', CUDA_VISIBLE_DEVICES='',
           CLASHER_BOT_RUNTIME='/mpac/sdicks02/jobs/clasher/e4v3-20261010-r1',
           CLASHER_LIVE_FAST='student:/mpac/sdicks02/scratch/live-loop/rl5/policy-00010.pt@0.5375',
           CLASHER_LOPP_MODELS='/mpac/sdicks02/jobs/clasher/live-macbench/lopp-models')
source = ast.parse((TREE/'live/loop/drive.py').read_text())
cls = next(n for n in source.body if isinstance(n, ast.ClassDef) and n.name == 'NavStability')
ns = {}
exec(compile(ast.Module(body=[cls], type_ignores=[]), 'candidate/NavStability', 'exec'), ns)
nav = ns['NavStability']()
assert [nav.observe(i, 'home', (550,1489)) for i in range(4)] == [1,2,3,4]
assert nav.observe(3, 'home', (550,1489)) == 0
nav.reset()
assert nav.observe(4, 'home', (550,1489)) == 1
assert nav.observe(5, 'result', (705,1740)) == 1
assert nav.observe(6, 'result', (705,1800)) == 1
assert nav.observe(7, None, None) == 0
print('PASS distinct/consecutive capture and target stability', flush=True)
for mode in (sys.argv[1:] or ('screens', 'handui', 'rollback', 'hold')):
    d = root/mode
    d.mkdir()
    wrapper = d/'bsgrab'
    wrapper.write_text('#!/bin/sh\nexec '+shlex.quote(VPY)+' '+shlex.quote(str(HERE/'fake_bsgrab.py'))+' "$@"\n')
    wrapper.chmod(0o755)
    battle = ('/mpac/sdicks02/scratch/live-loop/runs/s27/m04/video/000212.jpg' if mode == 'normal_battle'
              else '/mpac/sdicks02/scratch/live-loop/runs/s24/m01/video/000700.jpg')
    home = '/mpac/sdicks02/scratch/live-loop/shots/sol-home-ready.png'
    e = dict(env, LL_PROBE=mode, LL_HANDSYNC='0' if mode == 'rollback' else '1',
             LL_LOCK_FILE=str(d/'lock'), LL_PAUSE_FILE=str(d/'PAUSE'), LL_DECK_FILE=str(d/'deck'),
             LL_ADB=str(HERE/'fake_adb.sh'), FAKE_ADB_LOG=str(d/'adb.log'),
             FAKE_IMAGES=home if mode == 'screens' else battle+':'+home if mode == 'hold' else battle,
             FAKE_HOLD='50' if mode == 'hold' else '1000')
    (d/'deck').write_text(json.dumps(['Valkyrie','Archers','Minions','Cannon','Fireball','Giant','MiniPekka','Musketeer']))
    cmd = [BPY,'-B',str(HERE/'driver_guard_probe.py'),'--out',str(d/'run'),'--source','live',
           '--bsgrab',str(wrapper),'--tap','adb','--autonav','--overlay-port','0','--matches','2',
           '--seconds','12' if mode == 'hold' else '7' if mode == 'normal_battle' else '3',
           '--export','/mpac/sdicks02/jobs/clasher/live-perc-r3-20261015/export-interim-r5e3']
    (d/'argv.json').write_text(json.dumps(cmd))
    with (d/'driver.log').open('w') as f:
        p = subprocess.run(cmd, env=e, stdout=f, stderr=subprocess.STDOUT, timeout=60)
    assert p.returncode == 0, (mode, p.returncode, str(d/'driver.log'))
    events = [json.loads(l) for fn in (d/'run').glob('*/events.jsonl') for l in fn.read_text().splitlines()]
    errors = [x for x in events if x.get('ev') == 'step_error']
    taps = (d/'adb.log').read_text() if (d/'adb.log').exists() else ''
    if mode in ('screens','handui'):
        assert errors and all(x.get('component') == mode for x in errors), (mode, errors)
        assert 'input tap' not in taps
    elif mode == 'rollback':
        assert not errors
        assert 'rollback must not import' not in (d/'driver.log').read_text()
    elif mode == 'normal_battle':
        assert not errors, errors
        configs = [json.loads(p.read_text()) for p in (d/'run').glob('*/session-config.json')]
        assert configs[0]['session']['cls'] == 'handsync.SyncSession', configs
        assert configs[0]['translator']['cls'] == 'handsync.SyncTranslator', configs
        assert 'input tap' in taps, ('no verified play', str(d/'driver.log'))
        assert not any(x.get('ev') == 'handsync_hold' for x in events)
    else:
        assert len([x for x in events if x.get('ev') == 'handsync_hold']) == 1
        assert any(x.get('ev') == 'paused_by_user' and x.get('reason') == 'handsync:test_opening_unreliable' for x in events)
        assert not errors and 'input tap' not in taps
        assert not any(x.get('ev') == 'nav_tap' for x in events)
    print('PASS real driver '+mode+' exception/rollback/hold probe', flush=True)
print('logs:', root, flush=True)
