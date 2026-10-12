# read-only: apt unit states, apt-daily timer line, and count of apt/maintenance processes excluding this shell's tree
s=$(systemctl is-active apt-daily.service apt-daily-upgrade.service | tr "\n" " ")
t=$(systemctl list-timers --all 2>/dev/null | grep "apt-daily.timer" | cut -c1-110)
n=$(ps -eo pid=,ppid=,args= | awk -v me=$$ '$1!=me && $2!=me' | grep -E "(^| |/)(apt|apt-get|apt-check|apt.systemd.daily|unattended-upgrade|unattended-upgrades|dpkg|check-new-release|update-notifier)( |$)|/usr/lib/update-notifier/|/usr/lib/ubuntu-release-upgrader/" | grep -v -E "awk|grep" | wc -l)
echo "$s|$t|procs=$n"
