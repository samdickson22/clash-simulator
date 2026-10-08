"""Propagate the authoritative C56 completion manifest to the second replay host.

Metadata only, no overwrite: this lets both S122 supervisors observe the same
completion gate when lifting their 64-worker C56 reservation. Actual process
counts remain independently enforced by each S122 supervisor.
"""
import json,socket,subprocess,time
from pathlib import Path
from fetch_source import DATA,sha
assert socket.gethostname()=='127x01'
source=DATA/'c56-sidecars-v1/manifest.json'
while not source.exists():time.sleep(60)
r=json.loads(source.read_text());assert r['passed'] and r['perspectives']==82231 and r['rows']==64140802 and not any(r['violations'])
subprocess.run(['rsync','-c','--ignore-existing',str(source),'127x03:'+str(source)],check=True)
remote=subprocess.check_output(['ssh','127x03','sha256sum',str(source)],text=True).split()[0]
assert remote==sha(source),'existing peer C56 completion differs; never overwrite'
p=DATA/'receipts/s122-capacity-release.json';p.write_text(json.dumps({'source':str(source),'sha256':remote,'peer':'127x03','existing_files_not_overwritten':True,'released_unix':time.time()},indent=2)+'\n')
print(p.read_text(),flush=True)
