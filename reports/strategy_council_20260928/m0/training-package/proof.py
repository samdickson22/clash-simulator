"""Exercise default runtime data readers without training or producing labels."""
from __future__ import annotations

import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import sys

PACKAGE = Path(__file__).resolve().parent
INPUTS = PACKAGE/'inputs'
manifest = json.loads((PACKAGE/'manifest.json').read_text())
ROOT = Path(manifest['source_root'])
opened = set()
writes = set()


def audit(event,args):
    if event != 'open' or not isinstance(args[0],(str,bytes,os.PathLike)):
        return
    path = Path(os.fsdecode(args[0])).resolve()
    mode = args[1]
    flags = args[2] if len(args)>2 else 0
    writable = (isinstance(mode,str) and any(c in mode for c in 'wax+')) or (isinstance(flags,int) and bool(flags & (os.O_WRONLY|os.O_RDWR|os.O_CREAT)))
    if writable and path != Path(os.devnull):
        writes.add(str(path))
        if not path.is_relative_to(PACKAGE):
            raise RuntimeError(f'proof attempted a write outside staging: {path}')
    if path.is_relative_to(ROOT) and not path.is_relative_to(ROOT/'.venv'):
        opened.add(str(path))


sys.addaudithook(audit)
import numpy as np
import torch
from clasher.data import CardDataLoader
from clasher.paths import gamedata_path, project_root
from clasher.rl.model import ClasherPolicy, PolicyConfig
from clasher.rl.public_policy_contract import PublicPolicySequence
from clasher.rl.public_scripted_opponent import SUPPORTED_CARDS
from clasher.rl.selfplay_env import SelfPlayBattleEnv
from clasher.rl.structured_obs import StructuredObservationBuilder
from clasher.spells import SPELL_REGISTRY
from clasher.stat_scaling import _level_percentages

torch.set_num_threads(1)
torch.manual_seed(2928)
assert project_root() == INPUTS
assert gamedata_path() == INPUTS/'gamedata.json'
loader = CardDataLoader()
assert loader.get_card('IceSpirit').scaled_hitpoints == 215
assert loader.get_card('Goblins').scaled_damage == 125
builder = StructuredObservationBuilder(card_vocab=sorted(SUPPORTED_CARDS),max_entities=32,
    canonical_lane_globals=True,card_semantics_version=4,public_history_slots=4,
    public_seen_card_slots=8,public_entity_levels=True,public_hand_levels=True)
env = SelfPlayBattleEnv(public_contract_version=4,seed=2928,decision_interval_ticks=5)
env._structured_obs_builder = builder
env.reset()
assert env.battle.card_loader.data_file == INPUTS/'gamedata.json'
assert builder.loader.data_file == INPUTS/'gamedata.json'
assert env.battle.resolve_card_play(0,'IceSpirit')[1].scaled_hitpoints == 215
assert env.battle.resolve_card_play(0,'Goblins')[1].scaled_damage == 125
spell_values = {}
for name in ('Fireball','Log','Zap'):
    _,_,spell = env.battle.resolve_card_play(0,name)
    assert spell is SPELL_REGISTRY[name]
    spell_values[name] = {'damage':spell.damage,'crown_tower_damage':spell.crown_tower_damage,'level':spell.level}
assert spell_values['Fireball']['damage'] == 688
assert spell_values['Log']['damage'] == 268
assert spell_values['Zap']['damage'] == 192
observation = env.get_structured_observation(0)
mask = env.get_action_mask(0,structured_observation=observation)
sequence = PublicPolicySequence.from_observations(builder,[observation])
inputs = sequence.policy_inputs(action_mask=mask[None,:],previous_actions=[env.action_space.no_op_action],previous_rewards=[0],episode_starts=[True],device=torch.device('cpu'))
config = PolicyConfig(num_tokens=builder.spec.num_tokens,max_entities=32,
    public_contract_version=4,public_token_names=builder.token_names,public_observation_confidence=True,
    card_semantics_version=4,canonical_lane_globals=True,public_history_slots=4,public_seen_card_slots=8,
    d_model=32,num_heads=4,actor_layers=1,critic_layers=1,memory_size=48)
model = ClasherPolicy(config,builder.card_stat_features).eval()
def weights():
    digest=hashlib.sha256()
    for name,value in model.state_dict().items():
        digest.update(name.encode()); digest.update(value.detach().cpu().numpy().tobytes())
    return digest.hexdigest()
before = weights()
with torch.no_grad():
    output = model(inputs)
assert weights()==before
assert torch.isfinite(output.values).all()
assert inputs.hand_levels.shape == (1,1,5) and torch.all(inputs.hand_levels==11)
assert np.isclose(builder.card_stat_features[builder.token_id('IceSpirit'),5],np.log1p(84)/9)
assert np.isclose(builder.card_stat_features[builder.token_id('Goblins'),6],np.log1p(49)/8)
assert _level_percentages()[10] == 256
imports = {}
for name,module in sorted(sys.modules.items()):
    if name=='clasher' or name.startswith('clasher.'):
        if module.__file__ is None:
            assert all(Path(value).resolve().is_relative_to(ROOT/'src/clasher') for value in module.__path__), (name, list(module.__path__))
            imports[name]='src/clasher (namespace)'
            continue
        path=Path(module.__file__).resolve()
        assert path.is_relative_to(ROOT/'src/clasher')
        imports[name]=str(path.relative_to(ROOT))
dependencies = {name:importlib.metadata.version(name) for name in ('numpy','torch','pydantic','gymnasium','numba')}
data_reads = sorted(path for path in opened if not path.endswith(('.py','.pyc','.so','.dylib')))
assert str(ROOT/'gamedata.json') not in opened
assert str(ROOT/'decks.json') not in opened
assert str(INPUTS/'gamedata.json') in opened
assert str(INPUTS/'decks.json') in opened
unexpected_assets=[path for path in data_reads if not Path(path).is_relative_to(PACKAGE) and str(Path(path).relative_to(ROOT)) not in manifest['source_files']]
assert not unexpected_assets, unexpected_assets
result = {
    'status':'unadmitted-staging-proof-only',
    'source_tree_sha256':manifest['source_tree_sha256'],
    'gamedata_sha256':hashlib.sha256((INPUTS/'gamedata.json').read_bytes()).hexdigest(),
    'effective_loaders':{'engine':str(env.battle.card_loader.data_file),'semantics':str(builder.loader.data_file),'spell_registry':'default staged gamedata','scaling_table':'default staged gamedata'},
    'IceSpirit_level11_hp':215,'Goblins_level11_damage':125,'spells':spell_values,
    'semantic_hp_descriptor':float(builder.card_stat_features[builder.token_id('IceSpirit'),5]),
    'semantic_damage_descriptor':float(builder.card_stat_features[builder.token_id('Goblins'),6]),
    'public_v4':{'hand_levels':inputs.hand_levels.tolist(),'entity_levels':inputs.entity_levels.tolist(),'legal_actions':int(mask.sum()),'logit_shape':list(output.joint_logits.shape),'weights_unchanged':True},
    'imported_source_modules':imports,'project_asset_reads':data_reads,'writes_before_receipt':sorted(writes),
    'dependencies':dependencies,
    'python':sys.version,
}
(PACKAGE/'runtime/proof.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({'status':result['status'],'loaded_IceSpirit_hp':215,'loaded_Goblins_damage':125,'project_asset_reads':data_reads,'imported_source_modules':len(imports),'public_v4_forward':'passed','weights_unchanged':True},indent=2))
