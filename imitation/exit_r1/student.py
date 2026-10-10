"""Mixed human/teacher optimization without changes to T11/T4 scientific code."""
from dataclasses import asdict
import json
from pathlib import Path
import numpy as np
import torch
from torch import nn
from imitation.model.losses import loss_parts, total_loss
from imitation.model.network import ModelConfig, SetPolicy, masked_log_softmax
from imitation.model.store import PackedStore
from imitation.model.batching import build_batch
from .rows import sha


class TeacherStore(PackedStore):
    def __init__(self, directory, assets):
        self.root = Path(directory)/'train'
        seal = json.loads((self.root.parent/'manifest.json').read_text())
        if seal.get('schema')!='clasher.exit-r1.teacher-v6.v1' or not seal.get('complete'):
            raise ValueError('only sealed completed teacher games may train')
        for name,digest in seal['files'].items():
            if sha(self.root.parent/name) != digest:
                raise ValueError('teacher shard SHA mismatch: '+name)
        self.manifest = json.loads((self.root/'manifest.json').read_text())
        self.arrays = {k:np.load(self.root/(k+'.npy'), mmap_mode='r',allow_pickle=False)
                       for k in self.manifest['arrays']}
        self.arrays['mask_table'] = np.load(self.root.parent/'mask_table.npy', mmap_mode='r',allow_pickle=False)
        self.t3, self.role, self.mask_bitorder = True, 'train', 'big'
        self.costs = np.load(assets,allow_pickle=False)['costs']
        self.wait_keep_probability = 1.

    def batch(self, ix):
        b,y = build_batch(self,ix)
        # NumPy 2 preserves float32 scalar division; the frozen human vector
        # loader uses float64 intermediates. Match gate-c serving for teacher
        # rows here, without changing the frozen human loader/loss.
        dtype=np.asarray(self.costs[0]/10).dtype
        hand=self.arrays['hand_ids'][ix,:4]
        delta=self.costs[hand].astype(dtype)/10-self.arrays['global_features'][ix,5,None].astype(dtype)
        b['numeric'][:,:4,0]=torch.from_numpy(delta.astype(np.float32))
        y['intent_valid'].fill_(False)
        # Capacity-one pending commands cannot be inferred from gate-c features.
        y['supervised'] &= torch.from_numpy(self.arrays['teacher_wait_kind'][ix]!=3)
        sizes = self.arrays['root_offsets'][np.asarray(ix)+1]-self.arrays['root_offsets'][ix]
        width = max(1,int(sizes.max()))
        acts=np.full((len(ix),width),2304,np.int64)
        scores=np.zeros((len(ix),width),np.float64)
        valid=np.zeros((len(ix),width),bool)
        for i,idx in enumerate(ix):
            lo,hi=self.arrays['root_offsets'][idx:idx+2]
            if hi>lo:
                acts[i,:hi-lo]=self.arrays['root_actions'][lo:hi]
                scores[i,:hi-lo]=self.arrays['root_scores'][lo:hi]
                valid[i,:hi-lo]=self.arrays['root_valid'][lo:hi]
            else:
                valid[i,0]=True  # Explicit per-poll hard WAIT.
        y.update(root_actions=torch.from_numpy(acts),root_scores=torch.from_numpy(scores),
                 root_valid=torch.from_numpy(valid),
                 outcome=torch.from_numpy(np.asarray(self.arrays['recorded_outcome'][ix])))
        return b,y


def mixed_indices(human_size, teacher_size, batch_size, ratio, seed, step):
    """Ratio is the teacher fraction (T:H = ratio:(1-ratio)), deterministic per step."""
    if not 0<=ratio<=1 or human_size<0 or teacher_size<0 or batch_size<1:
        raise ValueError('invalid mixture')
    nteacher=round(batch_size*ratio)
    rng=np.random.default_rng(np.random.SeedSequence([seed,step]))
    if batch_size-nteacher and not human_size or nteacher and not teacher_size:
        raise ValueError('requested corpus has no rows')
    return (rng.integers(human_size,size=batch_size-nteacher) if batch_size>nteacher else np.empty(0,np.int64),
            rng.integers(teacher_size,size=nteacher) if nteacher else np.empty(0,np.int64))


