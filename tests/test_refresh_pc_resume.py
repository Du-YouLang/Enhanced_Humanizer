"""MOCK training: cache hits never launch, mismatches fail, time is retained."""
import sys,tempfile,unittest,subprocess
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from pi_checkpoint_policy import cached_training_runner,remaining_acceptance_seconds
class RecoveryTests(unittest.TestCase):
 def test_exact_saved_training_reuses_files_and_never_calls_trainer(self):
  with tempfile.TemporaryDirectory()as tmp:
   root=Path(tmp);events=[];cache={'grid/cell':{'config_name':'headline.yaml','overrides':{'width':'8'},'files':{'summary.json':'{}','config.json':'{}','metrics.csv':'a,b'}}}
   def forbidden(*a,**kw):raise AssertionError('Training replay')
   run=cached_training_runner(forbidden,cache,root,events)
   result=run(['python','train.py','--config','headline.yaml','--output-dir',str(root/'grid/cell'),'--width','8'])
   self.assertEqual(result.returncode,0);self.assertEqual(events,['grid/cell']);self.assertTrue((root/'grid/cell/metrics.csv').exists())
 def test_config_overrides_and_output_escape_are_rejected(self):
  with tempfile.TemporaryDirectory()as tmp:
   root=Path(tmp);cache={'cell':{'config_name':'headline.yaml','overrides':{'width':'8'},'files':{}}};run=cached_training_runner(lambda *a,**k:None,cache,root,[])
   for config,width in [('bad.yaml','8'),('headline.yaml','16')]:
    with self.assertRaises(ValueError):run(['python','train.py','--config',config,'--output-dir',str(root/'cell'),'--width',width])
   with self.assertRaises(ValueError):run(['python','train.py','--output-dir',str(root.parent/'escape')])
 def test_only_missing_training_falls_through_and_prior_time_is_debited(self):
  calls=[]
  with tempfile.TemporaryDirectory()as tmp:
   run=cached_training_runner(lambda *a,**k:calls.append(a),{},Path(tmp),[]);run(['python','train.py','--output-dir',str(Path(tmp)/'missing')])
  self.assertEqual(len(calls),1);self.assertEqual(remaining_acceptance_seconds(2898),4302)
  for debit in [0,7200,-1]:
   with self.assertRaises(ValueError):remaining_acceptance_seconds(debit)
if __name__=='__main__':unittest.main()
