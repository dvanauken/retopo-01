import * as THREE from 'three';
import { OrbitControls } from 'three/addons/OrbitControls.js';
import { GuideDocument } from './src/domain/GuideDocument.js';
import { GuideController } from './src/view/GuideController.js';
import { GuideSnap } from './src/snapping/GuideSnap.js';
import { WorkspaceShell } from './src/view/WorkspaceShell.js';
import { CircleConstruction } from './src/view/CircleConstruction.js';
import { SurfaceGuides } from './src/view/SurfaceGuides.js';
import { fromPositions } from './src/geometry/GuideCurve.js';
import { encodeGuides, decodeGuides } from './src/io/GuideSerializer.js';

const $ = id => document.getElementById(id);
const clone = value => JSON.parse(JSON.stringify(value));
const state = { mesh: null, result: null, guides: [], tool: 'draw', view: 'split', selected: -1, target: 600, guideMode: 2, busy: false, job: null, resultJob: null, dirty: false, space: false, version: 0, resultKey: null, density: null, lastAttempt: null };
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
let sourceRender = null, resultRender = null, grids = [], draft = [], generation = 0, noticeTimer;
const css = name => getComputedStyle(document.documentElement).getPropertyValue(name).trim();
const color = name => new THREE.Color(css(name));
const samePoint = (a, b) => a && b && a.every((x, i) => Math.abs(x - b[i]) < 1e-8);
const keyFor = () => JSON.stringify([state.mesh?.id, state.guides, state.target, state.guideMode]);
const countText = n => n.toLocaleString();
const createGuideId = () => crypto.randomUUID();
const guideDocument = new GuideDocument(createGuideId);
const guideChrome = document.createElement('canvas'); guideChrome.id = 'guideChrome'; guideChrome.setAttribute('aria-hidden', 'true'); canvas.after(guideChrome);
const chromeContext = guideChrome.getContext('2d');
let cameraRevision = 0, persistedGeneration = '', importTicket = 0;
controls.addEventListener('change', () => cameraRevision++);
const surfaceGuides = new SurfaceGuides({
  project, surface: (x, y, pane) => hit(x, y, pane)?.point.toArray() || null,
  inside: (x, y, pane) => { const r = canvas.getBoundingClientRect(); return x >= r.left && x <= r.right && y >= r.top && y <= r.bottom && paneAt(x) === pane && (pane === 0 || !!resultRender); },
  shown: () => $('guidesToggle').checked, stamp: () => { const r = canvas.getBoundingClientRect(); return `${state.version}:${cameraRevision}:${state.view}:${$('guidesToggle').checked}:${r.left}:${r.top}:${r.width}:${r.height}`; },
  guides: () => guideDocument.guides,
});
const guideSnap = new GuideSnap({
  surface: (x, y, pane) => hit(x, y, pane)?.point.toArray() || null, project,
  enabled: () => $('snapGuides').checked,
  guides: () => guideDocument.guides,
  visible: (p, pane) => $('guidesToggle').checked && surfaceGuides.visible(p, pane),
  stamp: () => `${guideDocument.epoch}:${guideDocument.generation}:${cameraRevision}:${$('snapGuides').checked}`,
});
const circleConstruction = new CircleConstruction({
  hit, project, nearest: p => surfaceGuides.nearest(p),
  ray: (x, y, pane) => { const r = canvas.getBoundingClientRect(); if (x < r.left || x > r.right || y < r.top || y > r.bottom || paneAt(x) !== pane) throw new Error('Keep the Circle construction in its original view.'); hit(x, y, pane); return raycaster.ray.clone(); },
});
const guideErrors = [], pendingGuideErrors = [];
function reportGuideError(message) {
  const incident = Object.freeze({ id: crypto.randomUUID(), message, stateEffect: 'No requested guide change was committed.' });
  guideErrors.push(incident); if (guideErrors.length > 32) guideErrors.shift();
  console.error('Guide operation rejected', incident);
  notify(message, true); pendingGuideErrors.push(incident); flushGuideErrors();
}
function flushGuideErrors() {
  if (!pendingGuideErrors.length || $('guideErrorDialog').open || editor.gate || editor.activity?.pointerId !== undefined) return;
  $('guideErrorMessage').textContent = pendingGuideErrors[0].message; $('guideErrorDialog').showModal();
}
$('guideErrorDialog').addEventListener('close', () => { pendingGuideErrors.shift(); queueMicrotask(flushGuideErrors); });
const expectedCaptureReleases = new Map(), captureOwners = new Map();
const editor = new GuideController(guideDocument, {
  id: createGuideId, changed: syncGuideState, clearSnap: () => guideSnap.clear(), resolve: (x, y, pane, options) => guideSnap.resolve(x, y, pane, options), report: reportGuideError, busy: () => state.busy || !state.mesh,
  circleFrame: (x, y, pane) => circleConstruction.frame(x, y, pane), circlePreview: (c, x, y) => circleConstruction.preview(c, x, y), circleEdit: (g, pointId, delta, pane) => circleConstruction.edit(g, pointId, delta, pane), closureVisible: (p, pane) => surfaceGuides.visible(p, pane),
  closed: () => $('closedGuide').checked, pane: paneAt, project,
  cameraRevision: () => cameraRevision,
  surface: (x, y, pane) => hit(x, y, pane)?.point.toArray() || null,
  showGuides: () => { $('guidesToggle').checked = true; },
  curve: g => surfaceGuides.curve(g),
  hit: (x, y, pane, selection) => surfaceGuides.hit(x, y, pane, selection),
  contained: (a, b, pane) => surfaceGuides.contained(a, b, pane),
  screenDistance: (a, b, pane) => { a = project(a, pane); b = project(b, pane); return Math.hypot(a.x - b.x, a.y - b.y); },
  capture: id => { try { canvas.setPointerCapture(id); captureOwners.set(id, { sequenceId: editor.activity.sequenceId, acknowledged: false }); return canvas.hasPointerCapture(id); } catch { captureOwners.delete(id); return false; } },
  release: id => { const owner = captureOwners.get(id); if (canvas.hasPointerCapture(id)) { if (owner?.acknowledged) expectedCaptureReleases.set(id, [...(expectedCaptureReleases.get(id) || []), owner.sequenceId]); canvas.releasePointerCapture(id); } captureOwners.delete(id); },
});
const workspaceShell = new WorkspaceShell($('appShell'), { beforeResize: () => { if (editor.activity) editor.escape(); } });
function syncGuideState() {
  state.tool = editor.tool; state.space = editor.temporary; controls.enabled = state.tool === 'orbit' || state.space;
  state.guides = guideDocument.guides.map(g => surfaceGuides.curve(g));
  state.selected = guideDocument.guides.findIndex(g => g.id === editor.selection.activeEntityId);
  draft = editor.drafts.at(-1) || [];
  canvas.className = editor.activity?.invalid || editor.construction?.invalid ? 'invalid' : state.tool;
  document.querySelectorAll('[data-tool]').forEach(button => { const active = button.dataset.tool === state.tool; button.classList.toggle('active', active); button.setAttribute('aria-pressed', active); });
  for (const model of ['object', 'direct']) { const b = $(model + 'Selection'); b.setAttribute('aria-pressed', editor.selection.model === model); b.disabled = model === 'direct' && !editor.selection.activeEntityId; }
  $('deleteGuides').querySelector('[data-label]').textContent = editor.selection.model === 'direct' && editor.selection.pointId && guideDocument.get(editor.selection.activeEntityId)?.type !== 'circle' ? 'Delete point' : 'Delete guides';
  $('deleteGuides').disabled = !editor.selection.entityIds.length; $('reverseGuides').disabled = !editor.selection.entityIds.some(id => guideDocument.get(id)?.type !== 'circle');
  $('finishGuide').hidden = !editor.construction;
  $('selectionStatus').textContent = editor.activity?.invalid || editor.construction?.invalid || (editor.selection.entityIds.length ? `${editor.selection.entityIds.length} selected · ${editor.selection.model === 'direct' ? 'Edit points' : 'Whole guides'}` : 'Select a guide body or drag a selection rectangle.');
  $('canvasInstruction').textContent = { draw: 'Drag a guide. Return within 5 px of the green first point and release to close.', polyline: 'Click vertices. Click the green first point within 5 px to close; Enter finishes open.', spline: 'Click fit points. Return within 5 px of the green first point and click to close.', circle: 'Click the center, then set the radius. The center may lie over the hole.', select: 'Click a guide, double-click to edit points, or drag a selection rectangle. Shift adds guides.', erase: 'Click a visible guide segment to remove the guide.', orbit: 'Drag to orbit. Right-drag to pan. Scroll to zoom.' }[state.tool];
  const selected = guideDocument.get(editor.selection.activeEntityId);
  $('selectedGuideType').textContent = selected?.type || 'No guide';
  $('selectedGuidePoints').textContent = selected ? selected.type === 'circle' ? 'Analytic circle' : `${selected.points.length} points${selected.closed ? ' · closed' : ''}` : '—';
  $('circleProperties').hidden = selected?.type !== 'circle';
  if (selected?.type === 'circle' && (document.activeElement !== $('circleRadius') || $('circleRadius').dataset.guideId !== selected.id)) { $('circleRadius').value = selected.radius; $('circleRadius').dataset.guideId = selected.id; }
  workspaceShell.history(guideDocument.history);
  updateGuideUI();
  const stamp = guideDocument.epoch + ':' + guideDocument.generation;
  if (stamp !== persistedGeneration && state.mesh) { persistedGeneration = stamp; persist(); }
  flushGuideErrors();
}

