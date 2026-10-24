import * as THREE from 'three';
import { OrbitControls } from 'three/addons/OrbitControls.js';

const $ = id => document.getElementById(id);
const clone = value => JSON.parse(JSON.stringify(value));
const state = { mesh: null, result: null, guides: [], tool: 'draw', view: 'split', history: [[]], historyIndex: 0, selected: -1, target: 600, guideMode: 2, busy: false, job: null, resultJob: null, dirty: false, space: false, version: 0, resultKey: null, density: null };
const canvas = $('viewport');
const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: false, preserveDrawingBuffer: true });
renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
renderer.outputColorSpace = THREE.SRGBColorSpace;
const scenes = [new THREE.Scene(), new THREE.Scene()];
const camera = new THREE.PerspectiveCamera(38, 1, .01, 100);
camera.up.set(0, 0, 1);
const controls = new OrbitControls(camera, canvas);
controls.enableDamping = true; controls.dampingFactor = .12;
controls.minDistance = .6; controls.maxDistance = 18; controls.enabled = false;
const sourceGroup = new THREE.Group(), resultGroup = new THREE.Group();
const guideGroups = [new THREE.Group(), new THREE.Group()];
scenes[0].add(sourceGroup, guideGroups[0]); scenes[1].add(resultGroup, guideGroups[1]);
for (const scene of scenes) {
  scene.add(new THREE.HemisphereLight(0xffffff, 0x627180, 2.0));
  const key = new THREE.DirectionalLight(0xffffff, 3.0); key.position.set(-3, -4, 7); scene.add(key);
  const fill = new THREE.DirectionalLight(0xffffff, .7); fill.position.set(4, 2, 1); scene.add(fill);
}
const raycaster = new THREE.Raycaster();
let sourceRender = null, resultRender = null, grids = [], draft = [], pointer = null, previousScreen = null, drawingPane = 0, generation = 0, noticeTimer;
const css = name => getComputedStyle(document.documentElement).getPropertyValue(name).trim();
const color = name => new THREE.Color(css(name));
const samePoint = (a, b) => a && b && a.every((x, i) => Math.abs(x - b[i]) < 1e-8);
const keyFor = () => JSON.stringify([state.mesh?.id, state.guides, state.target, state.guideMode]);
const countText = n => n.toLocaleString();

