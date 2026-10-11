"""Offline installation integrity and preservation; no paid/remote operations."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import zipfile
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from workbench.delivery import build, install, verify, safe_name
from workbench.memory import Memory
from workbench.execution import Execution


class DeliveryTests(unittest.TestCase):
    def setUp(self):
        base=ROOT/'.local-workbench/test-tmp';base.mkdir(parents=True,exist_ok=True)
        self.temp=tempfile.TemporaryDirectory(dir=base);self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.repo=self.root/'repo';self.repo.mkdir()
        self.git('init','-q');self.git('config','user.name','Delivery Test')
        self.git('config','user.email','delivery@example.invalid');self.git('config','core.autocrlf','false')
        (self.repo/'.gitignore').write_text('.local-workbench/\n')
        (self.repo/'README.md').write_text('TEST ONLY: local delivery round trip\n')
        self.git('add','.');self.git('commit','-q','-m','offline fixture')

    def git(self,*args):
        return subprocess.check_output(['git','-c','core.hooksPath=',*args],cwd=self.repo,stderr=subprocess.PIPE)

    def package(self):
        return build(self.repo,self.root/'package')

    def test_fresh_roundtrip_has_identical_commit_no_remote_no_private_state_and_no_overwrite(self):
        r=self.package();m=verify(r['archive'],r['archive_sha256'])
        target=self.root/'installed';result=install(r['archive'],r['archive_sha256'],target)
        self.assertEqual(result['commit'],r['commit']);self.assertFalse(result['credentials_copied'])
        self.assertEqual((target/'README.md').read_bytes(),(self.repo/'README.md').read_bytes())
        self.assertEqual(subprocess.check_output(['git','remote'],cwd=target),b'')
        with self.assertRaises(FileExistsError):install(r['archive'],r['archive_sha256'],target)
        self.assertEqual(len(m['files']),3)

    def test_changed_bytes_and_unsigned_inventory_edits_fail_before_target_creation(self):
        r=self.package();target=self.root/'bad-install'
        with self.assertRaises(ValueError):install(r['archive'],'a'*64,target)
        self.assertFalse(target.exists())
        bad=self.root/'tampered.zip'
        with zipfile.ZipFile(r['archive']) as src,zipfile.ZipFile(bad,'w') as dst:
            for n in src.namelist():dst.writestr(n,b'changed' if n=='payload/README.md' else src.read(n))
        with self.assertRaises(ValueError):install(bad,hashlib.sha256(bad.read_bytes()).hexdigest(),target)
        self.assertFalse(target.exists())

    def test_paths_symlinks_duplicates_case_collisions_and_unlisted_members_are_rejected(self):
        for name in ('../escape','/abs','D:/escape','a\\b','a/.git/config','NUL.txt','a/name.','a/name ', './x','a?.txt','CONIN$'):
            with self.subTest(name=name),self.assertRaises(ValueError):safe_name(name)
        r=self.package()
        for name in ('payload/README.MD','payload/extra.txt','payload/../escape'):
            bad=self.root/('bad-'+str(len(list(self.root.glob('bad-*'))))+'.zip')
            with zipfile.ZipFile(r['archive']) as src,zipfile.ZipFile(bad,'w') as dst:
                for n in src.namelist():dst.writestr(n,src.read(n))
                dst.writestr(name,b'extra')
            with self.assertRaises(ValueError):verify(bad,hashlib.sha256(bad.read_bytes()).hexdigest())
        bad=self.root/'symlink.zip'
        with zipfile.ZipFile(r['archive']) as src,zipfile.ZipFile(bad,'w') as dst:
            for n in src.namelist():
                i=zipfile.ZipInfo(n);i.external_attr=(0o120777<<16) if n=='payload/README.md' else (0o100644<<16)
                dst.writestr(i,src.read(n))
        with self.assertRaises(ValueError):verify(bad,hashlib.sha256(bad.read_bytes()).hexdigest())

    def test_dirty_or_private_source_and_outside_installation_are_rejected(self):
        (self.repo/'README.md').write_text('uncommitted change')
        with self.assertRaises(ValueError):self.package()
        self.git('checkout','--','README.md')
        (self.repo/'auth.json').write_text('TEST FIXTURE NO CREDENTIAL')
        self.git('add','auth.json');self.git('commit','-q','-m','privacy fixture')
        with self.assertRaises(ValueError):build(self.repo,self.root/'private-package')
        self.git('rm','auth.json');self.git('commit','-qm','remove private fixture')
        with self.assertRaises(ValueError):build(self.repo,self.root/'unsafe-history-package')
        with self.assertRaises(ValueError):install('irrelevant','a'*64,ROOT.parent/'not-authorized')

    def test_installed_preview_cannot_start_paid_models(self):
        (self.root/'.local-workbench/delivery').mkdir(parents=True)
        (self.root/'.local-workbench/delivery/install-receipt.json').write_text('{}')
        memory=Memory(self.root/'memory')
        execution=Execution(memory)
        with patch('workbench.execution.ROOT',self.root):
            with self.assertRaisesRegex(PermissionError,'Installed preview'):
                execution.start({})
        self.assertEqual(memory.list('run'),[])


if __name__=='__main__':unittest.main()
