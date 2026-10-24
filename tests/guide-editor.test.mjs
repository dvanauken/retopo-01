import test from 'node:test';
import assert from 'node:assert/strict';
import { GuideDocument } from '../src/domain/GuideDocument.js';
import { fromPositions, fromCircle, editPoints, makeGuide, evaluate, flatten } from '../src/geometry/GuideCurve.js';
import { encodeGuides, decodeGuides } from '../src/io/GuideSerializer.js';
import { GuideController } from '../src/view/GuideController.js';
import { GuideSnap } from '../src/snapping/GuideSnap.js';
import { readdirSync, readFileSync } from 'node:fs';

let next = 0;
const id = () => 'id-' + ++next;
const guide = (type = 'polyline') => fromPositions([[0, 0, 0], [1, 1, 0], [2, 0, 0]], type, false, id);
const moved = g => makeGuide({ ...g, points: g.points.map(p => ({ ...p, position: p.position.map(v => v + 1) })) });

test('atomic stale multi-edit leaves all values, revisions and history untouched', () => {
  const d = new GuideDocument(id), a = guide(), b = guide(); d.load([a, b]);
  d.execute('External edit', [a, moved(b)], [{ id: b.id, revision: 0 }]);
  const before = JSON.stringify(d.guides), history = d.history;
  assert.throws(() => d.execute('Stale edit', [moved(a), moved(b)], [{ id: a.id, revision: 0 }, { id: b.id, revision: 0 }]), /changed during/);
  assert.equal(JSON.stringify(d.guides), before); assert.deepEqual(d.history, history); assert.equal(d.revision(a.id), 0);
});
test('undo/redo restore authored IDs and values while revisions keep advancing', () => {
  const d = new GuideDocument(id), g = guide(); d.load([g]);
  d.execute('Move', [moved(g)], [{ id: g.id, revision: 0 }]);
  d.moveHistory(-1); assert.deepEqual(d.guides, [g]); assert.equal(d.revision(g.id), 2);
  d.moveHistory(1); assert.equal(d.revision(g.id), 3);
  d.execute('Delete', []); d.moveHistory(-1); assert.equal(d.get(g.id).points[0].id, g.points[0].id); assert.equal(d.revision(g.id), 5);
});
test('equal results preserve the redo branch and publish nothing', () => {
  const d = new GuideDocument(id), g = guide(); d.load([g]); d.execute('Move', [moved(g)]); d.moveHistory(-1);
  let changes = 0; d.subscribe(() => changes++);
  assert.equal(d.execute('No motion', [g]), false); assert.equal(changes, 0); assert.equal(d.history.length, 1); assert.equal(d.history.index, 0);
  assert.equal(d.moveHistory(1), true);
});
test('load starts an epoch and old authorization cannot modify it', () => {
  const d = new GuideDocument(id), g = guide(); d.load([g]); const epoch = d.epoch;
  d.load([g]); assert.throws(() => d.execute('Late edit', [moved(g)], [], epoch), /document changed/); assert.equal(d.generation, 0);
});
test('invalid second target and duplicate identities cannot partially install', () => {
  const d = new GuideDocument(id), g = guide(); d.load([g]);
  assert.throws(() => d.execute('Bad', [moved(g), { ...guide(), points: [] }]));
  assert.throws(() => d.execute('Duplicates', [g, g])); assert.deepEqual(d.guides, [g]); assert.equal(d.history.length, 0);
});
test('closed guides have distinct authored points and derive a closing sample only', () => {
  const g = fromPositions([[0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 0, 0]], 'polyline', false, id, { detectClosure: true });
  assert.equal(g.closed, true); assert.equal(g.points.length, 3); assert.equal(flatten(g).length, 4);
});
test('surface spline interpolates fit points, handles coincidences and reverses its locus', () => {
  const g = guide('spline');
  for (let i = 0; i < 3; i++) assert.ok(evaluate(g, i).every((v, k) => Math.abs(v - g.points[i].position[k]) < 1e-12));
  const r = makeGuide({ ...g, points: [...g.points].reverse() });
  for (let t = 0; t <= 2; t += .05) assert.ok(evaluate(g, t).every((v, k) => Math.abs(v - evaluate(r, 2 - t)[k]) < 1e-10));
  const repeated = fromPositions([[0, 0, 0], [0, 0, 0], [1, 1, 0]], 'spline', false, id);
  assert.ok(flatten(repeated).flat().every(Number.isFinite));
  assert.throws(() => flatten(g, { maxSamples: 2 }), /sample-budget-exceeded/);
});
test('native write/read/write preserves authored bytes and rejects foreign sources/versions', () => {
  const d = new GuideDocument(id); d.load([guide('spline')]);
  const bytes = encodeGuides(d, 'source-A', d.guides.map(g => flatten(g)));
  const read = decodeGuides(JSON.parse(bytes), 'source-A', id), e = new GuideDocument(id); e.load(read);
  assert.equal(encodeGuides(e, 'source-A', e.guides.map(g => flatten(g))), bytes);
  assert.throws(() => decodeGuides(JSON.parse(bytes), 'source-B', id), /different source/);
  assert.throws(() => decodeGuides({ ...JSON.parse(bytes), schemaVersion: 4 }, 'source-A', id), /Unsupported/);
});

