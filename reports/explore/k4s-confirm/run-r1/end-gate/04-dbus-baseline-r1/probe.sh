# read-only 04 system-bus baseline (coordinator DBus ruling R4): one long-lived ssh, nice 19, 1 Hz x 1800 samples of the
# pinned system dbus-daemon /proc/<pid>/stat; prints epoch.ns + the raw stat line; stops if the pid disappears.
P=2005
echo "BEGIN $(date -u +%FT%T.%3NZ) host=$(hostname) clk_tck=$(getconf CLK_TCK) nproc=$(nproc) who=$(who | wc -l) uid125=$(ps -u 125 -o pid= | wc -l) exe=$(readlink /proc/$P/exe)"
for i in $(seq 1 1800); do
  s=$(cat /proc/$P/stat 2>/dev/null) || { echo "GONE $(date +%s.%N)"; break; }
  echo "S $(date +%s.%N) $s"
  sleep 1
done
echo "END $(date -u +%FT%T.%3NZ) who=$(who | wc -l) uid125=$(ps -u 125 -o pid= | wc -l)"