async function api(url, options) {
  const response = await fetch(url, options); const data = await response.json();
  if (!response.ok) throw new Error(data.error || 'The local service did not complete the request.');
  return data;
}
function notify(message, error = false, persistent = false) {
  clearTimeout(noticeTimer); $('noticeText').textContent = message; $('notice').classList.toggle('error', error); $('notice').hidden = false;
  if (!persistent) noticeTimer = setTimeout(() => $('notice').hidden = true, 7000);
}
$('dismissNotice').onclick = () => { $('notice').hidden = true; };
function dispose(group) {
  for (const child of [...group.children]) {
    group.remove(child); child.traverse(o => { o.geometry?.dispose(); if (Array.isArray(o.material)) o.material.forEach(m => m.dispose()); else o.material?.dispose(); });
  }
}
function edgePositions(vertices, faces) {
  const seen = new Set(), coordinates = [];
  for (const face of faces) for (let j = 0; j < face.length; j++) {
    const a = face[j], b = face[(j + 1) % face.length], key = a < b ? `${a}:${b}` : `${b}:${a}`;
    if (!seen.has(key)) { seen.add(key); coordinates.push(...vertices[a], ...vertices[b]); }
  }
  return coordinates;
}
function lineSegments(coordinates, materialColor, opacity = 1) {
  const geometry = new THREE.BufferGeometry(); geometry.setAttribute('position', new THREE.Float32BufferAttribute(coordinates, 3));
  return new THREE.LineSegments(geometry, new THREE.LineBasicMaterial({ color: materialColor, transparent: opacity < 1, opacity }));
}
function buildMesh(data, group) {
  dispose(group); const geometry = new THREE.BufferGeometry();
  geometry.setAttribute('position', new THREE.Float32BufferAttribute(data.vertices.flat(), 3));
  const triangles = [];
  for (const face of data.faces) for (let j = 1; j < face.length - 1; j++) triangles.push(face[0], face[j], face[j + 1]);
  geometry.setIndex(triangles); geometry.computeVertexNormals();
  const material = new THREE.MeshStandardMaterial({ color: color('--model'), roughness: .78, metalness: .08, flatShading: true, side: THREE.DoubleSide, polygonOffset: true, polygonOffsetFactor: 1, polygonOffsetUnits: 1 });
  const solid = new THREE.Mesh(geometry, material); group.add(solid);
  const wire = lineSegments(edgePositions(data.vertices, data.faces), color('--wire'), .75); group.add(wire);
  const creases = lineSegments((data.creases || []).flatMap(([a, b]) => [...data.vertices[a], ...data.vertices[b]]), color('--crease'));
  creases.renderOrder = 2; group.add(creases);
  return { solid, wire, creases };
}
class Polyline extends THREE.Curve {
  constructor(points) { super(); this.points = points.map(p => new THREE.Vector3(...p)); }
  getPoint(t, output = new THREE.Vector3()) {
    const x = Math.min(t, .999999999) * (this.points.length - 1), i = Math.floor(x);
    return output.copy(this.points[i]).lerp(this.points[i + 1], x - i);
  }
}
function renderGuides() {
  for (const group of guideGroups) dispose(group);
  const all = draft.length > 1 ? [...state.guides, draft] : state.guides;
  for (let i = 0; i < all.length; i++) {
    const curve = all[i]; if (curve.length < 2) continue;
    // A straight-segment curve preserves displayed surface attachments; no spline overshoot.
    const tube = new THREE.TubeGeometry(new Polyline(curve), Math.min(2048, Math.max(8, curve.length * 2)), i === state.selected ? .012 : .008, 5, false);
    const material = new THREE.MeshBasicMaterial({ color: color('--guide'), depthTest: true });
    for (const group of guideGroups) {
      const shape = new THREE.Mesh(tube.clone(), material.clone()); shape.renderOrder = 3; group.add(shape);
      if (!samePoint(curve[0], curve.at(-1))) for (const point of [curve[0], curve.at(-1)]) {
        const endpoint = new THREE.Mesh(new THREE.SphereGeometry(.018, 8, 6), material.clone()); endpoint.position.fromArray(point); group.add(endpoint);
      }
    }
    tube.dispose(); material.dispose();
  }
  // A tap starts with a visible point, before there are enough samples for a line.
  if (draft.length === 1) for (const group of guideGroups) {
    const dot = new THREE.Mesh(new THREE.SphereGeometry(.018, 8, 6), new THREE.MeshBasicMaterial({ color: color('--guide') }));
    dot.position.fromArray(draft[0]); group.add(dot);
  }
  for (const group of guideGroups) group.visible = $('guidesToggle').checked;
}
function displaySettings() {
  for (const mesh of [sourceRender, resultRender]) if (mesh) {
    mesh.wire.visible = $('wireToggle').checked; mesh.creases.visible = $('creasesToggle').checked;
  }
  guideGroups.forEach(group => group.visible = $('guidesToggle').checked);
}
function refreshColors() {
  renderer.setClearColor(color('--bg'));
  scenes.forEach(scene => { scene.background = color('--bg'); });
  for (const mesh of [sourceRender, resultRender]) if (mesh) {
    mesh.solid.material.color.copy(color('--model')); mesh.wire.material.color.copy(color('--wire')); mesh.creases.material.color.copy(color('--crease'));
  }
  renderGuides(); buildGrids();
}
function buildGrids() {
  grids.forEach(grid => { grid.parent?.remove(grid); grid.geometry.dispose(); grid.material.dispose(); }); grids = [];
  if (!sourceRender) return;
  const box = new THREE.Box3().setFromObject(sourceRender.solid);
  for (const scene of scenes) {
    const grid = new THREE.GridHelper(8, 32, color('--grid'), color('--grid')); grid.rotation.x = Math.PI / 2; grid.position.z = box.min.z - .045;
    grid.material.transparent = true; grid.material.opacity = .3; scene.add(grid); grids.push(grid);
  }
}
function fit(top = false, preserveDirection = false) {
  if (!sourceRender) return;
  const direction = camera.position.clone().sub(controls.target).normalize();
  const box = new THREE.Box3().setFromObject(sourceRender.solid), center = box.getCenter(new THREE.Vector3()), size = box.getSize(new THREE.Vector3());
  controls.target.copy(center);
  const rect = canvas.getBoundingClientRect(), aspect = rect.width / rect.height / (state.view === 'split' ? 2 : 1);
  const radius = box.getBoundingSphere(new THREE.Sphere()).radius;
  const distance = radius / Math.sin(THREE.MathUtils.degToRad(19)) * Math.max(1, 1 / aspect) * 1.12;
  camera.position.copy(center).addScaledVector(preserveDirection ? direction : top ? new THREE.Vector3(0, -.0001, 1).normalize() : new THREE.Vector3(2.7, -4.2, 3.4).normalize(), distance);
  camera.lookAt(center); controls.update();
}
function setView(view) {
  const changed = state.view !== view; state.view = view; const overlay = view === 'overlay';
  document.querySelectorAll('[data-view]').forEach(button => { button.classList.toggle('active', button.dataset.view === view); button.setAttribute('aria-pressed', button.dataset.view === view); });
  $('divider').hidden = overlay; $('resultCaption').hidden = overlay; $('sourceCaption').style.width = overlay ? '100%' : '50%';
  $('sourceCaption').querySelector('.label').textContent = overlay ? 'Source + retopology' : 'Source';
  (overlay ? scenes[0] : scenes[1]).add(resultGroup);
  guideGroups[1].visible = !overlay && $('guidesToggle').checked;
  if (sourceRender) {
    const material = sourceRender.solid.material; material.transparent = overlay && !!state.result; material.opacity = overlay && state.result ? .25 : 1; material.depthWrite = !overlay || !state.result;
    sourceRender.wire.material.opacity = overlay ? .18 : .75;
  }
  $('resultEmpty').style.display = overlay ? 'none' : '';
  if (changed) fit(false, true);
}
function setTool(tool) {
  state.tool = tool; controls.enabled = tool === 'orbit' || state.space;
  canvas.className = tool;
  document.querySelectorAll('[data-tool]').forEach(button => { const active = button.dataset.tool === tool; button.classList.toggle('active', active); button.setAttribute('aria-pressed', active); });
  $('canvasInstruction').textContent = tool === 'draw' ? 'Click and drag on either mesh to draw a guide. Hold Space to orbit.' : tool === 'erase' ? 'Click near a guide in either view to remove it.' : 'Drag to orbit. Right-drag to pan. Scroll to zoom.';
}
function project(point, pane = 0) {
  const r = canvas.getBoundingClientRect(), width = state.view === 'split' ? r.width / 2 : r.width;
  camera.aspect = width / r.height; camera.updateProjectionMatrix(); camera.updateMatrixWorld();
  const p = new THREE.Vector3(...point).project(camera);
  return { x: r.left + (state.view === 'split' ? pane * width : 0) + (p.x + 1) * width / 2, y: r.top + (1 - p.y) * r.height / 2, z: p.z };
}
function paneAt(x) {
  const r = canvas.getBoundingClientRect();
  return state.view === 'split' && x >= r.left + r.width / 2 ? 1 : 0;
}
function hit(x, y, requiredPane = null) {
  if (!sourceRender) return null;
  const r = canvas.getBoundingClientRect(), w = state.view === 'split' ? r.width / 2 : r.width;
  if (x < r.left || x > r.right || y < r.top || y > r.bottom) return null;
  const pane = paneAt(x);
  if ((requiredPane !== null && pane !== requiredPane) || (pane === 1 && !resultRender)) return null;
  const left = r.left + pane * w;
  camera.aspect = w / r.height; camera.updateProjectionMatrix(); camera.updateMatrixWorld();
  raycaster.setFromCamera(new THREE.Vector2((x - left) / w * 2 - 1, 1 - (y - r.top) / r.height * 2), camera);
  // Both views share the source coordinate frame. Always attach guides to the
  // original source, so a new solve never depends on the previous output mesh.
  return raycaster.intersectObject(sourceRender.solid, false)[0] || null;
}
function persist() {
  if (!state.mesh) return;
  try { localStorage.setItem('retopo-1:' + state.mesh.id, JSON.stringify({ sourceSha256: state.mesh.sourceSha256, curves: state.guides, target: state.target, guideMode: state.guideMode })); } catch { /* Storage is optional. */ }
}
function dirty() {
  state.dirty = state.resultKey !== keyFor();
  if (state.result) { $('resultBadge').hidden = false; $('resultBadge').className = 'badge' + (state.dirty ? '' : ' good'); $('resultBadge').textContent = state.dirty ? 'Needs update' : state.resultJob ? 'Generated' : 'Example'; }
}
function updateGuideUI() {
  $('guideCount').textContent = state.guides.length;
  $('undoButton').disabled = state.historyIndex === 0; $('redoButton').disabled = state.historyIndex >= state.history.length - 1; $('clearButton').disabled = !state.guides.length; $('exportGuides').disabled = !state.mesh;
  const list = $('guideList'); list.replaceChildren();
  if (!state.guides.length) { const empty = document.createElement('div'); empty.className = 'empty-guides'; empty.innerHTML = 'Click and drag on either mesh.<br>Hold Space to turn the view.'; list.append(empty); }
  state.guides.forEach((curve, index) => {
    const row = document.createElement('div'); row.className = 'guide-item' + (state.selected === index ? ' selected' : '');
    const swatch = document.createElement('span'); swatch.className = 'line-swatch';
    const name = document.createElement('span'); name.className = 'name'; name.textContent = `Guide ${index + 1}${samePoint(curve[0], curve.at(-1)) ? ' · closed' : ''}`;
    name.onclick = () => { state.selected = index; updateGuideUI(); renderGuides(); };
    const remove = document.createElement('button'); remove.textContent = '×'; remove.setAttribute('aria-label', 'Delete guide ' + (index + 1)); remove.onclick = () => commit(state.guides.filter((_, i) => i !== index));
    row.append(swatch, name, remove); list.append(row);
  });
  dirty(); renderGuides();
}
function commit(curves) {
  if (curves.length > 48) return notify('Use at most48 curves in this demonstration.', true);
  state.guides = clone(curves); state.history = state.history.slice(0, state.historyIndex + 1); state.history.push(clone(curves));
  if (state.history.length > 51) state.history.shift(); state.historyIndex = state.history.length - 1; state.selected = -1; updateGuideUI(); persist();
}
function historyMove(delta) {
  const next = state.historyIndex + delta; if (next < 0 || next >= state.history.length) return;
  state.historyIndex = next; state.guides = clone(state.history[next]); state.selected = -1; updateGuideUI(); persist();
}
function finishPart(close = false) {
  if (draft.length >= 2) {
    if (close && draft.length >= 4 && !samePoint(draft[0], draft.at(-1))) {
      if (new THREE.Vector3(...draft[0]).distanceTo(new THREE.Vector3(...draft.at(-1))) < .3) draft.push([...draft[0]]);
      else notify('Finish near the starting point to close a stroke. This guide was kept open.');
    }
    const curve = draft; draft = []; commit([...state.guides, curve]);
  } else { draft = []; renderGuides(); }
}
function samplePointer(x, y) {
  const point = hit(x, y, drawingPane);
  if (!point) { if (draft.length) finishPart(false); return; }
  const p = point.point.toArray();
  if (!draft.length || new THREE.Vector3(...p).distanceTo(new THREE.Vector3(...draft.at(-1))) > .001) draft.push(p);
  if (draft.length >= 2046) finishPart(false);
}
canvas.addEventListener('pointerdown', event => {
  if (event.button !== 0 || pointer !== null || state.busy || !state.mesh || state.space || state.tool === 'orbit') return;
  const first = hit(event.clientX, event.clientY);
  if (!first) { if (state.tool === 'draw') notify('Start on a mesh surface, then hold and drag to draw a guide.'); return; }
  event.preventDefault(); canvas.focus();
  drawingPane = paneAt(event.clientX);
  if (state.tool === 'erase') {
    let nearest = -1, distance = 18;
    for (let i = 0; i < state.guides.length; i++) for (const point of state.guides[i]) { const p = project(point, drawingPane), d = Math.hypot(p.x - event.clientX, p.y - event.clientY); if (d < distance) { distance = d; nearest = i; } }
    if (nearest >= 0) commit(state.guides.filter((_, i) => i !== nearest)); else notify('Click within18 pixels of a guide to erase it.');
    return;
  }
  // Drawing is an explicit request to see the editable constraints, even if
  // their display was hidden while inspecting the previous result.
  $('guidesToggle').checked = true;
  pointer = event.pointerId; canvas.setPointerCapture(pointer); previousScreen = [event.clientX, event.clientY]; draft = [first.point.toArray()]; renderGuides();
}, { capture: true });
canvas.addEventListener('pointermove', event => {
  if (event.pointerId !== pointer || !previousScreen) return;
  const dx = event.clientX - previousScreen[0], dy = event.clientY - previousScreen[1], steps = Math.min(200, Math.ceil(Math.hypot(dx, dy) / 2));
  for (let i = 1; i <= steps; i++) samplePointer(previousScreen[0] + dx * i / steps, previousScreen[1] + dy * i / steps);
  previousScreen = [event.clientX, event.clientY]; renderGuides();
});
function endPointer(event) {
  if (event.pointerId !== pointer) return;
  finishPart($('closedGuide').checked); if (canvas.hasPointerCapture(pointer)) canvas.releasePointerCapture(pointer); pointer = null; previousScreen = null;
}
canvas.addEventListener('pointerup', endPointer); canvas.addEventListener('pointercancel', endPointer);
canvas.addEventListener('wheel', event => {
  if (controls.enabled) return;
  event.preventDefault(); const offset = camera.position.clone().sub(controls.target); offset.multiplyScalar(Math.exp(event.deltaY * .001)); offset.clampLength(controls.minDistance, controls.maxDistance); camera.position.copy(controls.target).add(offset); controls.update();
}, { passive: false });
canvas.addEventListener('contextmenu', event => event.preventDefault());

