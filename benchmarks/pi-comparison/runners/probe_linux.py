"""Real pinned Pi imports/discovery under existing Humanize fences; zero inference.

Run only in the project WSL as workbench. This does not declare provider or
background-run acceptance, nor grant a model direct access to this controller.
"""
import argparse
from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path
import subprocess
import socket
import sys
import time

sys.path.insert(0,'/opt/workbench/source')
from p2_candidates import namespace_command,exclusive_json
from hmz.coganchor.fence import Fence,wrapper


def probe(output, resource_script):
    base=Path('/opt/workbench/pi-comparison')
    if os.getuid()==0 or not output.resolve().is_relative_to(base):
        raise ValueError('Non-root new project-private probe path required')
    output.mkdir();canary=output/'controller-canary';canary.write_text('controller only, harmless')
    network_canary=socket.socket();network_canary.bind(('127.0.0.1',0));network_canary.listen()
    node=base/'tools/node-v24.19.0-linux-x64/bin/node'
    sdk=base/'runtime/node_modules/@earendil-works/pi-coding-agent'
    packages={'P1':base/'packages/p1/package','P2':next((base/'packages/p2').glob('neuroforge-skills-*')),
              'P3':base/'packages/p3/package'}
    # Local package peer imports resolve against the exact frozen runtime.
    for group in ('P1','P3'):
        link=packages[group]/'node_modules'
        if not link.exists():link.symlink_to(base/'runtime/node_modules',target_is_directory=True)
    for group in ('P0','P1','P2','P3'):
        folder=output/group;folder.mkdir();(folder/'peer-canary').write_text('peer only, harmless')
        for name in ('work','home','agent','tmp','cache'):(folder/name).mkdir()
    results={}
    for group in ('P0','P1','P2','P3'):
        folder=output/group;work=folder/'work';agent=folder/'agent'
        resource=folder/'resource_probe.mjs';resource.write_bytes(resource_script.read_bytes())
        ext=[str(packages[group]/('extensions' if group=='P1' else 'dist/extension.js'))] if group in ('P1','P3') else []
        skills=[str(packages[group]/'skills')] if group!='P0' else []
        prompts=[str(packages[group]/'prompts')] if group=='P3' else []
        denied=[str(canary),'/opt/workbench/state/codex/auth.json']+[
            str(output/peer/'peer-canary') for peer in ('P0','P1','P2','P3') if peer!=group]
        denied += [str(package/'package.json') if peer!='P2' else str(package/'README.md')
                   for peer,package in packages.items() if peer!=group]
        spec={'profile':group,'work':str(work),'agent_dir':str(agent),'sdk_root':str(sdk),
              'extensions':ext,'skills':skills,'prompts':prompts,'denied':denied,
              'readonly':str(sdk/'package.json'),'parent_namespace':os.readlink('/proc/self/ns/pid'),
              'network_canary_port':network_canary.getsockname()[1]}
        path=folder/'spec.json';exclusive_json(path,spec)
        fence=Fence.of(local='all',user='none',system='none',online=False,
                       workdir=work,home=folder/'home',
                       read=(base/'runtime',base/'tools/node-v24.19.0-linux-x64',path,resource,
                             *([packages[group]] if group in packages else [])),
                       write=(folder/'home',agent,folder/'cache'))
        fence=replace(fence,tmp=str(folder/'tmp'))
        env={'PATH':str(node.parent)+':/usr/bin:/bin','LANG':'C.UTF-8','HOME':str(folder/'home'),
             'PI_CODING_AGENT_DIR':str(agent),'PI_OFFLINE':'1','TMPDIR':str(folder/'tmp'),
             'XDG_CACHE_HOME':str(folder/'cache'),'HUMANIZE_SENTRY':'off'}
        started=time.perf_counter()
        child=subprocess.run(namespace_command([*wrapper(fence),str(node),str(resource),str(path)]),
                             cwd=work,env=env,capture_output=True,timeout=60)
        (folder/'stdout.private.log').write_bytes(child.stdout);(folder/'stderr.private.log').write_bytes(child.stderr)
        if child.returncode:
            results[group]={'status':'FAIL','exit':child.returncode,'elapsed_seconds':time.perf_counter()-started,
                            'error_log_sha256':hashlib.sha256(child.stderr).hexdigest()};continue
        row=json.loads(child.stdout);expected=len(denied)
        isolated=(row['uid']!=0 and row['cap_eff']=='0000000000000000' and row['private_pid_namespace']
                  and row['denied']==['DENIED']*expected and row['network_canary_denied'] and row['runtime_readonly'] and row['own_write']
                  and row['context_files']==0 and not row['extension_errors'])
        expected_resources=(not row['skills'] and not row['extensions']) if group=='P0' else bool(row['skills'])
        if group in ('P1','P3'):expected_resources=expected_resources and bool(row['extensions'])
        row.update(status='PASS' if isolated and expected_resources else 'FAIL',elapsed_seconds=time.perf_counter()-started)
        exclusive_json(folder/'receipt.json',row);results[group]=row
    network_canary.close()
    proof={'status':'PASS_RESOURCE_AND_OS_CONTROLS' if all(r['status']=='PASS' for r in results.values()) else 'FAIL',
           'results':results,'provider_calls':0,'live_tool_calls':0,'gate_p0':'PENDING_REAL_PROVIDER_TOOL_PROBE',
           'api_cash_cost':0,'source_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (Path(__file__),resource_script)}}
    exclusive_json(output/'receipt.json',proof);return proof


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--resource-script',type=Path,required=True);args=parser.parse_args()
    row=probe(args.output,args.resource_script)
    print(json.dumps({'status':row['status'],'profiles':{k:{'status':v['status'],'skills':len(v.get('skills',[])),
          'extensions':len(v.get('extensions',[])),'error_log_sha256':v.get('error_log_sha256')} for k,v in row['results'].items()},
          'provider_calls':0,'gate_p0':row['gate_p0']}))
    raise SystemExit(0 if row['status']=='PASS_RESOURCE_AND_OS_CONTROLS' else 1)
