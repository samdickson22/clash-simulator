"""Reviewer reference for the A19 r3 inventory fix (not production code).

Differences from r2 a19_resources.inventory():
  * ownership by REAL uid from /proc/<pid>/status, not the /proc inode owner
    (non-dumpable processes can present a root-owned inode and would be skipped);
  * PermissionError on cwd or smaps_rollup never propagates and never excludes:
    the process is COUNTED against the cap and flagged inaccessible;
  * PSS for an unreadable process falls back to resident bytes from the
    world-readable /proc/<pid>/statm, an upper bound on PSS;
  * descendants of a Clasher-marked process stay counted, as in r2; an
    inaccessible process does not mark its (separately classifiable) children.
"""
import os
from pathlib import Path

PAGE=os.sysconf('SC_PAGE_SIZE')

def _ruid(p):
    for line in (p/'status').read_text().splitlines():
        if line.startswith('Uid:'):return int(line.split()[1])
    raise ValueError('No Uid line: '+str(p))

def inventory(proc=Path('/proc'),uid=None):
    uid=os.getuid() if uid is None else uid
    candidates={};marked=set();inaccessible=set()
    for p in proc.iterdir():
        if not p.name.isdigit():continue
        pid=int(p.name)
        try:
            if _ruid(p)!=uid:continue
            stat=(p/'stat').read_text().rsplit(') ',1)[1].split()
            if stat[0] in ('Z','X'):continue
            cmd=(p/'cmdline').read_bytes().replace(b'\0',b' ').decode(errors='replace')
        except (FileNotFoundError,ProcessLookupError):continue
        try:cwd=os.readlink(p/'cwd')
        except (FileNotFoundError,ProcessLookupError):continue
        except PermissionError:cwd=None;inaccessible.add(pid)
        candidates[pid]=(p,int(stat[1]))
        if 'clasher' in cmd or (cwd and 'clasher' in cwd):marked.add(pid)
    while True:
        more={pid for pid,(p,parent) in candidates.items() if parent in marked}
        if more<=marked:break
        marked.update(more)
    rows=[]
    for pid in sorted(marked|inaccessible):
        p,parent=candidates[pid]
        try:
            pss=sum(int(s.split()[1])*1024 for s in (p/'smaps_rollup').read_text().splitlines() if s.startswith('Pss:'))
        except (FileNotFoundError,ProcessLookupError):continue
        except PermissionError:
            inaccessible.add(pid)
            try:pss=int((p/'statm').read_text().split()[1])*PAGE
            except (FileNotFoundError,ProcessLookupError):continue
        try:affinity=sorted(os.sched_getaffinity(pid))
        except (ProcessLookupError,FileNotFoundError):continue
        except PermissionError:affinity=None
        rows.append(dict(pid=pid,parent=parent,pss_bytes=pss,affinity=affinity,
                         inaccessible=pid in inaccessible,clasher_marked=pid in marked))
    return rows
