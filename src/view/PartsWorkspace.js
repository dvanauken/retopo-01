import * as THREE from 'three';
import { PartsDocument, assemblyOBJ } from '../domain/PartsDocument.js';

const $ = id => document.getElementById(id);
const copy = value => JSON.parse(JSON.stringify(value));
export class PartsWorkspace {
  constructor(hooks) {
    this.h = hooks; this.models = new Map(); this.results = new Map(); this.selected = new Set(); this.paint = false; this.context = false; this.ticket = 0;
    this.groups = hooks.scenes.map(scene => { const g = new THREE.Group(); scene.add(g); return g; });
    this.markers = new THREE.Group(); hooks.scenes[0].add(this.markers);
    this.selectionOverlay = new THREE.Group(); hooks.scenes[0].add(this.selectionOverlay);
    this.contextRevision = 0; this.viewMode = 'original'; this.selectionStamp = '';
    this.buildUI();
  }
  buildUI() {
    const section = document.createElement('section'); section.className = 'panel-section parts-panel'; section.id = 'partsPanel';
    section.innerHTML = `<h2 class="section-title">Parts <span class="badge" id="partsCount">1</span></h2>
      <div class="parts-actions"><button id="partsOriginal">Original</button><button id="partsAssembly">Assembly</button><button id="partsUndo">Undo split</button></div>
      <p class="hint">Click a part in the model or list. Shift-click adds or removes a part.</p>
      <div class="parts-actions"><button id="partsWork" class="primary">Work on selected</button><button id="partsShowAll">Show assembly</button></div>
      <div class="parts-actions"><button id="partsExcludeSelected">Exclude selected</button><button id="partsKeepSelected">Keep only selected</button><button id="partsRestoreAll">Restore all</button></div>
      <div class="parts-actions"><button id="partsUndoEdit">Undo inclusion / name</button><button id="partsRedoEdit">Redo</button></div>
      <p class="hint" id="partsWorkStatus" role="status"></p>
      <div id="partsList" class="parts-list"></div>
      <label class="inline-check"><input id="partsContext" type="checkbox">Show other parts</label>
      <label class="inline-check"><input id="partsCaps" type="checkbox" checked>Show current cut caps in gold</label>
      <details id="partsSelection"><summary>Split or exclude a region</summary>
        <p class="hint">Paint visible faces. Alt removes faces; orbit to reach the back. A split follows triangle edges.</p>
        <div class="parts-actions"><button id="partsPaint" aria-pressed="false">Paint faces</button><button id="partsGrow">Grow</button><button id="partsShrink">Shrink</button><button id="partsClear">Clear</button></div>
        <label class="field-label">Brush size <input id="partsBrush" type="range" min="5" max="70" value="22" aria-label="Face brush radius"></label>
        <p id="partsSelectedCount" class="hint">0 faces selected</p>
        <label class="field-label" for="partsName">New part name</label><input id="partsName" maxlength="80" value="New part">
        <label class="inline-check"><input id="partsExclude" type="checkbox">Exclude selected region</label>
        <button id="partsPreviewFaces">Preview face split</button>
        <div id="partsToiletExamples"><p class="hint">Toilet starting selections</p><button id="partsHandle">Select flush handle</button></div>
        <hr><label class="field-label">Plane cut <select id="partsAxis"><option value="0">X</option><option value="1">Y</option><option value="2" selected>Z</option></select></label>
        <input id="partsPlaneRange" type="range" min="-1" max="1" step=".001" value=".82" aria-label="Cut plane position">
        <input id="partsPlaneValue" type="number" step=".001" value=".82" aria-label="Cut plane coordinate">
        <p class="hint">The new part is on the positive side of the plane. Original coordinates are retained.</p><button id="partsPreviewPlane">Preview plane split</button>
      </details>
      <div id="partsReview" hidden><p class="hint" id="partsReviewText"></p><div class="parts-actions"><button id="partsApply" class="primary">Apply split</button><button id="partsCancel">Cancel</button></div></div>
      <p id="partsStatus" class="hint" role="status"></p>
      <div class="parts-actions"><button id="partsExport">Assembly OBJ</button><button id="partsSave">Save parts</button><button id="partsLoad">Load parts</button></div>
      <input id="partsFile" type="file" accept=".json" hidden>`;
    document.querySelector('.navigator .panel-body').children[0].after(section);
    const action = (id, fn) => $(id).onclick = () => this.guard(fn);
    action('partsOriginal', async () => { await this.activate(null); this.viewMode = 'original'; await this.renderContext(); }); action('partsAssembly', () => this.assembly());
    action('partsWork', () => this.workSelected()); action('partsShowAll', () => this.assembly());
    action('partsExcludeSelected', () => this.excludeSelected()); action('partsRestoreAll', () => this.restoreAll());
    action('partsKeepSelected', async () => {
      const ids = new Set(this.selectedParts().filter(n => !n.excluded).map(n => n.id));
      if (!ids.size) throw new Error('Select at least one included part.');
      this.doc.edit('Keep only selected', () => { for (const n of this.doc.leaves()) if (n.id !== 'original' && !n.excluded && !ids.has(n.id)) this.doc.exclude(n.id); });
      this.save(); await this.renderContext(); this.selectionStamp = ''; this.syncSelection();
    });
    action('partsUndo', async () => { const node = this.doc.undoSplit(); if (node) { this.save(); await this.activate(node.id === 'original' ? null : node.id); } });
    for (const [id, delta] of [['partsUndoEdit', -1], ['partsRedoEdit', 1]]) action(id, async () => { if (this.doc.moveEdit(delta)) { this.save(); await this.renderContext(); this.selectionStamp = ''; this.syncSelection(); } });
    action('partsPaint', () => { this.paint = !this.paint; this.h.cancelGuide(); this.h.setTool('select'); $('partsPaint').setAttribute('aria-pressed', this.paint); });
    action('partsClear', () => { this.selected.clear(); this.selectionChanged(); });
    action('partsGrow', () => this.expand(false)); action('partsShrink', () => this.expand(true));
    action('partsPreviewFaces', () => this.preview(false)); action('partsPreviewPlane', () => this.preview(true));
    action('partsApply', () => this.apply()); action('partsCancel', () => this.cancelPreview());
    action('partsHandle', () => this.handleSelection());
    action('partsExport', () => this.export()); action('partsSave', () => this.exportProject()); action('partsLoad', () => $('partsFile').click());
    $('partsFile').onchange = () => this.guard(() => this.importProject());
    $('partsContext').onchange = () => { this.context = $('partsContext').checked; this.renderContext(); };
    $('partsCaps').onchange = () => this.renderMarkers();
    $('partsPlaneRange').oninput = () => { $('partsPlaneValue').value = $('partsPlaneRange').value; this.renderMarkers(); };
    $('partsPlaneValue').oninput = () => { $('partsPlaneRange').value = $('partsPlaneValue').value; this.renderMarkers(); };
    $('partsAxis').onchange = () => this.planeBounds();
    $('partsSelection').ontoggle = () => this.renderMarkers();
  }
  async guard(fn) {
    if (this.h.busy() || this.h.preparing?.() || this.switching || this.pending) return this.h.notify('Wait for the active operation or cancel it first.', true);
    try { await fn(); } catch (e) { this.h.notify(e.message, true); $('partsStatus').textContent = e.message; }
  }
  key() { return 'retopo-1:parts:' + this.doc.source.id; }
  save() {
    try { localStorage.setItem(this.key(), JSON.stringify(this.doc.data)); }
    catch { this.h.notify('Parts could not be saved in browser storage. Use Save parts before leaving.', true); }
    this.renderList();
  }
  async sourceLoaded(mesh) {
    if (mesh.partSource) { this.current = mesh; this.selected.clear(); this.index(); this.renderList(); await this.renderContext(); this.renderMarkers(); return; }
    if (this.switching && this.doc?.source.id === mesh.id) {
      this.current = mesh; this.selected.clear(); this.index(); this.renderList(); await this.renderContext(); this.renderMarkers(); return;
    }
    ++this.ticket; this.active = null; this.current = mesh; this.context = false; $('partsContext').checked = false;
    this.paint = false; this.pending = false; this.previewData = null; this.h.sourceVisible(true); $('partsReview').hidden = true; $('partsPaint').setAttribute('aria-pressed', false);
    let saved = null; try { saved = JSON.parse(localStorage.getItem('retopo-1:parts:' + mesh.id)); } catch { /* Invalid storage is handled below. */ }
    try { this.doc = new PartsDocument(mesh, saved, () => crypto.randomUUID()); } catch { this.doc = new PartsDocument(mesh, null, () => crypto.randomUUID()); this.h.notify('Saved parts do not match this source; the original has been loaded.', true); }
    this.viewMode = this.doc.leaves().length > 1 ? 'assembly' : 'original';
    this.h.clearSelection(); this.selectionStamp = '';
    this.selected.clear(); this.index(); this.renderList(); await this.renderContext(); this.renderMarkers();
  }
  async model(node) {
    if (!node.partSource) return this.doc.source;
    if (!this.models.has(node.partSource)) this.models.set(node.partSource, await this.h.api('/api/parts/' + node.partSource));
    return this.models.get(node.partSource);
  }
  async result(node) {
    if (!node.result) return null;
    if (!this.results.has(node.result.job)) {
      try { this.results.set(node.result.job, await this.h.api(`/api/parts/${node.partSource}/results/${node.result.job}`)); }
      catch { return null; }
    }
    return this.results.get(node.result.job);
  }
  async activate(id, { preserveCamera = false } = {}) {
    if (this.h.busy()) throw new Error('Cancel the current calculation before changing parts.');
    if (this.previewData) this.cancelPreview();
    this.paint = false; $('partsPaint').setAttribute('aria-pressed', false); this.h.cancelGuide();
    const selection = this.selectedParts().map(n => 'part:' + n.id);
    const ticket = ++this.ticket, node = id ? this.doc.data.nodes[id] : null;
    const mesh = node ? await this.model(node) : this.doc.source;
    if (ticket !== this.ticket) return;
    this.active = id;
    this.viewMode = node ? 'working' : 'original'; this.context = false; $('partsContext').checked = false;
    this.switching = true;
    try { await this.h.load({ ...mesh, ...(node ? { id: this.doc.source.id + '--part-' + node.id, title: node.name, partNodeId: node.id } : {}) }, preserveCamera); }
    finally { this.switching = false; }
    if (ticket !== this.ticket) return;
    this.h.restoreSelection(selection.filter(id => this.entity(id)));
    if (node?.result) { const result = await this.result(node); if (result && ticket === this.ticket) this.h.showResult(result, node.result.job, node.result.curves, node.result.target, node.result.mode); }
    this.planeBounds(); this.renderList(); await this.renderContext();
    if (mesh.canRemesh === false || node?.excluded) this.h.disableGenerate(true);
  }
  entity(id) { return id?.startsWith('part:') ? this.doc?.leaves().find(n => n.id === id.slice(5)) : null; }
  selectedParts() { return (this.h.selection()?.entityIds || []).map(id => this.entity(id)).filter(Boolean); }
  canRemesh() { return this.current?.canRemesh ?? this.current?.repair?.closed !== false; }
  generationScope() {
    const chosen = this.selectedParts(), leaves = this.doc?.leaves() || [];
    const node = chosen.length === 1 ? chosen[0] : chosen.length ? null : this.active ? this.doc.data.nodes[this.active] : leaves.length === 1 ? leaves[0] : null;
    const mesh = node?.id === this.active ? this.current : node?.partSource ? this.models.get(node.partSource) : node ? this.doc.source : null;
    const supported = !!mesh && (mesh.canRemesh ?? mesh.repair?.closed !== false);
    const reason = this.h.busy() || this.h.preparing?.() || this.switching ? 'Finish or cancel the active operation first.' : this.pending || this.previewData ? 'Apply or cancel the part preview first.' : !node ? 'Select exactly one part to generate.' : node.excluded ? 'Restore the selected part before generating.' : !supported ? 'This part has no supported generation route. Undo its split to restore it.' : '';
    return { node, enabled: !reason, reason };
  }
  selectableParts() { return this.doc?.leaves().filter(n => !n.excluded && (this.viewMode !== 'working' || this.context || n.id === this.active)) || []; }
  choose(node, shift = false) { this.h.choose('part:' + node.id, shift); }
  async workSelected() {
    const nodes = this.selectedParts();
    if (nodes.length !== 1 || nodes[0].excluded) throw new Error('Select one included part to work on.');
    const node = nodes[0]; await this.activate(node.id === 'original' ? null : node.id);
    this.choose(node); this.h.setTool('select');
  }
  async toggleExcluded(node) {
    this.doc.edit('Change inclusion', () => this.doc.exclude(node.id)); this.save(); this.selectionStamp = '';
    if (this.active === node.id) this.h.disableGenerate(node.excluded || !this.canRemesh());
    await this.renderContext(); this.syncSelection();
  }
  async excludeSelected() {
    const nodes = this.selectedParts().filter(n => !n.excluded && n.id !== 'original');
    this.doc.edit('Exclude selected', () => { for (const node of nodes) this.doc.exclude(node.id); });
    this.save(); await this.assembly();
  }
  async restoreAll() {
    this.doc.edit('Restore all', () => { for (const node of this.doc.leaves()) if (node.excluded && (node.closed !== false || this.doc.source.initialParts?.some(p => p.id === node.id))) this.doc.exclude(node.id); });
    this.save(); await this.renderContext(); this.selectionStamp = ''; this.syncSelection();
  }
  syncSelection() {
    if (!this.doc) return;
    const stamp = this.h.selection().revision + ':' + this.contextRevision + ':' + this.viewMode;
    if (this.selectionStamp === stamp) return;
    this.selectionStamp = stamp; const nodes = this.selectedParts();
    this.renderList(); this.clearGroup(this.selectionOverlay);
    for (const n of nodes) {
      if (n.excluded || this.viewMode === 'working' && !this.context && n.id !== this.active) continue;
      const mesh = n.partSource ? this.models.get(n.partSource) : this.doc.source;
      if (!mesh) continue;
      this.addMesh(mesh, this.selectionOverlay, 0x2878eb, .45);
    }
    this.h.render();
  }
  hitPart(x, y, pane) {
    if (!this.doc || this.previewData) return null;
    const hit = this.h.queryObjects(x, y, pane, this.groups[pane].children);
    if (hit?.object.userData.partId) return { guideId: 'part:' + hit.object.userData.partId, pointId: null, kind: 'part' };
    if (this.viewMode !== 'assembly' && (this.viewMode !== 'working' || !this.doc.data.nodes[this.active]?.excluded)) {
      const own = this.h.hit(x, y, pane);
      if (own) return { guideId: 'part:' + (this.active || 'original'), pointId: null, kind: 'part' };
    }
    return null;
  }
  contained(a, b, pane) {
    if (!this.doc || this.previewData) return [];
    const objects = this.groups[pane].children.map(o => o.userData.render?.solid || o).filter(o => o.isMesh && o.userData.partId).map(mesh => ({ mesh, id: 'part:' + mesh.userData.partId }));
    return this.h.marquee(objects, this.viewMode !== 'assembly' && !this.doc.data.nodes[this.active]?.excluded ? 'part:' + (this.active || 'original') : null, a, b, pane);
  }