async function api(url, options) {
  const response = await fetch(url, options); const data = await response.json();
  if (!response.ok) throw new Error(data.error || 'The local service did not complete the request.');
  return data;
}
function notify(message, error = false, persistent = false) {
  workspaceShell.addLog(message, error);
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
  const material = new THREE.MeshStandardMaterial({ color: data.displayColor ? new THREE.Color(data.displayColor) : color('--model'), roughness: data.displaySmooth ? .28 : .78, metalness: data.displaySmooth ? 0 : .08, flatShading: !data.displaySmooth, side: THREE.DoubleSide, polygonOffset: true, polygonOffsetFactor: 1, polygonOffsetUnits: 1 });
  const solid = new THREE.Mesh(geometry, material); group.add(solid);
  const wire = lineSegments(edgePositions(data.vertices, data.faces), color('--wire'), data.wireOpacity ?? .75); group.add(wire);
  const creases = lineSegments((data.creases || []).flatMap(([a, b]) => [...data.vertices[a], ...data.vertices[b]]), color('--crease'));
  creases.renderOrder = 2; group.add(creases);
  return { solid, wire, creases, displayColor: data.displayColor, wireOpacity: data.wireOpacity };
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
  const addCurve = (curve, selected = false, opacity = 1) => {
    if (!curve.length) return;
    const geometry = curve.length > 1 ? new THREE.TubeGeometry(new Polyline(curve), Math.min(2048, Math.max(8, curve.length * 2)), selected ? .012 : .008, 5, false) : new THREE.SphereGeometry(.012, 8, 6);
    const material = new THREE.MeshBasicMaterial({ color: color('--guide'), depthTest: true, transparent: opacity < 1, opacity });
    for (const group of guideGroups) {
      const shape = new THREE.Mesh(geometry.clone(), material.clone()); shape.renderOrder = 3;
      if (curve.length === 1) shape.position.fromArray(curve[0]); group.add(shape);
    }
    geometry.dispose(); material.dispose();
  };
  for (const guide of guideDocument.guides) addCurve(surfaceGuides.curve(guide), editor.selection.entityIds.includes(guide.id) && !editor.editingIds.includes(guide.id), editor.editingIds.includes(guide.id) ? .22 : 1);
  for (const candidate of editor.candidates) addCurve(surfaceGuides.curve(candidate), true);
  const constructionGuide = editor.constructionGuide;
  if (constructionGuide) {
    try { addCurve(surfaceGuides.curve(constructionGuide), true); } catch { for (const points of editor.drafts) addCurve(points, false, .4); }
  } else for (const points of editor.drafts) addCurve(points, true);
  syncGuideVisibility();
}
function syncGuideVisibility() {
  guideGroups.forEach((group, pane) => group.visible = $('guidesToggle').checked && (pane === 0 || (state.view === 'split' && !!resultRender)));
}
function setAttempt(phase, message = '') {
  state.lastAttempt = { phase, message, target: state.target, guideCount: state.guides.length, sourceSha256: state.mesh?.sourceSha256 };
  if (state.mesh) try {
    const key = 'retopo-1:last-attempt:' + state.mesh.id;
    if (phase === 'failed' || phase === 'cancelled') localStorage.setItem(key, JSON.stringify(state.lastAttempt));
    else localStorage.removeItem(key);
  } catch { /* Optional operation history. */ }
  syncResultFeedback();
}
function syncResultFeedback() {
  const attempt = state.lastAttempt, failed = attempt?.phase === 'failed', cancelled = attempt?.phase === 'cancelled';
  const title = failed ? 'Last generation failed' : cancelled ? 'Generation cancelled' : 'No generated mesh';
  const attemptContext = Number.isInteger(attempt?.target) && Number.isInteger(attempt?.guideCount) ? ` Attempted ${countText(attempt.target)} quads with ${attempt.guideCount} guide${attempt.guideCount === 1 ? '' : 's'}.` : '';
  const detail = failed ? attempt.message + attemptContext : cancelled ? 'Your guides are saved. Click Generate to try again.' : 'Click Generate to build a mesh from the current source and guides.';
  $('resultEmpty').hidden = !!state.result;
  $('resultEmpty').dataset.state = failed ? 'failed' : cancelled ? 'cancelled' : 'ready';
  $('resultEmptyTitle').textContent = title; $('resultEmptyDetail').textContent = detail;
  $('generationFeedback').hidden = !(failed || cancelled) || (!state.result && state.view === 'split');
  $('generationFeedback').textContent = title + '. ' + detail + (state.result ? ' The previous accepted result is still shown.' : '');
  $('generationFeedback').classList.toggle('overlay', state.view === 'overlay');
  syncGuideVisibility();
}
function drawGuideChrome() {
  const r = canvas.getBoundingClientRect(), dpr = renderer.getPixelRatio();
  if (guideChrome.width !== Math.round(r.width * dpr) || guideChrome.height !== Math.round(r.height * dpr)) { guideChrome.width = Math.round(r.width * dpr); guideChrome.height = Math.round(r.height * dpr); }
  const ctx = chromeContext; ctx.setTransform(dpr, 0, 0, dpr, 0, 0); ctx.clearRect(0, 0, r.width, r.height);
  if (!$('guidesToggle').checked) return;
  const local = p => ({ x: p.x - r.left, y: p.y - r.top });
  for (let pane = 0; pane < (state.view === 'split' && resultRender ? 2 : 1); pane++) {
    ctx.save(); const w = state.view === 'split' ? r.width / 2 : r.width; ctx.beginPath(); ctx.rect(pane * w, 0, w, r.height); ctx.clip();
    ctx.strokeStyle = css('--guide'); ctx.fillStyle = css('--bg'); ctx.lineWidth = 1.5;
    const records = editor.editingIds.length ? editor.candidates : guideDocument.guides.filter(g => editor.selection.entityIds.includes(g.id));
    if (editor.selection.model === 'object' && records.length) {
      const boxes = records.map(g => surfaceGuides.bounds(g, pane)), left = Math.min(...boxes.map(b => b.left)) - r.left, top = Math.min(...boxes.map(b => b.top)) - r.top;
      ctx.setLineDash([4, 4]); ctx.strokeRect(left - 5, top - 5, Math.max(10, Math.max(...boxes.map(b => b.right)) - r.left - left + 10), Math.max(10, Math.max(...boxes.map(b => b.bottom)) - r.top - top + 10)); ctx.setLineDash([]);
    }
    // Exactly these descriptions are consumed by SurfaceGuides.hit.
    const handleSelection = editor.selection;
    let handles = surfaceGuides.handles(handleSelection, pane);
    if (editor.editingIds.length && handleSelection.model === 'direct') handles = editor.candidates.flatMap(g => surfaceGuides.handlesForGuide(g, pane));
    for (const h of handles) { const p = local(h); ctx.beginPath(); if (h.role === 'center') { ctx.moveTo(p.x, p.y - 7); ctx.lineTo(p.x + 7, p.y); ctx.lineTo(p.x, p.y + 7); ctx.lineTo(p.x - 7, p.y); ctx.closePath(); } else ctx.arc(p.x, p.y, 6, 0, Math.PI * 2); ctx.fillStyle = h.pointId === editor.selection.pointId ? css('--guide') : css('--bg'); ctx.fill(); ctx.stroke(); }
    if (editor.selection.model === 'direct') {
      const g = editor.candidates.find(g => g.id === editor.selection.activeEntityId) || guideDocument.get(editor.selection.activeEntityId);
      if (g && g.type !== 'circle') {
        const curve = surfaceGuides.curve(g), start = local(project(curve[0], pane));
        if (surfaceGuides.visible(curve[0], pane)) { ctx.beginPath(); ctx.moveTo(start.x, start.y - 8); ctx.lineTo(start.x + 8, start.y); ctx.lineTo(start.x, start.y + 8); ctx.lineTo(start.x - 8, start.y); ctx.closePath(); ctx.stroke(); }
        const index = Math.min(curve.length - 1, Math.max(1, Math.floor(curve.length / 5))), p = local(project(curve[index], pane)), q = local(project(curve[index - 1], pane)), angle = Math.atan2(p.y - q.y, p.x - q.x);
        if (surfaceGuides.visible(curve[index], pane)) { ctx.beginPath(); ctx.moveTo(p.x - 7 * Math.cos(angle - .5), p.y - 7 * Math.sin(angle - .5)); ctx.lineTo(p.x, p.y); ctx.lineTo(p.x - 7 * Math.cos(angle + .5), p.y - 7 * Math.sin(angle + .5)); ctx.stroke(); }
      }
    }
    // Object-mode endpoints are small, fixed-pixel, directly editable targets.
    if (handleSelection.model !== 'direct') for (const g of guideDocument.guides) if (!g.closed) for (const point of [g.points[0], g.points.at(-1)]) if (surfaceGuides.visible(point.position, pane)) { const p = local(project(point.position, pane)); ctx.fillStyle = css('--guide'); ctx.beginPath(); ctx.arc(p.x, p.y, 3, 0, Math.PI * 2); ctx.fill(); }
    if (editor.construction?.pane === pane) for (const point of editor.construction.points) { const p = local(project(point.position, pane)); ctx.fillStyle = css('--guide'); ctx.fillRect(p.x - 3, p.y - 3, 6, 6); }
    const closure = editor.closureSnap;
    const start = editor.construction?.type !== 'circle' ? editor.construction?.points[0]?.position : null;
    const freeStart = editor.activity?.kind === 'freehand' ? editor.activity.current[0] : null;
    if ((start || freeStart) && surfaceGuides.visible(start || freeStart, pane)) {
      const p = local(project(start || freeStart, pane)); ctx.fillStyle = closure ? css('--green-fg') : css('--guide'); ctx.strokeStyle = ctx.fillStyle;
      ctx.beginPath(); ctx.arc(p.x, p.y, closure ? 7 : 4, 0, Math.PI * 2); ctx.fill();
      if (closure) { ctx.beginPath(); ctx.arc(p.x, p.y, 11, 0, Math.PI * 2); ctx.stroke(); }
    }
    const circle = editor.construction?.preview || (editor.selection.model === 'direct' ? editor.candidates.find(g => g.type === 'circle') || guideDocument.get(editor.selection.activeEntityId) : null);
    if (circle?.type === 'circle') {
      const center = local(project(circle.points[0].position, pane)), rim = local(project(surfaceGuides.curve(circle)[0], pane));
      ctx.strokeStyle = css('--guide'); ctx.setLineDash([3, 3]); ctx.beginPath(); ctx.moveTo(center.x, center.y); ctx.lineTo(rim.x, rim.y); ctx.stroke(); ctx.setLineDash([]);
    }
    const a = editor.activity;
    if (a?.kind === 'marquee' && a.pane === pane) { ctx.setLineDash([4, 3]); ctx.strokeRect(a.press[0] - r.left, a.press[1] - r.top, a.current[0] - a.press[0], a.current[1] - a.press[1]); }
    const snap = guideSnap.marker;
    if (snap?.pane === pane) { const p = local(project(snap.position, pane)); ctx.strokeStyle = css('--accent'); ctx.beginPath(); ctx.arc(p.x, p.y, 10, 0, Math.PI * 2); ctx.stroke(); }
    ctx.restore();
  }
}
function displaySettings() {
  for (const mesh of [sourceRender, resultRender]) if (mesh) {
    mesh.wire.visible = $('wireToggle').checked; mesh.creases.visible = $('creasesToggle').checked;
  }
  syncGuideVisibility();
}
function refreshColors() {
  renderer.setClearColor(color('--bg'));
  scenes.forEach(scene => { scene.background = color('--bg'); });
  for (const mesh of [sourceRender, resultRender]) if (mesh) {
    mesh.solid.material.color.copy(mesh.displayColor ? new THREE.Color(mesh.displayColor) : color('--model')); mesh.wire.material.color.copy(color('--wire')); mesh.creases.material.color.copy(color('--crease'));
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
  $('sourceCaption').querySelector('.label').textContent = overlay && state.result ? 'Source + retopology' : 'Source';
  (overlay ? scenes[0] : scenes[1]).add(resultGroup);
  syncGuideVisibility();
  if (sourceRender) {
    const material = sourceRender.solid.material; material.transparent = overlay && !!state.result; material.opacity = overlay && state.result ? .25 : 1; material.depthWrite = !overlay || !state.result;
    sourceRender.wire.material.opacity = overlay ? .18 : sourceRender.wireOpacity ?? .75;
  }
  $('resultEmpty').style.display = overlay ? 'none' : '';
  syncResultFeedback();
  if (changed) fit(false, true);
}
function setTool(tool) { editor.activate(tool); }
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
  try { localStorage.setItem('retopo-1:' + state.mesh.id, JSON.stringify({ ...JSON.parse(encodeGuides(guideDocument, state.mesh.sourceSha256, state.guides)), target: state.target, guideMode: state.guideMode })); } catch { /* Storage is optional. */ }
}
function dirty() {
  state.dirty = state.resultKey !== keyFor();
  if (state.result) { $('resultBadge').hidden = false; $('resultBadge').className = 'badge' + (state.dirty ? '' : state.result.quality?.passed ? ' good' : ' busy'); $('resultBadge').textContent = state.dirty ? 'Needs update' : !state.result.quality?.passed ? 'Quality warning' : state.resultJob ? 'Generated' : 'Example'; }
  syncResultFeedback();
}
function updateGuideUI() {
  $('guideCount').textContent = state.guides.length;
  $('undoButton').disabled = guideDocument.history.index === 0; $('redoButton').disabled = guideDocument.history.index >= guideDocument.history.length; $('clearButton').disabled = !state.guides.length; $('exportGuides').disabled = !state.mesh;
  const list = $('guideList'); list.replaceChildren();
  if (!state.guides.length) { const empty = document.createElement('div'); empty.className = 'empty-guides'; empty.innerHTML = 'No guides yet.<br>Choose a drawing tool in the ribbon.'; list.append(empty); }
  state.guides.forEach((curve, index) => {
    const row = document.createElement('div'); row.className = 'guide-item' + (editor.selection.entityIds.includes(guideDocument.guides[index].id) ? ' selected' : '');
    const swatch = document.createElement('span'); swatch.className = 'line-swatch';
    const name = document.createElement('button'); name.className = 'name guide-name'; name.textContent = `Guide ${index + 1} · ${guideDocument.guides[index].type}${guideDocument.guides[index].closed ? ' · closed' : ''}`;
    name.setAttribute('aria-pressed', editor.selection.entityIds.includes(guideDocument.guides[index].id)); name.onclick = event => editor.choose(guideDocument.guides[index].id, event.shiftKey);
    const remove = document.createElement('button'); remove.className = 'guide-remove'; remove.innerHTML = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="m7 7 10 10M17 7 7 17"/></svg>'; remove.setAttribute('aria-label', 'Delete guide ' + (index + 1)); remove.onclick = () => editor.run(() => { editor.cancel(); editor.removeIds([guideDocument.guides[index].id]); });
    row.append(swatch, name, remove); list.append(row);
  });
  dirty(); renderGuides();
}
function commit(curves) { editor.replace(curves.map(c => fromPositions(c, 'polyline', false, createGuideId, { detectClosure: true }))); }
function historyMove(delta) { editor.history(delta); }
const pointerValue = e => Object.freeze({ pointerId: e.pointerId, pointerType: e.pointerType, button: e.button, buttons: e.buttons, x: e.clientX, y: e.clientY, shift: e.shiftKey, alt: e.altKey, time: e.timeStamp });
canvas.addEventListener('pointerdown', e => { if (!controls.enabled && e.button === 0) { e.preventDefault(); canvas.focus(); editor.down(pointerValue(e)); } }, { capture: true });
canvas.addEventListener('pointermove', e => {
  if (controls.enabled) return;
  const samples = e.getCoalescedEvents?.() || [];
  for (const sample of samples) editor.move(pointerValue(sample));
  editor.move(pointerValue(e));
});
canvas.addEventListener('pointerup', e => editor.up(pointerValue(e)));
canvas.addEventListener('pointercancel', e => editor.cancelPointer(e.pointerId));
canvas.addEventListener('gotpointercapture', e => { const owner = captureOwners.get(e.pointerId); if (owner) owner.acknowledged = true; });
canvas.addEventListener('lostpointercapture', e => {
  const expected = expectedCaptureReleases.get(e.pointerId);
  if (expected?.length) { expected.shift(); if (!expected.length) expectedCaptureReleases.delete(e.pointerId); return; }
  editor.cancelPointer(e.pointerId);
});
canvas.addEventListener('wheel', event => {
  if (controls.enabled) return;
  event.preventDefault(); if (editor.activity) return; const offset = camera.position.clone().sub(controls.target); offset.multiplyScalar(Math.exp(event.deltaY * .001)); offset.clampLength(controls.minDistance, controls.maxDistance); camera.position.copy(controls.target).add(offset); controls.update();
}, { passive: false });
canvas.addEventListener('contextmenu', event => event.preventDefault());

