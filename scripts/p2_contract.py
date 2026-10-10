"""Explicit frozen task contract; custom tasks stay private until separately reviewed for publication."""

from pathlib import PurePosixPath


def validate_contract(contract,env_hash):
    required={'task_id','prompt','base_repository','base_commit','env_hash','source_file','visible_test_program',
              'acceptance_test_program','protected_files'}
    if not isinstance(contract,dict) or set(contract)!=required:raise ValueError('Incomplete or unknown task contract fields')
    if not all(isinstance(contract[k],str) and contract[k] for k in required-{'protected_files'}):
        raise ValueError('Task contract needs nonempty string fields')
    if contract['env_hash']!=env_hash:raise ValueError('Task environment differs from the frozen runtime')
    if len(contract['base_commit'])!=40 or set(contract['base_commit'])-set('0123456789abcdef'):
        raise ValueError('Task base must be an exact commit SHA')
    base=PurePosixPath(contract['base_repository'])
    if '..' in base.parts or not base.is_relative_to('/opt/workbench/source'):
        raise ValueError('Task base repository must be a prepared project-local source checkout')
    if not isinstance(contract['protected_files'],dict):raise ValueError('Protected file hashes required')
    for name in [contract['source_file'],*contract['protected_files']]:
        path=PurePosixPath(name)
        if path.is_absolute() or '..' in path.parts or '.git' in path.parts or not path.parts:
            raise ValueError('Task file path escapes the candidate')
    for value in contract['protected_files'].values():
        if not isinstance(value,str) or len(value)!=64 or set(value)-set('0123456789abcdef'):
            raise ValueError('Protected file needs a SHA256')
    if sum(len(contract[k]) for k in ('prompt','visible_test_program','acceptance_test_program'))>250_000:
        raise ValueError('Task contract exceeds local MVP limit')
    return contract
