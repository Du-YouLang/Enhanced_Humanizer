import json
import os
from pathlib import Path
import subprocess
import sys
import types
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import quiet_process

class QuietProcessTests(unittest.TestCase):
    def test_windows_flags_preserve_io_and_grouping(self):
        startup=types.SimpleNamespace(dwFlags=0,wShowWindow=1)
        with patch.object(quiet_process.os,'name','nt'),patch.object(subprocess,'CREATE_NO_WINDOW',0x08000000,create=True),patch.object(subprocess,'STARTF_USESHOWWINDOW',1,create=True),patch.object(subprocess,'SW_HIDE',0,create=True),patch.object(subprocess,'STARTUPINFO',return_value=startup,create=True):
            original={'creationflags':0x200,'capture_output':True,'timeout':3,'input':b'x','env':{'ONLY':'kept'}}
            value=quiet_process.background_kwargs(original)
            self.assertEqual(value['creationflags'],0x08000200)
            self.assertEqual(value['startupinfo'].wShowWindow,0)
            self.assertEqual(value['startupinfo'].dwFlags&1,1)
            for k in ('capture_output','timeout','input','env'):self.assertEqual(value[k],original[k])
            self.assertEqual(original['creationflags'],0x200)
            for conflict in (0x10,0x8):
                with self.assertRaises(ValueError):quiet_process.background_kwargs({'creationflags':conflict})
    def test_non_windows_does_not_supply_windows_only_options(self):
        with patch.object(quiet_process.os,'name','posix'):
            self.assertEqual(quiet_process.background_kwargs({'timeout':3}),{'timeout':3})
    def test_output_nonzero_status_and_timeout_semantics_are_preserved(self):
        r=quiet_process.run([sys.executable,'-c',"import sys;print('ok');print('err',file=sys.stderr)"],capture_output=True,text=True,check=True,timeout=10)
        self.assertEqual(r.stdout.strip(),'ok');self.assertEqual(r.stderr.strip(),'err')
        self.assertEqual(quiet_process.check_output([sys.executable,'-c',"print('check-output')"],text=True,timeout=10).strip(),'check-output')
        with self.assertRaises(subprocess.CalledProcessError) as ctx:quiet_process.run([sys.executable,'-c','raise SystemExit(7)'],check=True,timeout=10)
        self.assertEqual(ctx.exception.returncode,7)
        with self.assertRaises(subprocess.TimeoutExpired):quiet_process.run([sys.executable,'-c','import time;time.sleep(5)'],timeout=.1)
    @unittest.skipUnless(os.name=='nt','Actual Windows console attachment control')
    def test_actual_windows_console_child_has_no_console(self):
        code="import ctypes,json;ctypes.windll.kernel32.GetConsoleWindow.restype=ctypes.c_void_p;print(json.dumps({'console':ctypes.windll.kernel32.GetConsoleWindow() or 0}))"
        r=quiet_process.run([sys.executable,'-c',code],capture_output=True,text=True,check=True,timeout=10)
        self.assertEqual(json.loads(r.stdout)['console'],0)

if __name__=='__main__':unittest.main()