function setTarget(value) {
  const requested = Math.round(Number(value));
  if (!Number.isFinite(requested) || requested < 150 || requested > 1800) {
    $('targetNumber').value = state.target; $('targetRange').value = state.target;
    notify('Supported targets are 150–1,800 quads. The target was not changed.', true); return;
  }
  state.target = requested; $('targetNumber').value = state.target; $('targetRange').value = state.target; updateDensity(); dirty(); persist();
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
  for (const [id, factor] of densityButtons) {
    const wanted = Math.round(d.quads * factor), supported = wanted >= 150 && wanted <= 1800;
    $(id).disabled = !supported;
    $(id).title = supported ? `Set the target to ${countText(wanted)} quads` : `${countText(wanted)} quads is outside the supported 150–1,800 range`;
  }
}
const densityButtons = [['halfButton', .5], ['sameButton', 1], ['doubleButton', 2]];
async function loadMesh(id) {
  $('notice').hidden = true;
  editor.run(() => { editor.cancel(); editor.select([]); }); ++importTicket;
  const version = ++state.version; if (state.job) await cancelGeneration();
  $('generateButton').disabled = true; const mesh = await api('/api/mesh/' + id); if (version !== state.version) return;
  state.mesh = mesh; state.density = sourceDensity(mesh); state.result = null; state.resultJob = null; state.resultKey = null; state.selected = -1; state.lastAttempt = null;
  try { const attempt = JSON.parse(localStorage.getItem('retopo-1:last-attempt:' + id)); if (attempt?.sourceSha256 === mesh.sourceSha256 && ['failed', 'cancelled'].includes(attempt.phase) && typeof attempt.message === 'string') state.lastAttempt = attempt; } catch { /* Optional operation history. */ }
  let loadedGuides = (id === 'hexagon' ? [] : mesh.presets[0]?.curves || []).map(c => fromPositions(c, 'polyline', false, createGuideId, { detectClosure: true })); state.target = mesh.target; state.guideMode = 2;
  try { const saved = JSON.parse(localStorage.getItem('retopo-1:' + id)); if (saved?.sourceSha256 === mesh.sourceSha256) { loadedGuides = decodeGuides({ ...saved, coordinateFrame: 'source' }, mesh.sourceSha256, createGuideId); if (Number.isInteger(saved.target) && saved.target >= 150 && saved.target <= 1800) state.target = saved.target; state.guideMode = saved.guideMode === 1 && id === 'cylinder' ? 1 : 2; } } catch { /* Ignore incompatible saved data. */ }
  draft = []; dispose(resultGroup); resultRender = null;
  sourceRender = buildMesh(mesh, sourceGroup); surfaceGuides.setSource(mesh); guideDocument.load(loadedGuides); $('sourceMeta').textContent = `${countText(mesh.faces.length)} triangles`; $('meshDescription').textContent = mesh.description; $('workspaceModelName').textContent = mesh.title; $('solverNote').classList.toggle('experimental', !!mesh.experimentalRetopology);
  const credit = $('sourceCredit'); credit.replaceChildren(); const author = document.createElement(mesh.source.url ? 'a' : 'span'); author.textContent = mesh.source.author;
  if (mesh.source.url) { author.href = mesh.source.url; author.target = '_blank'; author.rel = 'noreferrer'; } const license = document.createElement('span'); license.textContent = mesh.source.license; credit.append(author, license);
  $('presetSelect').replaceChildren(...mesh.presets.map((p, i) => new Option(p.name, i))); $('presetSelect').disabled = $('presetButton').disabled = !mesh.presets.length; $('modeControl').hidden = id !== 'cylinder'; $('guideMode').value = state.guideMode;
  $('solverNote').textContent = mesh.solverNotice || (id === 'hexagon' ? 'Hard edges and the hole stay fixed. Guides steer continuous edge loops.' : 'Curves influence the solved field. These examples can take one to three minutes.');
  setTarget(state.target); updateGuideUI(); buildGrids(); fit(); updateMetrics(); setView(state.view);
  $('resultEmpty').hidden = false; $('resultLabel').textContent = 'Retopology'; $('resultMeta').textContent = ''; $('resultBadge').hidden = true; $('exportMesh').disabled = true; $('detailsButton').disabled = true;
  if (mesh.previewUrl) {
    try { const preview = await api(mesh.previewUrl); if (version === state.version) showResult(preview, null, preview.curves || [], preview.target, preview.guideMode || 2); } catch { /* A missing preview does not disable live generation. */ }
  }
  $('generateButton').disabled = false; workspaceShell.addLog('Loaded ' + mesh.title + '.');
  syncResultFeedback();
}
function showResult(result, job, curves, target, mode) {
  state.result = result; state.resultJob = job; state.resultKey = JSON.stringify([state.mesh.id, curves, target, mode]);
  if (job) setAttempt('complete');
  resultRender = buildMesh({ ...result, displayColor: state.mesh.displayColor, displaySmooth: state.mesh.displaySmooth, wireOpacity: state.mesh.wireOpacity }, resultGroup); $('resultEmpty').hidden = true; $('resultMeta').textContent = `${countText(result.faces.length)} faces`;
  $('resultLabel').textContent = job ? 'Retopology' : 'Example result'; $('exportMesh').disabled = false; $('detailsButton').disabled = false;
  updateMetrics(); displaySettings(); dirty(); setView(state.view);
}
function updateMetrics() {
  const r = state.result;
  if (!r) { for (const id of ['faceMetric', 'quadMetric', 'guideMetric', 'topologyMetric']) $(id).textContent = '—'; $('faceDetail').textContent = 'Generate a mesh to compare'; $('quadDetail').textContent = 'No generated mesh'; $('guideDetail').textContent = 'No measured result'; $('topologyDetail').textContent = 'No measured result'; $('resultSummary').textContent = 'A local, working demonstration of guided retopology.'; return; }
  const stats = r.stats; $('faceMetric').textContent = countText(r.faces.length); $('faceDetail').textContent = `${countText(state.mesh.faces.length)} source triangles · target ${r.target}`;
  $('quadMetric').textContent = `${r.quadPercent.toFixed(r.quadPercent === 100 ? 0 : 1)}%`; $('quadDetail').textContent = `${countText(stats.quads)} quads · ${stats.triangles} triangles`;
  const distances = r.guideAlignment?.map(a => a.p95Distance) || [], distance = Math.max(0, ...distances);
  $('guideMetric').textContent = distances.length ? distance < .0001 ? '<0.0001' : distance.toPrecision(3) : '—';
  $('guideDetail').textContent = distances.length ? r.guidePaths?.length ? 'Measured output edge-path fit · p95' : 'Nearest edges · path not verified' : 'No guides in this result';
  $('topologyMetric').textContent = r.quality?.passed ? 'Good' : r.quality ? 'Needs work' : 'Unqualified';
  $('topologyDetail').textContent = r.quality ? `Min angle ${r.quality.minimumAngleDegrees.toFixed(0)}° · worst edge ratio ${r.quality.edgeRatioMax.toFixed(2)}` : 'Quad shape has not been checked';
  $('resultSummary').textContent = `${r.backend === 'engineering-guided-surface-quads' ? 'Quad surface solver' : r.backend === 'engineering-structured-prismatic-annulus' ? 'Continuous quad grid' : r.backend === 'engineering-planar-pslg-quads' ? 'Planar surface solver' : r.backend === 'heightfield-enclosure' ? 'Terrain enclosure solver' : 'Recovered field solver'} · ${r.elapsedSeconds.toFixed(1)}s · ${r.guideCount} guide${r.guideCount === 1 ? '' : 's'}`;
}
async function generate() {
  if (state.busy || !state.mesh) return;
  if (editor.activity || editor.construction) return reportGuideError('Finish or cancel the current guide before generating.');
  const request = { meshId: state.mesh.id, curves: clone(state.guides), target: state.target, guideMode: state.guideMode };
  if ((request.meshId === 'cylinder' || state.mesh.requiresGuides) && !request.curves.length) return notify('Draw a guide or load the example network for this curved mesh.', true);
  workspaceShell.addLog('Generating retopology…');
  setAttempt('running');
  const token = ++generation; state.busy = true; $('processing').hidden = false; $('generateButton').disabled = true; $('notice').hidden = true;
  const started = performance.now(); const timer = setInterval(() => { $('processTime').textContent = `${Math.round((performance.now() - started) / 1000)}s`; }, 300);
  $('processTime').textContent = '0s'; $('processDetail').textContent = state.mesh.solver === 'surface-quads' ? 'Building a quad layout, fitting your guide paths and checking the source surface…' : request.meshId === 'hexagon' ? 'Laying out continuous guide loops and sizing quad strips…' : 'Solving the field and fitting the mesh. This can take one to three minutes…';
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
        showResult(result, first.id, request.curves, request.target, request.guideMode); notify(`Generated ${countText(result.faces.length)} quads. Shape, spacing and density checks passed.`); return;
      }
      if (job.state === 'failed') throw new Error(job.error);
      if (job.state === 'cancelled') return;
      await new Promise(resolve => setTimeout(resolve, 500));
    }
  } catch (error) { if (token === generation) { setAttempt('failed', error.message); notify(error.message, true, true); } }
  finally { clearInterval(timer); if (token === generation) { state.busy = false; state.job = null; $('processing').hidden = true; $('generateButton').disabled = false; } }
}
async function cancelGeneration() {
  const id = state.job, wasBusy = state.busy; ++generation; state.busy = false; state.job = null; $('processing').hidden = true; $('generateButton').disabled = false;
  if (wasBusy) setAttempt('cancelled');
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
};
$('targetRange').oninput = event => setTarget(event.target.value); $('targetNumber').onchange = event => setTarget(event.target.value);
$('guideMode').onchange = event => { state.guideMode = Number(event.target.value); dirty(); persist(); };
for (const id of ['wireToggle', 'guidesToggle', 'creasesToggle']) $(id).onchange = () => { displaySettings(); if (state.view === 'overlay') guideGroups[1].visible = false; };
$('fitButton').onclick = () => { editor.run(() => editor.cancel()); fit(); }; $('topButton').onclick = () => { editor.run(() => editor.cancel()); fit(true); };
$('resetButton').onclick = () => $('resetDialog').showModal();
$('confirmReset').onclick = async () => {
  if (state.job) await cancelGeneration();
  // The theme is a viewer preference, not part of the work being discarded.
  try { for (const key of Object.keys(localStorage)) if (key.startsWith('retopo-1:') && key !== 'retopo-1:theme') localStorage.removeItem(key); } catch { /* Storage is optional. */ }
  location.reload();
};
$('helpButton').onclick = () => $('helpDialog').showModal(); document.querySelectorAll('[data-close-dialog]').forEach(button => button.onclick = () => button.closest('dialog').close());
$('themeButton').onclick = () => { const theme = document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark'; document.documentElement.dataset.theme = theme; localStorage.setItem('retopo-1:theme', theme); refreshColors(); };
$('exportGuides').onclick = () => { if (editor.activity || editor.construction) return reportGuideError('Finish or cancel the current guide before saving.'); downloadBlob(`${state.mesh.id}-guides.json`, encodeGuides(guideDocument, state.mesh.sourceSha256, state.guides)); };
$('importGuides').onclick = () => $('guideFile').click();
$('guideFile').onchange = async event => {
  const file = event.target.files[0], epoch = guideDocument.epoch, sourceGeneration = guideDocument.generation, ticket = ++importTicket; event.target.value = '';
  if (!file) return;
  try {
    if (file.size > 2e6) throw new Error('The guide file is too large.');
    const packet = JSON.parse(await file.text());
    if (epoch !== guideDocument.epoch || ticket !== importTicket) return;
    if (editor.activity || editor.construction) throw new Error('Finish or cancel the current guide, then load the file again.');
    if (sourceGeneration !== guideDocument.generation) throw new Error('Guides changed while the file was loading. Load the file again to replace them.');
    const guides = decodeGuides(packet, state.mesh.sourceSha256, createGuideId);
    editor.replace(guides, 'Load guides');
  } catch (error) { if (epoch === guideDocument.epoch && ticket === importTicket) reportGuideError(error.message); }
};
$('exportMesh').onclick = () => { if (!state.result) return; const a = document.createElement('a'); a.href = state.resultJob ? `/api/jobs/${state.resultJob}/output.obj` : `/assets/previews/${state.mesh.id}.obj`; a.download = `${state.mesh.id}-retopology.obj`; a.click(); };
$('detailsButton').onclick = () => {
  const r = state.result, s = r.stats, content = $('detailsContent'); content.replaceChildren();
  const table = document.createElement('table');
  const rows = [['Vertices', r.vertices.length], ['Faces', r.faces.length], ['Quads / triangles', `${s.quads} / ${s.triangles}`], ['Components', s.faceConnectedComponents], ['Boundary edges', s.boundaryEdges], ['Nonmanifold edges', s.nonmanifoldEdges], ['Nonmanifold vertices', r.vertexLinks.nonmanifoldVertices.length], ['Inconsistent winding edges', r.vertexLinks.inconsistentWindingEdges], ['Euler characteristic', s.eulerCharacteristic], ['Sharp edges', r.creases.length], ['Calculation time', r.elapsedSeconds.toFixed(3) + 's'], ['Minimum quad angle', r.quality?.minimumAngleDegrees.toFixed(2) + '°'], ['Worst edge ratio', r.quality?.edgeRatioMax.toFixed(3)], ['Minimum scaled Jacobian', r.quality?.scaledJacobianMin.toFixed(3)], ['Regular valence-four vertices', r.quality ? (100*r.quality.valence4Fraction).toFixed(1)+'%' : 'Unqualified'], ['Count error', r.quality ? (100*r.quality.targetRelativeError).toFixed(1)+'%' : 'Unqualified'], ['Quality warnings', r.quality?.failures.join('; ') || 'None'], ['Solver', r.backend]];
  for (const [label, value] of rows) { const tr = document.createElement('tr'); for (const text of [label, value]) { const td = document.createElement('td'); td.textContent = text; tr.append(td); } table.append(tr); }
  const p = document.createElement('p'); p.textContent = r.guideSampleMethod + ' Topology and sampled surface checks do not certify absence of every 3D self intersection. Engineering alternatives do not establish exact native equivalence.';
  content.append(table, p); $('detailsDialog').showModal();
};
$('circleRadius').onchange = event => { editor.radius(event.target.valueAsNumber); const g = guideDocument.get(editor.selection.activeEntityId); if (g?.type === 'circle') event.target.value = g.radius; };
$('snapGuides').onchange = () => { guideSnap.clear(); };
$('objectSelection').onclick = () => editor.model('object'); $('directSelection').onclick = () => editor.model('direct');
$('deleteGuides').onclick = () => editor.remove(); $('reverseGuides').onclick = () => editor.reverse(); $('finishGuide').onclick = () => editor.finishConstruction();
window.addEventListener('keydown', event => {
  if (event.target.matches('input,select,textarea,[contenteditable]') || document.querySelector('dialog[open]')) return;
  if (event.target.closest('button,a') && ['Enter', ' '].includes(event.key)) return;
  if (event.key === 'Escape') { event.preventDefault(); if (!event.repeat) editor.escape(); return; }
  if (event.code === 'Space') { event.preventDefault(); if (!event.repeat) editor.navigate(true); return; }
  if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'z') { event.preventDefault(); historyMove(event.shiftKey ? 1 : -1); return; }
  if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'a' && state.tool === 'select') { event.preventDefault(); editor.run(() => { editor.cancel(); editor.select(guideDocument.guides.map(g => g.id)); }); return; }
  if (event.ctrlKey || event.metaKey) return;
  if (event.key === 'Enter') { event.preventDefault(); if (editor.construction) editor.finishConstruction(event.altKey); else if (state.tool === 'select') editor.model('direct'); return; }
  if (event.key === 'Backspace' && editor.construction) { event.preventDefault(); editor.backspace(); return; }
  if (['Delete', 'Backspace'].includes(event.key) && state.tool === 'select') { event.preventDefault(); editor.remove(); return; }
  if (event.altKey) return;
  const tools = { g: 'draw', p: 'polyline', s: 'spline', c: 'circle', o: 'orbit', e: 'erase' }, key = event.key.toLowerCase();
  if (tools[key]) setTool(tools[key]); if (key === 'v') editor.model('object'); if (key === 'a') editor.model('direct'); if (key === 'f') fit();
});
window.addEventListener('keyup', event => { if (event.code === 'Space') editor.navigate(false); });
window.addEventListener('blur', () => editor.contextLost());
document.addEventListener('visibilitychange', () => { if (document.hidden) editor.contextLost(); });
document.addEventListener('focusin', event => { if (!event.target.closest('[data-app-shell],dialog')) editor.contextLost(); });
window.addEventListener('resize', () => { if (editor.activity) editor.escape(); fit(); });
window.addEventListener('pagehide', () => editor.contextLost());
function render() {
  const r = canvas.getBoundingClientRect(), w = Math.max(1, Math.round(r.width)), h = Math.max(1, Math.round(r.height));
  if (canvas.width !== Math.round(w * renderer.getPixelRatio()) || canvas.height !== Math.round(h * renderer.getPixelRatio())) renderer.setSize(w, h, false);
  controls.update(); renderer.setScissorTest(true);
  const half = state.view === 'split' ? w / 2 : w;
  camera.aspect = half / h; camera.updateProjectionMatrix(); renderer.setViewport(0, 0, half, h); renderer.setScissor(0, 0, half, h); renderer.clear(); renderer.render(scenes[0], camera);
  if (state.view === 'split') { renderer.setViewport(half, 0, half, h); renderer.setScissor(half, 0, half, h); renderer.clear(); renderer.render(scenes[1], camera); }
  drawGuideChrome(); requestAnimationFrame(render);
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
window.retopoDemo = { getState: () => ({ meshId: state.mesh?.id, guides: clone(state.guides), target: state.target, mode: state.guideMode, resultFaces: state.result?.faces.length, resultJob: state.resultJob, lastAttempt: clone(state.lastAttempt), resultGuideOverlayVisible: guideGroups[1].visible, busy: state.busy, dirty: state.dirty, view: state.view, tool: state.tool, draft: clone(draft), sourceStats: state.mesh?.stats, sourceMaterial: sourceRender ? { color: sourceRender.solid.material.color.getHexString(), metalness: sourceRender.solid.material.metalness } : null, guideDocument: clone(guideDocument.guides), guideHistory: guideDocument.history, guideRevisions: Object.fromEntries(guideDocument.guides.map(g => [g.id, guideDocument.revision(g.id)])), interaction: editor.observe(), guideErrors: clone(guideErrors) }), projectPoint: (point, pane = 0) => project(point, pane), pickSource: (x, y, pane = 0) => hit(x, y, pane)?.point.toArray() || null };
renderer.setClearColor(color('--bg')); render(); start();
