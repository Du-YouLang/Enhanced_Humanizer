"""Tool evidence is complete or refused, and never includes provider headers."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from p6_trace_evidence import tool_trace


class TraceEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.trace=self.root/'humanize/epics/task/epic/sessions/dsh/sessions/project/session/session.v3.jsonl'
        self.trace.parent.mkdir(parents=True)

    def write(self,rows):
        self.trace.write_text(''.join(json.dumps(r)+'\n' for r in rows))

    def test_complete_arguments_results_and_failure_are_retained(self):
        self.write([{'type':'request/header','data':{'header':'private-provider-configuration'}},
                    {'type':'tool/call','data':{'callId':'1','arguments':'run the complete command'}},
                    {'type':'tool/result','data':{'callId':'1','result':'failed output\nall details'}}])
        value=tool_trace(self.root)
        self.assertEqual((value['tool_calls'],value['tool_results']),(1,1))
        self.assertNotIn('private-provider',json.dumps(value))
        self.assertIn('all details',value['records'][1]['data']['result'])
        self.assertFalse(value['truncated'])

    def test_credentials_are_explicitly_redacted_without_losing_tool_records(self):
        fake='sk-'+'a'*32
        self.write([{'type':'tool/result','data':{'result':'value='+fake}}])
        value=tool_trace(self.root)
        self.assertEqual(value['credential_redactions'],1)
        self.assertNotIn(fake,json.dumps(value))
        self.assertEqual(len(value['records']),1)

    def test_missing_and_oversize_evidence_are_refused(self):
        with self.assertRaises(ValueError):tool_trace(self.root)
        self.write([{'type':'tool/result','data':{'result':'x'*2000}}])
        with self.assertRaisesRegex(ValueError,'no truncation'):tool_trace(self.root,max_bytes=1000)


if __name__=='__main__':unittest.main()
