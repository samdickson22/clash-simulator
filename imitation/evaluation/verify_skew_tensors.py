"""Light CPU verification of recorded train/serve feature tensors; no inference."""
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
from imitation.model.features import build_row, collate_features


def main():
    ap=argparse.ArgumentParser();ap.add_argument('folder',type=Path);ap.add_argument('--output',type=Path,required=True)
    args=ap.parse_args();games=[];checks=0
    for path in sorted(args.folder.glob('game-*.json')):
        receipt=json.loads(path.read_text());tensor_path=args.folder/receipt['tensor_file']
        assert hashlib.sha256(tensor_path.read_bytes()).hexdigest()==receipt['tensor_sha256']
        assert receipt['sidecar_bytes_equal'] and receipt['recorded_stream_equal'] and receipt['terminal']
        with np.load(tensor_path,allow_pickle=False) as archive:
            z={key:archive[key] for key in archive.files}
            for i in range(receipt['rows']):
                packet={k.removeprefix('packet_'):z[k][i] for k in z if k.startswith('packet_')}
                a={k.removeprefix('serve_'):z[k][i] for k in z if k.startswith('serve_')}
                b={k.removeprefix('train_'):z[k][i] for k in z if k.startswith('train_')}
                aa=collate_features([build_row(packet,a,z['costs'])])
                bb=collate_features([build_row(packet,b,z['costs'])])
                assert aa.keys()==bb.keys()
                for key in aa:
                    x,y=aa[key].numpy(),bb[key].numpy()
                    assert x.dtype==y.dtype and x.shape==y.shape and x.tobytes()==y.tobytes(),(path,i,key)
                checks+=1
        games.append({'seed':receipt['seed'],'rows':receipt['rows'],'tensor_sha256':receipt['tensor_sha256']})
    assert len(games)==8
    result=dict(complete=True,games=games,rows=checks,byte_equal=True,plumbing_only=True,
                feature_source_sha256=hashlib.sha256(Path(__file__).parents[1].joinpath('model/features.py').read_bytes()).hexdigest())
    with open(args.output,'x') as f:json.dump(result,f,indent=2)
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