  captureResult(result, job, curves, target, mode) {
    if (!this.active || !job || result.partSource !== this.current.partSource) return;
    const node = this.doc.data.nodes[this.active];
    node.result = { job, curves: copy(curves), target, mode }; this.results.set(job, result); this.save(); this.renderContext();
  }
  stale(node) {
    if (!node.result) return false;
    try { const saved = JSON.parse(localStorage.getItem('retopo-1:' + this.doc.source.id + '--part-' + node.id)); return saved && (saved.target !== node.result.target || JSON.stringify(saved.curves) !== JSON.stringify(node.result.curves)); } catch { return true; }
  }
  renderList() {
    if (!this.doc) return;
    const list = $('partsList'); list.replaceChildren();
    const leaves = this.doc.leaves(); $('partsCount').textContent = leaves.length;
    for (const node of leaves) {
      const selected = this.h.selection()?.entityIds.includes('part:' + node.id);
      const row = document.createElement('div'); row.className = 'part-row' + (selected ? ' active' : '') + (node.excluded ? ' excluded' : ''); row.dataset.partId = node.id;
      const name = document.createElement('button'); name.className = 'part-name'; name.textContent = node.name; name.setAttribute('aria-pressed', !!selected); name.onclick = e => this.guard(() => this.choose(node, e.shiftKey));
      const status = document.createElement('small'); status.textContent = node.excluded ? 'Excluded' : node.result ? this.stale(node) ? 'Previous output · needs update' : 'Accepted output' : `${node.closed === false ? 'Open surface' : 'Source part'}${this.active === node.id ? ' · Working' : ''}`;
      const rename = document.createElement('button'); rename.textContent = 'Rename'; rename.onclick = () => this.guard(() => { const text = prompt('Part name', node.name); if (text !== null) { this.doc.edit('Rename part', () => this.doc.rename(node.id, text)); this.save(); } });
      const imported = this.doc.source.initialParts?.some(p => p.id === node.id && p.partSource === node.partSource);
      const needsUndo = node.closed === false && !imported;
      const toggle = document.createElement('button'); toggle.textContent = node.excluded ? needsUndo ? 'Use Undo split' : 'Restore' : 'Exclude'; toggle.disabled = node.id === 'original' || (node.excluded && needsUndo); toggle.onclick = () => this.guard(() => this.toggleExcluded(node));
      row.append(name, status, rename, toggle); list.append(row);
    }
    $('partsUndo').disabled = !this.doc.data.history.length; $('partsToiletExamples').hidden = this.doc.source.id !== 'toilet';
    const chosen = this.selectedParts();
    $('partsUndoEdit').disabled = this.doc.editIndex === 0; $('partsRedoEdit').disabled = this.doc.editIndex >= this.doc.edits.length;
    $('partsWork').disabled = chosen.length !== 1 || chosen[0].excluded;
    $('partsExcludeSelected').disabled = !chosen.some(n => !n.excluded && n.id !== 'original');
    $('partsKeepSelected').disabled = !chosen.some(n => !n.excluded) || leaves.length < 2;
    $('partsRestoreAll').disabled = !leaves.some(n => n.excluded && (n.closed !== false || this.doc.source.initialParts?.some(p => p.id === n.id)));
    const scope = this.generationScope(), opensPart = scope.node && scope.node.id !== (this.active || 'original');
    $('partsWorkStatus').textContent = opensPart && scope.enabled ? `Selected: ${scope.node.name}. Generate selected uses the displayed target and this part's saved guides. Work on selected opens it for editing.` : this.active ? `Working: ${this.doc.data.nodes[this.active]?.name}. ${this.context ? 'Assembly context shown.' : 'Other parts hidden.'}` : `${chosen.length} selected · ${leaves.filter(n => !n.excluded).length} included. Select one part to generate or edit.`;
    this.h.disableGenerate(!scope.enabled);
    $('generateButton').title = scope.enabled ? `Generate ${scope.node.name}${opensPart ? ' using the displayed target and its saved guides' : ''}` : scope.reason;
    $('generateButton').querySelector('span').textContent = opensPart ? 'Generate selected' : 'Generate';
    const canSplit = !this.active ? !this.doc.data.nodes.original.children : !this.doc.data.nodes[this.active]?.children && !this.doc.data.nodes[this.active]?.excluded;
    for (const id of ['partsPreviewFaces', 'partsPreviewPlane', 'partsPaint', 'partsHandle']) $(id).disabled = !canSplit;
    $('partsStatus').textContent = this.active ? this.current.repair?.closed === false ? this.canRemesh() ? 'Editing an original open part. Generate preserves its boundaries; no caps are added.' : 'This cut region has no independent generation route. Undo its split to restore it.' : 'Editing one part. Other accepted results are retained.' : leaves.length > 1 ? 'Original reference. Select a part to continue working.' : 'Split the original to begin. Changes are reversible.';
  }
  index() {
    if (!this.current) return;
    const m = this.current; this.centers = m.faces.map(face => face.reduce((p, i) => p.map((x, k) => x + m.vertices[i][k] / face.length), [0, 0, 0]));
    this.adj = m.faces.map(() => []); const edges = new Map(); this.triFaces = [];
    m.faces.forEach((face, i) => { for (let j = 1; j < face.length - 1; j++) this.triFaces.push(i); for (let j = 0; j < face.length; j++) { const a = face[j], b = face[(j + 1) % face.length], key = a < b ? `${a}:${b}` : `${b}:${a}`; if (edges.has(key)) { const k = edges.get(key); this.adj[i].push(k); this.adj[k].push(i); } else edges.set(key, i); } });
    this.planeBounds();
  }
  planeBounds() {
    if (!this.current) return;
    const axis = +$('partsAxis').value, coordinates = this.current.vertices.map(p => p[axis]);
    const min = Math.min(...coordinates), max = Math.max(...coordinates);
    $('partsPlaneRange').min = min; $('partsPlaneRange').max = max;
    let value = +$('partsPlaneValue').value; if (value <= min || value >= max) value = (min + max) / 2;
    $('partsPlaneRange').value = $('partsPlaneValue').value = value.toFixed(4); this.renderMarkers();
  }
  pointer(e) {
    if (!this.paint || this.pending || this.previewData || this.h.busy() || this.h.navigating() || e.button > 0) return false;
    if (this.h.paneAt(e.clientX) !== 0) return true;
    const hit = this.h.hit(e.clientX, e.clientY, 0); if (!hit) return true;
    const radius = +$('partsBrush').value, candidates = [], projected = this.h.projectPoints(this.centers);
    for (let i = 0; i < this.centers.length; i++) {
      const p = projected[i];
      if (p.z < 1 && Math.hypot(p.x - e.clientX, p.y - e.clientY) <= radius) candidates.push([i, p]);
    }
    candidates.push([this.triFaces[hit.faceIndex], { x: e.clientX, y: e.clientY }]);
    for (const [i, p] of candidates) {
      const visible = this.h.hit(p.x, p.y, 0);
      if (visible && this.triFaces[visible.faceIndex] === i) { if (e.altKey) this.selected.delete(i); else this.selected.add(i); }
    }
    this.selectionChanged(); return true;
  }
  expand(shrink) {
    const next = new Set(this.selected);
    for (const i of this.selected) for (const neighbor of this.adj[i]) if (shrink && !this.selected.has(neighbor)) next.delete(i); else if (!shrink) next.add(neighbor);
    this.selected = next; this.selectionChanged();
  }
  selectionChanged() { $('partsSelectedCount').textContent = `${this.selected.size.toLocaleString()} faces selected`; this.renderMarkers(); }
  handleSelection() {
    this.selected = new Set(this.centers.flatMap((p, i) => p[0] > .55 && p[2] > .48 && p[2] < .74 && p[1] > .69 && p[1] < .84 ? [i] : []));
    $('partsName').value = 'Flush handle'; $('partsExclude').checked = true; this.selectionChanged();
  }
  escape() {
    if (this.pending) { ++this.ticket; this.pending = false; $('partsStatus').textContent = 'Part preview cancelled.'; return true; }
    if (this.previewData) { this.cancelPreview(); return true; }
    if (this.paint) { this.paint = false; $('partsPaint').setAttribute('aria-pressed', false); return true; }
    return false;
  }
  async preview(plane) {
    const node = this.active ? this.doc.data.nodes[this.active] : this.doc.data.nodes.original;
    if (node.children || node.excluded) throw new Error('Choose an included working part first.');
    const request = { meshId: this.doc.source.id, sourceSha256: this.doc.source.sourceSha256, ...(node.partSource ? { partSource: node.partSource } : {}), exclude: $('partsExclude').checked };
    if (plane) request.plane = { axis: +$('partsAxis').value, value: +$('partsPlaneValue').value }; else request.selectedFaces = [...this.selected].sort((a, b) => a - b);
    const ticket = this.ticket; this.pending = true; $('partsStatus').textContent = 'Preparing and checking repair boundaries…';
    try {
      const response = await this.h.api('/api/parts/split', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(request) });
      if (ticket !== this.ticket) return;
      this.previewData = { ...response, parent: node.id, name: $('partsName').value || 'New part', exclude: request.exclude };
      this.paint = false; $('partsPaint').setAttribute('aria-pressed', false); this.h.sourceVisible(false);
      this.clearGroup(this.groups[0]); this.addMesh(response.remainder, this.groups[0], 0xbac9dc, 1); this.addMesh(response.selected, this.groups[0], request.exclude ? 0xc87955 : 0x3975df, .8);
      this.clearGroup(this.markers); this.addCaps(response.remainder); if (response.selected.repair.closed) this.addCaps(response.selected);
      $('partsReview').hidden = false; $('partsReviewText').textContent = `${response.selected.faces.length.toLocaleString()} selected triangles; ${response.remainder.repair.capFaces} repair triangles on the remainder. Blue/orange shows the new part; gold shows repair caps. ${request.exclude ? 'The selected region will be excluded.' : 'Both parts will remain included.'}`;
      this.h.render();
    } finally { this.pending = false; }
  }
  async apply() {
    const p = this.previewData; if (!p) return;
    this.models.set(p.selected.partSource, p.selected); this.models.set(p.remainder.partSource, p.remainder);
    const node = this.doc.split(p.parent, p.selected, p.remainder, p.name, p.exclude); this.save(); this.cancelPreview(); await this.activate(node.id);
  }
  cancelPreview() { this.previewData = null; $('partsReview').hidden = true; this.h.sourceVisible(true); this.renderContext(); this.renderMarkers(); }
  clearGroup(group) { for (const child of [...group.children]) { group.remove(child); child.traverse(o => { o.geometry?.dispose(); o.material?.dispose(); }); } }
  addMesh(mesh, group, color, opacity = .35) {
    const positions = []; for (const face of mesh.faces) for (let j = 1; j < face.length - 1; j++) for (const i of [face[0], face[j], face[j + 1]]) positions.push(...mesh.vertices[i]);
    const g = new THREE.BufferGeometry(); g.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3)); g.computeVertexNormals();
    const solid = new THREE.Mesh(g, new THREE.MeshStandardMaterial({ color, transparent: opacity < 1, opacity, side: THREE.DoubleSide, depthWrite: opacity === 1, roughness: .7, polygonOffset: true, polygonOffsetFactor: -1 })); group.add(solid); return solid;
  }
  addCaps(mesh) {
    if (!mesh.repair?.capFaces) return;
    this.addMesh({ vertices: mesh.vertices, faces: mesh.faces.slice(mesh.repair.capFaceStart) }, this.markers, 0xc59427, .8);
  }
  renderMarkers() {
    if (!this.current || this.previewData) return;
    this.clearGroup(this.markers);
    if ($('partsCaps').checked) this.addCaps(this.current);
    if (this.selected.size) this.addMesh({ vertices: this.current.vertices, faces: [...this.selected].map(i => this.current.faces[i]) }, this.markers, 0x2b76e5, .75);
    if ($('partsSelection').open) {
      const axis = +$('partsAxis').value, box = new THREE.Box3().setFromPoints(this.current.vertices.map(p => new THREE.Vector3(...p))), center = box.getCenter(new THREE.Vector3()); center.setComponent(axis, +$('partsPlaneValue').value);
      const size = box.getSize(new THREE.Vector3()), other = [0, 1, 2].filter(i => i !== axis), coordinates = [];
      for (const [a, b] of [[-1, -1], [1, -1], [1, 1], [-1, 1]]) { const point = center.clone(); point.setComponent(other[0], center.getComponent(other[0]) + a * size.getComponent(other[0]) * .55); point.setComponent(other[1], center.getComponent(other[1]) + b * size.getComponent(other[1]) * .55); coordinates.push(...point.toArray()); }
      const geometry = new THREE.BufferGeometry(); geometry.setAttribute('position', new THREE.Float32BufferAttribute(coordinates, 3)); this.markers.add(new THREE.LineLoop(geometry, new THREE.LineBasicMaterial({ color: 0xb88a22 })));
    }
    this.h.render();
  }
  async renderContext() {
    const ticket = this.ticket, revision = ++this.contextRevision; if (this.previewData || !this.doc) return;
    this.groups.forEach(g => this.clearGroup(g));
    this.h.assemblyFeedback(0);
    const overview = this.viewMode === 'assembly';
    this.h.sourceVisible(!overview && !this.doc.data.nodes[this.active]?.excluded);
    if (!overview && (!this.context || !this.active)) { this.syncSelection(); this.h.render(); return; }
    const nodes = this.doc.leaves().filter(n => !n.excluded && (overview || n.id !== this.active));
    const items = await Promise.all(nodes.map(async n => ({ node: n, source: await this.model(n), result: await this.result(n) })));
    if (ticket !== this.ticket || revision !== this.contextRevision || this.previewData) return;
    this.groups.forEach(g => this.clearGroup(g));
    for (const item of items) {
      let left;
      if (overview) {
        const group = new THREE.Group(); this.groups[0].add(group);
        group.userData.render = this.h.buildPart(item.source, group); left = group.userData.render.solid;
      } else left = this.addMesh(item.source, this.groups[0], 0x8a9aad, .35);
      left.userData.partId = item.node.id;
      if (item.result) { const right = this.addMesh(item.result, this.groups[1], 0x6795ce, 1); right.userData.partId = item.node.id; }
    }
    this.h.assemblyFeedback(items.filter(item => item.result).length);
    this.h.display(); this.syncSelection(); this.h.render();
  }
  async assembly() {
    if (this.active) await this.activate(null, { preserveCamera: true });
    this.viewMode = 'assembly'; this.context = false; $('partsContext').checked = false;
    await this.renderContext(); this.renderList();
  }
  async export() {
    const parts = [];
    for (const node of this.doc.leaves().filter(n => !n.excluded)) {
      if (this.stale(node)) throw new Error(`${node.name} has changed since its accepted output. Generate it again before exporting the assembly.`);
      const source = await this.model(node), result = await this.result(node);
      if (node.result && !result) throw new Error(`${node.name}'s accepted output is unavailable. Restore the local run or generate this part again.`);
      const imported = this.doc.source.initialParts?.some(p => p.id === node.id && p.partSource === node.partSource);
      if (!source.repair?.closed && node.partSource && !imported) throw new Error('An included part is open. Undo its split before exporting.');
      parts.push({ name: node.name, mesh: result || source, generated: !!result });
    }
    if (!parts.length) throw new Error('There are no included parts to export.');
    this.h.download(this.doc.source.id + '-assembly.obj', assemblyOBJ(parts));
    this.h.notify(`Exported ${parts.length} separate objects: ${parts.filter(p => p.generated).length} accepted outputs and ${parts.filter(p => !p.generated).length} working sources. Caps retained; seams are not welded.`);
  }
  exportProject() {
    const guides = {}; for (const node of Object.values(this.doc.data.nodes)) { const key = 'retopo-1:' + this.doc.source.id + '--part-' + node.id; const text = localStorage.getItem(key); if (text) guides[node.id] = JSON.parse(text); }
    this.h.download(this.doc.source.id + '-parts.json', JSON.stringify({ ...this.doc.data, guides }, null, 2));
  }
  async importProject() {
    const file = $('partsFile').files[0]; $('partsFile').value = ''; if (!file) return;
    if (file.size > 4000000) throw new Error('The parts file is too large.');
    const ticket = this.ticket, data = JSON.parse(await file.text()), doc = new PartsDocument(this.doc.source, data, () => crypto.randomUUID());
    const validate = async id => {
      const node = doc.data.nodes[id], model = await this.model(node);
      if (node.partSource && (model.baseMeshId !== doc.source.id || model.originalSourceSha256 !== doc.source.sourceSha256)) throw new Error('A prepared part belongs to a different source.');
      if (node.children) for (const childId of node.children) { const child = doc.data.nodes[childId], prepared = await this.model(child); if (prepared.partRecipe.parent !== node.partSource) throw new Error('A child part does not match its recorded parent.'); await validate(childId); }
    };
    await validate(doc.data.root);
    if (ticket !== this.ticket) return;
    this.doc = doc;
    for (const [id, packet] of Object.entries(data.guides || {})) if (doc.data.nodes[id]) localStorage.setItem('retopo-1:' + doc.source.id + '--part-' + id, JSON.stringify(packet));
    this.save(); await this.activate(null); this.h.notify('Parts and per-part guide settings loaded. Prepared sources and results are retained in this local project.');
  }
  observe() { return this.doc ? { active: this.active, visibleParts: this.groups[0].children.map(o => o.userData.partId || o.userData.render?.solid.userData.partId).filter(Boolean), selectedParts: this.selectedParts().map(n => n.id), viewMode: this.viewMode, selectedFaces: [...this.selected], preview: !!this.previewData, pending: this.pending, parts: copy(this.doc.leaves()) } : null; }
}
