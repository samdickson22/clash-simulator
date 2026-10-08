"""Copy only frozen study files from hub to an authorized, smoke-qualified peer."""
from pathlib import Path
import argparse,hashlib,json,subprocess,socket
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]

def main():
    ap=argparse.ArgumentParser();ap.add_argument('host',choices=['127x04','127x07','127x08']);args=ap.parse_args()
    assert socket.gethostname().split('.')[0]=='127x01'
    host=args.host
    smoke=subprocess.check_output(['ssh',host,'cat',f'/mpac/sdicks02/jobs/clasher/recovery-smoke-{host}-20261008.exit'],text=True).strip()
    assert smoke=='0'
    manifest=HERE/'evaluation-manifest.json';sha=hashlib.sha256(manifest.read_bytes()).hexdigest()
    previous=subprocess.run(['ssh',host,'sha256sum',str(manifest)],capture_output=True,text=True)
    if previous.returncode==0:assert previous.stdout.split()[0]==sha,'peer has a different frozen study'
    names=sorted(json.loads(manifest.read_text())['files'])+['evaluation-manifest.json']
    listing=HERE/'frozen-files.txt';listing.write_text('\n'.join(names)+'\n')
    subprocess.run(['ssh',host,'mkdir','-p',str(HERE)],check=True)
    subprocess.run(['rsync','-a','--files-from='+str(listing),str(HERE)+'/',f'{host}:{HERE}/'],check=True)
    command=f"cd {ROOT} && nice -n 10 .venv/bin/python -B -c \"import sys;sys.path.insert(0,'{HERE}');from evaluate import verify;import json;verify(json.load(open('{manifest}')));print('verified')\""
    subprocess.run(['ssh',host,command],check=True)
    print(host,sha)

if __name__=='__main__':main()
