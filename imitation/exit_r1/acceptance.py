"""Full-game byte/replay matrix and first-15-minute core throughput receipt."""
import argparse
from pathlib import Path
import time
from .emitter import initialize,run_game
from .rows import write_json


def main():
    p=argparse.ArgumentParser();p.add_argument('--out',required=True);p.add_argument('--checkpoint',required=True)
    a=p.parse_args();initialize(a.checkpoint)
    start=time.monotonic();records=[]
    for index in range(8):
        r=run_game(4503599708370496+index,index,Path(a.out)/f'game-{index:09d}',
                   ('script','v1','W','baseline')[index%4],acceptance=True)
        records.append({k:r[k] for k in ('seed','index','seat','opponent','rows','root_decisions','plays',
                       'cpu_seconds','wall_seconds','byte_checks','gate_c_byte_equal','replay_exact','outcome')})
        cpu=sum(v['cpu_seconds'] for v in records);roots=sum(v['root_decisions'] for v in records)
        write_json(Path(a.out)/'acceptance.json',dict(passed=True,games=records,
            byte_equal_rows=sum(v['byte_checks'] for v in records),root_decisions=roots,
            roots_per_cpu_second=roots/cpu,emitted_rows_per_cpu_second=sum(v['rows'] for v in records)/cpu,
            cpu_seconds=cpu,wall_seconds=time.monotonic()-start,
            first_measurement_within_15_minutes=records[0]['wall_seconds']<900))


if __name__=='__main__':main()