function setTarget(value) {
  state.target = Math.max(150, Math.min(1800, Math.round(Number(value) || 600))); $('targetNumber').value = state.target; $('targetRange').value = state.target; updateDensity(); dirty(); persist();
}
// Source density in quad equivalents: two triangles cover about one quad.
// Spacing is sqrt(area / count), the same edge-size rule the solvers apply to the target.
function sourceDensity(mesh) {
  let area = 0, quads = 0; const a = new THREE.Vector3(), b = new THREE.Vector3(), c = new THREE.Vector3();
  for (const face of mesh.faces) for (let j = 1; j < face.length - 1; j++) {
    a.fromArray(mesh.vertices[face[0]]); b.fromArray(mesh.vertices[face[j]]).sub(a); c.fromArray(mesh.vertices[face[j + 1]]).sub(a); area += b.cross(c).length() / 2; quads += .5;
  }
  return { area, quads: Math.max(1, Math.round(quads)) };
}
function updateDensity() {
  const d = state.density; if (!d) return;
  const spacing = n => Math.sqrt(d.area / n), finer = spacing(d.quads) / spacing(state.target);
  const relation = finer > 1.05 ? `${finer.toFixed(1)}× finer than source` : finer < .95 ? `${(1 / finer).toFixed(1)}× coarser than source` : 'matches source';
  $('densityInfo').textContent = `Source ≈ ${countText(d.quads)} quads, spacing ${spacing(d.quads).toPrecision(2)}. Target spacing ${spacing(state.target).toPrecision(2)}, ${relation}.`;
  $('densityWarning').hidden = Number(finer.toFixed(1)) <= 1.5;
  for (const [id, factor] of densityButtons) $(id).title = `Set the target to ${countText(Math.round(d.quads * factor))} quads`;
}
const densityButtons = [['halfButton', .5], ['sameButton', 1], ['doubleButton', 2]];
function validateGuides(packet) {
  if (!packet || packet.coordinateFrame !== 'source' || !Array.isArray(packet.curves) || packet.curves.length > 48) throw new Error('Use a source-space curves JSON file saved by this demo.');
  let total = 0;
  for (const curve of packet.curves) {
    if (!Array.isArray(curve) || curve.length < 2 || curve.length > 2048) throw new Error('Each curve needs2–2048 XYZ positions.');
    total += curve.length;
    for (const point of curve) if (!Array.isArray(point) || point.length !== 3 || !point.every(x => typeof x === 'number' && Number.isFinite(x) && Math.abs(x) < 1e6)) throw new Error('The file contains invalid surface positions.');
  }
  if (total > 8192) throw new Error('The file contains too many curve samples.'); return packet.curves;
}
async function loadMesh(id) {
  const version = ++state.version; if (state.job) await cancelGeneration();
  $('generateButton').disabled = true; const mesh = await api('/api/mesh/' + id); if (version !== state.version) return;
  state.mesh = mesh; state.density = sourceDensity(mesh); state.result = null; state.resultJob = null; state.resultKey = null; state.selected = -1;
  state.guides = id === 'hexagon' ? [] : clone(mesh.presets[0]?.curves || []); state.target = mesh.target; state.guideMode = 2;
  try { const saved = JSON.parse(localStorage.getItem('retopo-1:' + id)); if (saved?.sourceSha256 === mesh.sourceSha256) { state.guides = clone(validateGuides({ coordinateFrame: 'source', curves: saved.curves })); state.target = saved.target; state.guideMode = saved.guideMode === 1 && id === 'cylinder' ? 1 : 2; } } catch { /* Ignore incompatible saved data. */ }
  state.history = [clone(state.guides)]; state.historyIndex = 0; draft = []; dispose(resultGroup); resultRender = null;
  sourceRender = buildMesh(mesh, sourceGroup); $('sourceMeta').textContent = `${countText(mesh.faces.length)} triangles`; $('meshDescription').textContent = mesh.description;
  const credit = $('sourceCredit'); credit.replaceChildren(); const author = document.createElement(mesh.source.url ? 'a' : 'span'); author.textContent = mesh.source.author;
  if (mesh.source.url) { author.href = mesh.source.url; author.target = '_blank'; author.rel = 'noreferrer'; } const license = document.createElement('span'); license.textContent = mesh.source.license; credit.append(author, license);
  $('presetSelect').replaceChildren(...mesh.presets.map((p, i) => new Option(p.name, i))); $('modeControl').hidden = id !== 'cylinder'; $('guideMode').value = state.guideMode;
  $('solverNote').textContent = id === 'hexagon' ? 'Hard edges stay fixed. Guide curves become edges in the new mesh.' : 'Curves influence the solved field. These examples can take one to three minutes.';
  setTarget(state.target); updateGuideUI(); buildGrids(); fit(); updateMetrics(); setView(state.view);
  $('resultEmpty').hidden = false; $('resultMeta').textContent = ''; $('resultBadge').hidden = true; $('exportMesh').disabled = true; $('detailsButton').disabled = true;
  if (mesh.previewUrl) {
    try { const preview = await api(mesh.previewUrl); if (version === state.version) showResult(preview, null, preview.curves || [], preview.target, preview.guideMode || 2); } catch { /* A missing preview does not disable live generation. */ }
  }
  $('generateButton').disabled = false;
}
function showResult(result, job, curves, target, mode) {
  state.result = result; state.resultJob = job; state.resultKey = JSON.stringify([state.mesh.id, curves, target, mode]);
  resultRender = buildMesh(result, resultGroup); $('resultEmpty').hidden = true; $('resultMeta').textContent = `${countText(result.faces.length)} faces`;
  $('resultLabel').textContent = job ? 'Retopology' : 'Example result'; $('exportMesh').disabled = false; $('detailsButton').disabled = false;
  updateMetrics(); displaySettings(); dirty(); setView(state.view);
}
function updateMetrics() {
  const r = state.result;
  if (!r) { for (const id of ['faceMetric', 'quadMetric', 'guideMetric', 'topologyMetric']) $(id).textContent = '—'; $('faceDetail').textContent = 'Generate a mesh to compare'; $('resultSummary').textContent = 'A local, working demonstration of guided retopology.'; return; }
  const stats = r.stats; $('faceMetric').textContent = countText(r.faces.length); $('faceDetail').textContent = `${countText(state.mesh.faces.length)} source triangles · target ${r.target}`;
  $('quadMetric').textContent = `${r.quadPercent.toFixed(r.quadPercent === 100 ? 0 : 1)}%`; $('quadDetail').textContent = `${countText(stats.quads)} quads · ${stats.triangles} triangles`;
  const distances = r.guideAlignment?.map(a => a.p95Distance) || [], distance = Math.max(0, ...distances);
  $('guideMetric').textContent = distances.length ? distance < .0001 ? '<0.0001' : distance.toPrecision(3) : '—';
  $('guideDetail').textContent = distances.length ? '95% of sampled guide distances' : 'No guides in this result';
  $('topologyMetric').textContent = stats.nonmanifoldEdges === 0 && !r.vertexLinks.nonmanifoldVertices.length ? 'Passed' : 'Inspect';
  $('topologyDetail').textContent = `${stats.faceConnectedComponents} component · ${stats.boundaryEdges ? stats.boundaryEdges + ' border edges' : 'closed surface'}`;
  $('resultSummary').textContent = `${r.backend === 'engineering-planar-pslg-quads' ? 'Planar surface solver' : r.backend === 'heightfield-enclosure' ? 'Terrain enclosure solver' : 'Recovered field solver'} · ${r.elapsedSeconds.toFixed(1)}s · ${r.guideCount} guide${r.guideCount === 1 ? '' : 's'}`;
}
async function generate() {
  if (state.busy || !state.mesh) return;
  const request = { meshId: state.mesh.id, curves: clone(state.guides), target: state.target, guideMode: state.guideMode };
  if (request.meshId === 'cylinder' && !request.curves.length) return notify('Draw a guide or load the example network for this curved mesh.', true);
  const token = ++generation; state.busy = true; $('processing').hidden = false; $('generateButton').disabled = true; $('notice').hidden = true;
  const started = performance.now(); const timer = setInterval(() => { $('processTime').textContent = `${Math.round((performance.now() - started) / 1000)}s`; }, 300);
  $('processTime').textContent = '0s'; $('processDetail').textContent = request.meshId === 'hexagon' ? 'Embedding surface curves and constructing new quads…' : 'Solving the field and fitting the mesh. This can take one to three minutes…';
  try {
    const first = await api('/api/remesh', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(request) });
    if (token !== generation) {
      await api('/api/jobs/' + first.id + '/cancel', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' });
      return;
    }
    state.job = first.id;
    while (token === generation) {
      const job = await api('/api/jobs/' + first.id); $('processTitle').textContent = job.stage;
      if (job.state === 'complete') {
        const result = await api(job.resultUrl); if (token !== generation) return;
        showResult(result, first.id, request.curves, request.target, request.guideMode); notify(`Generated ${countText(result.faces.length)} faces. Your previous inputs and output are saved locally.`); return;
      }
      if (job.state === 'failed') throw new Error(job.error);
      if (job.state === 'cancelled') return;
      await new Promise(resolve => setTimeout(resolve, 500));
    }
  } catch (error) { if (token === generation) notify(error.message, true, true); }
  finally { clearInterval(timer); if (token === generation) { state.busy = false; state.job = null; $('processing').hidden = true; $('generateButton').disabled = false; } }
}
async function cancelGeneration() {
  const id = state.job; ++generation; state.busy = false; state.job = null; $('processing').hidden = true; $('generateButton').disabled = false;
  if (id) { try { await api('/api/jobs/' + id + '/cancel', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' }); } catch (error) { notify(error.message, true); } }
}
function downloadBlob(name, data) {
  const url = URL.createObjectURL(new Blob([data], { type: 'application/json' })), a = document.createElement('a'); a.href = url; a.download = name; a.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
}
$('generateButton').onclick = generate; $('cancelButton').onclick = cancelGeneration;
$('meshSelect').onchange = event => loadMesh(event.target.value).catch(error => notify(error.message, true));
document.querySelectorAll('[data-tool]').forEach(button => button.onclick = () => setTool(button.dataset.tool));
document.querySelectorAll('[data-view]').forEach(button => button.onclick = () => setView(button.dataset.view));
$('undoButton').onclick = () => historyMove(-1); $('redoButton').onclick = () => historyMove(1); $('clearButton').onclick = () => commit([]);
$('presetButton').onclick = () => { commit(state.mesh.presets[Number($('presetSelect').value)].curves); notify('Example guides loaded. Generate to apply them.'); };
for (const [id, factor] of densityButtons) $(id).onclick = () => {
  if (!state.density) return;
  const wanted = Math.round(state.density.quads * factor); setTarget(wanted);
  if (state.target !== wanted) notify(`${countText(wanted)} quads is outside this demo's 150–1,800 range, so the target is ${countText(state.target)}.`);
};
$('targetRange').oninput = event => setTarget(event.target.value); $('targetNumber').onchange = event => setTarget(event.target.value);
$('guideMode').onchange = event => { state.guideMode = Number(event.target.value); dirty(); persist(); };
for (const id of ['wireToggle', 'guidesToggle', 'creasesToggle']) $(id).onchange = () => { displaySettings(); if (state.view === 'overlay') guideGroups[1].visible = false; };
$('fitButton').onclick = () => fit(); $('topButton').onclick = () => fit(true);
$('resetButton').onclick = () => $('resetDialog').showModal();
$('confirmReset').onclick = async () => {
  if (state.job) await cancelGeneration();
  // The theme is a viewer preference, not part of the work being discarded.
  try { for (const key of Object.keys(localStorage)) if (key.startsWith('retopo-1:') && key !== 'retopo-1:theme') localStorage.removeItem(key); } catch { /* Storage is optional. */ }
  location.reload();
};
$('helpButton').onclick = () => $('helpDialog').showModal(); document.querySelectorAll('[data-close-dialog]').forEach(button => button.onclick = () => button.closest('dialog').close());
$('themeButton').onclick = () => { const theme = document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark'; document.documentElement.dataset.theme = theme; localStorage.setItem('retopo-1:theme', theme); refreshColors(); };
$('exportGuides').onclick = () => downloadBlob(`${state.mesh.id}-guides.json`, JSON.stringify({ coordinateFrame: 'source', curves: state.guides }, null, 2) + '\n');
$('importGuides').onclick = () => $('guideFile').click();
$('guideFile').onchange = async event => { try { const file = event.target.files[0]; if (file) { if (file.size > 2e6) throw new Error('The guide file is too large.'); commit(validateGuides(JSON.parse(await file.text()))); notify('Guide file loaded. Generate to apply it to this source.'); } } catch (error) { notify(error.message, true); } event.target.value = ''; };
$('exportMesh').onclick = () => { if (!state.result) return; const a = document.createElement('a'); a.href = state.resultJob ? `/api/jobs/${state.resultJob}/output.obj` : `/assets/previews/${state.mesh.id}.obj`; a.download = `${state.mesh.id}-retopology.obj`; a.click(); };
$('detailsButton').onclick = () => {
  const r = state.result, s = r.stats, content = $('detailsContent'); content.replaceChildren();
  const table = document.createElement('table');
  const rows = [['Vertices', r.vertices.length], ['Faces', r.faces.length], ['Quads / triangles', `${s.quads} / ${s.triangles}`], ['Components', s.faceConnectedComponents], ['Boundary edges', s.boundaryEdges], ['Nonmanifold edges', s.nonmanifoldEdges], ['Nonmanifold vertices', r.vertexLinks.nonmanifoldVertices.length], ['Inconsistent winding edges', r.vertexLinks.inconsistentWindingEdges], ['Euler characteristic', s.eulerCharacteristic], ['Sharp edges', r.creases.length], ['Calculation time', r.elapsedSeconds.toFixed(3) + 's'], ['Solver', r.backend]];
  for (const [label, value] of rows) { const tr = document.createElement('tr'); for (const text of [label, value]) { const td = document.createElement('td'); td.textContent = text; tr.append(td); } table.append(tr); }
  const p = document.createElement('p'); p.textContent = 'Guide distance uses up to129 samples per curve, measured against actual output edges. Topology and sampled surface checks do not certify absence of every3D self intersection. The planar and terrain routes are engineering alternatives informed by the research; exact native equivalence is not claimed.';
  content.append(table, p); $('detailsDialog').showModal();
};
window.addEventListener('keydown', event => {
  if (event.target.matches('input,select,textarea') || document.querySelector('dialog[open]')) return;
  if (event.code === 'Space') { event.preventDefault(); state.space = true; controls.enabled = true; return; }
  if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'z') { event.preventDefault(); historyMove(event.shiftKey ? 1 : -1); return; }
  if (event.ctrlKey || event.metaKey || event.altKey) return;
  if (event.key.toLowerCase() === 'g') setTool('draw'); if (event.key.toLowerCase() === 'o') setTool('orbit'); if (event.key.toLowerCase() === 'e') setTool('erase'); if (event.key.toLowerCase() === 'f') fit();
});
window.addEventListener('keyup', event => { if (event.code === 'Space') { state.space = false; controls.enabled = state.tool === 'orbit'; } });
window.addEventListener('blur', () => { state.space = false; controls.enabled = state.tool === 'orbit'; });
window.addEventListener('resize', () => fit());
function render() {
  const r = canvas.getBoundingClientRect(), w = Math.max(1, Math.round(r.width)), h = Math.max(1, Math.round(r.height));
  if (canvas.width !== Math.round(w * renderer.getPixelRatio()) || canvas.height !== Math.round(h * renderer.getPixelRatio())) renderer.setSize(w, h, false);
  controls.update(); renderer.setScissorTest(true);
  const half = state.view === 'split' ? w / 2 : w;
  camera.aspect = half / h; camera.updateProjectionMatrix(); renderer.setViewport(0, 0, half, h); renderer.setScissor(0, 0, half, h); renderer.clear(); renderer.render(scenes[0], camera);
  if (state.view === 'split') { renderer.setViewport(half, 0, half, h); renderer.setScissor(half, 0, half, h); renderer.clear(); renderer.render(scenes[1], camera); }
  requestAnimationFrame(render);
}
async function start() {
  try {
    const theme = localStorage.getItem('retopo-1:theme'); if (theme === 'light' || theme === 'dark') document.documentElement.dataset.theme = theme;
    const [health, catalog] = await Promise.all([api('/api/health'), api('/api/catalog')]);
    $('connection').className = 'badge good'; $('connection').innerHTML = '<i class="dot"></i>Local engine ready';
    $('meshSelect').replaceChildren(...catalog.map(m => new Option(m.title, m.id))); $('meshSelect').disabled = false;
    await loadMesh('hexagon'); refreshColors();
  } catch (error) { $('connection').className = 'badge error'; $('connection').textContent = 'Service unavailable'; notify(error.message + ' Start the app using start.cmd.', true, true); }
}
// Read-only inspection hooks support reproducible canvas interaction checks.
window.retopoDemo = { getState: () => ({ meshId: state.mesh?.id, guides: clone(state.guides), target: state.target, mode: state.guideMode, resultFaces: state.result?.faces.length, busy: state.busy, dirty: state.dirty, view: state.view, tool: state.tool, draft: clone(draft), sourceStats: state.mesh?.stats }), projectPoint: point => project(point) };
renderer.setClearColor(color('--bg')); render(); start();
