"""Finish owned workers at game boundaries, then balance remaining whole games."""
import argparse
import os
import signal
import subprocess
import time
from run import HERE, alive, note, launch, finish, finish_pilot


def completed(start, stop):
    return {g for g in range(start,stop) if (HERE/'games'/f'game-{g:03d}.json').exists()}


def main(first=None, second=None):
    note(f'Coordinator PID {os.getpid()}. Drain owned collectors at their next completed game, then schedule remaining games with two workers.')
    pending_stops = {} if first is None else {first:(1,20), second:(20,40)}
    initial = {pid:completed(*bounds) for pid,bounds in pending_stops.items()}
    while pending_stops:
        for pid,bounds in list(pending_stops.items()):
            now = completed(*bounds)
            if not alive(pid):
                if len(now) != bounds[1]-bounds[0]:
                    raise RuntimeError(f'collector PID {pid} exited before boundary handoff')
                del pending_stops[pid]
                continue
            if now - initial[pid]:
                command = subprocess.check_output(['ps','-p',str(pid),'-o','command='],text=True)
                expected = f'{HERE}/kit.py collect --start {bounds[0]} --stop {bounds[1]}'
                if expected not in command:
                    raise RuntimeError(f'PID {pid} no longer matches the owned collector')
                os.kill(pid, signal.SIGTERM)
                while alive(pid): time.sleep(.1)
                note(f'Stopped owned collector PID {pid} after complete game receipt(s) {sorted(now-initial[pid])}. Preserved all completed data; no completed game will be repeated.')
                del pending_stops[pid]
        time.sleep(.2)
    # Retain any incomplete publication before retrying that uncompleted game.
    interrupted = HERE/'interrupted'
    for path in (HERE/'games').glob('*.npz'):
        if path.name.endswith('.partial.npz') or not path.with_suffix('.json').exists():
            interrupted.mkdir(exist_ok=True)
            path.rename(interrupted/path.name)
            note(f'Preserved incomplete artifact {path.name} under interrupted/.')
    pending = sorted(set(range(40))-completed(0,40))
    note(f'Next: collect remaining game IDs {pending}; at most two concurrent processes.')
    running = {}
    while pending or running:
        while pending and len(running)<2:
            game = pending.pop(0)
            running[game] = launch(f'collect-game-{game:03d}',
                [HERE/'kit.py','collect','--start',game,'--stop',game+1])
        for game, proc in list(running.items()):
            if proc.poll() is not None:
                finish(f'collect-game-{game:03d}',proc)
                if game not in completed(game,game+1):
                    raise RuntimeError(f'game {game} exited without its receipt')
                del running[game]
        time.sleep(1)
    finish_pilot()


if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--first-pid',type=int)
    parser.add_argument('--second-pid',type=int)
    args=parser.parse_args()
    if (args.first_pid is None) != (args.second_pid is None):
        parser.error('provide both owned PIDs, or neither to resume with no active collectors')
    try: main(args.first_pid,args.second_pid)
    except Exception as exc:
        note(f'FAILED: {exc!r}. No completion receipt written.')
        raise
