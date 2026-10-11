"""Owner-reviewed product PR delivery. Never merges, releases or changes access."""
import json
import os
from pathlib import Path
import re
import subprocess
import sys

from .memory import ROOT, canonical, local, safe_text, sha
from .gitops import git

sys.path.insert(0, str(ROOT/'scripts'))
from check_repository import private_path

COMMIT = re.compile(r'[0-9a-f]{40}')


class GitHubCLI:
    def __init__(self, repository, scan_binary=None):
        self.repository = Path(repository)
        self.scan_binary = scan_binary or ROOT/'.local-workbench/tools/gitleaks/8.30.1/gitleaks.exe'
        self.env = dict(os.environ)
        self.env.update(GIT_TERMINAL_PROMPT='0', GH_PROMPT_DISABLED='1')
        # Reuse the owner's configured local proxy for this subprocess only.
        if os.name == 'nt' and not self.env.get('HTTPS_PROXY'):
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r'Software\Microsoft\Windows\CurrentVersion\Internet Settings') as key:
                try:
                    enabled = winreg.QueryValueEx(key,'ProxyEnable')[0]
                    proxy = winreg.QueryValueEx(key,'ProxyServer')[0]
                except FileNotFoundError:
                    enabled, proxy = False, ''
            if enabled and re.fullmatch(r'127\.0\.0\.1:[0-9]{1,5}',proxy):
                self.env.update(HTTPS_PROXY='http://'+proxy, HTTP_PROXY='http://'+proxy)

    def command(self, argv, *, timeout=60):
        result = subprocess.run(argv,cwd=self.repository,env=self.env,capture_output=True,timeout=timeout)
        if result.returncode:
            # CLI diagnostics can include auth or untrusted provider bodies.
            raise RuntimeError('Delivery command failed; no automatic replay: '+Path(argv[0]).name)
        return result.stdout

    def identity(self): return json.loads(self.command(['gh','api','user']))['login']

    def metadata(self, repository, base):
        info = json.loads(self.command(['gh','api','repos/'+repository]))
        head = json.loads(self.command(['gh','api',f'repos/{repository}/commits/{base}']))['sha']
        return {'repository':info['full_name'],'private':info['private'],
                'can_push':info.get('permissions',{}).get('push',False),'base_head_sha':head}

    def fetch(self, repository, base):
        self.command(['git','-c','core.hooksPath=/dev/null','-c','core.fsmonitor=false',
                      '-c','credential.helper=','-c','credential.helper=!gh auth git-credential',
                      'fetch','--no-tags','https://github.com/'+repository+'.git','refs/heads/'+base])
        return git(self.repository,'rev-parse','FETCH_HEAD')

    def scan(self, base, head):
        if not Path(self.scan_binary).is_file(): raise RuntimeError('Pinned Gitleaks is required before upload')
        self.command([str(self.scan_binary),'git',str(self.repository),'--redact','--no-banner',
                      '--log-opts='+base+'..'+head,'--exit-code','1'],timeout=60)
        return {'scanner':'Gitleaks 8.30.1','range':base+'..'+head,'verdict':'PASS'}

    def create(self, target, head, branch, title, body_file):
        repository = target['repository']
        if self.identity() != repository.split('/')[0] or self.metadata(repository,target['base'])['base_head_sha'] != target['base_head_sha']:
            raise RuntimeError('Account or remote base changed after human review')
        # A one-use nonce names a new branch. Existing refs are never overwritten.
        existing = subprocess.run(['gh','api',f'repos/{repository}/git/ref/heads/{branch}'],
            cwd=self.repository,env=self.env,capture_output=True,timeout=30)
        if existing.returncode == 0 or b'404' not in existing.stderr:
            raise RuntimeError('Unable to verify a new remote product branch')
        self.command(['git','-c','core.fsmonitor=false','-c','credential.helper=',
                      '-c','credential.helper=!gh auth git-credential','push',
                      'https://github.com/'+repository+'.git',head+':refs/heads/'+branch],timeout=120)
        if self.metadata(repository,target['base'])['base_head_sha'] != target['base_head_sha']:
            raise RuntimeError('Remote base advanced after branch upload; prepare a fresh review')
        url = self.command(['gh','pr','create','--repo',repository,'--base',target['base'],
                            '--head',branch,'--draft','--title',title,'--body-file',str(body_file)],timeout=60).decode().strip()
        if not re.fullmatch(r'https://github\.com/'+re.escape(repository)+r'/pull/[0-9]+',url):
            raise RuntimeError('PR outcome is uncertain; reconcile the saved remote branch before any retry')
        return url


