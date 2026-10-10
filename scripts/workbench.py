"""Project-local workbench CLI. Imports/recovery/exports make zero model requests."""

import argparse
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from workbench.memory import Memory
from workbench.gitops import GitOps,restore
from workbench.importer import import_p3


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('mode',choices=['import-p3','verify','rebuild','list','fork','revert','handoff','export','restore','serve'])
    p.add_argument('--state',default=str(ROOT/'.local-workbench/workbench'))
    p.add_argument('--node');p.add_argument('--reason',default='Human requested a new route')
    p.add_argument('--sha');p.add_argument('--archive');p.add_argument('--destination');p.add_argument('--port',type=int,default=8765)
    a=p.parse_args()
    if a.mode=='restore':memory,repo=restore(a.archive,a.destination);value={'state':str(memory.root),'repository':str(repo),'audit':memory.verify()}
    else:
        memory=Memory(a.state);ops=GitOps(memory)
        if a.mode=='import-p3':value=import_p3(memory)
        elif a.mode=='verify':value=memory.verify()
        elif a.mode=='rebuild':value={'events_rebuilt':memory.rebuild(),'audit':memory.verify()}
        elif a.mode=='list':value={'tasks':memory.list('task'),'attempts':memory.list('attempt')}
        elif a.mode=='fork':value=ops.fork(a.node,a.reason)
        elif a.mode=='revert':value=ops.revert(a.node,a.sha,a.reason)
        elif a.mode=='handoff':value=memory.handoff(a.node,'builder',a.reason)
        elif a.mode=='export':value=ops.export()
        elif a.mode=='serve':
            from workbench.server import serve
            serve(memory,a.port);return
    print(json.dumps(value,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
