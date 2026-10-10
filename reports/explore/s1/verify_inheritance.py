"""Pre-qualification immutable snapshot audit; hashes only, no compute imports."""
import argparse,hashlib,json,subprocess
from pathlib import Path

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--job',type=Path,required=True);a=ap.parse_args();j=a.job
    reference=json.loads((j/'inherited-runtime-pin.json').read_text())
    for name,h in reference['files'].items():assert sha(j/'repo'/name)==h,name
    for name,h in reference['native_source'].items():assert sha(j/'native-source'/name)==h,name
    assert sha(j/'native/clasher_core.abi3.so')==reference['native_sha256']
    for name,h in reference['gate_adapter_exact'].items():assert sha(j/'repo/imitation/evaluation'/name)==h,name
    (j/'inheritance-verified.json').write_text(json.dumps(dict(utc=subprocess.check_output(['date','-u','+%FT%TZ'],text=True).strip(),source_files=len(reference['files']),native_source_files=len(reference['native_source']),native_sha256=reference['native_sha256'],gate_adapter_exact=reference['gate_adapter_exact']),indent=2)+'\n')
if __name__=='__main__':main()
