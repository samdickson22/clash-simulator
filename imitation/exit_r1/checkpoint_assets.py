"""Export unchanged static model buffers for teacher-store tensor qualification."""
import argparse
import numpy as np
import torch
from .rows import sha,write_json


def main():
    p=argparse.ArgumentParser();p.add_argument('--checkpoint',required=True);p.add_argument('--output',required=True)
    a=p.parse_args();s=torch.load(a.checkpoint,map_location='cpu',weights_only=True)['ema']
    np.savez(a.output,descriptors=s['descriptors'].numpy(),tiles=s['tile_features'].numpy(),costs=s['costs'].numpy())
    write_json(a.output+'.json',dict(checkpoint_sha256=sha(a.checkpoint),asset_sha256=sha(a.output)))


if __name__=='__main__':main()
