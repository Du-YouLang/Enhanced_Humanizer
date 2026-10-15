import json,subprocess,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import Mock
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'benchmarks/pi-comparison/runners'))
from pi_checkpoint_policy import AcceptanceJournal,cached_training_runner,checkpoint_cells
from pi_full_protocol import digest,exclusive,UncertainStage


class CheckpointTests(unittest.TestCase):
    def test_only_authorized_interruption_and_exact_unstarted_suffix(self):
        plan=json.loads((ROOT/'benchmarks/pi-comparison/full-main-plan-v4.json').read_bytes())
        cells=plan['cells'][27:];rows=[{'cell':c} for c in cells[:61]]
        self.assertEqual(checkpoint_cells({'remaining_cells':cells},rows,cells[61]),cells[62:])
        for bad in (rows[:-1],rows[::-1],rows+[{'cell':cells[61]}]):
            with self.assertRaises(ValueError):checkpoint_cells({'remaining_cells':cells},bad,cells[61])
        with self.assertRaises(ValueError):checkpoint_cells({'remaining_cells':cells},rows,cells[62])

    def test_model_public_and_freeze_are_reused_acceptance_once_original_marker_retained(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);original=root/'old';original.mkdir();name='SCI-PC-ALM-P0-deepseek'
            for s in ('setup','model','public','freeze'):
                stage=name+'-'+s;v={'status':'COMPLETED','s':s}
                exclusive(original/(stage+'.completed.json'),{'stage':stage,'value':v,'value_sha256':digest(v)})
            started=original/(name+'-acceptance.started.json');exclusive(started,{'stage':name+'-acceptance'})
            before={p:p.read_bytes() for p in original.iterdir()}
            journal=AcceptanceJournal(original,root/'new',name)
            forbidden=Mock(side_effect=AssertionError('Model replay'))
            for s in ('setup','model','public','freeze'):journal.run(name+'-'+s,forbidden)
            forbidden.assert_not_called();action=Mock(return_value={'verdict':'INDETERMINATE'})
            self.assertEqual(journal.run(name+'-acceptance',action),{'verdict':'INDETERMINATE'})
            journal.run(name+'-acceptance',action);action.assert_called_once()
            self.assertEqual(before,{p:p.read_bytes() for p in original.iterdir()})
            with self.assertRaises(ValueError):journal.run('other-model',forbidden)
            done=original/(name+'-model.completed.json');value=json.loads(done.read_bytes());value['value']['s']='changed';done.write_text(json.dumps(value))
            with self.assertRaises(ValueError):journal.run(name+'-model',forbidden)

    def test_uncertain_recovery_acceptance_does_not_auto_execute_twice(self):
        with tempfile.TemporaryDirectory() as tmp:
            name='PC';journal=AcceptanceJournal(Path(tmp)/'old',Path(tmp)/'new',name)
            action=Mock(side_effect=RuntimeError('Power loss'))
            with self.assertRaises(RuntimeError):journal.run(name+'-acceptance',action)
            with self.assertRaises(UncertainStage):journal.run(name+'-acceptance',action)
            action.assert_called_once()

    def test_cached_training_skips_only_exact_command_and_preserves_unknown_tasks(self):
        with tempfile.TemporaryDirectory() as tmp:
            target=Path(tmp)/'result';events=[];real=Mock(return_value=subprocess.CompletedProcess([],0))
            cache={'grid/a':{'config_name':'headline_fashion.yaml','overrides':{'width':'8','method':'bp'},
                'files':{'summary.json':'{}','config.json':'{}','metrics.csv':'a\n1\n'}}}
            run=cached_training_runner(real,cache,target,events)
            argv=['python','/code/train.py','--config','/code/configs/headline_fashion.yaml','--width','8','--method','bp','--output-dir',str(target/'grid/a')]
            self.assertEqual(run(argv).returncode,0);real.assert_not_called();self.assertEqual(events,['grid/a'])
            bad=list(argv);bad[bad.index('--width')+1]='16'
            with self.assertRaises(ValueError):run(bad)
            bad=list(argv);bad[-1]=str(Path(tmp)/'escape')
            with self.assertRaises(ValueError):run(bad)
            run(['python','-c','pass']);real.assert_called_once()


if __name__=='__main__':unittest.main()
