import hashlib
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from pi_gc_sync_repair import repaired_text

class SyncRepairTests(unittest.TestCase):
    def test_exact_single_site_and_no_double_patch(self):
        old='prefix\n        if (tid < d) sG[tid * d + tid] += ridge;\n        if (tid < p * p) {\nbody\n'
        digest=hashlib.sha256(old.encode()).hexdigest();new=repaired_text(old,digest)
        self.assertEqual(new.count('__syncthreads()'),1)
        self.assertIn('sG[tid * d + tid] += ridge;\n        __syncthreads();',new)
        for text,expected in ((old,'0'*64),(new,hashlib.sha256(new.encode()).hexdigest()),(old+old,hashlib.sha256((old+old).encode()).hexdigest())):
            with self.assertRaises(ValueError):repaired_text(text,expected)

if __name__=='__main__':unittest.main()
