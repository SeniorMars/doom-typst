"""Check benchmark workloads at the plugin's input-size boundary."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from benchmark import edit_histories


class WorkloadTests(unittest.TestCase):
    def test_partial_rewind_cycle_uses_only_requested_edits(self):
        histories = edit_histories('w' * 4080, 'rewind', 1)
        self.assertEqual([len(history) for history in histories], [4096])

    def test_repeated_patterns_do_not_grow_with_edit_count(self):
        histories = edit_histories('w' * 4092, 'tail', 32)
        self.assertEqual(max(map(len, histories)), 4096)
        self.assertEqual(histories[:8], histories[8:16])

    def test_append_history_grows_by_one_each_edit(self):
        self.assertEqual(edit_histories('jf', 'append', 3), ['jfw', 'jfww', 'jfwww'])
