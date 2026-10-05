"""Stop only this task's owned emulator to keep image plus allocated AVD storage below 7 GB."""
import json
import shutil
import subprocess
import time
from official_loop import ROOT,AVD,owned_pid,adb


def main():
    pid=owned_pid()
    while True:
        try:
            if owned_pid()!=pid:return
        except (subprocess.CalledProcessError,RuntimeError):return
        size=sum(f.stat().st_blocks*512 for f in AVD.rglob('*') if f.is_file())
        free=shutil.disk_usage(AVD).free
        row={'time':time.time(),'pid':pid,'avd_allocated_bytes':size,'host_free_bytes':free}
        (ROOT/'resource-status.json').write_text(json.dumps(row,indent=2)+'\n')
        # 4.4 GB AVD + 2.31 GB Play image leaves headroom below 7 GB.
        if size>=4_400_000_000 or free<3_000_000_000:
            row['action']='stop_owned_emulator'
            (ROOT/'resource-stop.json').write_text(json.dumps(row,indent=2)+'\n')
            adb('emu','kill')
            return
        time.sleep(2)

if __name__=='__main__':main()
