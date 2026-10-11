"""Trusted GPU measurement worker. Receives inputs, never private expected answers."""
import importlib.util
import json
from pathlib import Path
import sys
import time

import cupy as cp
import numpy as np


def main():
    source, inputs, output = map(Path, sys.argv[1:4])
    cases = json.loads((inputs/'cases.json').read_text())
    launches = [0]
    raw_kernel, download = cp.RawKernel, cp.asnumpy
    class TrackedKernel:
        def __init__(self,*args,**kwargs): self.kernel=raw_kernel(*args,**kwargs)
        def __call__(self,*args,**kwargs):
            launches[0]+=1
            return self.kernel(*args,**kwargs)
        def __getattr__(self,name): return getattr(self.kernel,name)
    cp.RawKernel=TrackedKernel
    spec=importlib.util.spec_from_file_location('submission',source/'gc_cupy.py')
    module=importlib.util.module_from_spec(spec);sys.path.insert(0,str(source));spec.loader.exec_module(module)
    def call(x,pairs,windows,kwargs):
        def refuse(*args,**kwargs): raise AssertionError('CPU download inside regression is forbidden')
        previous=cp.asnumpy;cp.asnumpy=refuse
        try:return module.compute_gc(x,pairs,windows,**kwargs)
        finally:cp.asnumpy=previous
    arrays={};measurements=[]
    def checked(name,x,pairs,windows,kwargs):
        before=download(x);p0=pairs.copy();w0=windows.copy()
        tick=time.perf_counter();actual=call(x,pairs,windows,kwargs);cp.cuda.Stream.null.synchronize()
        elapsed=time.perf_counter()-tick
        if not isinstance(actual,cp.ndarray) or actual.dtype!=cp.float64 or actual.device.id!=x.device.id:
            raise AssertionError('Output must be CuPy float64 on the input GPU')
        np.testing.assert_array_equal(download(x),before)
        np.testing.assert_array_equal(pairs,p0);np.testing.assert_array_equal(windows,w0)
        arrays[name]=download(actual);measurements.append({'name':name,'wall_seconds':elapsed})
    performance=None
    for index,row in enumerate(cases):
        with np.load(inputs/row['file'],allow_pickle=False) as data:
            x,pairs,windows=data['signals'],data['pairs'],data['windows']
            kwargs={'lag':int(data['lag']),'ridge':float(data['ridge']),'eps':float(data['eps'])}
        checked('case_'+str(index),cp.asarray(x),pairs,windows,kwargs)
        if row['noncontiguous']:
            padded=cp.empty((x.shape[0],x.shape[1],x.shape[2]*2),cp.float32)
            padded[:,:,::2]=cp.asarray(x);padded[:,:,1::2]=7
            checked('noncontiguous',padded[:,:,::2],pairs[::-1].copy(),windows[::-1].copy(),kwargs)
        if row['performance']: performance=(x,pairs,windows,kwargs)
    base=cp.arange(40,dtype=cp.float32).reshape(1,2,20)
    pair=np.asarray([[0,1]],np.int16);win=np.asarray([[0,20]],np.int32)
    invalid=[]
    for value in (np.nan,np.inf):
        bad=base.copy();bad[0,0,0]=value;invalid.append((bad,pair,win,{}))
    invalid += [(base.astype(cp.float64),pair,win,{}),(base[0],pair,win,{}),
                (base,np.asarray([[0,2]],np.int16),win,{}),(base,np.asarray([[0,0]],np.int16),win,{}),
                (base,pair,np.asarray([[-1,20]],np.int32),{}),(base,pair,np.asarray([[0,21]],np.int32),{}),
                (base,pair,np.asarray([[4,4]],np.int32),{}),(base,pair,win,{'lag':0}),
                (base,pair,win,{'lag':9}),(base,pair,win,{'ridge':0}),(base,pair,win,{'eps':np.nan})]
    for args in invalid:
        try:call(*args)
        except ValueError:pass
        else:raise AssertionError('Invalid input must raise ValueError')
    if launches[0]==0:raise AssertionError('No RawKernel execution observed')
    x,pairs,windows,kwargs=performance;device_x=cp.asarray(x)
    for _ in range(3):call(device_x,pairs,windows,kwargs)
    cp.cuda.Stream.null.synchronize()
    cuda_ms=[];resident_ms=[];transfer_ms=[]
    for repeat in range(5):
        start,end=cp.cuda.Event(),cp.cuda.Event();tick=time.perf_counter();start.record()
        actual=call(device_x,pairs,windows,kwargs);end.record();end.synchronize()
        resident_ms.append((time.perf_counter()-tick)*1000);cuda_ms.append(float(cp.cuda.get_elapsed_time(start,end)))
        arrays['repeat_'+str(repeat)]=download(actual)
        tick=time.perf_counter();actual=call(cp.asarray(x),pairs,windows,kwargs)
        cp.cuda.Stream.null.synchronize();arrays['transfer_'+str(repeat)]=download(actual)
        transfer_ms.append((time.perf_counter()-tick)*1000)
    np.savez(output/'actual.npz',**arrays)
    report={'cupy':cp.__version__,'numpy':np.__version__,'rawkernel_launches':launches[0],
            'invalid_cases':len(invalid),'measurements':measurements,'warmups':3,
            'gpu_cuda_event_ms':cuda_ms,'gpu_resident_wall_ms':resident_ms,
            'gpu_transfer_inclusive_ms':transfer_ms,'cache_state':'FRESH_PRIVATE_COLD_COMPILE_CACHE',
            'integrity_note':'Worker type/immutability/launch guards are advisory against deliberate Python monkeypatching; parent grades every numeric output independently.'}
    (output/'measurements.json').write_text(json.dumps(report,indent=2))


if __name__=='__main__':main()
