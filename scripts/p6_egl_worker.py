"""Execute the public EGL entry and independent signed optimizer probes."""
import importlib.util
import json
from pathlib import Path
import runpy
import sys
import numpy as np
import torch

def main():
    source,inputs,output=map(Path,sys.argv[1:4]);sys.path.insert(0,str(source))
    spec=importlib.util.spec_from_file_location('candidate_optimizer',source/'candidate_optimizer.py')
    optimizer=importlib.util.module_from_spec(spec);sys.modules['candidate_optimizer']=optimizer;spec.loader.exec_module(optimizer)
    probes=json.loads((inputs/'probes.json').read_text());actual={}
    with np.load(inputs/'probes.npz',allow_pickle=False) as data:
        for index,row in enumerate(probes):
            weight=torch.from_numpy(data['w'+str(index)].copy());gradient=torch.from_numpy(data['g'+str(index)].copy())
            expected=weight*torch.exp(-row['lr']*torch.sign(weight)*gradient)
            value=optimizer.eg_step(weight,gradient,row['lr'])
            if not isinstance(value,torch.Tensor) or value.device.type!='cpu' or value.dtype!=weight.dtype or value.shape!=weight.shape:
                raise ValueError('eg_step must return a CPU tensor of the original shape and dtype')
            tolerance=2e-6 if weight.dtype==torch.float32 else 1e-12
            if not torch.allclose(value,expected,rtol=tolerance,atol=tolerance):
                raise ValueError('Signed/zero optimizer probe failed before training')
            actual['p'+str(index)]=value.detach().numpy()
    np.savez(output/'optimizer_actual.npz',**actual)
    calls=[0];original=optimizer.eg_step
    def counted(*args,**kwargs):calls[0]+=1;return original(*args,**kwargs)
    optimizer.eg_step=counted
    sys.argv=[str(source/'candidate.py'),'--out',str(output/'result')]
    runpy.run_path(str(source/'candidate.py'),run_name='__main__')
    if calls[0]<5400:raise ValueError('The submitted EG interface was not used for all nine 600-update training runs')
    (output/'optimizer_usage.json').write_text(json.dumps({'training_eg_step_calls':calls[0],'probe_cases':len(probes)}))

if __name__=='__main__':main()
