"""Load the pure Python limiter from the task's existing sealed environment."""
import hashlib
import importlib.util
from pathlib import Path
import sys


def ensure_gc_threadpool(prefix, *, expected_sha256=None):
    prefix = Path(prefix).resolve()
    candidates = list(prefix.glob('lib/python*/site-packages/threadpoolctl.py'))
    choices = {path.resolve() for path in candidates}
    if len(choices) != 1 or any(path.is_symlink() for path in candidates) or not next(iter(choices)).is_relative_to(prefix):
        raise RuntimeError('GRANGER controller requires one frozen threadpoolctl module')
    path = next(iter(choices))
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    if expected_sha256 is not None and actual != expected_sha256:
        raise ValueError('Frozen GRANGER threadpoolctl changed')
    present = sys.modules.get('threadpoolctl')
    if present is not None:
        if Path(present.__file__).resolve() != path.resolve():
            raise RuntimeError('A different threadpoolctl is already loaded')
        return present
    # Load only this pure Python dependency. Adding the whole Python 3.11
    # site-packages directory to the Python 3.12 controller would mix ABIs.
    spec = importlib.util.spec_from_file_location('threadpoolctl', path)
    module = importlib.util.module_from_spec(spec)
    sys.modules['threadpoolctl'] = module
    try:
        spec.loader.exec_module(module)
        if not callable(getattr(module, 'threadpool_limits', None)):
            raise RuntimeError('Invalid GRANGER threadpoolctl interface')
    except Exception:
        sys.modules.pop('threadpoolctl', None)
        raise
    return module
