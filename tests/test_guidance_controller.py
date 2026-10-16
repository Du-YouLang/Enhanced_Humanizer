"""Exercise the real stage controller with synthetic model outputs, no providers."""
from contextlib import nullcontext
import importlib.util
import json
from pathlib import Path
import shutil
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'scripts'),str(ROOT/'benchmarks/pi-comparison/runners')]


class GuidanceControllerTests(unittest.TestCase):
    def test_shared_checkpoint_hidden_barrier_and_completed_recovery(self):
        shared=SimpleNamespace(ACTIVE={})
        fake_main=SimpleNamespace(shared=shared)
        spec=importlib.util.spec_from_file_location('guidance_stage_control',ROOT/'scripts/p6_guidance_linux.py')
        module=importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules,{'p6_main_runtime_linux':fake_main,'fcntl':SimpleNamespace()}):spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);task={'id':'BIP-black-1','prompt':'Fix synthetic boundary','base_commit':'base',
                'fixture_context':nullcontext(None)}
            calls=[];starts=[];hidden=[]
            def activate(*args,**kwargs):shared.ACTIVE={'workers':{},'root':args[0],'task':task}
            def job(name,backend,role,source=None,view=None,prompt=None,**kwargs):
                dest=shared.ACTIVE['root']/name;dest.mkdir();work=dest/'code';work.mkdir()
                content=(Path(source)/'program').read_text() if source else 'baseline'
                (work/'program').write_text(content)
                if name.endswith('-ds') and name!='initial-ds':starts.append(content)
                (dest/'input.json').write_text(json.dumps(view or {}))
                return {'root':str(dest),'work':str(work),'role':role,'backend':backend,
                    'input_file':str(dest/'input.json'),'denied_paths':[]},{}
            def program(work,base):return (Path(work)/'program').read_text(),'complete-source'
            def execute(s):
                d=s['descriptor'];name=Path(d['root']).name;calls.append(name)
                if d['role']=='builder':(Path(d['work'])/'program').write_text('first' if name=='initial-ds' else name)
                w={'status':'COMPLETED','work':d['work'],'scope':d['scope'],'wall_seconds':1,
                    'answer':{'guidance':{'diagnosis':'Boundary issue','observations':[{'finding':'Issue','evidence_kind':'code','reference':'program:1'}],
                    'hypotheses':[],'next_actions':['Check boundary'],'public_verification':['Run public check'],'limitations':[]}}}
                (Path(d['root'])/'controller-outcome.json').write_text(json.dumps(w))
                return w
            def candidate(name,w):
                p,source=program(w['work'],'base')
                return {'base_commit':'base','head_commit':p,'patch':p,'source':source,'root':str(Path(w['work']).parent),
                        'verdict':'PASS','test_report':{'elapsed_seconds':.1}}
            def tester(work,private):
                self.assertTrue(private)
                stages=shared.ACTIVE['root']/'control/stages'
                self.assertTrue((stages/'all-branches-frozen.completed.json').exists())
                self.assertTrue((stages/'code-tests-ds-freeze.completed.json').exists())
                self.assertTrue((stages/'code-tests-trace-ds-freeze.completed.json').exists())
                hidden.append(str(work));return {'verdict':'PASS','elapsed_seconds':1}
            shared.program_evidence=program;shared.candidate=candidate;shared.metrics=lambda *_:{}
            fake_main.job=job
            payload={'run_id':'guidance-20261016T120000Z'}
            with patch.object(module,'make_task',return_value=({},task,tester)),patch.object(module,'activate',side_effect=activate),\
                 patch.object(module,'execute',side_effect=execute),patch.object(module,'tool_trace',return_value={'truncated':False,'records':[]}):
                first=module.task_run(root,payload,task['id'])
                self.assertEqual(starts,['first','first'])
                self.assertEqual(len(calls),5);self.assertEqual(len(hidden),3)
                self.assertEqual([r['outcome'] for r in first['rows']],['PASS']*3)
                second=module.task_run(root,payload,task['id'])
                self.assertEqual(len(calls),5);self.assertEqual(len(hidden),3)
                self.assertEqual(first['barrier_sha256'],second['barrier_sha256'])


if __name__=='__main__':unittest.main()
