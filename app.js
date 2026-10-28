import * as THREE from 'three';
import { partMarquee } from './src/view/PartMarquee.js';
import { ViewportNavigation } from './src/view/ViewportNavigation.js';
import { GuideDocument } from './src/domain/GuideDocument.js';
import { GuideController } from './src/view/GuideController.js';
import { GuideSnap } from './src/snapping/GuideSnap.js';
import { VertexSnapIndex } from './src/snapping/VertexSnapIndex.js';
import { WorkspaceShell } from './src/view/WorkspaceShell.js';
import { PartsWorkspace } from './src/view/PartsWorkspace.js';
import { CircleConstruction } from './src/view/CircleConstruction.js';
import { SurfaceGuides } from './src/view/SurfaceGuides.js';
import { fromPositions } from './src/geometry/GuideCurve.js';
import { creaseNormals } from './src/geometry/CreaseNormals.js';
import { encodeGuides, decodeGuides } from './src/io/GuideSerializer.js';

const $ = id => document.getElementById(id);
const clone = value => JSON.parse(JSON.stringify(value));
const DEFAULT_CREASE_ANGLE = 30;   // ZRemesher's feature threshold F(pi/6); mirrors crease_angle.DEFAULT
const state = { mesh: null, result: null, guides: [], tool: 'draw', view: 'split', selected: -1, target: 600, guideMode: 2, creaseAngle: DEFAULT_CREASE_ANGLE, busy: false, job: null, resultJob: null, dirty: false, space: false, version: 0, resultKey: null, density: null, lastAttempt: null };
const canvas = $('viewport');
let renderFrame = null, partsWorkspace = null;
let guidesDirty = false, guideBuildCount = 0, renderedFrames = 0;
let batchGuideSync = false, guideSyncPending = false;
let cameraGesture = false, pointerNavigation = null, spaceKeyHeld = false, requestedNavigation = null, lastCameraMotion = -Infinity, chromeResumeTimer;
let paintPointer = null;
function endPaint() { const id = paintPointer; paintPointer = null; if (id !== null && canvas.hasPointerCapture(id)) canvas.releasePointerCapture(id); }
const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: false, preserveDrawingBuffer: true });
renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
renderer.outputColorSpace = THREE.SRGBColorSpace;
const scenes = [new THREE.Scene(), new THREE.Scene()];
let camera = new THREE.PerspectiveCamera(45, 1, .01, 100);
camera.up.set(0, 0, 1);
const controls = new ViewportNavigation(camera, next => { camera = next; });
camera.position.set(2.7, -4.2, 3.4); canvas.style.touchAction = 'none';
const sourceGroup = new THREE.Group(), resultGroup = new THREE.Group();
const guideGroups = [new THREE.Group(), new THREE.Group()];
// Source creases the solver treats as guides; drawn apart from the user's own guides.
const autoGuideGroup = new THREE.Group();
scenes[0].add(sourceGroup, guideGroups[0], autoGuideGroup); scenes[1].add(resultGroup, guideGroups[1]);
for (const scene of scenes) {
  scene.add(new THREE.HemisphereLight(0xffffff, 0x627180, 2.0));
  const key = new THREE.DirectionalLight(0xffffff, 3.0); key.position.set(-3, -4, 7); scene.add(key);
  const fill = new THREE.DirectionalLight(0xffffff, .7); fill.position.set(4, 2, 1); scene.add(fill);
}
const raycaster = new THREE.Raycaster();
let sourceRender = null, resultRender = null, grids = [], draft = [], generation = 0, noticeTimer;
const ownedOperations = new Map();
const css = name => getComputedStyle(document.documentElement).getPropertyValue(name).trim();
const color = name => new THREE.Color(css(name));
const samePoint = (a, b) => a && b && a.every((x, i) => Math.abs(x - b[i]) < 1e-8);
const keyFor = () => JSON.stringify([state.mesh?.id, state.guides, state.target, state.guideMode, state.creaseAngle]);
const countText = n => n.toLocaleString();
const createGuideId = () => crypto.randomUUID();
const guideDocument = new GuideDocument(createGuideId);
const guideChrome = document.createElement('canvas'); guideChrome.id = 'guideChrome'; guideChrome.setAttribute('aria-hidden', 'true'); canvas.after(guideChrome);
const chromeContext = guideChrome.getContext('2d');
let cameraRevision = 0, persistedGeneration = '', importTicket = 0;
controls.addEventListener('change', () => {
  cameraRevision++; lastCameraMotion = performance.now(); requestRender();
  clearTimeout(chromeResumeTimer); chromeResumeTimer = setTimeout(requestRender, 110);
});
controls.addEventListener('start', () => { cameraGesture = true; guideSnap.clear(); requestRender(); });
controls.addEventListener('end', () => {
  cameraGesture = false;
  if (pointerNavigation !== null) { const id = pointerNavigation; pointerNavigation = null; if (canvas.hasPointerCapture(id)) canvas.releasePointerCapture(id); }
  requestedNavigation = null; if (!spaceKeyHeld) editor.navigate(false);
  requestRender();
});
const vertexIndex = new VertexSnapIndex(requestRender);
const surfaceGuides = new SurfaceGuides({
  project, surface: (x, y, pane) => hit(x, y, pane)?.point.toArray() || null,
  inside: (x, y, pane) => { const r = canvas.getBoundingClientRect(); return x >= r.left && x <= r.right && y >= r.top && y <= r.bottom && paneAt(x) === pane && (pane === 0 || !!resultRender); },
  shown: () => $('guidesToggle').checked, stamp: () => { const r = canvas.getBoundingClientRect(); return `${state.version}:${cameraRevision}:${state.view}:${$('guidesToggle').checked}:${r.left}:${r.top}:${r.width}:${r.height}`; },
  guides: () => guideDocument.guides,
});
const guideSnap = new GuideSnap({
  surface: (x, y, pane) => hit(x, y, pane)?.point.toArray() || null, project,
  enabled: () => $('snapGuides').checked,
  verticesEnabled: () => $('snapVertices').checked, vertices: sourceVertexCandidates,
  guides: () => guideDocument.guides,
  visible: (p, pane) => $('guidesToggle').checked && surfaceGuides.visible(p, pane),
  stamp: () => `${guideDocument.epoch}:${guideDocument.generation}:${cameraRevision}:${$('snapGuides').checked}:${$('snapVertices').checked}`,
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
  // Consume before showing: close() restores focus before its close event, and
  // that focus change can otherwise show the same queued incident again.
  $('guideErrorMessage').textContent = pendingGuideErrors.shift().message; $('guideErrorDialog').showModal();
}
$('guideErrorDialog').addEventListener('close', () => queueMicrotask(flushGuideErrors));
const expectedCaptureReleases = new Map(), captureOwners = new Map();
const editor = new GuideController(guideDocument, {
  id: createGuideId, changed: () => { if (batchGuideSync) guideSyncPending = true; else syncGuideState(); }, clearSnap: () => guideSnap.clear(), resolve: (x, y, pane, options) => guideSnap.resolve(x, y, pane, options), report: reportGuideError, busy: () => state.busy || state.preparingGeneration || !state.mesh,
  circleFrame: (x, y, pane) => circleConstruction.frame(x, y, pane), circlePreview: (c, x, y) => circleConstruction.preview(c, x, y), circleEdit: (g, pointId, delta, pane) => circleConstruction.edit(g, pointId, delta, pane), closureVisible: (p, pane) => surfaceGuides.visible(p, pane),
  closed: () => $('closedGuide').checked, pane: paneAt, project,
  cameraRevision: () => cameraRevision,
  surface: (x, y, pane) => hit(x, y, pane)?.point.toArray() || null,
  showGuides: () => { $('guidesToggle').checked = true; },
  curve: g => surfaceGuides.curve(g),
  entityExists: id => !!partsWorkspace?.entity(id),
  hit: (x, y, pane, selection) => surfaceGuides.hit(x, y, pane, selection) || (editor.tool === 'select' ? partsWorkspace?.hitPart(x, y, pane) : null),
  contained: (a, b, pane) => [...(partsWorkspace?.contained(a, b, pane) || []), ...surfaceGuides.contained(a, b, pane)],
  screenDistance: (a, b, pane) => { a = project(a, pane); b = project(b, pane); return Math.hypot(a.x - b.x, a.y - b.y); },
  capture: id => { try { canvas.setPointerCapture(id); captureOwners.set(id, { sequenceId: editor.activity.sequenceId, acknowledged: false }); return canvas.hasPointerCapture(id); } catch { captureOwners.delete(id); return false; } },
  release: id => { const owner = captureOwners.get(id); if (canvas.hasPointerCapture(id)) { if (owner?.acknowledged) expectedCaptureReleases.set(id, [...(expectedCaptureReleases.get(id) || []), owner.sequenceId]); canvas.releasePointerCapture(id); } captureOwners.delete(id); },
});
const workspaceShell = new WorkspaceShell($('appShell'), { beforeResize: () => { if (editor.activity) editor.escape(); } });
partsWorkspace = new PartsWorkspace({
  preparing: () => !!state.preparingGeneration,
  scenes, api, notify, busy: () => state.busy || !!editor.activity || !!editor.construction, cancelGuide: () => editor.escape(), setTool: tool => editor.activate(tool),
  load: (mesh, preserveCamera) => loadMesh(mesh.id, mesh, preserveCamera), showResult, disableGenerate: value => { $('generateButton').disabled = value; },
  selection: () => editor.selection, choose: (id, shift) => editor.choose(id, shift), clearSelection: () => editor.run(() => editor.select([])),
  restoreSelection: ids => editor.run(() => editor.select(ids)),
  buildPart: (mesh, group) => buildMesh(mesh, group), display: () => displaySettings(),
  assemblyFeedback: count => { state.assemblyResults = count; if (!state.result) $('resultMeta').textContent = count ? `${count} accepted part output${count === 1 ? '' : 's'}` : ''; syncResultFeedback(); },
  queryObjects: (x, y, pane, objects) => {
    const r = paneRect(pane); if (x < r.left || x > r.left + r.width || y < r.top || y > r.top + r.height) return null;
    controls.resize(r.width / r.height); camera.updateMatrixWorld();
    raycaster.setFromCamera(new THREE.Vector2((x - r.left) / r.width * 2 - 1, 1 - (y - r.top) / r.height * 2), camera);
    const solids = objects.map(o => o.userData.render?.solid || o).filter(o => o.isMesh);
    const others = visibleHit(raycaster.intersectObjects(solids, false));
    const own = sourceGroup.visible ? visibleHit(raycaster.intersectObject(sourceRender.solid, false)) : null;
    return own && (!others || own.distance < others.distance - 1e-7) ? null : others;
  },
  marquee: (objects, ownId, a, b, pane) => {
    const rect = paneRect(pane); controls.resize(rect.width / rect.height); camera.updateMatrixWorld();
    const own = pane === 0 ? sourceRender : resultRender;
    if (ownId && own) objects.push({ mesh: own.solid, id: ownId });
    return partMarquee(renderer, camera, rect, objects, a, b);
  },
  hit, project, paneAt, navigating: () => controls.enabled, render: requestRender,
  projectPoints: points => { const r = canvas.getBoundingClientRect(), width = state.view === 'split' ? r.width / 2 : r.width; controls.resize(width / r.height); camera.updateMatrixWorld(); const matrix = new THREE.Matrix4().multiplyMatrices(camera.projectionMatrix, camera.matrixWorldInverse); const vector = new THREE.Vector3(); return points.map(point => { vector.fromArray(point).applyMatrix4(matrix); return { x: r.left + (vector.x + 1) * width / 2, y: r.top + (1 - vector.y) * r.height / 2, z: vector.z }; }); },
  sourceVisible: value => { sourceGroup.visible = value; syncAutoGuideVisibility(); },
  frameOriginal: mesh => controls.frame(mesh.vertices, paneRect(0).width / paneRect(0).height),
  download: (name, text) => downloadBlob(name, text),
});
function syncGuideState() {
  state.tool = editor.tool; state.space = editor.temporary; controls.enabled = state.tool === 'orbit' || state.space;
  state.guides = guideDocument.guides.map(g => surfaceGuides.curve(g));
  state.selected = guideDocument.guides.findIndex(g => g.id === editor.selection.activeEntityId);
  draft = editor.drafts.at(-1) || [];
  canvas.className = editor.activity?.invalid || editor.construction?.invalid ? 'invalid' : state.tool;
  document.querySelectorAll('[data-tool]').forEach(button => { const active = button.dataset.tool === (requestedNavigation || state.tool); button.classList.toggle('active', active); button.setAttribute('aria-pressed', active); });
  for (const model of ['object', 'direct']) { const b = $(model + 'Selection'); b.setAttribute('aria-pressed', editor.selection.model === model); b.disabled = model === 'direct' && !guideDocument.get(editor.selection.activeEntityId); }
  $('deleteGuides').querySelector('[data-label]').textContent = editor.selection.model === 'direct' && editor.selection.pointId && guideDocument.get(editor.selection.activeEntityId)?.type !== 'circle' ? 'Delete point' : 'Delete guides';
  $('deleteGuides').disabled = !editor.selection.entityIds.some(id => guideDocument.get(id)); $('reverseGuides').disabled = !editor.selection.entityIds.some(id => guideDocument.get(id) && guideDocument.get(id).type !== 'circle');
  $('finishGuide').hidden = !editor.construction;
  $('selectionStatus').textContent = editor.activity?.invalid || editor.construction?.invalid || (editor.selection.entityIds.length ? `${editor.selection.entityIds.length} selected · ${editor.selection.model === 'direct' ? 'Edit guide points' : 'Objects'}` : 'Click a part or guide. Shift-click toggles; drag empty space to select contained objects.');
  $('canvasInstruction').textContent = { draw: 'Drag a guide. Return within 5 px of the green first point and release to close.', polyline: 'Click vertices. Click the green first point within 5 px to close; Enter finishes open.', spline: 'Click fit points. Return within 5 px of the green first point and click to close.', circle: 'Click the center, then set the radius. The center may lie over the hole.', select: 'Click a part or guide. Shift-click toggles. Middle: orbit · Shift-middle / right: pan · Scroll: zoom at cursor.', erase: 'Click a visible guide segment to remove the guide.', orbit: 'Drag to orbit. Right-drag to pan. Scroll to zoom.' }[state.tool];
  const selected = guideDocument.get(editor.selection.activeEntityId);
  const part = partsWorkspace?.entity(editor.selection.activeEntityId);
  $('selectedGuideType').textContent = selected?.type || (part ? 'Mesh part' : 'No selection');
  $('selectedGuidePoints').textContent = selected ? selected.type === 'circle' ? 'Analytic circle' : `${selected.points.length} points${selected.closed ? ' · closed' : ''}` : '—';
  if (part) $('selectedGuidePoints').textContent = part.name + (part.closed === false ? ' · Open surface' : '');
  $('circleProperties').hidden = selected?.type !== 'circle';
  if (selected?.type === 'circle' && (document.activeElement !== $('circleRadius') || $('circleRadius').dataset.guideId !== selected.id)) { $('circleRadius').value = selected.radius; $('circleRadius').dataset.guideId = selected.id; }
  workspaceShell.history(guideDocument.history);
  updateGuideUI();
  partsWorkspace?.syncSelection();
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
  requestRender();
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
  if (data.displaySmooth) {
    const { positions, normals } = creaseNormals(data.vertices, triangles);
    geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
    geometry.setAttribute('normal', new THREE.BufferAttribute(normals, 3));
  } else { geometry.setIndex(triangles); geometry.computeVertexNormals(); }
  const material = new THREE.MeshStandardMaterial({ color: data.displayColor ? new THREE.Color(data.displayColor) : color('--model'), roughness: data.displaySmooth ? .28 : .78, metalness: data.displaySmooth ? 0 : .08, flatShading: !data.displaySmooth, side: THREE.DoubleSide, polygonOffset: true, polygonOffsetFactor: 1, polygonOffsetUnits: 1 });
  const solid = new THREE.Mesh(geometry, material); group.add(solid);
  const wire = lineSegments(edgePositions(data.vertices, data.faces), color('--wire'), data.wireOpacity ?? .75); group.add(wire);
  const creases = lineSegments((data.creases || []).flatMap(([a, b]) => [...data.vertices[a], ...data.vertices[b]]), color('--crease'));
  creases.renderOrder = 2; group.add(creases);
  const pointGeometry = new THREE.BufferGeometry(); pointGeometry.setAttribute('position', new THREE.Float32BufferAttribute(data.vertices.flat(), 3));
  const points = new THREE.Points(pointGeometry, new THREE.PointsMaterial({ color: color('--wire'), size: 4, sizeAttenuation: false, depthWrite: false }));
  points.renderOrder = 2; points.visible = $('pointsToggle').checked; group.add(points);
  return { solid, wire, creases, points, displayColor: data.displayColor, wireOpacity: data.wireOpacity };
}
class Polyline extends THREE.Curve {
  constructor(points) { super(); this.points = points.map(p => new THREE.Vector3(...p)); }
  getPoint(t, output = new THREE.Vector3()) {
    const x = Math.min(t, .999999999) * (this.points.length - 1), i = Math.floor(x);
    return output.copy(this.points[i]).lerp(this.points[i + 1], x - i);
  }
}
function renderGuides() {
  guidesDirty = true; requestRender();
}
function rebuildGuides() {
  guideBuildCount++;
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
  requestRender();
  guideGroups.forEach((group, pane) => group.visible = $('guidesToggle').checked && (pane === 0 || (state.view === 'split' && !!resultRender)));
  syncAutoGuideVisibility();
}
function setAttempt(phase, message = '', context = null) {
  state.lastAttempt = { phase, message, jobId: context?.jobId ?? state.job ?? null, target: context?.target ?? state.target, guideCount: context?.guideCount ?? state.guides.length, sourceSha256: context?.sourceSha256 ?? state.mesh?.sourceSha256 };
  if (state.mesh) try {
    const key = 'retopo-1:last-attempt:' + state.mesh.id;
    if (phase === 'failed' || phase === 'cancelled') localStorage.setItem(key, JSON.stringify(state.lastAttempt));
    else localStorage.removeItem(key);
  } catch { /* Optional operation history. */ }
  syncResultFeedback();
}
const jobActivity = new Map();
function logJobActivity(job) {
  const activity = jobActivity.get(job.id) || { cursor: 0, stage: null, heartbeat: 0 };
  const entries = [], prefix = `Job ${job.id.slice(0, 8)} · `;
  for (const event of job.events || []) {
    if (event.cursor <= activity.cursor) continue;
    entries.push({ message: prefix + event.message, time: event.time, level: event.level, jobId: job.id });
    for (const measurement of event.details?.measurements || []) {
      if (!Number.isFinite(measurement.value) || !Number.isFinite(measurement.limit)) continue;
      entries.push({ message: prefix + `${measurement.check}: ${measurement.value.toPrecision(5)}; limit ${measurement.limit.toPrecision(5)}${measurement.limit > 0 ? ` (${(measurement.value / measurement.limit).toFixed(2)}× limit)` : ''}`, time: event.time, level: event.level, jobId: job.id });
    }
    activity.cursor = event.cursor;
  }
  if (job.stage !== activity.stage && !entries.length) entries.push({ message: prefix + job.stage, jobId: job.id });
  if (entries.length) activity.heartbeat = Date.now();
  else if (job.state === 'running' && Date.now() - activity.heartbeat > 30000) {
    entries.push({ message: prefix + `Still working · ${job.stage} · ${Math.round(job.elapsedSeconds || 0)}s elapsed`, jobId: job.id }); activity.heartbeat = Date.now();
  }
  activity.stage = job.stage; jobActivity.set(job.id, activity);
  if (jobActivity.size > 100) jobActivity.delete(jobActivity.keys().next().value);
  workspaceShell.addLogs(entries);
}
async function restoreAttemptActivity(mesh, version) {
  if (!mesh.partSource || state.lastAttempt?.phase !== 'failed') return;
  const jobId = state.lastAttempt.jobId;
  try {
    const job = await api(jobId ? `/api/jobs/${jobId}?after=${jobActivity.get(jobId)?.cursor || 0}` : `/api/parts/${mesh.partSource}/latest-job`);
    if (version !== state.version || state.busy || state.preparingGeneration || job.sourceSha256 !== mesh.sourceSha256 || job.state !== 'failed') return;
    logJobActivity(job); setAttempt('failed', job.error, { ...state.lastAttempt, jobId: job.id });
  } catch { /* Stored attempts remain usable when detailed logs are unavailable. */ }
}
function syncResultFeedback() {
  const attempt = state.lastAttempt, failed = attempt?.phase === 'failed', cancelled = attempt?.phase === 'cancelled';
  const stopping = attempt?.phase === 'cancelling', unconfirmed = attempt?.phase === 'cancellation-failed';
  const needsPart = partsWorkspace?.doc?.leaves().length > 1 && !partsWorkspace.active;
  const selectedScope = needsPart ? partsWorkspace.generationScope() : null;
  const title = unconfirmed ? 'Cancellation not confirmed' : stopping ? 'Cancellation requested' : failed ? 'Last generation failed' : cancelled ? 'Generation cancelled' : selectedScope?.enabled ? 'Ready to generate selected part' : needsPart ? 'Select one part to begin' : 'No generated mesh';
  const attemptContext = Number.isInteger(attempt?.target) && Number.isInteger(attempt?.guideCount) ? ` Attempted ${countText(attempt.target)} quads with ${attempt.guideCount} guide${attempt.guideCount === 1 ? '' : 's'}.` : '';
  const detail = unconfirmed ? 'The calculation may still be running. Retry cancellation or Reset; your guides are saved.' : stopping ? 'Waiting for the local service to confirm the calculation has stopped.' : failed ? attempt.message + attemptContext : cancelled ? 'Your guides are saved. Click Generate to try again.' : selectedScope?.enabled ? `Generate selected opens ${selectedScope.node.name} and uses the displayed target with its saved guides. Work on selected opens it for editing first.` : needsPart ? 'Select one included part, then Generate selected. Use Work on selected to edit its guides and density first.' : 'Click Generate to build a mesh from the current source and guides.';
  $('resultEmpty').hidden = !!state.result || state.assemblyResults > 0;
  $('resultEmpty').dataset.state = failed || unconfirmed ? 'failed' : cancelled ? 'cancelled' : 'ready';
  $('resultEmptyTitle').textContent = title; $('resultEmptyDetail').textContent = detail;
  $('generationFeedback').hidden = !(failed || cancelled || stopping || unconfirmed) || (!state.result && state.view === 'split');
  $('generationFeedback').textContent = title + '. ' + detail + (state.result ? ' The previous accepted result is still shown.' : '');
  $('generationFeedback').classList.toggle('overlay', state.view === 'overlay');
  syncGuideVisibility();
}
function drawGuideChrome() {
  const r = canvas.getBoundingClientRect(), dpr = renderer.getPixelRatio();
  if (guideChrome.width !== Math.round(r.width * dpr) || guideChrome.height !== Math.round(r.height * dpr)) { guideChrome.width = Math.round(r.width * dpr); guideChrome.height = Math.round(r.height * dpr); }
  const ctx = chromeContext; ctx.setTransform(dpr, 0, 0, dpr, 0, 0); ctx.clearRect(0, 0, r.width, r.height);
  // Editable handles require source raycasts. Restore them when the camera settles.
  if (cameraGesture || performance.now() - lastCameraMotion < 100) return;
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
    if (snap?.pane === pane) { const p = local(project(snap.position, pane)); ctx.strokeStyle = css('--accent'); ctx.beginPath(); if (snap.kind === 'vertex') ctx.rect(p.x - 6, p.y - 6, 12, 12); else ctx.arc(p.x, p.y, 10, 0, Math.PI * 2); ctx.stroke(); }
    ctx.restore();
  }
}
function displaySettings() {
  const ghost = $('ghostToggle').checked, opacity = Number($('ghostOpacity').value) / 100;
  $('ghostOpacityControl').hidden = !ghost; $('ghostOpacityValue').textContent = `${Math.round(opacity * 100)}%`;
  document.querySelectorAll('[data-display-toggle]').forEach(button => button.setAttribute('aria-pressed', $(button.dataset.displayToggle).checked));
  for (const mesh of [sourceRender, resultRender, ...(partsWorkspace?.groups.flatMap(g => g.children.map(o => o.userData.render).filter(Boolean)) || [])]) if (mesh) {
    mesh.wire.visible = $('wireToggle').checked; mesh.creases.visible = $('creasesToggle').checked;
    mesh.points.visible = $('pointsToggle').checked;
    const overlaySource = mesh === sourceRender && state.view === 'overlay' && !!state.result;
    const transparent = ghost || overlaySource;
    const material = mesh.solid.material;
    if (material.transparent !== !!transparent) { material.transparent = !!transparent; material.needsUpdate = true; }
    material.opacity = ghost ? opacity : overlaySource ? .25 : 1; material.depthWrite = !transparent;
    mesh.wire.material.opacity = overlaySource ? .18 : mesh.wireOpacity ?? .75;
  }
  syncGuideVisibility();
}
function refreshColors() {
  renderer.setClearColor(color('--bg'));
  scenes.forEach(scene => { scene.background = color('--bg'); });
  for (const mesh of [sourceRender, resultRender, ...(partsWorkspace?.groups.flatMap(g => g.children.map(o => o.userData.render).filter(Boolean)) || [])]) if (mesh) {
    mesh.solid.material.color.copy(mesh.displayColor ? new THREE.Color(mesh.displayColor) : color('--model')); mesh.wire.material.color.copy(color('--wire')); mesh.creases.material.color.copy(color('--crease')); mesh.points.material.color.copy(color('--wire'));
  }
  for (const item of autoGuideGroup.children) item.material.color.copy(color('--auto-guide'));
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
function fit(top = false, preserveDirection = true) {
  if (!sourceRender) return;
  if (top) { camera.position.copy(controls.target).add(new THREE.Vector3(0, -.0001, 1).normalize().multiplyScalar(controls.snapshot().distance)); controls.update(); return; }
  const chosen = partsWorkspace?.selectedParts().filter(n => !n.excluded) || [];
  const points = chosen.flatMap(n => (n.partSource ? partsWorkspace.models.get(n.partSource) : partsWorkspace.doc.source)?.vertices || []);
  const rect = paneRect(0);
  controls.frame(points.length ? points : state.mesh.vertices, rect.width / rect.height);
}
function setView(view) {
  const changed = state.view !== view; state.view = view; const overlay = view === 'overlay';
  document.querySelectorAll('[data-view]').forEach(button => { button.classList.toggle('active', button.dataset.view === view); button.setAttribute('aria-pressed', button.dataset.view === view); });
  $('divider').hidden = overlay; $('resultCaption').hidden = overlay; $('sourceCaption').style.width = overlay ? '100%' : '50%';
  $('sourceCaption').querySelector('.label').textContent = overlay && state.result ? 'Source + retopology' : 'Source';
  (overlay ? scenes[0] : scenes[1]).add(resultGroup);
  syncGuideVisibility();
  displaySettings();
  $('resultEmpty').style.display = overlay ? 'none' : '';
  syncResultFeedback();
  if (changed) fit(false, true);
}
function setTool(tool) {
  if (['draw', 'polyline', 'spline', 'circle'].includes(tool) && partsWorkspace?.doc?.leaves().length > 1 && (!partsWorkspace.active || partsWorkspace.selectedParts().some(n => n.id !== partsWorkspace.active))) { notify('Select a part and choose Work on selected before drawing its guides.'); return; }
  if (partsWorkspace) { partsWorkspace.paint = false; $('partsPaint').setAttribute('aria-pressed', false); }
  if (tool === 'orbit' || tool === 'pan') { requestedNavigation = tool; editor.navigate(true); if (!editor.temporary) requestedNavigation = null; return; }
  controls.end(); requestedNavigation = null; editor.activate(tool);
}
function paneRect(pane) {
  const r = canvas.getBoundingClientRect(), width = state.view === 'split' ? r.width / 2 : r.width;
  return { left: r.left + pane * width, top: r.top, width, height: r.height };
}
function project(point, pane = 0) {
  const r = canvas.getBoundingClientRect(), width = state.view === 'split' ? r.width / 2 : r.width;
  controls.resize(width / r.height); camera.updateMatrixWorld();
  const p = new THREE.Vector3(...point).project(camera);
  return { x: r.left + (state.view === 'split' ? pane * width : 0) + (p.x + 1) * width / 2, y: r.top + (1 - p.y) * r.height / 2, z: p.z };
}
function paneAt(x) {
  const r = canvas.getBoundingClientRect();
  return state.view === 'split' && x >= r.left + r.width / 2 ? 1 : 0;
}
function updateVertexIndex() {
  if (!$('snapVertices').checked || !state.mesh) return;
  const r = canvas.getBoundingClientRect(), width = state.view === 'split' ? r.width / 2 : r.width;
  controls.resize(width / r.height); camera.updateMatrixWorld();
  const matrix = new THREE.Matrix4().multiplyMatrices(camera.projectionMatrix, camera.matrixWorldInverse);
  vertexIndex.update({ key: `${state.version}:${cameraRevision}:${width}:${r.height}`, matrix: matrix.elements, width, height: r.height });
}
function sourceVertexCandidates(x, y, pane, prior) {
  if (!state.mesh) return [];
  updateVertexIndex();
  const r = canvas.getBoundingClientRect(), width = state.view === 'split' ? r.width / 2 : r.width;
  let candidates = vertexIndex.nearby(x - r.left - pane * width, y - r.top);
  if (!vertexIndex.ready) {
    // While the new view is indexing, the front hit triangle is a bounded fallback.
    const face = hit(x, y, pane)?.face;
    candidates = face ? [...new Set([face.a, face.b, face.c])].map(vertexId => {
      const p = project(state.mesh.vertices[vertexId], pane);
      return { vertexId, distance: Math.hypot(x - p.x, y - p.y) };
    }).filter(c => c.distance <= 12).sort((a, b) => a.distance - b.distance || a.vertexId - b.vertexId) : [];
  }
  const visible = candidate => {
    const position = state.mesh.vertices[candidate.vertexId], p = project(position, pane), surface = hit(p.x, p.y, pane)?.point;
    // Ghosting reveals back points visually; it never grants through-surface snapping.
    return surface && surface.distanceTo(new THREE.Vector3(...position)) <= 1e-5 ? { ...candidate, position } : null;
  };
  const retained = prior?.kind === 'vertex' && prior.pane === pane ? candidates.find(c => c.vertexId === prior.vertexId) : null;
  const first = retained && visible(retained);
  if (first) return [first];
  for (const candidate of candidates) { const found = visible(candidate); if (found) return [found]; }
  return [];
}
function hit(x, y, requiredPane = null) {
  if (!sourceRender) return null;
  const r = canvas.getBoundingClientRect(), w = state.view === 'split' ? r.width / 2 : r.width;
  if (x < r.left || x > r.right || y < r.top || y > r.bottom) return null;
  const pane = paneAt(x);
  if ((requiredPane !== null && pane !== requiredPane) || (pane === 1 && !resultRender)) return null;
  const left = r.left + pane * w;
  controls.resize(w / r.height); camera.updateMatrixWorld();
  raycaster.setFromCamera(new THREE.Vector2((x - left) / w * 2 - 1, 1 - (y - r.top) / r.height * 2), camera);
  // Both views share the source coordinate frame. Always attach guides to the
  // original source, so a new solve never depends on the previous output mesh.
  const own = visibleHit(raycaster.intersectObject(sourceRender.solid, false));
  if (own && partsWorkspace?.viewMode === 'working' && partsWorkspace.context) {
    const solids = partsWorkspace.groups[0].children.map(o => o.userData.render?.solid || o).filter(o => o.isMesh);
    const occluder = visibleHit(raycaster.intersectObjects(solids, false));
    if (occluder && occluder.distance < own.distance - 1e-7) return null;
  }
  return own;
}
function visibleHit(hits) { return hits.find(h => { const depth = h.point.clone().project(camera).z; return depth >= -1 && depth <= 1; }) || null; }
function persist() {
  if (!state.mesh) return;
  try { localStorage.setItem('retopo-1:' + state.mesh.id, JSON.stringify({ ...JSON.parse(encodeGuides(guideDocument, state.mesh.sourceSha256, state.guides)), target: state.target, guideMode: state.guideMode, creaseAngle: state.creaseAngle, creaseAngleSet: !!state.creaseAngleSet })); partsWorkspace?.renderList(); } catch { /* Storage is optional. */ }
}
function dirty() {
  state.dirty = state.resultKey !== keyFor();
  if (state.result) { $('resultBadge').hidden = false; $('resultBadge').className = 'badge' + (state.dirty ? '' : state.result.quality?.passed && state.result.featureValidation?.passed !== false ? ' good' : ' busy'); $('resultBadge').textContent = state.dirty ? 'Needs update' : !state.result.quality?.passed ? 'Quality warning' : state.result.featureValidation?.passed === false ? 'Feature drift' : state.resultJob ? 'Generated' : 'Example'; }
  if (state.result) updateMetrics();
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
canvas.addEventListener('pointerdown', e => {
  if (pointerNavigation !== null || paintPointer !== null || editor.activity) return;
  const navigation = e.button === 2 || e.button === 1 && e.shiftKey ? 'pan' : e.button === 1 ? 'orbit' : e.button === 0 && (editor.temporary || editor.tool === 'orbit') ? (e.shiftKey ? 'pan' : requestedNavigation || 'orbit') : null;
  if (navigation) {
    e.preventDefault(); canvas.focus(); editor.navigate(true);
    if (!editor.temporary) return;
    pointerNavigation = e.pointerId; canvas.setPointerCapture(e.pointerId);
    controls.begin(navigation, e.clientX, e.clientY, paneRect(paneAt(e.clientX))); return;
  }
  if (e.button === 0 && partsWorkspace?.pointer(e)) { e.preventDefault(); canvas.focus(); paintPointer = e.pointerId; canvas.setPointerCapture(e.pointerId); return; }
  if (!controls.enabled && e.button === 0) { e.preventDefault(); canvas.focus(); editor.down(pointerValue(e)); }
}, { capture: true });
canvas.addEventListener('pointermove', e => {
  if (pointerNavigation === e.pointerId) { controls.move(e.clientX, e.clientY); return; }
  if (paintPointer === e.pointerId) { partsWorkspace?.pointer(e); return; }
  if (controls.enabled) return;
  if (!editor.activity && !editor.construction) {
    if (!state.busy && ['draw', 'polyline', 'spline'].includes(editor.tool)) guideSnap.resolve(e.clientX, e.clientY, paneAt(e.clientX), { bypass: e.altKey });
    else guideSnap.clear();
    requestRender(); return;
  }
  const samples = e.getCoalescedEvents?.() || [];
  batchGuideSync = true;
  try { for (const sample of samples) editor.move(pointerValue(sample)); editor.move(pointerValue(e)); }
  finally { batchGuideSync = false; if (guideSyncPending) { guideSyncPending = false; syncGuideState(); } }
});
canvas.addEventListener('pointerup', e => { if (paintPointer === e.pointerId) { partsWorkspace?.pointer(e); endPaint(); return; } if (pointerNavigation === e.pointerId) { controls.move(e.clientX, e.clientY); controls.end(); return; } editor.up(pointerValue(e)); });
canvas.addEventListener('pointercancel', e => { if (paintPointer === e.pointerId) endPaint(); else if (pointerNavigation === e.pointerId) controls.end(); else editor.cancelPointer(e.pointerId); });
canvas.addEventListener('gotpointercapture', e => { const owner = captureOwners.get(e.pointerId); if (owner) owner.acknowledged = true; });
canvas.addEventListener('lostpointercapture', e => {
  if (paintPointer === e.pointerId) { endPaint(); return; }
  if (pointerNavigation === e.pointerId) { controls.end(); return; }
  const expected = expectedCaptureReleases.get(e.pointerId);
  if (expected?.length) { expected.shift(); if (!expected.length) expectedCaptureReleases.delete(e.pointerId); return; }
  editor.cancelPointer(e.pointerId);
});
canvas.addEventListener('wheel', event => {
  event.preventDefault(); if (editor.activity || pointerNavigation !== null || paintPointer !== null) return;
  controls.dolly(event.deltaY * (event.deltaMode === 1 ? 16 : event.deltaMode === 2 ? canvas.clientHeight : 1), event.clientX, event.clientY, paneRect(paneAt(event.clientX)));
}, { passive: false });
canvas.addEventListener('contextmenu', event => event.preventDefault());
canvas.addEventListener('pointerleave', () => { guideSnap.clear(); requestRender(); });

const maximumTarget = () => state.mesh?.maxTargetQuads ?? 1800;
function setTarget(value) {
  const requested = Math.round(Number(value));
  if (!Number.isFinite(requested) || requested < 150 || requested > maximumTarget()) {
    $('targetNumber').value = state.target; $('targetRange').value = state.target;
    notify(`Supported targets are 150–${countText(maximumTarget())} quads. The target was not changed.`, true); return;
  }
  state.target = requested; $('targetNumber').value = state.target; $('targetRange').value = state.target; updateDensity(); dirty(); persist(); refreshAutoGuides();
}
const usesSourceCreases = mesh => ['surface-quads', 'open-surface-quads'].includes(mesh?.solver);
function setCreaseAngle(value) {
  if (!Number.isFinite(value) || value < 10 || value > 120) {
    $('creaseAngle').value = state.creaseAngle; notify('Crease angle must be from 10° to 120°. It was not changed.', true); return;
  }
  state.creaseAngle = value; state.creaseAngleSet = true; $('creaseAngle').value = value; dirty(); persist(); refreshAutoGuides();
}
// The server runs the solver's own crease detection, so what is drawn is what a solve will follow.
let autoGuideTimer = null, autoGuideTicket = 0, autoGuideData = null;
function refreshAutoGuides() {
  clearTimeout(autoGuideTimer);
  autoGuideTimer = setTimeout(loadAutoGuides, 150);
}
function clearAutoGuides(message = '') {
  ++autoGuideTicket; autoGuideData = null; dispose(autoGuideGroup); $('creaseInfo').textContent = message; syncAutoGuideVisibility();
}
async function loadAutoGuides() {
  const mesh = state.mesh;
  if (!usesSourceCreases(mesh)) { clearAutoGuides(); return; }
  const ticket = ++autoGuideTicket, base = mesh.partSource ? `/api/parts/${mesh.partSource}` : `/api/mesh/${mesh.baseMeshId || mesh.id}`;
  try {
    const data = await api(`${base}/creases?angle=${state.creaseAngle}&target=${state.target}`);
    if (ticket !== autoGuideTicket || mesh !== state.mesh) return;
    autoGuideData = data; buildAutoGuides(mesh.vertices, data.edges);
    $('creaseInfo').textContent = data.resolvedEdges ? `${countText(data.resolvedEdges)} crease edges in ${countText(data.chains)} chains guide the solver.${data.fragmentEdges ? ` ${countText(data.fragmentEdges)} edges in fragments smaller than one quad are ignored.` : ''}` : `No creases at ${data.angleDegrees}° or sharper${data.fragmentEdges ? `; ${countText(data.fragmentEdges)} small fragment edges are ignored` : ''}.`;
  } catch (error) {
    if (ticket !== autoGuideTicket) return;
    autoGuideData = null; dispose(autoGuideGroup); $('creaseInfo').textContent = 'Auto guides are unavailable: ' + error.message;
  }
  syncAutoGuideVisibility();
}
const AUTO_GUIDE_RADIUS = .006;
function buildAutoGuides(vertices, edges) {
  dispose(autoGuideGroup);
  if (!edges.length) return;
  // One instanced tube per crease edge: thick enough to see, a single draw call.
  const mesh = new THREE.InstancedMesh(new THREE.CylinderGeometry(AUTO_GUIDE_RADIUS, AUTO_GUIDE_RADIUS, 1, 5, 1, true), new THREE.MeshBasicMaterial({ color: color('--auto-guide') }), edges.length);
  const a = new THREE.Vector3(), b = new THREE.Vector3(), up = new THREE.Vector3(0, 1, 0), middle = new THREE.Vector3(), direction = new THREE.Vector3(), turn = new THREE.Quaternion(), size = new THREE.Vector3(), matrix = new THREE.Matrix4();
  edges.forEach(([i, j], n) => {
    a.fromArray(vertices[i]); b.fromArray(vertices[j]); direction.subVectors(b, a); const length = direction.length();
    turn.setFromUnitVectors(up, length > 1e-12 ? direction.divideScalar(length) : up);
    mesh.setMatrixAt(n, matrix.compose(middle.addVectors(a, b).multiplyScalar(.5), turn, size.set(1, Math.max(length, 1e-9), 1)));
  });
  mesh.instanceMatrix.needsUpdate = true; mesh.frustumCulled = false; mesh.renderOrder = 3; mesh.userData.autoGuides = true;
  autoGuideGroup.add(mesh);
}
function syncAutoGuideVisibility() {
  autoGuideGroup.visible = $('autoGuidesToggle').checked && sourceGroup.visible && usesSourceCreases(state.mesh); requestRender();
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
  const recommended = state.mesh.recommendedTarget, coarse = Number.isFinite(recommended) && state.target < recommended;
  $('densityWarning').hidden = !coarse && Number(finer.toFixed(1)) <= 1.5;
  $('densityWarning').textContent = coarse ? `Start around ${countText(recommended)} quads to resolve this model's small creases and guide paths.` : 'Finer than the source mesh.';
  for (const [id, factor] of densityButtons) {
    const wanted = Math.round(d.quads * factor), supported = wanted >= 150 && wanted <= maximumTarget();
    $(id).disabled = !supported;
    $(id).title = supported ? `Set the target to ${countText(wanted)} quads` : `${countText(wanted)} quads is outside the supported 150–${countText(maximumTarget())} range`;
  }
}
const densityButtons = [['halfButton', .5], ['sameButton', 1], ['doubleButton', 2]];
async function loadMesh(id, suppliedMesh = null, preserveCamera = false) {
  $('notice').hidden = true;
  editor.run(() => { editor.cancel(); editor.select([]); }); ++importTicket;
  const version = ++state.version; if (state.busy || state.job) await cancelGeneration();
  $('generateButton').disabled = true; const mesh = suppliedMesh || await api('/api/mesh/' + id); if (version !== state.version) return;
  state.mesh = mesh; state.density = sourceDensity(mesh); state.result = null; state.assemblyResults = 0; state.resultJob = null; state.resultKey = null; state.selected = -1; state.lastAttempt = null;
  try { const attempt = JSON.parse(localStorage.getItem('retopo-1:last-attempt:' + id)); if (attempt?.sourceSha256 === mesh.sourceSha256 && ['failed', 'cancelled'].includes(attempt.phase) && typeof attempt.message === 'string') state.lastAttempt = attempt; } catch { /* Optional operation history. */ }
  let loadedGuides = (id === 'hexagon' ? [] : mesh.presets[0]?.curves || []).map(c => fromPositions(c, 'polyline', false, createGuideId, { detectClosure: true })); state.target = mesh.target; state.guideMode = 2; state.creaseAngle = DEFAULT_CREASE_ANGLE; state.creaseAngleSet = false;
  try { const saved = JSON.parse(localStorage.getItem('retopo-1:' + id)); if (saved?.sourceSha256 === mesh.sourceSha256) { loadedGuides = decodeGuides({ ...saved, coordinateFrame: 'source' }, mesh.sourceSha256, createGuideId); if (Number.isInteger(saved.target) && saved.target >= 150 && saved.target <= maximumTarget()) state.target = saved.target; // A saved angle counts only when the user set it; earlier saves carried the default of the day.
      if (saved.creaseAngleSet && Number.isFinite(saved.creaseAngle) && saved.creaseAngle >= 10 && saved.creaseAngle <= 120) { state.creaseAngle = saved.creaseAngle; state.creaseAngleSet = true; } state.guideMode = saved.guideMode === 1 && id === 'cylinder' ? 1 : 2; } } catch { /* Ignore incompatible saved data. */ }
  draft = []; dispose(resultGroup); resultRender = null; clearAutoGuides(); $('creaseControl').hidden = !usesSourceCreases(mesh); $('creaseAngle').value = state.creaseAngle;
  sourceRender = buildMesh(mesh, sourceGroup); vertexIndex.setSource(mesh.vertices, version); surfaceGuides.setSource(mesh); guideDocument.load(loadedGuides); $('sourceMeta').textContent = `${countText(mesh.faces.length)} triangles`; $('meshDescription').textContent = mesh.description; $('workspaceModelName').textContent = mesh.title; $('solverNote').classList.toggle('experimental', !!mesh.experimentalRetopology);
  const credit = $('sourceCredit'); credit.replaceChildren(); const author = document.createElement(mesh.source.url ? 'a' : 'span'); author.textContent = mesh.source.author;
  if (mesh.source.url) { author.href = mesh.source.url; author.target = '_blank'; author.rel = 'noreferrer'; } const license = document.createElement('span'); license.textContent = mesh.source.license; credit.append(author, license);
  $('presetSelect').replaceChildren(...mesh.presets.map((p, i) => new Option(p.name, i))); $('presetSelect').disabled = $('presetButton').disabled = !mesh.presets.length; $('modeControl').hidden = id !== 'cylinder'; $('guideMode').value = state.guideMode;
  $('solverNote').textContent = mesh.solverNotice || (id === 'hexagon' ? 'Hard edges and the hole stay fixed. Guides steer continuous edge loops.' : 'Curves influence the solved field. These examples can take one to three minutes.');
  $('targetNumber').max = $('targetRange').max = maximumTarget();
  $('densityLimits').textContent = `Supported: 150–${countText(maximumTarget())} quads. Half / Same / Double are relative to the source; unavailable targets are disabled.`;
  setTarget(state.target); updateGuideUI(); buildGrids(); if (!preserveCamera) controls.frame(mesh.vertices, paneRect(0).width / paneRect(0).height); updateMetrics(); setView(state.view);
  $('resultEmpty').hidden = false; $('resultLabel').textContent = 'Retopology'; $('resultMeta').textContent = ''; $('resultBadge').hidden = true; $('exportMesh').disabled = true; $('detailsButton').disabled = true;
  if (mesh.previewUrl) {
    try { const preview = await api(mesh.previewUrl); if (version === state.version) showResult(preview, null, preview.curves || [], preview.target, preview.guideMode || 2); } catch { /* A missing preview does not disable live generation. */ }
  }
  if (version !== state.version) return;
  await partsWorkspace?.sourceLoaded(mesh);
  if (version !== state.version) return;
  $('generateButton').disabled = mesh.repair?.closed === false; partsWorkspace?.renderList(); workspaceShell.addLog('Loaded ' + mesh.title + '.');
  if (!mesh.partSource) { try { localStorage.setItem('retopo-1:last-model', mesh.id); } catch { /* Optional workspace preference. */ } }
  syncResultFeedback();
  void restoreAttemptActivity(mesh, version);
}
function showResult(result, job, curves, target, mode) {
  state.result = result; state.resultJob = job; state.resultKey = JSON.stringify([state.mesh.id, curves, target, mode, result.featureValidation?.detection?.angleDegrees ?? state.creaseAngle]);
  if (job) setAttempt('complete', '', { target, guideCount: curves.length, sourceSha256: result.sourceSha256 });
  resultRender = buildMesh({ ...result, displayColor: state.mesh.displayColor, displaySmooth: state.mesh.displaySmooth, wireOpacity: state.mesh.wireOpacity }, resultGroup); $('resultEmpty').hidden = true; $('resultMeta').textContent = `${countText(result.faces.length)} faces`;
  $('resultLabel').textContent = job ? 'Retopology' : 'Example result'; $('exportMesh').disabled = false; $('detailsButton').disabled = false;
  updateMetrics(); displaySettings(); dirty(); setView(state.view);
  partsWorkspace?.captureResult(result, job, curves, target, mode);
}
function updateMetrics() {
  const r = state.result;
  if (!r) { for (const id of ['faceMetric', 'quadMetric', 'guideMetric', 'topologyMetric']) $(id).textContent = '—'; $('faceDetail').textContent = 'Generate a mesh to compare'; $('quadDetail').textContent = 'No generated mesh'; $('guideDetail').textContent = 'No measured result'; $('topologyDetail').textContent = 'No measured result'; $('resultSummary').textContent = 'A local, working demonstration of guided retopology.'; return; }
  const stats = r.stats; $('faceMetric').textContent = countText(r.faces.length); $('faceDetail').textContent = `${countText(state.mesh.faces.length)} source triangles · target ${r.target}`;
  $('quadMetric').textContent = `${r.quadPercent.toFixed(r.quadPercent === 100 ? 0 : 1)}%`; $('quadDetail').textContent = `${countText(stats.quads)} quads · ${stats.triangles} triangles`;
  const distances = r.guideAlignment?.map(a => a.p95Distance) || [], distance = Math.max(0, ...distances);
  $('guideMetric').textContent = distances.length ? distance < .0001 ? '<0.0001' : distance.toPrecision(3) : '—';
  $('guideDetail').textContent = distances.length ? r.guidePaths?.length ? 'Measured output edge-path fit · p95' : 'Nearest edges · path not verified' : 'No guides in this result';
  $('topologyMetric').textContent = r.quality?.passed ? r.featureValidation?.passed ? 'Checks passed' : r.featureValidation?.passed === false ? 'Feature drift' : 'Geometry checked' : r.quality ? 'Needs work' : 'Unqualified';
  $('topologyDetail').textContent = r.quality ? `${r.featureValidation?.passed ? 'Resolved source creases checked' : r.featureValidation?.passed === false ? 'Source crease checks failed' : 'Source features not checked'} · min angle ${r.quality.minimumAngleDegrees.toFixed(0)}°` : 'Quad shape has not been checked';
  $('resultSummary').textContent = `${r.backend === 'engineering-guided-surface-quads' ? 'Quad surface solver' : r.backend === 'engineering-structured-prismatic-annulus' ? 'Continuous quad grid' : r.backend === 'engineering-planar-pslg-quads' ? 'Planar surface solver' : r.backend === 'heightfield-enclosure' ? 'Terrain enclosure solver' : 'Recovered field solver'} · ${r.elapsedSeconds.toFixed(1)}s · ${r.guideCount} guide${r.guideCount === 1 ? '' : 's'}`;
  if (state.dirty) $('resultSummary').textContent += ` · Previous result; current document has ${state.guides.length} guides`;
}
async function generate() {
  if (state.busy || state.preparingGeneration || !state.mesh) return;
  if (partsWorkspace?.previewData || partsWorkspace?.pending) return notify('Apply or cancel the part preview first.', true);
  if (editor.activity || editor.construction) return reportGuideError('Finish or cancel the current guide before generating.');
  const scope = partsWorkspace?.generationScope();
  if (!scope?.enabled) return notify(scope?.reason || 'Choose a source to generate.', true);
  if (scope.node.id !== (partsWorkspace.active || 'original')) {
    const target = state.target, document = partsWorkspace.doc, node = scope.node;
    state.preparingGeneration = true; partsWorkspace.renderList();
    try {
      await partsWorkspace.workSelected();
      if (partsWorkspace.doc !== document || partsWorkspace.active !== node.id || state.mesh.partSource !== node.partSource) return;
      setTarget(target);
    } catch (error) { notify(error.message, true); return; }
    finally { state.preparingGeneration = false; partsWorkspace.renderList(); }
  }
  const request = { requestId: crypto.randomUUID().replaceAll('-', ''), meshId: state.mesh.baseMeshId || state.mesh.id, ...(state.mesh.partSource ? { partSource: state.mesh.partSource } : {}), curves: clone(state.guides), target: state.target, guideMode: state.guideMode, creaseAngle: state.creaseAngle };
  const attempt = { target: request.target, guideCount: request.curves.length, sourceSha256: state.mesh.sourceSha256 };
  if (!request.partSource && (request.meshId === 'cylinder' || state.mesh.requiresGuides) && !request.curves.length) return notify('Draw a guide or load the example network for this curved mesh.', true);
  workspaceShell.showLog(); workspaceShell.addLog(`Generating ${state.mesh.title} · target ${request.target.toLocaleString()} quads · ${request.curves.length} guides · crease angle ${request.creaseAngle}°`);
  setAttempt('running', '', attempt);
  const token = ++generation; state.busy = true; $('processing').hidden = false; $('generateButton').disabled = true; $('notice').hidden = true;
  const started = performance.now(); const timer = setInterval(() => { if (token !== generation) { clearInterval(timer); return; } $('processTime').textContent = `${Math.round((performance.now() - started) / 1000)}s`; }, 300);
  $('processTitle').textContent = 'Generating retopology'; $('processTime').textContent = '0s'; $('processDetail').textContent = state.mesh.solver === 'surface-quads' ? 'Building a quad layout, fitting your guide paths and checking the source surface…' : request.meshId === 'hexagon' ? 'Laying out continuous guide loops and sizing quad strips…' : 'Solving the field and fitting the mesh. This can take one to three minutes…';
  if (state.mesh.featureLayout) $('processDetail').textContent = 'Preserving source creases and your guide paths. Detailed meshes can take 15–25 minutes; you can cancel at any time.';
  const operation = { requestId: request.requestId };
  ownedOperations.set(operation.requestId, operation);
  $('cancelButton').textContent = 'Cancel calculation';
  try {
    const first = await api('/api/remesh', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(request) });
    if (token !== generation) {
      await cancelOperation(operation);
      return;
    }
    if (first.state === 'cancelled') { ownedOperations.delete(operation.requestId); setAttempt('cancelled', '', attempt); return; }
    state.job = first.id;
    attempt.jobId = first.id;
    if (state.lastAttempt?.phase === 'running') state.lastAttempt.jobId = first.id;
    while (token === generation) {
      const job = await api('/api/jobs/' + first.id + '?after=' + (jobActivity.get(first.id)?.cursor || 0)); if (token !== generation) return;
      logJobActivity(job);
      if (job.moreEvents) continue;
      if (['complete', 'failed', 'cancelled'].includes(job.state)) { ownedOperations.delete(operation.requestId); }
      $('processTitle').textContent = job.stage;
      if (job.state === 'complete') {
        const result = await api(job.resultUrl); if (token !== generation) return;
        showResult(result, first.id, request.curves, request.target, request.guideMode); notify(`Generated ${countText(result.faces.length)} quads. ${result.featureValidation?.passed === false ? 'Geometry checks passed; source crease checks failed.' : 'Geometry checks passed.'}`, result.featureValidation?.passed === false); return;
      }
      if (job.state === 'failed') throw new Error(job.error);
      if (job.state === 'cancelled') { setAttempt('cancelled', '', attempt); return; }
      await new Promise(resolve => setTimeout(resolve, 500));
    }
  } catch (error) {
    if (token === generation) { setAttempt('failed', error.message, attempt); notify(error.message, true, true); }
    // A polling/transport error does not prove that the worker stopped.
    if (ownedOperations.has(operation.requestId)) { try { await cancelOperation(operation); } catch { /* Ownership and retry feedback are retained. */ } }
  }
  finally { clearInterval(timer); if (token === generation) { state.busy = false; state.job = null; $('generateButton').disabled = false; partsWorkspace?.renderList(); } syncCancellationUI(); }
}
// The progress card starts centred on the screen and can be dragged by its header (or moved with the
// arrow keys; Home re-centres it); the position is kept for the session and clamped to the window.
function makeMovable(card, handle) {
  document.body.appendChild(card);   // fixed positioning relative to the window, whatever the workspace does
  let drag = null;
  const clamp = (value, low, high) => Math.min(Math.max(value, low), high);
  const place = (x, y) => { card.dataset.moved = ''; card.style.left = clamp(x, 0, innerWidth - card.offsetWidth) + 'px'; card.style.top = clamp(y, 0, innerHeight - card.offsetHeight) + 'px'; };
  const centre = () => { delete card.dataset.moved; card.style.left = card.style.top = ''; };
  handle.onpointerdown = event => { if (event.button !== 0 || event.target.closest('button')) return; const box = card.getBoundingClientRect(); drag = { id: event.pointerId, dx: event.clientX - box.left, dy: event.clientY - box.top }; handle.setPointerCapture(event.pointerId); event.preventDefault(); };
  handle.onpointermove = event => { if (drag?.id === event.pointerId) place(event.clientX - drag.dx, event.clientY - drag.dy); };
  const end = event => { if (drag?.id !== event.pointerId) return; if (handle.hasPointerCapture(event.pointerId)) handle.releasePointerCapture(event.pointerId); drag = null; };
  handle.onpointerup = end; handle.onpointercancel = end;
  handle.onkeydown = event => {
    const step = { ArrowLeft: [-10, 0], ArrowRight: [10, 0], ArrowUp: [0, -10], ArrowDown: [0, 10] }[event.key];
    if (event.key === 'Home') { centre(); event.preventDefault(); }
    else if (step) { const box = card.getBoundingClientRect(); place(box.left + step[0], box.top + step[1]); event.preventDefault(); }
  };
  addEventListener('resize', () => { if ('moved' in card.dataset) place(parseFloat(card.style.left), parseFloat(card.style.top)); });
}
function outstandingOperations() { return [...ownedOperations.values()]; }
function syncCancellationUI() {
  if (state.busy) return;
  const stopping = outstandingOperations().filter(operation => operation.cancelling);
  $('processing').hidden = !stopping.length;
  if (stopping.length) {
    const failed = stopping.some(operation => operation.cancelError);
    $('processTitle').textContent = failed ? 'Cancellation not confirmed' : 'Stopping calculation';
    $('processDetail').textContent = failed ? 'The calculation may still be running. Your guides are saved; retry when the local service is reachable.' : 'Waiting for the local service to confirm cancellation…';
    $('processTime').textContent = '';
    $('cancelButton').textContent = failed ? 'Retry cancellation' : 'Cancel calculation';
  }
  const relevant = stopping.filter(operation => operation.feedbackToken === generation);
  if (['cancelling', 'cancellation-failed'].includes(state.lastAttempt?.phase)) {
    if (!relevant.length) setAttempt('cancelled', '', state.lastAttempt);
    else setAttempt(relevant.some(operation => operation.cancelError) ? 'cancellation-failed' : 'cancelling', '', state.lastAttempt);
  }
}
async function cancelOperation(operation) {
  if (operation.cancelPromise) return operation.cancelPromise;
  if (!ownedOperations.has(operation.requestId)) return;
  operation.cancelling = true; operation.cancelError = null;
  operation.cancelPromise = (async () => {
    try {
      const job = await api('/api/requests/' + operation.requestId + '/cancel', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' });
      if (!['cancelled', 'complete', 'failed'].includes(job.state)) throw new Error('The local service has not confirmed cancellation.');
      ownedOperations.delete(operation.requestId);
      if (!state.busy && !outstandingOperations().some(op => op.cancelling)) notify('Calculation stopped. Your guides are saved.');
    } catch (error) {
      operation.cancelError = error.message;
      notify('Cancellation not confirmed. ' + error.message + ' Retry cancellation or Reset.', true, true);
      throw error;
    } finally { operation.cancelPromise = null; syncCancellationUI(); }
  })();
  return operation.cancelPromise;
}
async function cancelGeneration(options = {}) {
  const wasBusy = state.busy, attempt = state.lastAttempt;
  ++generation; state.busy = false; state.job = null; $('generateButton').disabled = false;
  partsWorkspace?.renderList();
  for (const operation of outstandingOperations()) { operation.cancelling = true; operation.feedbackToken = generation; }
  if (wasBusy || ['cancelling', 'cancellation-failed'].includes(attempt?.phase)) setAttempt('cancelling', '', attempt);
  syncCancellationUI();
  const cancelled = await Promise.allSettled([...ownedOperations.values()].map(cancelOperation));
  const failure = cancelled.find(result => result.status === 'rejected');
  if (failure && options.propagateError) throw failure.reason;
}
function downloadBlob(name, data) {
  const url = URL.createObjectURL(new Blob([data], { type: name.endsWith('.obj') ? 'text/plain' : 'application/json' })), a = document.createElement('a'); a.href = url; a.download = name; a.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
}
$('generateButton').onclick = generate; $('cancelButton').onclick = cancelGeneration; makeMovable($('processing'), $('processingHandle'));
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
for (const id of ['wireToggle', 'guidesToggle', 'autoGuidesToggle', 'creasesToggle', 'pointsToggle', 'ghostToggle']) $(id).onchange = () => { displaySettings(); persistViewer(); };
$('creaseAngle').onchange = event => setCreaseAngle(event.target.valueAsNumber);
document.querySelectorAll('[data-display-toggle]').forEach(button => button.onclick = () => { const input = $(button.dataset.displayToggle); input.checked = !input.checked; input.dispatchEvent(new Event('change')); });
$('ghostOpacity').oninput = () => { displaySettings(); persistViewer(); };
$('fitButton').onclick = () => { editor.run(() => editor.cancel()); fit(); };
for (const name of ['front', 'top', 'right', 'isometric']) $(name + 'Button').onclick = () => { controls.end(); controls.standardView(name); $('projectionSelect').value = controls.snapshot().projection; };
$('projectionSelect').onchange = () => { controls.end(); controls.setProjection($('projectionSelect').value); };
$('resetButton').onclick = () => $('resetDialog').showModal();
$('confirmReset').onclick = async () => {
  const button = $('confirmReset'), label = button.textContent;
  button.disabled = true; button.textContent = 'Stopping calculation…';
  try {
    await cancelGeneration({ propagateError: true });
    // Request IDs exist before submission. Server cancellation also records
    // requests that have not arrived, so delayed delivery cannot start a worker
    // after this page reloads. An admission acknowledgement is no longer needed.
    // The theme is a viewer preference, not part of the work being discarded.
    try { for (const key of Object.keys(localStorage)) if (key.startsWith('retopo-1:') && key !== 'retopo-1:theme') localStorage.removeItem(key); } catch { /* Storage is optional. */ }
    location.reload();
  } catch (error) { $('resetDialog').close(); notify('Reset could not stop the calculation. ' + error.message, true, true); }
  finally { button.disabled = false; button.textContent = label; }
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
$('exportMesh').onclick = () => { if (!state.result) return; const a = document.createElement('a'); a.href = state.resultJob ? state.result.partSource ? `/api/parts/${state.result.partSource}/results/${state.resultJob}/output.obj` : `/api/jobs/${state.resultJob}/output.obj` : `/assets/previews/${state.mesh.id}.obj`; a.download = `${state.mesh.id}-retopology.obj`; a.click(); };
$('detailsButton').onclick = () => {
  const r = state.result, s = r.stats, content = $('detailsContent'); content.replaceChildren();
  const table = document.createElement('table');
  const rows = [['Vertices', r.vertices.length], ['Faces', r.faces.length], ['Quads / triangles', `${s.quads} / ${s.triangles}`], ['Components', s.faceConnectedComponents], ['Boundary edges', s.boundaryEdges], ['Nonmanifold edges', s.nonmanifoldEdges], ['Nonmanifold vertices', r.vertexLinks.nonmanifoldVertices.length], ['Inconsistent winding edges', r.vertexLinks.inconsistentWindingEdges], ['Euler characteristic', s.eulerCharacteristic], ['Detected output creases', r.creases.length], ['Calculation time', r.elapsedSeconds.toFixed(3) + 's'], ['Minimum quad angle', r.quality?.minimumAngleDegrees.toFixed(2) + '°'], ['Worst edge ratio', r.quality?.edgeRatioMax.toFixed(3)], ['Minimum scaled Jacobian', r.quality?.scaledJacobianMin.toFixed(3)], ['Regular valence-four vertices', r.quality ? (100*r.quality.valence4Fraction).toFixed(1)+'%' : 'Unqualified'], ['Count error', r.quality ? (100*r.quality.targetRelativeError).toFixed(1)+'%' : 'Unqualified'], ['Geometry check failures', r.quality?.failures.join('; ') || 'None'], ['Source feature preservation', r.featureValidation ? (r.featureValidation.passed ? 'Checked' : 'Failed') : 'Not checked'], ...(r.featureValidation?.detection ? [['Source crease angle', r.featureValidation.detection.angleDegrees + '°']] : []), ['Solver', r.backend]];
  if (r.boundaryValidation) rows.push(['Original boundary loops', r.boundaryValidation.loops], ['Boundary preservation', r.boundaryValidation.passed ? 'Checked in both directions' : 'Failed'], ['Boundary tolerance', r.boundaryValidation.tolerance.toPrecision(4)], ['Added caps', 'None']);
  for (const [label, value] of rows) { const tr = document.createElement('tr'); for (const text of [label, value]) { const td = document.createElement('td'); td.textContent = text; tr.append(td); } table.append(tr); }
  const p = document.createElement('p'); p.textContent = r.guideSampleMethod + ' Topology and sampled surface checks do not certify absence of every 3D self intersection. Engineering alternatives do not establish exact native equivalence.';
  content.append(table, p); $('detailsDialog').showModal();
};
$('circleRadius').onchange = event => { editor.radius(event.target.valueAsNumber); const g = guideDocument.get(editor.selection.activeEntityId); if (g?.type === 'circle') event.target.value = g.radius; };
for (const id of ['snapGuides', 'snapVertices']) $(id).onchange = () => { guideSnap.clear(); updateVertexIndex(); requestRender(); persistViewer(); };
function persistViewer() {
  const ids = ['wireToggle', 'guidesToggle', 'autoGuidesToggle', 'creasesToggle', 'pointsToggle', 'ghostToggle', 'snapGuides', 'snapVertices'];
  try { localStorage.setItem('retopo-1:viewer', JSON.stringify({ ...Object.fromEntries(ids.map(id => [id, $(id).checked])), ghostOpacity: Number($('ghostOpacity').value) })); } catch { /* Optional view preferences. */ }
}
$('objectSelection').onclick = () => editor.model('object'); $('directSelection').onclick = () => editor.model('direct');
$('deleteGuides').onclick = () => editor.remove(); $('reverseGuides').onclick = () => editor.reverse(); $('finishGuide').onclick = () => editor.finishConstruction();
window.addEventListener('keydown', event => {
  if (event.target.matches('input,select,textarea,[contenteditable]') || document.querySelector('dialog[open]')) return;
  if (event.target.closest('button,a') && ['Enter', ' '].includes(event.key)) return;
  if (event.key === 'Escape') { event.preventDefault(); const wasNavigation = editor.temporary; endPaint(); controls.end(); requestedNavigation = null; if (!event.repeat) { if (wasNavigation) editor.contextLost(); else if (!partsWorkspace?.escape()) editor.escape(); } return; }
  if (event.code === 'Space') { event.preventDefault(); spaceKeyHeld = true; if (!event.repeat) editor.navigate(true); return; }
  if (event.key === 'F10') { event.preventDefault(); if (!event.repeat) { $('pointsToggle').checked = !$('pointsToggle').checked; displaySettings(); persistViewer(); } return; }
  if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'z') { event.preventDefault(); historyMove(event.shiftKey ? 1 : -1); return; }
  if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'a' && state.tool === 'select') { event.preventDefault(); editor.run(() => { editor.cancel(); editor.select([...(partsWorkspace?.selectableParts().map(n => 'part:' + n.id) || []), ...guideDocument.guides.map(g => g.id)]); }); return; }
  if (event.ctrlKey || event.metaKey) return;
  if (event.key === 'Enter') { event.preventDefault(); if (editor.construction) editor.finishConstruction(event.altKey); else if (state.tool === 'select') editor.model('direct'); return; }
  if (event.key === 'Backspace' && editor.construction) { event.preventDefault(); editor.backspace(); return; }
  if (['Delete', 'Backspace'].includes(event.key) && state.tool === 'select') { event.preventDefault(); editor.remove(); return; }
  if (event.altKey) return;
  const tools = { g: 'draw', p: 'polyline', s: 'spline', c: 'circle', o: 'orbit', h: 'pan', e: 'erase' }, key = event.key.toLowerCase();
  if (tools[key]) setTool(tools[key]); if (key === 'v') editor.model('object'); if (key === 'a') editor.model('direct'); if (key === 'f') fit();
});
window.addEventListener('keyup', event => { if (event.code === 'Space') { spaceKeyHeld = false; if (pointerNavigation === null) editor.navigate(false); } });
function leaveInteractions() {
  spaceKeyHeld = false;
  endPaint();
  controls.end(); requestedNavigation = null;
  if (pointerNavigation !== null) canvas.dispatchEvent(new PointerEvent('pointercancel', { pointerId: pointerNavigation }));
  cameraGesture = false; pointerNavigation = null; editor.contextLost();
}
window.addEventListener('blur', leaveInteractions);
document.addEventListener('visibilitychange', () => { if (document.hidden) leaveInteractions(); else requestRender(); });
document.addEventListener('focusin', event => { if (!event.target.closest('[data-app-shell],dialog')) editor.contextLost(); });
window.addEventListener('resize', () => { if (editor.activity) editor.escape(); fit(); });
window.addEventListener('pagehide', leaveInteractions);
// Render changed views and damping frames; an idle mesh must not compete with
// the solver for CPU when WebGL falls back to software rendering.
function requestRender() {
  if (renderFrame === null) renderFrame = requestAnimationFrame(render);
}
new ResizeObserver(requestRender).observe(canvas);
canvas.addEventListener('webglcontextrestored', requestRender);
function render() {
  renderFrame = null;
  if (guidesDirty) { guidesDirty = false; rebuildGuides(); }
  const r = canvas.getBoundingClientRect(), w = Math.max(1, Math.round(r.width)), h = Math.max(1, Math.round(r.height));
  if (canvas.width !== Math.round(w * renderer.getPixelRatio()) || canvas.height !== Math.round(h * renderer.getPixelRatio())) renderer.setSize(w, h, false);
  controls.update(); renderer.setScissorTest(true);
  updateVertexIndex(); renderedFrames++;
  const half = state.view === 'split' ? w / 2 : w;
  controls.resize(half / h); renderer.setViewport(0, 0, half, h); renderer.setScissor(0, 0, half, h); renderer.clear(); renderer.render(scenes[0], camera);
  if (state.view === 'split') { renderer.setViewport(half, 0, half, h); renderer.setScissor(half, 0, half, h); renderer.clear(); renderer.render(scenes[1], camera); }
  drawGuideChrome();
}
async function start() {
  try {
    const theme = localStorage.getItem('retopo-1:theme'); if (theme === 'light' || theme === 'dark') document.documentElement.dataset.theme = theme;
    try {
      const saved = JSON.parse(localStorage.getItem('retopo-1:viewer'));
      for (const id of ['wireToggle', 'guidesToggle', 'autoGuidesToggle', 'creasesToggle', 'pointsToggle', 'ghostToggle', 'snapGuides', 'snapVertices']) if (typeof saved?.[id] === 'boolean') $(id).checked = saved[id];
      if (Number.isFinite(saved?.ghostOpacity)) $('ghostOpacity').value = Math.max(10, Math.min(70, saved.ghostOpacity));
    } catch { /* Invalid viewer preferences do not affect guides. */ }
    const [health, catalog] = await Promise.all([api('/api/health'), api('/api/catalog')]);
    $('connection').className = 'badge good'; $('connection').innerHTML = '<i class="dot"></i>Local engine ready';
    $('meshSelect').replaceChildren(...catalog.map(m => new Option(m.title, m.id))); $('meshSelect').disabled = false;
    let lastModel; try { lastModel = localStorage.getItem('retopo-1:last-model'); } catch { /* Storage is optional. */ }
    const initialModel = catalog.some(m => m.id === lastModel) ? lastModel : 'hexagon'; $('meshSelect').value = initialModel;
    await loadMesh(initialModel); refreshColors();
  } catch (error) { $('connection').className = 'badge error'; $('connection').textContent = 'Service unavailable'; notify(error.message + ' Start the app using start.cmd.', true, true); }
}
// Read-only inspection hooks support reproducible canvas interaction checks.
window.retopoDemo = { getState: () => ({ meshId: state.mesh?.id, guides: clone(state.guides), target: state.target, mode: state.guideMode, creaseAngle: state.creaseAngle, autoGuideEdges: autoGuideData?.edges.length ?? null, autoGuidesVisible: autoGuideGroup.visible, resultFaces: state.result?.faces.length, resultJob: state.resultJob, lastAttempt: clone(state.lastAttempt), resultGuideOverlayVisible: guideGroups[1].visible, busy: state.busy, dirty: state.dirty, view: state.view, tool: state.tool, draft: clone(draft), sourceStats: state.mesh?.stats, sourceMaterial: sourceRender ? { color: sourceRender.solid.material.color.getHexString(), metalness: sourceRender.solid.material.metalness } : null, guideDocument: clone(guideDocument.guides), guideHistory: guideDocument.history, guideRevisions: Object.fromEntries(guideDocument.guides.map(g => [g.id, guideDocument.revision(g.id)])), interaction: editor.observe(), guideErrors: clone(guideErrors) }), projectPoint: (point, pane = 0) => project(point, pane), pickSource: (x, y, pane = 0) => hit(x, y, pane)?.point.toArray() || null };
renderer.setClearColor(color('--bg')); requestRender(); start();
window.retopoDemo.getPartsState = () => partsWorkspace.observe();
window.retopoDemo.getViewerState = () => ({
  points: $('pointsToggle').checked, edges: $('wireToggle').checked, ghosted: $('ghostToggle').checked,
  snapVertices: $('snapVertices').checked, snap: guideSnap.marker ? clone(guideSnap.marker) : null,
  source: sourceRender ? { pointCount: sourceRender.points.geometry.attributes.position.count, pointsVisible: sourceRender.points.visible, edgesVisible: sourceRender.wire.visible, opacity: sourceRender.solid.material.opacity, depthWrite: sourceRender.solid.material.depthWrite } : null,
  result: resultRender ? { pointCount: resultRender.points.geometry.attributes.position.count, pointsVisible: resultRender.points.visible, opacity: resultRender.solid.material.opacity } : null,
  camera: { position: camera.position.toArray(), target: controls.target.toArray(), revision: cameraRevision, navigating: cameraGesture },
  vertexIndex: { worker: !!vertexIndex.worker, ready: vertexIndex.ready, completed: vertexIndex.completed }, guideBuildCount, renderedFrames,
});

window.retopoDemo.getCameraState = () => controls.snapshot();
window.retopoDemo.pickPart = (x, y, pane = 0) => partsWorkspace.hitPart(x, y, pane)?.guideId || null;
