import { test } from 'node:test';
import assert from 'node:assert/strict';
import { creaseNormals } from '../src/geometry/CreaseNormals.js';

test('a right-angle corner keeps separate normals and exact source positions', () => {
  const v = [[0, 0, 0], [1, 0, 0], [0, 1, 0], [0, 0, 1]], ids = [0, 1, 2, 1, 0, 3];
  const { positions, normals } = creaseNormals(v, ids);
  assert.deepEqual([...positions], ids.flatMap(i => v[i]));
  assert.deepEqual([...normals.slice(0, 3)], [0, 0, 1]);
  assert.deepEqual([...normals.slice(9, 12)], [0, 1, 0]);
});

test('a shallow shared edge smooths; coincident disconnected triangles stay separate', () => {
  const v = [[0, 0, 0], [1, 0, 0], [0, 1, 0], [0, -1, .2], [0, 0, 0], [0, 0, 1], [1, 0, 0]];
  const { normals } = creaseNormals(v, [0, 1, 2, 1, 0, 3, 4, 5, 6]);
  assert.deepEqual([...normals.slice(0, 3)], [...normals.slice(12, 15)]);
  assert.ok(normals[1] > 0 && normals[2] > .9);
  assert.deepEqual([...normals.slice(18, 21)], [0, 1, 0]);
});
