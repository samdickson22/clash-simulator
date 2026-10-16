"""Read-only dependency census for an owned candidate; exclusive receipt output."""
import argparse
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import socket
import sys


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def digest(value):return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def inventory(root):
    result={}
    for p in sorted(root.rglob('*')):
        if '__pycache__' in p.parts or p.suffix=='.pyc':continue
        name=str(p.relative_to(root))
        if p.is_symlink():
            assert p.is_file(),f'directory/dangling dependency symlink is not covered: {p}'
            result[name]=dict(link=os.readlink(p),sha256=sha(p))
        elif p.is_file():result[name]=dict(sha256=sha(p))
    return result


def main():
    ap=argparse.ArgumentParser()
    for name in ('job','source','runtime','approved_source','out'):ap.add_argument('--'+name.replace('_','-'),type=Path,required=True)
    a=ap.parse_args();job=a.job.resolve()
    assert job==a.job and job.is_dir() and job.stat().st_uid==os.getuid()
    for p in (a.source,a.runtime,a.approved_source,a.out.parent):
        assert p.resolve().is_relative_to(job),(p,job)
    expected=json.loads(a.approved_source.read_text())
    assert sha(a.approved_source)=='71d4e713ebd1eb3c720acca6d7266cf33b0563cf16b8727950969f7d883b1e3c'
    actual={}
    for relative,want in expected['source_sha256'].items():
        root=a.runtime if relative.startswith('engine-rs/') or relative.endswith('/fair_player.py') else a.source
        actual[relative]=sha(root/relative)
        assert actual[relative]==want,(relative,actual[relative],want)
    complete_runtime=inventory(a.runtime);bot=inventory(a.source/'bot')
    assert (a.source/'reports/cards/tools/pool.py').is_file()
    tools=inventory(a.source/'reports/cards/tools')
    provenance={k:v for k,v in complete_runtime.items() if Path(k).name.endswith('RECEIPT.json')}
    runtime={k:v for k,v in complete_runtime.items() if k not in provenance}
    dependencies=dict(runtime_files=runtime,bot_files=bot,card_tools_files=tools,accepted_source=actual,
        python_binary_sha256=sha(Path(sys.executable).resolve()),python_version=platform.python_version(),
        machine=platform.machine(),packages={n:importlib.metadata.version(n) for n in ('numpy','torch')})
    # This binds all config-generating bytes; it is not an emitted R.config hash.
    config_inputs={k:v for k,v in runtime.items() if k=='gamedata.json' or k.startswith(('engine-rs/','src/clasher/')) or k.endswith('/fair_player.py')}
    out=dict(result='PASS',host=socket.gethostname(),uid=os.getuid(),source=str(a.source),runtime=str(a.runtime),
        approved_commit=expected['commit'],approved_manifest_sha256=sha(a.approved_source),
        native_sha256=sha(a.runtime/'native/clasher_core.abi3.so'),gamedata_sha256=sha(a.runtime/'gamedata.json'),
        runtime_manifest_sha256=digest(runtime),config_dependency_sha256=digest(config_inputs),
        bot_manifest_sha256=digest(bot),dependencies_sha256=digest(dependencies),dependencies=dependencies,
        card_tools_manifest_sha256=digest(tools),
        root_file_inventory_sha256=digest(complete_runtime),provenance_receipts=provenance)
    assert out['native_sha256']=='de11f12401da396b309cd2e5d3ea422cfa1c94f462a4e3250fd51d89a62887b1'
    assert out['gamedata_sha256']=='a7de3e93eb4320c48775da97cd0e5113fb793ea57782ba0eb006af0bd6eb0ccb'
    with a.out.open('x') as f:f.write(json.dumps(out,indent=2,sort_keys=True)+'\n')
    print(json.dumps({k:v for k,v in out.items() if k!='dependencies'}))


if __name__=='__main__':main()
