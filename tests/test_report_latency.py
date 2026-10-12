"""Prevent overlapping tool calls and missing timestamps from inventing latency."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from report_latency import tool_timing


def event(kind, identifier, seconds):
    return {'type': 'tool/' + kind, 'time': seconds * 1000,
            'data': {'callId': identifier} if kind == 'call' else
                    {'message': {'content': [{'type': 'tool-result', 'toolCallId': identifier}]}}}


class ReportLatencyTests(unittest.TestCase):
    def test_overlapping_calls_count_union_not_sum(self):
        value = tool_timing({'records': [event('call', 'a', 0), event('call', 'b', 1),
                                        event('result', 'b', 2), event('result', 'a', 3)],
                             'origin_hashes': []})
        self.assertEqual(value['native_tools_observed_seconds'], 3)
        self.assertEqual(value['status'], 'COMPLETE')

    def test_missing_result_is_partial_not_zero_time(self):
        value = tool_timing({'records': [event('call', 'a', 0)], 'origin_hashes': []})
        self.assertEqual(value['status'], 'PARTIAL')
        self.assertEqual(value['native_tools_observed_seconds'], 'unavailable')
        self.assertEqual(value['unpaired_calls'], 1)

    def test_duplicate_or_reversed_clock_refused(self):
        for rows in ([event('call', 'a', 1), event('call', 'a', 2)],
                     [event('call', 'a', 2), event('result', 'a', 1)]):
            with self.subTest(rows=rows), self.assertRaises(ValueError):
                tool_timing({'records': rows, 'origin_hashes': []})
