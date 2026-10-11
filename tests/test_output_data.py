"""Hostile result headers are rejected before allocating candidate-declared arrays."""
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from p6_output_data import bounded_json,bounded_npy,bounded_npz


class JsonBoundaryTests(unittest.TestCase):
    def test_duplicate_keys_nonstandard_numbers_and_size_are_refused(self):
        base=ROOT/'.local-workbench/test-tmp';base.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(dir=base) as folder:
            p=Path(folder)/'result.json'
            for raw in ('{"a":1,"a":2}','{"a":NaN}','{"a":Infinity}'):
                p.write_text(raw)
                with self.assertRaises(ValueError):bounded_json(p)
            p.write_text('{"a":1}')
            self.assertEqual(bounded_json(p),{'a':1})
            with self.assertRaises(ValueError):bounded_json(p,max_bytes=2)


@unittest.skipUnless(importlib.util.find_spec('numpy'),'Task-native NumPy required')
class NumericBoundaryTests(unittest.TestCase):
    def setUp(self):
        import numpy as np
        self.np=np;base=ROOT/'.local-workbench/test-tmp';base.mkdir(parents=True,exist_ok=True)
        self.temp=tempfile.TemporaryDirectory(dir=base);self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)

    def test_valid_nan_and_boolean_arrays_keep_their_values(self):
        p=self.root/'result.npz';self.np.savez_compressed(p,x=self.np.array([self.np.nan,1.]),mask=self.np.array([True,False]))
        arrays=bounded_npz(p,expected_keys={'x','mask'})
        self.assertTrue(self.np.isnan(arrays['x'][0]));self.assertEqual(arrays['mask'].tolist(),[True,False])
        with self.assertRaises(ValueError):bounded_npz(p,expected_keys={'x'})

    def test_shape_bomb_object_duplicate_and_archive_path_are_refused(self):
        raw=io.BytesIO();self.np.save(raw,self.np.array([1.]))
        for members in ([('x.npy',raw.getvalue()),('x.npy',raw.getvalue())],[('../x.npy',raw.getvalue())]):
            p=self.root/'bad.npz'
            with zipfile.ZipFile(p,'w') as z:
                for name,data in members:z.writestr(name,data)
            with self.assertRaises(ValueError):bounded_npz(p)
        p=self.root/'object.npz';self.np.savez(p,x=self.np.array([{}],dtype=object))
        with self.assertRaises(ValueError):bounded_npz(p)
        header=io.BytesIO();self.np.lib.format.write_array_header_1_0(header,{'descr':'<f8','fortran_order':False,'shape':(10**12,)})
        p=self.root/'bomb.npy';p.write_bytes(header.getvalue())
        with self.assertRaises(ValueError):bounded_npy(p)
        q=self.root/'bomb.npz'
        with zipfile.ZipFile(q,'w') as z:z.writestr('x.npy',header.getvalue())
        with self.assertRaises(ValueError):bounded_npz(q)
        good=self.root/'good.npy';self.np.save(good,self.np.arange(4,dtype=self.np.float32))
        self.assertEqual(bounded_npy(good).tolist(),[0.,1.,2.,3.])
        with self.assertRaises(ValueError):bounded_npy(good,max_elements=2)


if __name__=='__main__':unittest.main()
