"""Run the frozen named tests with SymPy's native runner and exact selection."""
import json
import sys
from pathlib import Path
sys.path.insert(0,str(Path.cwd()))
from sympy.utilities import runtests

if __name__=='__main__':
    names=set(json.loads(sys.argv[1]));paths=json.loads(sys.argv[2])
    runtests.SymPyTests.matches=lambda self,test:test.__name__ in names
    sys.exit(not runtests.test(*paths,kw=sorted(names),verbose=True,subprocess=False,colors=False,sort=True))
