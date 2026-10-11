"""Adversarial artifacts for the independent PC-ALM checks, never real runs."""
import csv
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from p6_pc_validation import validate_grid
from workbench.science import claim_checks


class PCValidationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.eta={(w,d):.125 for w in (8,16,128) for d in (8,64,128)}
        self.rows=[]
        for (w,d),eta in self.eta.items():
            for method in ('bp','pc','pcalm'):
                row=dict(dataset='fashion_mnist',activation='relu',method=method,width=w,depth=d,seed=0,
                         final_test_acc=.7,grad_cos_to_bp=.7)
                self.rows.append(row)
                folder=self.folder(row);folder.mkdir()
                config={'dataset':'fashion_mnist','model':{'activation':'relu','width':w,'depth':d,'input_dim':784,'output_dim':10},
                        'training':{'seed':0,'epochs':1,'batch_size':64,'gamma0':1.,'eta0':.001,'train_subset':60000,
                                    'test_subset':10000,'drop_last':True,'learning_rate':None},
                        'method':{'name':method,'budget':0 if method=='bp' else 2*d,'rho':1.,'alpha':1.,'inner_steps':1,
                                  'weight_credit_timing':'pre_dual_energy','state_lr':eta}}
                summary=row|{'steps':937,'epochs':1,'batch_size':64,'gamma0':1.,'eta0':.001,'rho':1.,'train_subset':60000,
                             'test_subset':10000,'budget':config['method']['budget'],'state_lr':eta,
                             'final_train_acc':.6,'final_test_mse':.4,'final_train_mse':.5}
                (folder/'config.json').write_text(json.dumps(config))
                (folder/'summary.json').write_text(json.dumps(summary))
                (folder/'metrics.csv').write_text('epoch,step,test_acc,train_acc,test_mse,train_mse\n1,937,.7,.6,.4,.5\n')
        self.csv(self.rows)

    def folder(self,row):
        return self.root/f"fashion_mnist_relu_n{row['width']}_l{row['depth']}_seed{row['seed']}_{row['method']}"

    def csv(self,rows):
        with (self.root/'cells.csv').open('w',newline='') as stream:
            writer=csv.DictWriter(stream,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)

    def validate(self):
        return validate_grid(self.root,self.eta,widths=(8,16,128),depths=(8,64,128),seeds=(0,))

    def test_faithful_artifacts_can_fail_science_claim(self):
        stats=self.validate()
        result=claim_checks(stats,{'C1':.04,'C2':.1,'C3':.1,'C4':.05,'C5':.15})
        self.assertFalse(result['claim_supported'])
        self.assertEqual(result['implementation_fidelity'],'NOT_DETERMINED_BY_CLAIM_STATISTICS')

    def test_extra_seed_missing_row_and_impossible_cosine_fail(self):
        for rows in (self.rows+[self.rows[0]|{'seed':99}],self.rows[1:],
                     [self.rows[0]|{'grad_cos_to_bp':2.}]+self.rows[1:]):
            self.csv(rows)
            with self.assertRaises(ValueError):self.validate()

    def test_summary_only_missing_native_records_fails(self):
        (self.folder(self.rows[0])/'metrics.csv').unlink()
        with self.assertRaises(ValueError):self.validate()

    def test_wrong_eta_and_shortened_dataset_fail(self):
        path=self.folder(self.rows[0])/'config.json';original=json.loads(path.read_text())
        for section,key,value in (('method','state_lr',.25),('training','train_subset',100)):
            cfg=json.loads(json.dumps(original));cfg[section][key]=value;path.write_text(json.dumps(cfg))
            with self.assertRaises(ValueError):self.validate()

    def test_native_summary_and_metrics_must_agree_with_cells(self):
        path=self.folder(self.rows[0])/'summary.json';summary=json.loads(path.read_text());summary['final_test_acc']=.71
        path.write_text(json.dumps(summary))
        with self.assertRaises(ValueError):self.validate()


if __name__=='__main__':unittest.main()
