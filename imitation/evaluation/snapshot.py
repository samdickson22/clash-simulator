"""Create and verify content-addressed immutable evaluation source snapshots."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess


def digest(data): return hashlib.sha256(data).hexdigest()


def verify(root):
    manifest=json.loads((root/'snapshot-manifest.json').read_text())
    for name, want in manifest['files'].items():
        if digest((root/name).read_bytes()) != want:
            raise ValueError(f'snapshot file changed: {name}')
    tree=digest(json.dumps(manifest['files'],sort_keys=True,separators=(',',':')).encode())
    if tree != manifest['tree_sha256']: raise ValueError('snapshot tree hash mismatch')
    return manifest


def provenance():
    root=Path(__file__).resolve().parents[2]
    path=root/'snapshot-manifest.json'
    if not path.exists(): return {'snapshot_tree_sha256':None}
    m=verify(root)
    return {'snapshot_tree_sha256':m['tree_sha256'],
            'snapshot_manifest_sha256':digest(path.read_bytes()),'snapshot_root':str(root)}


def main():
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path);p.add_argument('--parent',type=Path)
    p.add_argument('--verify',type=Path);args=p.parse_args()
    if args.verify:
        print(json.dumps({'verified':True,'tree_sha256':verify(args.verify)['tree_sha256']}));return
    source=args.source.resolve();blobs={};committed={}
    model_commit=subprocess.check_output(['git','rev-parse','43d895e'],cwd=source,text=True).strip()
    head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=source,text=True).strip()
    for folder in ('model','evaluation'):
        for path in sorted((source/'imitation'/folder).rglob('*')):
            if not path.is_file() or '__pycache__' in path.parts or path.suffix=='.pyc':continue
            name=str(path.relative_to(source));blobs[name]=path.read_bytes()
            if folder=='model':
                result=subprocess.run(['git','show',f'{model_commit}:{name}'],cwd=source,capture_output=True)
                if result.returncode==0 and result.stdout==blobs[name]:committed[name]=model_commit
    # Prevent Python namespace merging with another task's mutable package.
    blobs['imitation/__init__.py']=b'"""Isolated evaluation snapshot package."""\n'
    # Drafts are inputs to freeze, kept inside the same immutable snapshot.
    for gate in ('b','c'):
        name=f'imitation/gate-{gate}/PREREG.md';blobs[name]=(source/name).read_bytes()
    files={name:digest(data) for name,data in sorted(blobs.items())}
    tree=digest(json.dumps(files,sort_keys=True,separators=(',',':')).encode())
    root=args.parent/tree[:16]
    if root.exists():
        verify(root);print(root);return
    for name,data in blobs.items():
        target=root/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
    manifest={'tree_sha256':tree,'files':files,'source_checkout':str(source),'source_head_commit':head,
              'model_reference_commit':model_commit,'byte_identical_committed_files':committed,
              'note':'All other bytes are pinned working-tree files; no claim they are committed.'}
    (root/'snapshot-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    verify(root);print(root)


if __name__=='__main__':main()
