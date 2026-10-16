#!/bin/bash
# usage: run_dash.sh JOBDIR NATIVEDIR OUTPREFIX   (127x08; two parallel shards of probe_dash_paths.py, nice 15)
J=$1; N=$2; O=$3; R1=/mpac/sdicks02/repos/clasher-bot-runtime/r1
cd $J/root
export CLASHER_ROOT=$J/root PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=$N:$J/root/engine-rs:$J/root/src:$R1/reports/strategy_council_20260928/engine-speed
PY="nice -n 15 /mpac/sdicks02/repos/clasher-bot/.venv/bin/python -B $J/fid/probe_dash_paths.py"
$PY $J/fid/$O-a.json zap fireball arrows rocket lightning log barblog snowball earthquake poison > $J/fid/$O-a.log 2>&1 &
$PY $J/fid/$O-b.json freeze tornado goblin_curse vines void electro_spirit ice_spirit rage heal clone > $J/fid/$O-b.log 2>&1 &
wait
