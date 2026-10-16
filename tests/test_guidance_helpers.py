"""Serialized task manifests must agree with actual frozen helper fences."""
from pathlib import Path
import sys,tempfile,unittest

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from p6_guidance_helpers import LEGACY,NAMES,bind_argv,bind_task


class HelperBindingTests(unittest.TestCase):
    def test_only_exact_trusted_paths_change_and_all_arguments_stay(self):
        with tempfile.TemporaryDirectory() as folder:
            for name in NAMES:(Path(folder)/name).write_text('trusted helper\n')
            argv=['/task/env/bin/python','-B',LEGACY+'/p6_requests_runner.py','--frozen-selection','["case"]','--junit','{junit}']
            result=bind_argv(argv,folder)
            self.assertEqual(result[:2],argv[:2]);self.assertEqual(result[3:],argv[3:])
            self.assertEqual(result[2],str(Path(folder)/NAMES[0]))
            task={'visible':argv,'hidden_argv':['/task/env/bin/python',LEGACY+'/p6_pytest_runner.py','test_case'],
                  'test_patch':'unchanged','expected':['test_case']}
            bind_task(task,folder)
            self.assertEqual(task['test_patch'],'unchanged');self.assertEqual(task['expected'],['test_case'])
            self.assertEqual(task['helper_binding']['before']['visible'],argv)
            self.assertEqual(set(task['helper_binding']['helper_sha256']),set(NAMES))
    def test_unknown_embedded_paths_missing_helpers_and_symlinks_are_denied(self):
        with tempfile.TemporaryDirectory() as folder:
            for argv in ([LEGACY+'/other.py'],["runpy.run_path('"+LEGACY+"/p6_pytest_runner.py')"],
                         [LEGACY+'/p6_pytest_runner.py'],[False]):
                with self.assertRaises(ValueError):bind_argv(argv,folder)


if __name__=='__main__':unittest.main()
