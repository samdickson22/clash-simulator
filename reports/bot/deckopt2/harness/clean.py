"""BOT LEAD clean rule: opponent refusals are behavior; own refusals remain flags.

Interpret raw rows without editing them. Existing historical `issues` includes
both seats, so remove only that rejection tag when our seat had zero refusals.
"""
from pathlib import Path
import json


def rejected(row,seat):
    channels=row.get('result',{}).get('channels',{})
    return int(channels.get(str(seat),channels.get(seat,{})).get('rejected',0))


def problems(row):
    issues=list(row.get('issues',[]))
    if 'error'in row:issues.append(row['error'])
    if 'command rejections' in issues and rejected(row,row['seat'])==0:
        issues.remove('command rejections')
    if rejected(row,row['seat']) and 'command rejections'not in issues:issues.append('our command rejections')
    return issues


def read_rows(root,stage,complete=False):
    from bot.deckopt2.run import jobs_for,sha
    root=Path(root);data=json.loads((root/stage/'bank.json').read_text())
    rows=[json.loads(p.read_text()) for p in sorted((root/stage/'rows').glob('*.json'))]
    assert all(not problems(r) for r in rows),[(r['id'],r['candidate'],r['player'],problems(r)) for r in rows if problems(r)]
    digest=sha(root/stage/'bank.json')
    assert all(r['bank_sha256']==digest for r in rows)
    if complete:assert len(rows)==len(jobs_for(data)),(len(rows),len(jobs_for(data)))
    keys=[(r['id'],r['candidate'],r['player']) for r in rows]
    assert len(keys)==len(set(keys))
    return data,rows


def install():
    from bot.deckopt2 import run as h
    h.read_rows=read_rows
