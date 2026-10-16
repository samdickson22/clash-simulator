"""Run a budget-stage partition with candidate-specific feasible upgrade vectors."""
from pathlib import Path
import argparse,json
from bot.deckopt2 import run as harness


def main():
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True)
    p.add_argument('--stage',choices=['screen','validation'],required=True)
    p.add_argument('--workers',type=int,required=True);p.add_argument('--shard',type=int,required=True);p.add_argument('--shards',type=int,required=True)
    args=p.parse_args()
    meta=json.loads((args.root/'manifest.json').read_text())
    for name,digest in meta['job_source_sha256'].items():
        assert harness.sha(Path(__file__).with_name(name))==digest,('job source changed',name)
    import instrument
    instrument.install()
    original=harness.game
    def game(rt,vocab,root,stage,meta,case,candidate,player_name,out):
        current=dict(meta,own_levels=meta['candidate_plans'][candidate]['levels'])
        return original(rt,vocab,root,stage,current,case,candidate,player_name,out)
    harness.game=game
    from bot.players.runtime import Runtime
    harness.run(args.root,Runtime(),args)

if __name__=='__main__':main()
