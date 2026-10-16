"""Load exact owner-pinned NPZ inputs, distinct from untrusted output arrays."""
import hashlib
from pathlib import Path


def owner_npz(path, expected_sha256):
    import numpy as np
    path=Path(path)
    if path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest()!=expected_sha256:
        raise ValueError('Exact frozen owner input required')
    with np.load(path,allow_pickle=False) as archive:
        # Owner input includes Unicode channel names and scalar JSON metadata.
        # Never relax the numeric-only candidate output reader for these fields.
        return {name:archive[name].copy() for name in archive.files}
