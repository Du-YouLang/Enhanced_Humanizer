"""Independent, explicit P1 redesign contract checks, outside the model's repository."""


def verification_command(work,argv,scratch):
    """Test imports execute candidate code too: fence them with no API/auth-state access."""
    from dataclasses import replace
    from pathlib import Path
    from hmz.coganchor.fence import Fence,wrapper
    scratch=Path(scratch)
    scratch.mkdir(parents=True,exist_ok=True)
    fence=Fence.of(local='none',user='none',system='none',online=False,workdir=work,home=Path.home(),
                   read=(work,'/opt/workbench/.venv-linux'),write=(scratch,),hosts=())
    return [*wrapper(replace(fence,tmp=str(scratch))),*argv]

DESIGN_CHECK='''
from pathlib import Path
import weighted_stats as module

acc=module.WeightedMean()
acc.add(2,1)
acc.add(8,3)
assert abs(acc.result()-6.5)<1e-12
other=module.WeightedMean()
other.add(10,4)
acc.merge(other)
assert abs(acc.result()-8.25)<1e-12
for action in (lambda:module.WeightedMean().result(),lambda:module.WeightedMean().add(1,-1)):
    try:action()
    except ValueError:pass
    else:raise AssertionError('Required ValueError was not raised')
class Spy:
    def __init__(self):self.seen=[]
    def add(self,value,weight):self.seen.append((value,weight))
    def result(self):
        assert self.seen==[(2,1),(8,3)]
        return 123.456
module.WeightedMean=Spy
assert module.weighted_mean(iter([(2,1),(8,3)]))==123.456,'weighted_mean must delegate to the accumulator'
assert Path('test_accumulator.py').is_file(),'Builder must add accumulator tests'
print('P1 independent add/merge/errors/delegation checks PASS')
'''
