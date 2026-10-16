import hashlib
import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from p6_owner_input import owner_npz
from p6_output_data import bounded_npz


@unittest.skipUnless(importlib.util.find_spec('numpy'),'Task-native NumPy required')
class OwnerInputBoundaryTests(unittest.TestCase):
    def test_frozen_unicode_metadata_loads_without_relaxing_output_boundary(self):
        import numpy as np
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'input.npz'
            np.savez(path,data=np.zeros((2,4,3)),ch_names=np.array(['FC3','FC1','C3','C1']),metadata_json=np.array('{"synthetic":true}'))
            h=hashlib.sha256(path.read_bytes()).hexdigest()
            self.assertEqual(owner_npz(path,h)['metadata_json'].item(),'{"synthetic":true}')
            with self.assertRaises(ValueError):bounded_npz(path)

    def test_wrong_fingerprint_refuses_even_valid_numeric_input(self):
        import numpy as np
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'input.npz';np.savez(path,data=np.zeros(2))
            with self.assertRaises(ValueError):owner_npz(path,'0'*64)

    def test_owner_fingerprint_does_not_allow_pickle(self):
        import numpy as np
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'input.npz';np.savez(path,data=np.array([{}],dtype=object))
            with self.assertRaises(ValueError):owner_npz(path,hashlib.sha256(path.read_bytes()).hexdigest())
