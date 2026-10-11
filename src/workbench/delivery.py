"""Verified local source packages. No model, remote Git or credential operations."""
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[2]
LIMIT = 250 * 1024 * 1024
VERSION = '0.1.0-preview.1'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def git(repo, *args):
    return subprocess.check_output(['git', '-c', 'core.hooksPath=', '-c', 'core.fsmonitor=false',
                                   '-c', 'credential.helper=', *args], cwd=repo, stderr=subprocess.PIPE)


def local_target(path):
    target = Path(path).resolve()
    private = (ROOT / '.local-workbench').resolve()
    if not private.is_relative_to(ROOT.resolve()) or not target.is_relative_to(private) or target == private:
        raise ValueError('Delivery targets must be below this project .local-workbench')
    return target


def safe_name(name):
    if not isinstance(name, str) or not name or '\\' in name or ':' in name or any(ord(c) < 32 for c in name):
        raise ValueError('Unsafe archive path')
    path = PurePosixPath(name)
    if path.is_absolute() or str(path) != name or any(p in ('.', '..') for p in path.parts):
        raise ValueError('Unsafe archive path')
    for part in path.parts:
        if any(c in part for c in '<>"|?*') or part.endswith((' ', '.')) or part.lower() in ('.git','conin$','conout$') or re.fullmatch(r'(con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\..*)?', part, re.I):
            raise ValueError('Unsafe Windows archive path')
    return path


def clean(repo):
    # Ignore private ignored files; refuse tracked changes and untracked public source.
    if git(repo, 'status', '--porcelain', '--untracked-files=normal').strip():
        raise ValueError('Build from a clean committed source tree')


def public_source(name):
    import sys
    sys.path.insert(0, str(ROOT/'scripts'))
    from check_repository import private_path
    if private_path(name): raise ValueError('Private material cannot enter a source package')


