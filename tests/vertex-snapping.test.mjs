import test from 'node:test';
import assert from 'node:assert/strict';
import { GuideSnap } from '../src/snapping/GuideSnap.js';
import { VertexSnapIndex } from '../src/snapping/VertexSnapIndex.js';
import { buildVertexProjection } from '../src/snapping/VertexProjection.js';

const identity = [1,0,0,0, 0,1,0,0, 0,0,1,0, 0,0,0,1];
test('vertex projection uses CSS pixels and excludes offscreen/depth-clipped vertices', () => {
  const p = buildVertexProjection([0,0,0, 1,1,0, -1,-1,0, 2,0,0, 0,0,2], identity, 200, 100);
  assert.deepEqual([...p.screen.slice(0,9)], [100,50,0, 200,0,0, 0,100,0]);
  assert.ok([...p.screen.slice(9)].every(Number.isNaN));
  assert.equal([...p.bins.values()].flat().length, 3);
});
test('points behind the perspective camera are excluded', () => {
  const matrix = [...identity]; matrix[15] = -1;
  assert.equal(buildVertexProjection([0,0,0], matrix, 200, 100).bins.size, 0);
});
test('worker coalesces camera updates and never exposes stale or foreign-source candidates', () => {
  const sent = [], worker = { postMessage: d => sent.push(d), terminate() {} };
  const index = new VertexSnapIndex(() => {}, () => worker);
  index.setSource([[0,0,0]], 1);
  const view = key => ({ key, matrix: identity, width: 200, height: 100 });
  index.update(view('a')); index.update(view('b')); index.update(view('c'));
  assert.equal(sent.filter(d => d.type === 'project').length, 1);
  const response = (key, sourceKey) => worker.onmessage({ data: { key, sourceKey, ...buildVertexProjection([0,0,0], identity, 200, 100) } });
  response('a', 1); assert.equal(index.ready, false); assert.equal(sent.at(-1).key, 'c');
  response('c', 1); assert.deepEqual(index.nearby(107, 50), [{ vertexId: 0, distance: 7 }]);
  index.update(view('d')); assert.deepEqual(index.nearby(100,50), []);
  index.setSource([[.5,0,0]], 2); index.update(view('new'));
  response('d', 1); assert.equal(index.ready, false); assert.equal(sent.at(-1).sourceKey, 2);
});
test('mesh vertex snap commits exact coordinates, retains hysteresis and respects Alt/toggles', () => {
  let enabled = true, stamp = 0, d = 7;
  const point = [.123456789, .2, .3];
  const snap = new GuideSnap({ surface: () => [1,2,3], stamp: () => stamp,
    enabled: () => false, verticesEnabled: () => enabled,
    vertices: () => [{ vertexId: 3, position: point, distance: d }], guides: () => [] });
  assert.deepEqual(snap.resolve(0,0,0), point); assert.equal(snap.marker.kind, 'vertex');
  d = 11; assert.deepEqual(snap.resolve(0,0,0), point);
  stamp++; assert.deepEqual(snap.resolve(0,0,0), [1,2,3]);
  d = 7; snap.resolve(0,0,0); assert.deepEqual(snap.resolve(0,0,0,{bypass:true}),[1,2,3]); assert.equal(snap.marker,null);
  enabled = false; assert.deepEqual(snap.resolve(0,0,0), [1,2,3]);
});
test('guide and vertex candidates share distance ranking and excluded guides stay excluded', () => {
  const snap = new GuideSnap({ surface: () => [10,10,0], stamp: () => 'a', enabled: () => true,
    verticesEnabled: () => true, vertices: () => [{ vertexId: 1, position: [2,0,0], distance: 2 }],
    guides: () => [{ id:'g', points:[{id:'p',position:[1,0,0]}] }],
    project: p => ({x:p[0], y:p[1]}), visible: () => true });
  assert.deepEqual(snap.resolve(0,0,0), [1,0,0]); snap.clear();
  assert.deepEqual(snap.resolve(0,0,0,{excluded:['g']}), [2,0,0]);
});