class Publisher:
    def __init__(self, memory, ops, reviews, approval_path, backend=None):
        self.memory, self.ops, self.reviews = memory, ops, reviews
        self.approval_path = local(approval_path,memory.boundary)
        self.backend = backend or GitHubCLI(ops.repository)

    def approval(self):
        value = json.loads(self.approval_path.read_text(encoding='utf-8'))
        if (value.get('approved_by') != 'human_user' or not value.get('authorization_reference')
                or value.get('visibility') not in ('PUBLIC','PRIVATE')
                or 'refs/heads/codex/' not in value.get('allowed_ref_prefixes',[])
                or not re.fullmatch(r'[A-Za-z0-9_.-]+',value.get('owner',''))
                or not re.fullmatch(r'[A-Za-z0-9_.-]+',value.get('repository',''))):
            raise PermissionError('A specifically authorized repository, visibility and branch namespace are required')
        return value

    def target(self):
        value = self.approval()
        return {'repository':value['owner']+'/'+value['repository'],'base':'main'}

    def privacy(self, base, head):
        commits = git(self.ops.repository,'rev-list',base+'..'+head).splitlines()
        if not commits or len(commits)>100: raise ValueError('A bounded nonempty change is required')
        inventories = []
        for commit in commits:
            entries = git(self.ops.repository,'ls-tree','-rlz',commit).split('\0')
            inventory = {}
            total = 0
            for entry in filter(None,entries):
                metadata,name = entry.split('\t',1)
                mode,kind,oid,size = metadata.split()
                if (mode not in ('100644','100755') or kind != 'blob' or private_path(name)
                        or Path(name).suffix.lower() in {'.csv','.tsv','.npz','.npy','.parquet','.h5','.hdf5','.zip','.tar','.gz'}):
                    raise ValueError('Private paths, symlinks and submodules cannot be uploaded')
                if name.startswith(('-', '/')) or any(p in ('..','.git') for p in name.split('/')):
                    raise ValueError('Unsafe repository path')
                size = int(size); total += size
                if size>1_000_000 or total>10_000_000: raise ValueError('Public tree exceeds review limits')
                raw = subprocess.check_output(['git','cat-file','blob',oid],cwd=self.ops.repository,timeout=20)
                try: text = raw.decode('utf-8-sig')
                except UnicodeDecodeError: raise ValueError('Binary/research assets require a separate reviewed distribution path') from None
                safe_text(text)
                inventory[name] = sha(raw)
            inventories.append({'commit':commit,'files':inventory})
        scan = self.backend.scan(base,head)
        if scan.get('verdict') != 'PASS': raise ValueError('Secret scanner did not pass')
        return {'trees_sha256':sha(inventories),'scan':scan,'commits':len(commits)}

    def preflight(self, node_id, target=None):
        approved = self.approval(); expected = self.target()
        if target is not None and target != expected: raise PermissionError('Target is outside the authorized repository/base')
        if self.backend.identity() != approved['owner']: raise PermissionError('Restore the specifically authorized GitHub identity')
        info = self.backend.metadata(expected['repository'],expected['base'])
        if (info['repository'] != expected['repository'] or not info['can_push']
                or info['private'] != (approved['visibility']=='PRIVATE')
                or not COMMIT.fullmatch(info['base_head_sha'])):
            raise PermissionError('Repository identity, visibility or access differs from authorization')
        fetched = self.backend.fetch(expected['repository'],expected['base'])
        if fetched != info['base_head_sha']: raise ValueError('Remote base advanced during preflight; prepare a fresh review')
        node = self.memory.get('attempt',node_id); head = self.ops.commit(node['head_sha'])
        if head == fetched: raise ValueError('The saved implementation has no change against the target')
        git(self.ops.repository,'merge-base','--is-ancestor',fetched,head)
        evidence = self.reviews.evidence(node_id)
        for identifier in node.get('artifacts',{}).values(): self.memory.read_artifact(identifier)
        for test in self.memory.list('test_result',node['task_id']):
            if test.get('attempt_id') == node_id:
                for key in ('artifact','hidden_test_artifact'):
                    if test.get(key): self.memory.read_artifact(test[key])
        privacy = self.privacy(fetched,head)
        diff = git(self.ops.repository,'diff','--no-ext-diff','--no-textconv',fetched,head,'--')
        return {'mode':'GITHUB_DRAFT_PR',**expected,'base_head_sha':fetched,
                'privacy_sha256':sha(privacy),'diff_sha256':sha(diff.encode()),
                'approval_sha256':sha(approved),'evidence_hash':evidence}

    def prepare(self,node_id,reason,target=None):
        if not isinstance(reason,str) or not reason.strip() or len(reason)>2000: raise ValueError('A bounded public PR reason is required')
        safe_text(reason)
        checked = self.preflight(node_id,target)
        return self.reviews.intent(node_id,checked,reason)

    def publish(self,intent_id):
        with self.memory.lock():
            intent = self.memory.get('action',intent_id)
            if intent['status'] != 'HUMAN_APPROVED': raise PermissionError('Each product PR requires its own real human review')
            if intent['target'].get('mode') != 'GITHUB_DRAFT_PR': raise PermissionError('Prepare a GitHub preflight and a fresh human review')
            target = {k:intent['target'][k] for k in ('repository','base')}
            checked = self.preflight(intent['attempt_id'],target)
            if checked != intent['target']: raise PermissionError('Target, base, code or privacy/evidence changed; review again')
            node = self.memory.get('attempt',intent['attempt_id'])
            consumed = self.reviews.consume(intent_id,node['head_sha'],checked,checked['evidence_hash'])
            branch = 'codex/product-pr-'+consumed['nonce']
            title = 'Workbench change '+node['head_sha'][:12]
            body = (intent['reason']+'\n\nHuman owner reviewed exact commit `'+node['head_sha']+
                    '` and evidence `'+checked['evidence_hash']+'`. Independent passing tests and privacy/secret preflight are bound to this proposal. '
                    'This draft still requires GitHub CI and human review before merge; the workbench does not merge it.\n')
            folder = self.memory.root/'publication'; folder.mkdir(exist_ok=True)
            body_file = folder/(consumed['nonce']+'.md'); body_file.write_text(body,encoding='utf-8')
            consumed.update(branch=branch)
            self.memory.record('action',intent_id,consumed,'controller')
            try:
                url = self.backend.create(checked,node['head_sha'],branch,title,body_file)
            except Exception:
                consumed.update(status='PUBLISH_UNCERTAIN_RECONCILE_BEFORE_NEW_REVIEW')
                self.memory.record('action',intent_id,consumed,'controller')
                raise RuntimeError('Delivery stopped after consuming this approval. Inspect the saved remote branch/PR; do not replay it.') from None
            consumed.update(status='DRAFT_PR_CREATED_AWAITING_CI_AND_GITHUB_HUMAN_REVIEW',pr_url=url)
            self.memory.record('action',intent_id,consumed,'controller')
            self.memory.record('attempt',intent['attempt_id'],node|{'pr_url':url},'controller')
            return consumed