def teacher_targets(y, temperature, score_zscore=False):
    """Softmax over completed scores; optional per-root population z-score."""
    scores=y['root_scores'].double()
    valid=y['root_valid'].bool()
    if temperature<=0 or not valid.any(-1).all():
        raise ValueError('positive temperature and completed root scores required')
    if score_zscore:
        count=valid.sum(-1,keepdim=True)
        mean=scores.masked_fill(~valid,0).sum(-1,keepdim=True)/count
        centered=(scores-mean).masked_fill(~valid,0)
        std=(centered.square().sum(-1,keepdim=True)/count).sqrt()
        scores=centered/std.clamp_min(1e-12)
    return torch.softmax((scores/temperature).masked_fill(~valid,-torch.inf),-1).float()


def teacher_loss(o,y,temperature=.1,play_weight=4.,value_weight=0.,denominators=None,score_zscore=False):
    if temperature<=0 or play_weight<1 or value_weight<0:
        raise ValueError('invalid teacher loss controls')
    a=y['root_actions'].long()
    a=torch.where(a>=2400,2304,a)
    if ((a<0)|(a>2305)).any(): raise ValueError('invalid root action')
    valid=y['root_valid'].bool()
    if not valid.any(-1).all(): raise ValueError('root has no completed scores')
    q=teacher_targets(y,temperature,score_zscore)
    rows=torch.arange(len(a),device=a.device)[:,None]
    slot=(a//576).clamp(0,3);tile=a%576
    gate=torch.where(a==2304,0,torch.where(a==2305,2,1))
    gp=masked_log_softmax(o['gate'],o['gate_mask'])
    cp=masked_log_softmax(o['card'],o['card_mask'])
    tp=masked_log_softmax(o['tile'],o['tile_mask'])
    if tp.shape[1]!=4: raise ValueError('soft targets require all four conditional tile heads')
    w=y['weight'].float()*y['supervised'].float()
    w=w*torch.where(y['action']<2304,play_weight,1.)
    play=(a<2304).float()
    play_mass=(q*play).sum(-1)
    gate_ce=-(q*gp[rows,gate]).sum(-1)
    card_ce=-(q*play*cp[rows,slot]).sum(-1)
    tile_ce=-(q*play*tp[rows,slot,tile]).sum(-1)
    gate_den=w.sum() if denominators is None else w.new_tensor(denominators[0])
    play_den=(w*play_mass).sum() if denominators is None else w.new_tensor(denominators[1])
    loss=(gate_ce*w).sum()/gate_den.clamp_min(1e-12)
    loss += ((card_ce+tile_ce)*w).sum()/play_den.clamp_min(1e-12)
    if value_weight:
        if 'value' not in o: raise ValueError('value loss needs the optional value head')
        loss += value_weight*((o['value'].float()-y['outcome'].float()).square()*w).sum()/gate_den.clamp_min(1e-12)
    return loss


def mixed_loss(human_output,human_targets,teacher_output=None,teacher_targets=None,ratio=0.,**kw):
    if not 0<=ratio<=1: raise ValueError('teacher ratio outside [0,1]')
    if ratio==0:
        # Exact qualified T11 loss: no extra term or changed reduction.
        return total_loss(loss_parts(human_output,human_targets))['loss']
    teacher=teacher_loss(teacher_output,teacher_targets,**kw)
    if ratio==1: return teacher
    return (1-ratio)*total_loss(loss_parts(human_output,human_targets))['loss']+ratio*teacher


class ValuePolicy(SetPolicy):
    def __init__(self,c,*assets):
        super().__init__(c,*assets)
        self.value_head=nn.Linear(c.width,1)

    def forward(self,b,teacher,tile_rows=None):
        # Optional branch; no temporal state or reconstructed-root dependency.
        o=super().forward(b,teacher,tile_rows)
        o['value']=self.value_head(self.encode(b)[:,0]).squeeze(-1).tanh()
        return o


def initialize(checkpoint,value_head=False):
    ck=torch.load(checkpoint,map_location='cpu',weights_only=True)
    c=ModelConfig(**ck['config']); s=ck['ema']
    model=(ValuePolicy if value_head else SetPolicy)(c,s['descriptors'],s['tile_features'],s['costs'])
    missing,extra=model.load_state_dict(s,strict=not value_head)
    if value_head and (set(missing)!={'value_head.weight','value_head.bias'} or extra):
        raise ValueError('unexpected initialization mismatch')
    return model,c


def screen(teacher_play_recall, fallback_score_delta):
    if not 0<=teacher_play_recall<=1: raise ValueError('invalid play recall')
    reasons=[]
    if teacher_play_recall<.5: reasons.append('teacher play recall below 50% (wait collapse)')
    if fallback_score_delta<=0: reasons.append('fallback does not beat v2 fallback')
    return dict(survives=not reasons, kill_reasons=reasons)
