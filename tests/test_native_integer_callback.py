"""Native captured-boundary regressions for geometric rows and integer transfer.
The fixtures contain no native DLL or runtime dependency. Upstream captured
inputs are explicit; final native arrays are comparison oracles only.
"""
import json
from pathlib import Path
import sys
import unittest
import numpy as np
from scipy import sparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'engine/targets/zbrush/experiments/python'))
from recovered_integer_geometric_rows import policy
from recovered_torus_integer_geometric_rows import policy as torus_policy
from recovered_unit_constraint_elimination import eliminate_unit
from recovered_integer_substitution import substitute
from recovered_integer_transfer import compress, transfer
from recovered_integer_system import solve

FIXTURES = ROOT / 'tests/fixtures/native_integer'


class NativeIntegerRegressions(unittest.TestCase):
    def test_mixed_policy_native_branch_boundaries(self):
        self.assertIs(policy, torus_policy)
        # Native candidate8 on the real rim: d <= c < 2d is still soft.
        for first, second, delta in [(True, False, 2.), (False, True, -2.)]:
            self.assertEqual(policy(first, second, delta, 3.), (delta, 1., False, True))
        self.assertEqual(policy(True, False, 2., 4.), (2., 1., False, False))
        self.assertEqual(policy(True, False, 4.5, 1.), (4.5, 1., False, False))
        self.assertEqual(policy(True, False, .5, .7), (1., 1., False, True))
        self.assertEqual(policy(True, True, .5, .7), (1., 1., True, False))
        self.assertEqual(policy(True, True, 2., 1.), (2., 1., False, True))

    def test_mode2_native_constant_only_rows_and_nonunit_guard(self):
        # RVA0x28935b..0x2893b1 advances rows with no eligible scalar.
        self.assertEqual(eliminate_unit([[[2, -1.]]], 2), [])
        self.assertEqual(eliminate_unit([[[0, 1.], [1, -1.]], [[2, -1.]]], 2),
                         [dict(dependent=0, terms=[[1, 1.]])])
        with self.assertRaisesRegex(ValueError, 'Nonunit scalar pivot'):
            eliminate_unit([[[0, 2.], [1, -3.]]], 2)

    def test_native_geometric_rows_targets_and_constraints(self):
        for name in ['ellipsoid-v59', 'island6-200']:
            with self.subTest(fixture=name):
                f = json.loads((FIXTURES / (name + '.json')).read_text())['policy']
                rows, weights, targets, constraints = [], [], [], []
                pins = set(f['gaugeScalars'])
                for c in f['candidates']:
                    target, weight, hard, soft = policy(c['firstGuide'], c['secondGuide'],
                                                        c['delta'], c['cross'])
                    if hard or soft:
                        self.assertIsNotNone(c['integral'])
                        if np.float32(c['integral'] * np.float32(c['delta'])) < 0:
                            target = -target
                    a, b = c['scalars']
                    row = [t for t in [[b, 1.], [a, -1.]] if t[0] not in pins]
                    if hard:
                        if len(row) > 1:
                            constraints.append(sorted(row))
                    else:
                        rows.append(row); weights.append(weight); targets.append(target)
                        if soft:
                            aux = sorted([[i, v * (1 if target > 0 else -1)] for i, v in row])
                            aux.append([f['constant'] + c['index'] + 1, -1.])
                            if len(aux) > 1:
                                constraints.append(aux)
                self.assertEqual(rows, f['expectedRows'])
                self.assertEqual(weights, f['expectedWeights'])
                self.assertEqual(targets, f['expectedTargets'])
                self.assertEqual(constraints, f['expectedConstraintPrefix'])

    def test_native_complete_nested_solve_and_outer_fix_transfer(self):
        for name in ['ellipsoid-v59', 'island6-200']:
            with self.subTest(fixture=name):
                f = json.loads((FIXTURES / (name + '.json')).read_text())['callback']
                constant, dimension = f['constant'], f['dimension']
                deps = eliminate_unit(f['augmentedRows'], constant)
                self.assertEqual(deps, f['expectedDependencies'])
                dependency_map = [-1] * dimension
                for i, d in enumerate(deps):
                    dependency_map[d['dependent']] = i
                rows = substitute(f['initialReducedRows'], deps, dependency_map,
                                  [0, -1, -1, -1, -1])
                weights, targets = list(f['initialWeights']), list(f['initialTargets'])
                for i, row in enumerate(rows):
                    targets[i] += sum(v for c, v in row if c == constant)
                rows = [[t for t in row if t[0] != constant] for row in rows]
                rows, forward, inverse = compress(rows, dimension)
                regularization = dict(f['regularizationTargetsByOriginal'])
                self.assertEqual(set(inverse), set(regularization))
                for original, reduced in enumerate(forward):
                    if reduced >= 0:
                        rows.append([[reduced, 1.]])
                        weights.append(9.999999747378752e-5)
                        targets.append(regularization[original])
                self.assertEqual(rows, f['expectedRows'])
                self.assertEqual(weights, f['expectedWeights'])
                self.assertEqual(targets, f['expectedTargets'])
                originals = f['outerOriginalScalars']
                indices = [forward[v] for v in originals if forward[v] >= 0]
                indices += [forward[v] for v in range(constant, dimension) if forward[v] >= 0]
                rr, cc, vv = [], [], []
                for i, row in enumerate(rows):
                    for c, value in row:
                        rr.append(i); cc.append(c); vv.append(value)
                matrix = sparse.csr_matrix((vv, (rr, cc)), shape=(len(rows), len(inverse)))
                result = solve(matrix, np.asarray(weights), np.asarray(targets), indices,
                               [], inverse, constant + 1, f['budget'])
                self.assertEqual(result['solution'].tolist(), f['expectedSolution'])
                # List positions are the transfer identity; reduced outer numbering
                # is compacted here without changing its ordered original scalars.
                positions, values = transfer(result['solution'], list(range(len(originals))),
                                              originals, forward, deps, dependency_map, constant, [])
                self.assertEqual(positions, f['expectedFixPositions'])
                self.assertEqual(values, f['expectedFixValues'])


if __name__ == '__main__':
    unittest.main()
