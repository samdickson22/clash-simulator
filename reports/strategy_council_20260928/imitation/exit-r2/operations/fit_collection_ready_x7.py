"""Require clean fit exit and final artifacts before collecting a final EMA."""
import inspect
import json
import os
from pathlib import Path
import shlex
import subprocess


def group_alive(pgid):
    try:
        os.killpg(int(pgid), 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def snapshot(job, arm, step, alive=group_alive):
    job = Path(job)
    fit = job / 'fits' / arm
    required = {
        'checkpoint': fit / f'step-{step:08d}.pt',
        'complete': fit / 'complete.json',
        'segment': fit / 'segment.json',
        'inputs': fit / 'inputs.json',
        'runtime': fit / 'runtime.json',
        'exit': job / f'{arm}-exit.json',
        'launch': job / f'{arm}-launch.json',
    }
    result = dict(arm=arm, step=step, ready=False)
    missing = [name for name, path in required.items()
               if not path.is_file() or not path.stat().st_size]
    if missing:
        return dict(result, reason='final artifacts not yet closed', missing=missing)
    try:
        values = {name: json.loads(path.read_text())
                  for name, path in required.items() if name != 'checkpoint'}
        complete, segment, exited, launch = (values[name] for name in
                                             ('complete', 'segment', 'exit', 'launch'))
        groups = [launch['supervisor_pgid'], launch['trainer_pgid']]
        live = [int(pgid) for pgid in groups if alive(pgid)]
        result.update(live_owned_pgids=live, exit=exited,
                      segment_status=segment['status'],
                      complete_step=complete['step'], stopped=complete['stopped'])
        if live:
            return dict(result, reason='owned fit groups still live')
        if exited['exit_code'] != 0 or exited.get('reason') is not None:
            return dict(result, reason='fit did not exit cleanly')
        if complete['stopped'] or complete['step'] != step:
            return dict(result, reason='not the complete final step')
        if segment['status'] != 'returned' or (
            segment['cursor_start'] + segment['optimizer_steps'] != step
        ):
            return dict(result, reason='fit segment incomplete')
        if complete['pins'] != values['inputs']['pins']:
            return dict(result, reason='complete and input pins differ')
        return dict(result, ready=True, reason='final artifacts and clean fit exit ready')
    except (ValueError, KeyError, TypeError, FileNotFoundError) as exc:
        return dict(result, reason='fit metadata incomplete', error=str(exc))


def collection_ready(job, arm, host, step):
    assert arm in ('X1', 'X2', 'X3', 'X4', 'X5', 'X6', 'X7')
    assert host in ('127x01', '127x04', '127x08', '127x09', '127x13', '127x14', '127x16')
    # Execute only this frozen metadata probe; no new code is staged on fit hosts.
    code = ('import json,os,sys\nfrom pathlib import Path\n' +
            inspect.getsource(group_alive) + '\n' + inspect.getsource(snapshot) +
            '\nprint(json.dumps(snapshot(sys.argv[1],sys.argv[2],int(sys.argv[3]))))\n')
    command = shlex.join(['nice', '-n', '10', 'python3', '-c', code,
                          str(job), arm, str(step)])
    response = subprocess.run(['ssh', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=5',
                               host, command], capture_output=True, text=True)
    if response.returncode:
        state = dict(arm=arm, step=step, ready=False, reason='metadata probe unavailable',
                     probe_exit_code=response.returncode)
    else:
        try:
            state = json.loads(response.stdout)
        except ValueError:
            state = dict(arm=arm, step=step, ready=False, reason='metadata probe incomplete')
    from imitation.exit_r1.rows import write_json
    write_json(Path(job) / f'collection-{arm}.json', dict(
        state, host=host,
        utc=subprocess.check_output(['date', '-u', '+%FT%TZ'], text=True).strip()))
    return state['ready']