def build(repo, output):
    repo = Path(repo).resolve(); output = local_target(output)
    clean(repo)
    if output.exists():
        raise FileExistsError('Preserve existing delivery; choose a new output directory')
    head = git(repo, 'rev-parse', 'HEAD').decode().strip()
    if not re.fullmatch('[0-9a-f]{40}', head):
        raise ValueError('A real Git commit is required')
    # A safe current tree alone does not make the bundled history safe to ship.
    for raw in git(repo,'log','--format=','--name-only','-z','HEAD').split(b'\0'):
        name=raw.decode('utf8').lstrip('\n')
        if name: safe_name(name); public_source(name)
    output.mkdir(parents=True)
    bundle = output / 'source.bundle'
    git(repo, 'bundle', 'create', str(bundle), 'HEAD')
    payload = {'source.bundle': bundle.read_bytes()}
    for entry in git(repo, 'ls-tree', '-r', '-z', 'HEAD').split(b'\0'):
        if not entry: continue
        header, raw = entry.split(b'\t', 1)
        mode, kind, oid = header.split()
        name = raw.decode('utf-8'); safe_name(name); public_source(name)
        if mode not in (b'100644', b'100755') or kind != b'blob':
            raise ValueError('Delivery refuses symlinks, submodules and unsupported Git entries')
        payload['payload/' + name] = git(repo, 'cat-file', 'blob', oid.decode())
    if sum(map(len, payload.values())) > LIMIT:
        raise ValueError('Delivery exceeds 250 MiB limit')
    if len(payload) != len({n.casefold() for n in payload}):
        raise ValueError('Source paths collide on Windows')
    manifest = {'schema_version': 1, 'version': VERSION, 'status': 'LOCAL_PREVIEW_NOT_PUBLISHED',
                'commit': head, 'contains_runtime': False, 'contains_private_state': False,
                'project_license': 'UNDECIDED_EXTERNAL_RELEASE_BLOCKED',
                'files': {n: {'sha256': sha(b), 'size': len(b)} for n, b in sorted(payload.items())}}
    archive = output / ('Enhanced_Humanizer-' + VERSION + '-' + head[:12] + '.zip')
    with zipfile.ZipFile(archive, 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for name, data in sorted(payload.items()): z.writestr(name, data)
        z.writestr('manifest.json', json.dumps(manifest, indent=2, sort_keys=True).encode())
    receipt = {'status': 'BUILT_LOCAL_PREVIEW', 'commit': head, 'archive': str(archive),
               'archive_sha256': sha(archive.read_bytes()), 'bytes': archive.stat().st_size,
               'file_count': len(payload), 'bundle_sha256': manifest['files']['source.bundle']['sha256']}
    (output / 'receipt.json').write_text(json.dumps(receipt, indent=2), encoding='utf-8')
    return receipt


def unique_json(pairs):
    result = {}
    for k, v in pairs:
        if k in result: raise ValueError('Duplicate manifest key')
        result[k] = v
    return result


def verify(archive, expected_sha):
    archive = Path(archive)
    if not re.fullmatch('[0-9a-f]{64}', expected_sha) or archive.stat().st_size > LIMIT:
        raise ValueError('Expected SHA256 and bounded local archive required')
    if sha(archive.read_bytes()) != expected_sha:
        raise ValueError('Archive checksum mismatch')
    with zipfile.ZipFile(archive) as z:
        infos = z.infolist(); names = [i.filename for i in infos]
        if len(names) != len(set(n.casefold() for n in names)) or sum(i.file_size for i in infos) > LIMIT:
            raise ValueError('Duplicate/case-colliding or oversized archive')
        for info in infos:
            safe_name(info.filename)
            if info.is_dir() or stat.S_IFMT(info.external_attr >> 16) not in (0,stat.S_IFREG):
                raise ValueError('Archive must contain regular files only')
        if 'manifest.json' not in names or z.getinfo('manifest.json').file_size > 2_000_000:
            raise ValueError('Missing or oversized manifest')
        m = json.loads(z.read('manifest.json'), object_pairs_hook=unique_json)
        if m.get('schema_version') != 1 or m.get('status') != 'LOCAL_PREVIEW_NOT_PUBLISHED' or not re.fullmatch('[0-9a-f]{40}', m.get('commit', '')):
            raise ValueError('Unsupported preview manifest')
        files = m.get('files')
        if not isinstance(files, dict) or set(files) | {'manifest.json'} != set(names) or 'source.bundle' not in files:
            raise ValueError('Manifest/archive inventory mismatch')
        for name, meta in files.items():
            if name != 'source.bundle' and not name.startswith('payload/'):
                raise ValueError('Unexpected archive component')
            if name.startswith('payload/'): public_source(name.removeprefix('payload/'))
            data = z.read(name)
            if meta != {'sha256': sha(data), 'size': len(data)}:
                raise ValueError('Payload checksum mismatch')
        return m


def install(archive, expected_sha, destination):
    target = local_target(destination)
    if target.exists():
        raise FileExistsError('Installation requires a new directory; existing state is preserved')
    manifest = verify(archive, expected_sha)  # Verify the entire archive before writing any file.
    target.mkdir(parents=True)
    private = target / '.local-workbench' / 'delivery'; private.mkdir(parents=True)
    bundle = private / 'source.bundle'
    with zipfile.ZipFile(archive) as z: bundle.write_bytes(z.read('source.bundle'))
    git(target, 'init', '-q')
    git(target, 'config', 'core.autocrlf', 'false')
    git(target, 'config', 'core.hooksPath', '')
    git(target, 'bundle', 'verify', str(bundle))
    git(target, 'fetch', '--no-tags', str(bundle), 'HEAD')
    git(target, 'checkout', '-q', '-b', 'codex/installed-preview', manifest['commit'])
    if git(target, 'rev-parse', 'HEAD').decode().strip() != manifest['commit']:
        raise ValueError('Bundle commit differs from manifest')
    tracked = {n for n in git(target, 'ls-files', '-z').decode().split('\0') if n}
    wanted = {n.removeprefix('payload/') for n in manifest['files'] if n.startswith('payload/')}
    if tracked != wanted: raise ValueError('Bundle tree differs from payload inventory')
    for name in tracked:
        f = target / name; meta = manifest['files']['payload/' + name]
        if f.is_symlink() or not f.resolve().is_relative_to(target) or sha(f.read_bytes()) != meta['sha256']:
            raise ValueError('Installed tree differs from verified payload')
    clean(target)
    receipt = {'status': 'SOURCE_INSTALLED_RUNTIME_NOT_PROVISIONED', 'commit': manifest['commit'],
               'archive_sha256': expected_sha, 'destination': str(target), 'models_called': 0,
               'remote_operations': 0, 'credentials_copied': False}
    (private / 'install-receipt.json').write_text(json.dumps(receipt, indent=2), encoding='utf-8')
    return receipt
