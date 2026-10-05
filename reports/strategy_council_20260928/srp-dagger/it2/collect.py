"""Reuse pilot collection with one extra student root candidate."""
import sys,json,tomllib
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import kit
from pydantic import Field
OUT=Path(__file__).resolve().parent
class Config(kit.Config):
    games:int=Field(ge=60,le=80)
def config():return Config.model_validate(tomllib.loads((OUT/'config.toml').read_text()))
def note(s):
    from datetime import datetime,timezone
    with (kit.HERE/'PROGRESS.md').open('a') as f:f.write(f'\n- {datetime.now(timezone.utc).isoformat()} it2: {s}\n')
class StudentCandidatePlanner(kit.RecordedPlanner):
    def _rollout(self,battle,player_id,action,other_action):
        self.other_action=other_action
        return super()._rollout(battle,player_id,action,other_action)
    def select_action(self,battle,player_id,legal):
        best=super().select_action(battle,player_id,legal)
        assert self.student_action in legal
        if self.student_action not in [a for a,_ in self.root_values]:
            # The same root snapshot, opponent move, rollout and leaf evaluator.
            self._rollout(battle,player_id,self.student_action,self.other_action)
        winner,value=self.root_values[0]
        for action,score in self.root_values:
            if score>value+1e-9:winner,value=action,score
        return winner

def main(start,stop):
    cfg=config();kit.torch.set_num_threads(1)
    loaded=kit.ev.load_policy_checkpoint(kit.INITIAL,device=kit.DEVICE,decks_path=kit.TRAINING)
    for game in range(start,min(stop,cfg.games)):
        kit.budget();path=OUT/'games'/f'game-{game:03d}.npz'
        if path.exists():
            receipt=json.loads(path.with_suffix('.json').read_text());assert kit.sha(path)==receipt['npz_sha256']
            continue
        r=kit.collect_game(game,loaded,cfg,output_dir=OUT/'games',planner_class=StudentCandidatePlanner)
        with kit.np.load(path) as d:
            for row in kit.np.flatnonzero(d['expert_action_supervision_valid']):
                ids=d['root_candidate_ids'][d['root_candidate_rows']==row]
                assert d['student_actions'][row] in ids and len(ids)==len(set(ids))
        note(f'Collected game {game:03d}, {r["labels"]} labels, student candidate present on every labelled row; native/canonical guards passed.')
if __name__=='__main__':main(int(sys.argv[1]),int(sys.argv[2]))
