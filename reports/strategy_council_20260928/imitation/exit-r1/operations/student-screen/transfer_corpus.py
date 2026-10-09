import concurrent.futures
import hashlib
from pathlib import Path
import subprocess
import time
job=Path('/mpac/sdicks02/jobs/clasher/exit-r1-student-screen-20261009-r1')
deadline=time.monotonic()+1800
while not (job/'corpus.sha256').exists():
    if time.monotonic()>deadline:raise TimeoutError('corpus did not seal within 30 minutes')
    if (job/'pack-r2.exit').exists() and (job/'pack-r2.exit').read_text().strip()!='0':
        raise RuntimeError('packing failed')
    time.sleep(10)
digest=hashlib.sha256((job/'corpus/manifest.json').read_bytes()).hexdigest()
assert digest==(job/'corpus.sha256').read_text().split()[0]
def transfer(host):
    log=(job/f'corpus-transfer-{host}.log').open('w')
    for command in (["rsync","-a","--quiet",str(job/'corpus'),f'127x{host}:{job}/'],
                    ['scp','-q',str(job/'ops/verify_corpus.py'),f'127x{host}:{job}/ops/'],
                    ['ssh',f'127x{host}',f'nice -n 19 python3 -B {job}/ops/verify_corpus.py {job}/corpus {digest}']):
        subprocess.run(command,check=True,stdout=log,stderr=subprocess.STDOUT)
    log.close();return host
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
    for host in pool.map(transfer,['01','04','09']):print('verified',host,flush=True)
(job/'corpus-transfers-complete.txt').write_text(digest+'\n')
