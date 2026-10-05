"""Audit saved opened native frames; never contacts an emulator or runs a policy."""
from __future__ import annotations
import argparse
from pathlib import Path
from clasher.rl.native_public_calibration import audit_saved_run, verify_calibration_receipt


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run',type=Path)
    parser.add_argument('--output',type=Path)
    parser.add_argument('--verify',type=Path)
    args=parser.parse_args()
    if args.verify:
        if args.run or args.output:parser.error('--verify cannot combine with --run/--output')
        receipt=verify_calibration_receipt(args.verify)
    else:
        if args.run is None or args.output is None:parser.error('--run and --output are required')
        receipt=audit_saved_run(args.run)
        args.output.parent.mkdir(parents=True,exist_ok=True)
        with args.output.open('x') as stream:stream.write(receipt.model_dump_json(indent=2)+'\n')
    print(f'{receipt.frame_count} frames / {receipt.owner_packet_count} owner packets: native known-channel audit passed; camera and own-card level calibration remain unestablished')


if __name__=='__main__':main()
