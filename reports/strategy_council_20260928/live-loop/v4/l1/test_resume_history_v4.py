"""Preserve interrupted logs and enforce checkpoint-prefix identity."""
import argparse
import json
from pathlib import Path
from train_v4 import resume_history


def main(root):
    root.mkdir(exist_ok=False);p=root/'training.jsonl';checks=0
    full=b''.join((json.dumps(dict(step=i,loss=1.))+'\n').encode() for i in range(1,12))
    p.write_bytes(full);backup=resume_history(p,8)
    assert backup.read_bytes()==full and len(p.read_bytes().splitlines())==8;checks+=1
    assert resume_history(p,8) is None;checks+=1
    partial=p.read_bytes()+b'{"step":9,"loss":'
    p.write_bytes(partial);backup=resume_history(p,8)
    assert backup.read_bytes()==partial and len(p.read_bytes().splitlines())==8;checks+=1
    for content,step in [(full,12),(full,-1),(full,True),(b'{"step":2}\n',1),
                         (b'{"step":1}\n{"step":1}\n',1),(b'{"step":1}\nbroken\n',1),
                         (b'broken\n{"step":1}\n',1)]:
        p.write_bytes(content)
        try:resume_history(p,step)
        except ValueError:assert p.read_bytes()==content;checks+=1
        else:raise AssertionError('Invalid checkpoint/log accepted')
    print(json.dumps(dict(checks=checks,passed=True,synthetic_only=True)))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);main(p.parse_args().output)
