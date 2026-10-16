"""Bind serialized, frozen helper argv to the exact isolated executor.

Only three known trusted helper files are aliases. No broader file permission,
test selection, assertion, interpreter, environment or tolerance is changed.
"""
import hashlib
from pathlib import Path

REVISION='GUIDANCE_SERIALIZED_HELPER_BINDING_V2'
LEGACY='/opt/workbench/'+'source'
NAMES=('p6_requests_runner.py','p6_pytest_runner.py','p6_sympy_runner.py')


def bind_argv(argv, executor):
    if not isinstance(argv,list) or any(not isinstance(s,str) for s in argv):
        raise ValueError('Frozen argv must be a string list')
    executor=Path(executor)
    aliases={LEGACY+'/'+name:str(executor/name) for name in NAMES}
    result=[]
    for value in argv:
        if value in aliases:
            path=Path(aliases[value])
            if not path.is_file() or path.is_symlink():raise ValueError('Exact frozen helper unavailable')
            result.append(str(path))
        elif LEGACY in value:
            raise ValueError('Unapproved embedded legacy helper reference')
        else:result.append(value)
    return result


def bind_task(task,executor):
    before={field:list(task[field]) for field in ('visible','hidden_argv')}
    for field in before:task[field]=bind_argv(task[field],executor)
    task['helper_binding']={'revision':REVISION,'before':before,
        'after':{field:task[field] for field in before},
        'helper_sha256':{name:hashlib.sha256((Path(executor)/name).read_bytes()).hexdigest()
                         for name in NAMES}}
    return task
