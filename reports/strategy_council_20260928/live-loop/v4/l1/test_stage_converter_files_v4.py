"""Converter allowlist rejects heldout/unknown files; optional skip logs retained."""
from copy import deepcopy
import json
from stage_training import FILES,T6_FILES,staging_files


def main():
    checks=0
    row=dict(split='train',files={n:'a'*64 for n in (*FILES,*T6_FILES) if n!='receipt.json'})
    def check(value):
        nonlocal checks
        assert value;checks+=1
    def refuses(rows,**kwargs):
        nonlocal checks
        try:staging_files(rows,all_training_payloads=True,**kwargs)
        except ValueError:checks+=1
        else:raise AssertionError('Unsafe converter files accepted')
    check(set(staging_files([row]))==set(FILES))
    check('video.mp4' not in staging_files([row],labels_only=True))
    check(set(row['files'])<=set(staging_files([row],all_training_payloads=True)))
    optional=deepcopy(row);optional['files']['observation-skips.jsonl']='b'*64
    check(set(optional['files'])<=set(staging_files([row,optional],all_training_payloads=True)))
    for name in ('../secret','unknown.jsonl','/tmp/input'):
        bad=deepcopy(row);bad['files'][name]='c'*64;refuses([bad])
    for name in ('video.mp4','evaluation-only.jsonl.gz','objects.jsonl.gz'):
        bad=deepcopy(row);bad['files'].pop(name);refuses([bad])
    refuses([dict(row,split='heldout')]);refuses([row],labels_only=True)
    check('observation-skips.jsonl' in staging_files([dict(optional,split='validation')],all_training_payloads=True))
    print(json.dumps(dict(checks=checks,passed=True,synthetic_only=True,heldout_payloads_opened=False)),flush=True)


if __name__=='__main__':main()
