#!/usr/bin/env bash
# ovpeek.sh <name>: one frame of the driver's overlay stream (no extra SCK client) -> 05 shots/<name>.jpg
n=$1
ssh macmini-fleet 'curl -s -m 2 http://127.0.0.1:8765/stream -o ~/clasher-live/loop/tmp/ovp.mjpeg; true' && scp -q macmini-fleet:clasher-live/loop/tmp/ovp.mjpeg /tmp/ovp.mjpeg && python3 -c "
d=open('/tmp/ovp.mjpeg','rb').read(); i=d.rfind(b'\xff\xd8'); i=d.rfind(b'\xff\xd8',0,i) if i>0 else i; j=d.find(b'\xff\xd9',i)
open('/mpac/sdicks02/scratch/live-loop/shots/$n.jpg','wb').write(d[i:j+2]) if i>=0 and j>0 else print('no frame')"
