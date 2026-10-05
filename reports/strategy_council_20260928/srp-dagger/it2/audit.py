"""Final receipts, checkpoint finiteness and preserved pilot identities."""
import sys,json,ast
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import kit
OUT=Path(__file__).resolve().parent

def main():
    done=json.loads((OUT/'completion.json').read_text());assert done['complete']
    pins=json.loads((kit.HERE/'preflight.json').read_text());kit.check_data_pins(pins);kit.check_native_pins();assert kit.sources_match(pins['sources'])
    original=json.loads((kit.HERE/'fit.json').read_text());assert kit.sha(kit.FINAL)==original['checkpoint_sha256'];assert kit.sha(kit.HERE/'aggregate.npz')==original['corpus_sha256'];assert kit.sha(kit.INITIAL)==pins['initial_sha256'];assert kit.config().model_dump()==pins['config']
    fit=json.loads((OUT/'fit.json').read_text());assert kit.sha(OUT/'student.pt')==fit['checkpoint_sha256']
    payload=kit.torch.load(OUT/'student.pt',map_location='cpu',weights_only=False)
    def finite(x):
        if isinstance(x,kit.torch.Tensor):assert kit.torch.isfinite(x).all();return 1
        if isinstance(x,dict):return sum(finite(v) for v in x.values())
        if isinstance(x,(list,tuple)):return sum(finite(v) for v in x)
        return 0
    tensors=finite(payload);assert tensors>0
    assert payload['srp_dagger']['iteration']==2 and payload['srp_dagger']['config']['epochs']==1
    quick=json.loads((OUT/'quick.json').read_text());assert quick['gate_passed']==done['quick_gate_passed'];assert done['full_evaluation_run']==quick['gate_passed']
    if not quick['gate_passed']:assert not (OUT/'evaluation/full-it2').exists()
    else:
        files=list((OUT/'evaluation/full-it2').glob('*.games.json'));assert len(files)==6
        for path in files:
            assert json.loads(path.read_text())[:8]==json.loads((OUT/'evaluation/quick-it2'/path.name).read_text())
    games=list((OUT/'games').glob('game-*.npz'));assert len(games)==72
    for path in games:assert kit.sha(path)==json.loads(path.with_suffix('.json').read_text())['npz_sha256']
    for p in OUT.glob('*.py'):ast.parse(p.read_text())
    size=kit.budget()
    result=dict(passed=True,finite_checkpoint_tensors=tensors,pilot_checkpoint_and_corpus_unchanged=True,initial_checkpoint_and_pilot_config_unchanged=True,canonical_and_native_guards=True,source_guard=True,quick_gate_obeyed=True,artifact_bytes=size)
    kit.write_json(OUT/'audit.json',result);print(json.dumps(result))
if __name__=='__main__':main()
