#!/bin/bash
# CANDIDATE (not run; needs coordinator review + GO). Option A for the A4 03 l01 failure: create the empty, read-only
# directory <runtime>/reports/strategy_council_20260928/engine-speed/results that frozen es_common.py:20 mkdirs at
# import, inside the staged a-w runtime. One login per host from 05. Usage: mkdir-results.sh HOST   (127x03 | 127x04)
set -u
H=$1
case $H in 127x03) BASE=/mpac/sdicks02/jobs/clasher/k4s-end-r1;; 127x04) BASE=/mpac/sdicks02/jobs-k4s/k4s-end-r1;; *) echo bad host; exit 2;; esac
P=$BASE/runtime-98566c032d0b/reports/strategy_council_20260928/engine-speed
/usr/bin/ssh -T -o BatchMode=yes -o ControlMaster=no -o ControlPath=none -o StrictHostKeyChecking=yes -o ConnectTimeout=20 \
  -o ClearAllForwardings=yes -o RequestTTY=no -- "$H" "set -u; P='$P'; H='$H'
  [ \"\$(hostname -s)\" = \"\$H\" ] || { echo __RC=90; exit 0; }
  [ -d \"\$P\" ] && [ ! -L \"\$P\" ] || { echo __RC=91; exit 0; }
  [ \"\$(realpath -e \"\$P\")\" = \"\$P\" ] || { echo __RC=92; exit 0; }
  [ ! -e \"\$P/results\" ] && [ ! -L \"\$P/results\" ] || { echo __RC=93; exit 0; }
  [ -z \"\$(find \"\$P\" -maxdepth 0 -perm /222)\" ] || { echo __RC=94; exit 0; }
  chmod u+w \"\$P\" && mkdir \"\$P/results\" && chmod a-w \"\$P/results\" && chmod a-w \"\$P\" || { echo __RC=95; exit 0; }
  stat -c '%A %h %n' \"\$P\" \"\$P/results\"; ls -A \"\$P/results\" | wc -l; echo __RC=0"