function host() {
  const d = new GuideDocument(id), captures = new Set(), errors = [];
  const ports = { id, changed() {}, report: m => errors.push(m), busy: () => false, closed: () => false,
    pane: () => 0, surface: (x, y) => x < 0 ? null : [x, y, 0], project: p => ({ x: p[0], y: p[1] }),
    cameraRevision: () => 0, curve: flatten, hit: () => null, contained: () => [], showGuides() {}, screenDistance: (a, b) => Math.hypot(a[0] - b[0], a[1] - b[1]),
    capture: p => { captures.add(p); return true; }, release: p => captures.delete(p),
  };
  return { d, c: new GuideController(d, ports), captures, errors };
}
const pointer = (x, y = 0, pointerId = 1) => ({ x, y, button: 0, pointerId, shift: false, time: 0 });
test('pointer cancellation discards all staged fragments and releases capture', () => {
  const { d, c, captures } = host(); c.down(pointer(0)); c.move(pointer(5)); c.move(pointer(-5)); c.move(pointer(3));
  assert.equal(d.guides.length, 0); c.cancelPointer(1); assert.equal(d.guides.length, 0); assert.equal(d.history.length, 0); assert.equal(captures.size, 0);
});
test('release movement is included and all freehand fragments form one undo unit', () => {
  const { d, c } = host(); c.down(pointer(0)); c.move(pointer(5)); c.move(pointer(-5)); c.move(pointer(3)); c.up(pointer(6));
  assert.equal(d.guides.length, 2); assert.equal(d.guides.at(-1).points.at(-1).position[0], 6); assert.equal(d.history.length, 1);
  c.history(-1); assert.equal(d.guides.length, 0);
});
test('temporary navigation preserves pointer-free construction; Escape discards it', () => {
  const { c, d } = host(); c.activate('spline'); c.down(pointer(0)); c.down(pointer(2)); const activity = c.observe().activityId;
  c.navigate(true); c.navigate(false); assert.equal(c.observe().activityId, activity); c.escape(); assert.equal(c.observe().activityId, null); assert.equal(d.history.length, 0);
});
test('snapping uses acquire/release hysteresis, invalidates stamps and honors Alt bypass', () => {
  const g = guide(); let stamp = 0;
  const snap = new GuideSnap({ surface: (x, y) => [x, y, 0], project: p => ({ x: p[0], y: p[1] }), enabled: () => true, guides: () => [g], visible: () => true, stamp: () => stamp });
  assert.deepEqual(snap.resolve(-7, 0, 0), [0, 0, 0]);
  assert.deepEqual(snap.resolve(-11, 0, 0), [0, 0, 0]);
  stamp++; assert.deepEqual(snap.resolve(-11, 0, 0), [-11, 0, 0]);
  snap.resolve(-7, 0, 0); assert.deepEqual(snap.resolve(-7, 0, 0, { bypass: true }), [-7, 0, 0]); assert.equal(snap.marker, null);
  assert.deepEqual(snap.resolve(-7, 0, 0, { excluded: [g.id] }), [-7, 0, 0]);
});
test('guide records reject sparse points, accessors and unadvertised fields', () => {
  const g = guide(), sparse = new Array(3); sparse[0] = 0;
  assert.throws(() => makeGuide({ ...g, points: [{ id: 'p', position: sparse }, ...g.points.slice(1)] }), /Sparse/);
  assert.throws(() => makeGuide({ ...g, surprise: true }), /Unexpected/);
  assert.throws(() => makeGuide({ ...g, get closed() { throw new Error('getter executed'); } }), /Unexpected/);
});
test('open guide endpoint coincidence does not silently become authored closure', () => {
  const g = fromPositions([[0, 0, 0], [1, 0, 0], [0, 0, 0]], 'polyline', false, id);
  assert.equal(g.closed, false); assert.equal(g.points.length, 3);
});
test('editing an owned direct point retains the other selected guide IDs', () => {
  const { c, d } = host(), a = guide(), b = guide(); d.load([a, b]);
  c.choose(a.id); c.choose(b.id, true); c.model('direct');
  c.ports.hit = () => ({ guideId: a.id, pointId: a.points[0].id });
  c.down(pointer(0)); c.move(pointer(7)); c.up(pointer(7));
  assert.deepEqual(c.selection.entityIds, [a.id, b.id]); assert.equal(c.selection.activeEntityId, a.id);
  assert.notDeepEqual(d.get(a.id), a); assert.deepEqual(d.get(b.id), b);
});
test('module imports obey the guide subsystem dependency boundaries', () => {
  const allowed = { contracts: [], geometry: ['contracts'], domain: ['contracts', 'geometry'], io: ['contracts', 'geometry', 'domain'], snapping: ['contracts', 'geometry', 'domain'], view: ['contracts', 'geometry', 'domain', 'snapping'] };
  for (const [folder, imports] of Object.entries(allowed)) for (const file of readdirSync(new URL('../src/' + folder, import.meta.url))) {
    if (!file.endsWith('.js')) continue;
    const source = readFileSync(new URL('../src/' + folder + '/' + file, import.meta.url), 'utf8');
    for (const match of source.matchAll(/from\s+['"]\.\.\/([^/]+)\//g)) assert.ok(imports.includes(match[1]), `${folder}/${file} imports ${match[1]}`);
    if (['geometry', 'domain', 'contracts'].includes(folder)) assert.doesNotMatch(source, /\b(document|window|localStorage|requestAnimationFrame|THREE|crypto)\s*\./);
  }
});
test('rejection is reported only after the controller gate closes and native capture releases', () => {
  const { c, captures } = host(); let observed = 0;
  c.ports.report = () => { assert.equal(c.gate, false); assert.equal(captures.size, 0); observed++; };
  c.down(pointer(0)); c.move(pointer(5)); c.navigate(true);
  assert.equal(observed, 0); assert.equal(captures.size, 1);
  c.escape(); assert.equal(observed, 1); assert.equal(captures.size, 0);
});
test('returning within exactly 5 CSS pixels closes the clicked loop without a duplicate point', () => {
  const { c, d } = host(); c.activate('polyline');
  for (const [x, y] of [[10, 10], [60, 10], [60, 60], [10, 60]]) c.down(pointer(x, y));
  c.move(pointer(15.01, 10)); assert.equal(c.closureSnap, null);
  c.move(pointer(15, 10)); assert.deepEqual(c.closureSnap.position, [10, 10, 0]); assert.equal(c.constructionGuide.closed, true);
  c.down(pointer(15, 10)); assert.equal(d.guides[0].closed, true); assert.equal(d.guides[0].points.length, 4); assert.equal(d.history.length, 1); assert.equal(c.construction, null);
});
test('freehand proximity closure works without the close-stroke checkbox', () => {
  const { c, d } = host(); c.down(pointer(10, 10));
  for (const [x, y] of [[60, 10], [60, 60], [10, 60], [14, 10]]) c.move(pointer(x, y));
  assert.ok(c.closureSnap); c.up(pointer(14, 10)); assert.equal(d.guides[0].closed, true);
  assert.notDeepEqual(d.guides[0].points[0].position, d.guides[0].points.at(-1).position);
});
test('Circle preserves its analytic center, radius, plane and semantic edit roles through IO and history', () => {
  const g = fromCircle([0, 0, 1], [.64, 0, 1], [0, 0, 1], id), d = new GuideDocument(id); d.load([g]);
  assert.equal(g.type, 'circle'); assert.equal(g.points.length, 1); assert.equal(g.radius, .64);
  const samples = flatten(g); assert.deepEqual(samples[0], samples.at(-1));
  assert.ok(samples.every(p => Math.abs(Math.hypot(p[0], p[1]) - .64) < 1e-12 && p[2] === 1));
  assert.deepEqual(editPoints(g).map(p => p.role), ['center', 'radius']);
  const encoded = encodeGuides(d, 'source', [samples]);
  assert.deepEqual(decodeGuides(JSON.parse(encoded), 'source', id), [g]);
  d.execute('Radius', [makeGuide({ ...g, radius: .7 })]); d.moveHistory(-1); assert.deepEqual(d.guides, [g]);
  assert.throws(() => fromCircle([0, 0, 0], [0, 0, 0], [0, 0, 1], id), /radius/);
});
test('version 2 guide files migrate while Circle requires version 3', () => {
  const d = new GuideDocument(id); d.load([guide()]); const old = { ...JSON.parse(encodeGuides(d, 'source', [])), schemaVersion: 2 };
  assert.deepEqual(decodeGuides(old, 'source', id), d.guides);
  old.guides = [fromCircle([0, 0, 0], [1, 0, 0], [0, 0, 1], id)]; assert.throws(() => decodeGuides(old, 'source', id), /version 3/);
});
