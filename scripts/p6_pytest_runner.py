"""Select frozen SWE identities while preserving upstream collection order.

    The pinned SWE parser truncates parametrized names at the first whitespace.
    Select every corresponding full identity and record them in JUnit; the owner
    evaluator requires every member of each frozen identity group to pass.
"""
import json
import sys
import pytest


class Selection:
    def __init__(self,names):self.names=set(names)
    def pytest_collection_modifyitems(self,config,items):
        selected=[item for item in items if item.nodeid.split()[0] in self.names]
        deselected=[item for item in items if item not in selected]
        items[:]=selected
        if deselected:config.hook.pytest_deselected(items=deselected)


if __name__=='__main__':
    names=json.loads(sys.argv[1]);paths=list(dict.fromkeys(n.split('::',1)[0] for n in names))
    sys.exit(pytest.main([*sys.argv[2:],*paths],plugins=[Selection(names)]))
