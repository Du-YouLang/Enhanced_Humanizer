"""Trusted data/weight replay only. Never import any candidate Python module."""
import gc
import json
from pathlib import Path
import sys
import numpy as np
import torch

def main():
    _,inputs,output=map(Path,sys.argv[1:4]);torch.set_num_threads(8);torch.set_num_interop_threads(1)
    rows=[]
    for n in (200,2000,20000):
        for seed in (1,2,3):
            np.random.seed(seed)
            for split,count in (('train',10000),('val',1000),('test',1000)):
                relevant=np.random.binomial(1,.5,size=(count,100));irrelevant=np.random.binomial(1,.5,size=(count,n-100))
                x=np.concatenate((relevant,irrelevant),axis=1).astype(np.float32)
                noise=np.random.choice([-1,0,1],size=count,p=(.05,.9,.05)) if split=='train' else 0
                y=(relevant.sum(axis=1)+noise>=50).astype(np.int64)
                del relevant,irrelevant,noise
                if split!='test':del x,y;gc.collect()
            for algorithm in ('eg','gd'):
                weights=np.load(inputs/f'N{n}_seed{seed}_{algorithm}.npy',allow_pickle=False)
                correct=loss=0
                with torch.no_grad():
                    for start in (0,500):
                        logits=torch.nn.functional.linear(torch.from_numpy(x[start:start+500]),torch.from_numpy(weights[None,:])).squeeze(-1)-50
                        truth=torch.from_numpy(y[start:start+500]);correct+=((logits>=0).long()==truth).sum().item()
                        loss+=torch.nn.functional.binary_cross_entropy_with_logits(logits,truth.float(),reduction='sum').item()
                rows.append({'n':n,'seed':seed,'algorithm':algorithm,'test_accuracy_pct':correct/10.,'test_loss':loss/1000.})
            del x,y;gc.collect()
    (output/'replay.json').write_text(json.dumps(rows))

if __name__=='__main__':main()
