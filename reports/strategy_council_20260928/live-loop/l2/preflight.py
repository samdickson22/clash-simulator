"""Owned offline renderer calibration; never an evaluation game."""
import json,sys,time,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4]
sys.path[:0]=[str(ROOT/'scripts'),str(ROOT/'src')]
from collect_l1_rendered import BASE,ADB
from smoke_reference_battle import request
from certify_l1_timing_v3 import verify_owner
import cv2,numpy as np
HERE=Path(__file__).resolve().parent
owner=json.loads((HERE/'emulator/complete.json').read_text());verify_owner(owner)
call=lambda c:request(owner['probe_port'],c)
config=json.loads(BASE.read_text())['config'];config.update(rndSeed=1967040301,endTick=7200)
seq=call('configure-native '+json.dumps(config,separators=(',',':')))['sequence']
for _ in range(450):
 s=call('status')
 if s['nativeRenderLoaded']==seq and s['nativeRenderReady']:break
 time.sleep(.1)
else:raise TimeoutError('renderer')
tick=call('pause')['tick'];call('render on');call('speed 1')
if tick<220:call(f'advance-native {220-tick}')
def capture(name):
 raw=subprocess.check_output([str(ADB),'-s',owner['serial'],'exec-out','screencap','-p'])
 (HERE/name).write_bytes(raw)
def tap(x,y):
 start=time.perf_counter();subprocess.run([str(ADB),'-s',owner['serial'],'shell','input','tap',str(round(x)),str(round(y))],check=True)
 return time.perf_counter()-start
capture('preflight.png')
before=call('observe');card=min(next(p for p in before['players'] if p['owner']==1)['hand'],key=lambda c:c['cost'])
slot=card['handIndex'];x,y=6.5,22.5
# Calibrated 1080x2280 visual hand centers and arena affine ground contacts.
geo=json.loads((HERE.parent/'l1/calibration.json').read_text())['tile_to_pixel']
point=2*(np.array(geo)@np.array([x,y,1]))
timing=[tap(210+142*slot,2100),tap(*point)]
call('advance-native 30');after=call('observe');capture('after-visual-taps.png')
# Also test the existing compiled hook's unscaled 1080x1920 coordinates.
legacy=[tap([211,354,497,640][slot],1749),tap(111+x/18*856,436+y/32*1230)]
call('advance-native 30');after_legacy=call('observe');capture('after-hook-taps.png')
result=dict(seed=config['rndSeed'],before=before,after=after,after_legacy=after_legacy,card=card,
 visual_hand=[210+142*slot,2100],visual_tile=point.tolist(),tap_seconds=timing,hook_tap_seconds=legacy,
 existing_layout='native_touch_layout.h kNativeRender1080x1920',calibration='l1/calibration.json')
(HERE/'touch-preflight.json').write_text(json.dumps(result,indent=2)+'\n')
with (HERE/'PROGRESS.md').open('a') as f:f.write('\nPreflight renderer launch and calibrated visual/legacy-hook tap trials completed. Network UID reject rules and pinned APK attestation verified. See touch-preflight.json and screenshots. Evaluation has not started.\n')
print('preflight complete',flush=True)
