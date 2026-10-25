"""Target invariants and artifact ownership for bounded layout retries."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'engine/targets/zbrush/clone'), str(ROOT / 'engine/targets/zbrush/experiments/python')]
import surface_guide_repair as repair


class LayoutRetryTests(unittest.TestCase):
    def test_all_supported_targets_have_bounded_unique_layout_counts(self):
        for target in range(150, 1801):
            candidates = repair.layout_targets(target)
            self.assertEqual(candidates[0], target)
            self.assertLessEqual(len(candidates), 4)
            self.assertEqual(len(candidates), len(set(candidates)))
            self.assertTrue(all(isinstance(c, int) and abs(c - target) <= .15 * target for c in candidates))
        self.assertIn(1800, repair.layout_targets(1799))
        self.assertIn(660, repair.layout_targets(600))

    def run_construct(self, folder, implementation):
        source, curves, history = object(), [], []
        with patch.object(repair, '_construct_layout', side_effect=implementation) as call:
            result = repair.construct(source, curves, target=600, job=folder, blender=Path('blender'),
                                      input_path=folder / 'input.json', history=history)
        for args in call.call_args_list:
            self.assertIs(args.args[0], source)
            self.assertIs(args.args[1], curves)
            self.assertEqual(args.kwargs['target'], 600)
        return result, call.call_count, history

    def test_first_success_preserves_result_and_avoids_further_layouts(self):
        accepted = object()
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            result, count, _ = self.run_construct(folder, lambda *args, **kwargs: accepted)
            self.assertIs(result, accepted)
            self.assertEqual(count, 1)
            record = json.loads((folder / 'nearby-layout-attempts.json').read_text())
            self.assertEqual(len(record['attempts']), 1)
            self.assertTrue(record['attempts'][0]['accepted'])

    def test_retries_preserve_requested_target_and_separate_diagnostics(self):
        accepted = object()
        def attempt(*args, **kwargs):
            folder, count = kwargs['job'], kwargs['layout_target']
            self.assertFalse((folder / 'joint-guide-repair.json').exists())
            (folder / 'quadri-layout-2.json').write_text(str(count))
            (folder / 'joint-guide-repair.json').write_text(str(count))
            kwargs['history'].append(dict(layout=count))
            return accepted if count == 660 else None
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            result, count, history = self.run_construct(folder, attempt)
            self.assertIs(result, accepted)
            self.assertEqual(count, 3)
            self.assertEqual(history, [dict(layout=n) for n in (600, 630, 660)])
            for n in (600, 630, 660):
                self.assertEqual((folder / f'sampled-layout-{n}/quadri-layout-2.json').read_text(), str(n))
            self.assertEqual((folder / 'quadri-layout-2.json').read_text(), '660')
            rows = json.loads((folder / 'nearby-layout-attempts.json').read_text())['attempts']
            self.assertEqual([r['firstHistoryIndex'] for r in rows], [0, 1, 2])
            self.assertEqual([r['accepted'] for r in rows], [False, False, True])

    def test_total_failure_keeps_final_candidate_and_all_prior_artifacts(self):
        def attempt(*args, **kwargs):
            (kwargs['job'] / 'failed-sampled-guide-candidate.json').write_text(str(kwargs['layout_target']))
            return None
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            result, count, _ = self.run_construct(folder, attempt)
            self.assertIsNone(result)
            self.assertEqual(count, 3)
            self.assertEqual((folder / 'failed-sampled-guide-candidate.json').read_text(), '660')
            for n in (600, 630, 660):
                self.assertEqual((folder / f'sampled-layout-{n}/failed-sampled-guide-candidate.json').read_text(), str(n))

    def test_execution_error_propagates_without_trying_another_layout(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(repair, '_construct_layout', side_effect=RuntimeError('interrupted')) as call:
                with self.assertRaisesRegex(RuntimeError, 'interrupted'):
                    repair.construct(object(), [], target=600, job=Path(directory), blender=Path('blender'),
                                     input_path=Path(directory) / 'input.json', history=[])
            self.assertEqual(call.call_count, 1)


if __name__ == '__main__':
    unittest.main()
