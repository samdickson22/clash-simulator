"""Terminal polling guards; no SSH, Phase A reads or match payload access."""
import argparse
from contextlib import redirect_stdout
import io
import json
from pathlib import Path
from unittest.mock import patch

import phase_watch


def main(root):
    root.mkdir()
    checks=0
    def check(ok):
        nonlocal checks
        assert ok
        checks+=1
    def invoke(folder,now=1000,deadline=2000):
        text=io.StringIO()
        with patch('sys.argv',['phase_watch','--once','--output',str(folder),'--deadline',str(deadline)]), \
             patch.object(phase_watch.time,'time',return_value=now), \
             patch.object(phase_watch.subprocess,'run',side_effect=AssertionError('Unexpected SSH')) as remote, \
             redirect_stdout(text):
            phase_watch.main()
            check(not remote.called)
        return text.getvalue()
    for index,status in enumerate(('12-hour-timeout','schedule-deleted-coordinator-confirmed-completion')):
        folder=root/str(index);folder.mkdir()
        receipt=json.dumps(dict(status=status,deleted=True,time=900))+'\n'
        (folder/'stopped.json').write_text(receipt)
        check('terminal stop' in invoke(folder))
        check('terminal stop' in invoke(folder,now=3000))
        check((folder/'stopped.json').read_text()==receipt)
        check(not (folder/'latest.json').exists())
    folder=root/'deadline'
    check('deadline reached' in invoke(folder,now=2000))
    check(json.loads((folder/'stopped.json').read_text())['status']=='12-hour-timeout')
    folder=root/'duplicate';folder.mkdir()
    (folder/'latest.json').write_text(json.dumps(dict(time=900)))
    check('less than 15 minutes' in invoke(folder))
    folder=root/'signal';folder.mkdir()
    (folder/'stopped.json').write_text(json.dumps(dict(status='signal')))
    check(phase_watch.terminal_status(folder) is None)
    check(phase_watch.terminal_status(root/'missing') is None)
    for record in ('[]','{"status":"unknown"}','not json'):
        folder=root/'malformed';folder.mkdir(exist_ok=True)
        (folder/'stopped.json').write_text(record)
        try:invoke(folder)
        except ValueError:checks+=1
        else:raise AssertionError('Malformed stop receipt accepted')
    print(json.dumps(dict(checks=checks,passed=True,remote_calls=0)))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True)
    main(parser.parse_args().output)
