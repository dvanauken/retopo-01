import test from 'node:test';
import assert from 'node:assert/strict';
import { PartsDocument, assemblyOBJ } from '../src/domain/PartsDocument.js';
const source = { id: 'toilet', title: 'Toilet', sourceSha256: 'source' };
const model = n => ({ partSource: n.repeat(64), repair: { closed: true } });

test('multi-part inclusion is one reversible command; failure rolls back and outputs survive undo', () => {
  const mesh = { ...source, initialParts: ['a', 'b', 'c'].map(id => ({ id, name: id, partSource: id.repeat(64), excluded: false, closed: false })) };
  const doc = new PartsDocument(mesh);
  doc.edit('Keep a', () => { doc.exclude('b'); doc.exclude('c'); });
  assert.equal(doc.editIndex, 1);
  doc.data.nodes.b.result = { job: 'later-output' };
  doc.moveEdit(-1); assert.ok(doc.leaves().every(p => !p.excluded));
  assert.equal(doc.data.nodes.b.result.job, 'later-output');
  doc.moveEdit(1); assert.deepEqual(doc.leaves().filter(p => p.excluded).map(p => p.id), ['b', 'c']);
  assert.throws(() => doc.edit('Invalid', () => { doc.rename('a', 'changed'); doc.rename('b', ''); }));
  assert.equal(doc.data.nodes.a.name, 'a'); assert.equal(doc.editIndex, 1);
  doc.moveEdit(-1); doc.edit('Rename', () => doc.rename('a', 'Seat'));
  assert.equal(doc.moveEdit(1), false); assert.equal(doc.data.nodes.a.name, 'Seat');
});

test('imported source parts survive split, undo and project roundtrip', () => {
  const mesh = { ...source, initialParts: ['a', 'b', 'c'].map(id => ({ id, name: id, partSource: id.repeat(64), excluded: false, closed: true })) };
  const doc = new PartsDocument(mesh, null, () => crypto.randomUUID());
  assert.equal(doc.leaves().length, 3);
  assert.equal(doc.undoSplit(), null);
  doc.split('a', model('d'), model('e'), 'Subpart', false);
  doc.validate();
  assert.equal(new PartsDocument(mesh, JSON.parse(JSON.stringify(doc.data))).leaves().length, 4);
  doc.undoSplit(); doc.validate();
  assert.deepEqual(doc.leaves().map(p => p.id), ['a', 'b', 'c']);
  doc.data.nodes.original.children.reverse();
  assert.throws(() => doc.validate(), /Invalid split/);
});
test('independent output survives a sibling split, exclusion and undo', () => {
  const doc = new PartsDocument(source, null, () => crypto.randomUUID()), part = doc.split('original', model('a'), model('b'), 'Lid', false);
  part.result = { job: 'accepted-lid' }; const other = doc.leaves().find(n => n.id !== part.id);
  doc.split(other.id, model('c'), model('d'), 'Handle', true);
  assert.equal(doc.leaves().length, 3); assert.equal(part.result.job, 'accepted-lid');
  doc.exclude(part.id); doc.exclude(part.id); assert.equal(part.result.job, 'accepted-lid');
  doc.undoSplit(); assert.equal(doc.leaves().length, 2); assert.equal(part.result.job, 'accepted-lid');
  const roundtrip = new PartsDocument(source, JSON.parse(JSON.stringify(doc.data))); assert.equal(roundtrip.leaves().length, 2);
});
test('invalid source and cyclic project are rejected; open exclusion has explicit restore', () => {
  const doc = new PartsDocument(source, null, () => crypto.randomUUID()); const open = model('c'); open.repair.closed = false;
  doc.split('original', open, model('d'), 'Handle', true);
  assert.throws(() => doc.exclude(doc.leaves().find(n => n.excluded).id), /Undo split/);
  assert.throws(() => new PartsDocument({ ...source, sourceSha256: 'different' }, doc.data));
  doc.data.nodes.original.children = ['original', 'original']; assert.throws(() => doc.validate());
});
test('assembly export offsets faces and preserves shared frame without merging objects', () => {
  const mesh = { vertices: [[2,3,4],[3,3,4],[2,4,4]], faces: [[0,1,2]] };
  const text = assemblyOBJ([{ name: 'Lid\no bad', mesh, generated: true }, { name: 'Tank', mesh, generated: false }]);
  assert.match(text, /f 1 2 3/); assert.match(text, /f 4 5 6/); assert.equal((text.match(/^o /gm) || []).length, 2); assert.match(text, /v 2 3 4/);
});
