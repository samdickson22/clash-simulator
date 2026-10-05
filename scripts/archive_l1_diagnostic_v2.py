"""Losslessly pack the unscored pacing diagnostic, then remove verified loose JPEGs."""
import hashlib
import json
import tarfile
import time

from collect_l1_rendered import REPORT,append,progress


def main():
    root=REPORT/'v2/stream-dataset';deadline=time.monotonic()+7200
    while not (root/'complete.json').exists():
        if time.monotonic()>deadline:raise TimeoutError('Diagnostic capture incomplete')
        time.sleep(5)
    archive=root/'archives';archive.mkdir(exist_ok=False)
    rows=[json.loads(l) for l in (root/'inputs.jsonl').read_text().splitlines()]
    before=after=0
    for start in range(0,len(rows),100):
        batch=rows[start:start+100];path=archive/f'frames-{start:05d}.tar.xz'
        hashes={r['image']:hashlib.sha256((root/r['image']).read_bytes()).hexdigest() for r in batch}
        with tarfile.open(path,'w:xz',preset=1) as tar:
            for row in batch:tar.add(root/row['image'],arcname=row['image'],recursive=False)
        with tarfile.open(path,'r:xz') as tar:
            actual={m.name:hashlib.sha256(tar.extractfile(m).read()).hexdigest() for m in tar.getmembers()}
        if actual!=hashes:raise ValueError('Archive did not exactly preserve all JPEG bytes')
        for row in batch:
            file=root/row['image'];before+=file.stat().st_size
            append(archive/'index.jsonl',dict(image=row['image'],archive=str(path.relative_to(root)),sha256=hashes[row['image']]))
            file.unlink()
        after+=path.stat().st_size
    record=dict(frames=len(rows),loose_jpeg_bytes=before,archive_bytes=after,lossless_byte_verified=True,
        scope='Unscored single-tick pacing diagnostic only; core/scored and event-boundary images unchanged',
        extraction='Each tar.xz contains original frames/... paths. Extract into this dataset to restore loose images.')
    (archive/'complete.json').write_text(json.dumps(record,indent=2)+'\n')
    progress(f'v2 diagnostic JPEG conversion: {len(rows)} frames losslessly archived and every member hash verified before deleting its loose original; {before} -> {after} bytes.')


if __name__=='__main__':main()
