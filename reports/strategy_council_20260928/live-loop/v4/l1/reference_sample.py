"""Historical sampler for prefetch RNG/tensor regression; pixels supplied by verified raw cache."""
import cv2
import numpy as np
import torch
from clasher.vision.l1_v4 import prepare_pixels as pixels

def original_sample(self, index):
        ep,end=self.examples[index];indices=self.subset(ep,end);images=self.pixel_cache.get(ep,indices,raw=True)
        arenas=[];hud=None
        quality=self.rng.randrange(50,96) if self.augment and self.rng.random()<.3 else None
        for image in images:
            if quality is not None:
                ok,encoded=cv2.imencode('.jpg',image,[cv2.IMWRITE_JPEG_QUALITY,quality])
                if not ok:raise RuntimeError('Augmentation encoding failed')
                image=cv2.imdecode(encoded,cv2.IMREAD_COLOR)
            arena,hud=pixels(image);arenas.append(arena)
        frames=self.frames[ep];now=frames[end]['produced_at']
        ages=np.asarray([0.]*(16-len(indices))+[(now-frames[i]['produced_at'])*1000 for i in indices],np.float32)
        valid=np.asarray([False]*(16-len(indices))+[True]*len(indices))
        arenas=[np.zeros_like(arenas[-1])]*(16-len(arenas))+arenas
        x=np.stack(arenas).transpose(0,3,1,2).astype(np.float32)/255
        h=hud.transpose(2,0,1).astype(np.float32)/255
        target=self.targets(ep,end)
        if self.augment:
            gain=self.rng.uniform(.85,1.15);gamma=self.rng.uniform(.9,1.1)
            x=np.clip(x*gain,0,1)**gamma;h=np.clip(h*gain,0,1)**gamma
            if self.rng.random()<.5:
                x=x[:,:,:,::-1].copy()
                for key in ('event','age','event_mask','origin','origin_mask','body','body_valid','box','hp','hp_mask','body_mask'):
                    target[key]=target[key][...,::-1].copy()
                target['box'][0]=1-target['box'][0]
            if self.rng.random()<.5:
                scale=self.rng.uniform(.98,1.02);dx=self.rng.uniform(-4,4);dy=self.rng.uniform(-4,4)
                matrix=np.asarray([[scale,0,(1-scale)*224+dx],[0,scale,(1-scale)*416+dy]],np.float32)
                x=np.stack([cv2.warpAffine(frame.transpose(1,2,0),matrix,(448,832)).transpose(2,0,1) for frame in x])
                # Convert this pixel affine into half-tile coordinates with the frozen calibration.
                tile_to_crop=np.vstack((self.geo.matrix,[0,0,1])).copy()
                tile_to_crop=np.diag([448/540,832/800,1])@np.asarray([[1,0,0],[0,1,-200],[0,0,1]])@tile_to_crop
                transform=np.linalg.inv(tile_to_crop)@np.vstack((matrix,[0,0,1]))@tile_to_crop
                grid=np.diag([2,2,1])@transform@np.diag([.5,.5,1])
                for key in ('event','age','event_mask','origin','origin_mask','body','body_valid','box','hp','hp_mask','body_mask'):
                    target[key]=np.stack([cv2.warpAffine(channel,grid[:2].astype(np.float32),(36,64),flags=cv2.INTER_NEAREST) for channel in target[key]])
                target['box'][0]=target['box'][0]*scale+(1-scale)/2+dx/448
                target['box'][1]=target['box'][1]*scale+(1-scale)/2+dy/832
                target['box'][2:]*=scale
            jitter=np.asarray([self.rng.uniform(-10,10) if v and a else 0 for v,a in zip(valid,ages)],np.float32)
            ages=np.maximum(0,ages+jitter)
        target={k:torch.as_tensor(v) for k,v in target.items()}
        return dict(arena=torch.from_numpy(x),hud=torch.from_numpy(h),ages=torch.from_numpy(ages),valid=torch.from_numpy(valid),
                    births=torch.zeros(2,64,36),target=target)
