"""Native shallow-history and resume boundaries; all controls make zero model calls."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))


@unittest.skipUnless(os.name=='posix','Production fences and shallow export execute in Linux')
class NativeRuntimeTests(unittest.TestCase):
    def setUp(self):
        import p6_runtime_linux as runtime
        self.r=runtime
        folder=ROOT/'.local-workbench/test-tmp';folder.mkdir(parents=True,exist_ok=True)
        self.tmp=tempfile.TemporaryDirectory(dir=folder);self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)

    def git(self,root,*args):
        return subprocess.check_output(['git','-c','core.hooksPath=/dev/null',*args],cwd=root,stderr=subprocess.PIPE).decode().strip()

    def test_fenced_shallow_bundle_restores_independent_head_and_partial_files(self):
        origin=self.root/'origin';origin.mkdir();self.git(origin,'init','-q')
        self.git(origin,'config','user.name','Native Test');self.git(origin,'config','user.email','native@example.invalid')
        (origin/'module.py').write_text('value = 1\n');self.git(origin,'add','.');self.git(origin,'commit','-qm','parent')
        (origin/'module.py').write_text('value = 2\n');self.git(origin,'commit','-am','frozen base','-q')
        base=self.root/'base';self.git(origin,'clone','--depth','1','file://'+str(origin),str(base))
        source=self.root/'candidate';source.mkdir();(source/'home').mkdir()
        with patch.dict(self.r.ACTIVE,{'task':{'base':str(base)}}):
            self.r.clone(base,source/'code','run/control-source',trusted=True)
            (source/'code/module.py').write_text('value = 3\n');self.git(source/'code','commit','-am','real candidate','-q')
            head=self.git(source/'code','rev-parse','HEAD')
            (source/'code/module.py').write_text('value = 4\n');(source/'code/regression.py').write_text('assert True\n')
            target=self.root/'relay';target.mkdir();(target/'home').mkdir()
            self.r.clone(source/'code',target/'code','run/control-relay')
        self.assertEqual(self.git(target/'code','rev-parse','HEAD'),head)
        self.assertEqual((target/'code/module.py').read_text(),'value = 4\n')
        self.assertTrue((target/'code/regression.py').is_file())
        self.assertTrue((target/'code/.git/shallow').is_file())
        self.assertFalse((target/'code/.git/objects/info/alternates').exists())
        self.assertEqual(self.git(target/'code','remote'),'')

    def test_continuation_refuses_changed_contract_and_cycles(self):
        name='p6-execute-BIP-black-2-20261011T010101Z';root=self.root/'private/runs'/name
        (root/'control').mkdir(parents=True);contract={'manifest':{'manifest_sha256':'a'*64},'public_prompt_sha256':self.r.digest(b'frozen')}
        (root/'control/run-contract.json').write_text(json.dumps(contract))
        task={'id':'BIP-black-2','prompt':'frozen'}
        with patch.object(self.r,'BASE',self.root),patch.dict(self.r.ACTIVE,{'payload':{'manifest':{'manifest_sha256':'b'*64}}}):
            with self.assertRaisesRegex(ValueError,'changed frozen'):self.r.prior_chain(name,task)
        (root/'control/reuse.json').write_text(json.dumps({'source_run':name}))
        with patch.object(self.r,'BASE',self.root),patch.dict(self.r.ACTIVE,{'payload':{'manifest':{'manifest_sha256':'a'*64}}}):
            with self.assertRaisesRegex(ValueError,'cycle'):self.r.prior_chain(name,task)

    def test_inner_readonly_compatibility_mode_cannot_accept_write_permissions(self):
        from hmz.flows import Permission
        from p1_drivers import MeteredDriver
        with self.assertRaises(RuntimeError):
            MeteredDriver('verifier=codex/gpt-6.1-sol:low',None,'offline',[],
                          permission=Permission(local='all',user='none',system='none',online='none'),
                          fence_transform=lambda f:f,external_readonly=True)


if __name__=='__main__':unittest.main()
