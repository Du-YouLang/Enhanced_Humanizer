"""Frozen identities must map to every full parameter case and the correct file."""
from pathlib import Path
import sys
import unittest
import xml.etree.ElementTree as ET
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from p6_evaluate_linux import pytest_statuses

class IdentityTests(unittest.TestCase):
    def case(self,module,name,failed=False):
        case=ET.Element('testcase',classname=module,name=name)
        if failed:ET.SubElement(case,'failure')
        return case

    def test_whitespace_truncated_group_cannot_hide_a_failed_member(self):
        names=['testing/test_assert.py::TestClass::test_expr[assert']
        cases=[self.case('testing.test_assert.TestClass','test_expr[assert x]'),
               self.case('testing.test_assert.TestClass','test_expr[assert y]',True)]
        states,mapping=pytest_statuses(cases,names)
        self.assertEqual(states[names[0]],'FAIL');self.assertEqual(len(mapping[names[0]]),2)
        states,_=pytest_statuses(cases[:1],names);self.assertEqual(states[names[0]],'PASS')

    def test_parameter_double_colon_is_preserved_and_other_module_cannot_match(self):
        name='testing/acceptance.py::TestUse::test_case[test_fun.py::test_a]'
        states,_=pytest_statuses([self.case('other.acceptance.TestUse','test_case[test_fun.py::test_a]')],[name])
        self.assertEqual(states[name],'UNMAPPED')
        case=self.case('testing.acceptance.TestUse','test_case[test_fun.py::test_a]')
        states,_=pytest_statuses([case],[name]);self.assertEqual(states[name],'PASS')
        with self.assertRaises(ValueError):pytest_statuses([case,case],[name])

if __name__=='__main__':unittest.main()
