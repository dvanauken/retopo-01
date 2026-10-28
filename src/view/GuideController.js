import { freeze } from '../contracts/GuideData.js';
import { fromPositions, makeGuide, distance, editPoints } from '../geometry/GuideCurve.js';

// The single guide interaction owner. Browser events, camera and raycaster enter
// only through injected ports; no native event is retained by a Tool activity.
export class GuideController {
  constructor(document, ports) {
    this.document = document; this.ports = ports; this.tool = 'select'; this.selection = freeze({ model: 'object', entityIds: [], activeEntityId: null, pointId: null, revision: 0 });
    this.activity = null; this.construction = null; this.hover = null; this.closureSnap = null; this.temporary = false; this.gate = false; this.activationId = this.ports.id(); this.sequence = 0; this.lastClick = null; this.reports = [];
    document.subscribe(() => { if (!this.gate) this.run(() => this.reconcile()); });
  }
  run(fn) {
    if (this.gate) return false;
    this.gate = true;
    try { return fn(); } catch (error) { this.cancel(); this.report(error.message); return false; }
    finally {
      this.reconcile(); this.gate = false; this.ports.changed();
      // A side-effect-free rejected activation may leave the original drag owned.
      // Its diagnostic waits until that gesture releases native capture.
      if (this.activity?.pointerId === undefined) for (const message of this.reports.splice(0)) this.ports.report(message);
    }
  }
  report(message) { if (this.reports.length < 32) this.reports.push(message); }
  reconcile() {
    const s = this.selection, ids = s.entityIds.filter(id => this.entityExists(id));
    const active = ids.includes(s.activeEntityId) ? s.activeEntityId : ids.at(-1) || null;
    const pointId = active === s.activeEntityId && this.document.get(active) && editPoints(this.document.get(active)).some(p => p.id === s.pointId) ? s.pointId : null;
    this.select(ids, active === s.activeEntityId && active ? s.model : 'object', pointId, active);
    if (this.activity?.epoch && this.activity.epoch !== this.document.epoch) this.cancel();
    if (this.activity?.expected?.some(t => !this.document.get(t.id) || this.document.revision(t.id) !== t.revision)) this.cancel();
  }
  select(ids, model = 'object', pointId = null, active = ids.at(-1) || null) {
    ids = [...new Set(ids)].filter(id => this.entityExists(id));
    if (!ids.includes(active)) active = ids.at(-1) || null;
    if (!active || !this.document.get(active)) model = 'object';
    if (model === 'object') pointId = null;
    const next = { model, entityIds: ids, activeEntityId: active, pointId };
    const { revision, ...old } = this.selection;
    if (JSON.stringify(next) !== JSON.stringify(old)) this.selection = freeze({ ...next, revision: revision + 1 });
  }
  entityExists(id) { return !!this.document.get(id) || !!this.ports.entityExists?.(id); }
  activate(tool) {
    return this.run(() => {
      if (!['draw', 'polyline', 'spline', 'circle', 'select', 'erase', 'orbit'].includes(tool)) throw new Error('Unknown guide tool.');
      if (this.tool === tool && !this.temporary) return;
      this.cancel(); this.temporary = false; this.tool = tool; this.activationId = this.ports.id(); this.lastClick = null;
      if (tool !== 'select') this.select(this.selection.entityIds);
    });
  }
  model(model) {
    return this.run(() => {
      if (!['object', 'direct'].includes(model)) throw new Error('Unknown selection model.');
      if (model === 'direct' && !this.document.get(this.selection.activeEntityId)) return;
      this.cancel(); this.temporary = false; if (this.tool !== 'select') this.activationId = this.ports.id(); this.tool = 'select'; this.lastClick = null; this.select(this.selection.entityIds, model, model === this.selection.model ? this.selection.pointId : null, this.selection.activeEntityId);
    });
  }
  choose(id, toggle = false) {
    return this.run(() => {
      this.cancel(); if (this.tool !== 'select') this.activationId = this.ports.id(); this.tool = 'select'; this.lastClick = null;
      if (toggle) this.toggle(id); else this.select([id]);
    });
  }
  toggle(id) {
    const s = this.selection, ids = s.entityIds.includes(id) ? s.entityIds.filter(v => v !== id) : [...s.entityIds, id];
    this.select(ids, ids.includes(s.activeEntityId) ? s.model : 'object', s.pointId, ids.includes(s.activeEntityId) ? s.activeEntityId : ids.at(-1));
  }
  navigate(enabled) {
    return this.run(() => {
      if (enabled && this.activity?.pointerId !== undefined) { this.report('Finish or cancel the current drag before orbiting.'); return; }
      if (enabled && this.construction?.type === 'circle' && !this.construction.frame) { this.report('Choose a radius on the source plane before orbiting.'); return; }
      this.temporary = enabled; this.hover = null; this.closureSnap = null;
    });
  }
  cancel() {
    const a = this.activity; this.activity = null; this.construction = null; this.hover = null; this.closureSnap = null; this.ports.clearSnap?.();
    if (a?.pointerId !== undefined) this.ports.release(a.pointerId);
  }
  contextLost() {
    return this.run(() => { this.cancel(); this.temporary = false; this.tool = 'select'; this.select(this.selection.entityIds); });
  }
  escape() {
    return this.run(() => {
      if (this.temporary) { this.cancel(); this.temporary = false; this.tool = 'select'; this.select(this.selection.entityIds); }
      else if (this.activity || this.construction) this.cancel();
      else { this.tool = 'select'; this.select(this.selection.entityIds); }
    });
  }
  get drafts() {
    if (this.activity?.kind === 'freehand') return [...this.activity.parts, this.activity.current].filter(p => p.length);
    if (this.construction?.type !== 'circle' && this.construction) return [this.construction.points.map(p => p.position).concat(this.hover ? [this.hover] : [])];
    return [];
  }
  get candidates() { return this.activity?.candidates || []; }
  get constructionGuide() {
    const c = this.construction;
    if (!c) return null;
    if (c.type === 'circle') return c.preview || null;
    if (c.points.length < (this.closureSnap ? 3 : 2)) return null;
    try { return makeGuide({ ...fromPositions(c.points.map(p => p.position).concat(this.hover && !this.closureSnap ? [this.hover] : []), c.type, !!this.closureSnap || c.closed, this.ports.id), id: c.id }); } catch { return null; }
  }
  get editingIds() { return this.activity?.kind === 'edit' && this.activity.moved ? this.activity.baselines.map(g => g.id) : []; }
  observe() {
    return freeze({ tool: this.tool, selection: this.selection, activationId: this.activationId, activityId: this.activity?.id || this.construction?.id || null, pointerId: this.activity?.pointerId ?? null, sequenceId: this.activity?.sequenceId ?? null, temporary: this.temporary, invalid: !!this.activity?.invalid || !!this.construction?.invalid, constructionType: this.construction?.type || null, constructionPreview: this.construction?.preview || null, closureSnap: this.closureSnap ? { ...this.closureSnap, position: [...this.closureSnap.position] } : null, draft: this.drafts.map(part => part.map(p => [...p])), candidates: this.candidates });
  }
  down(e) {
    return this.run(() => {
      if (e.button !== 0 || this.activity || this.temporary || this.tool === 'orbit' || this.ports.busy()) return;
      if (this.tool === 'circle') {
        const pane = this.ports.pane(e.x);
        if (!this.construction) { this.ports.showGuides(); this.construction = { id: this.ports.id(), type: 'circle', pane, epoch: this.document.epoch, screen: [e.x, e.y], frame: this.ports.circleFrame(e.x, e.y, pane), points: [] }; }
        else if (pane === this.construction.pane) { this.update(e); this.finishCurrentConstruction(); }
        return;
      }
      const pane = this.ports.pane(e.x), point = this.resolve(e.x, e.y, pane, e.alt);
      if (['polyline', 'spline'].includes(this.tool)) {
        if (this.findClosure(e.x, e.y, pane)) { this.finishCurrentConstruction(true); return; }
        if (!point) return;
        if (!this.construction) this.construction = { id: this.ports.id(), type: this.tool, pane, epoch: this.document.epoch, closed: this.ports.closed(), points: [] };
        if (this.construction.pane !== pane) return;
        this.ports.showGuides(); this.construction.points.push({ id: this.ports.id(), position: point }); this.hover = null; this.closureSnap = null;
        return;
      }
      const target = this.ports.hit(e.x, e.y, pane, this.selection);
      if (this.tool === 'erase') { if (target) this.removeIds([target.guideId]); return; }
      if (this.tool === 'draw') {
        if (!point) return;
        this.ports.showGuides();
        this.activity = { kind: 'freehand', id: this.ports.id(), pointerId: e.pointerId, sequenceId: ++this.sequence, pane, epoch: this.document.epoch, closed: this.ports.closed(), current: [point], parts: [], previous: [e.x, e.y] };
      } else if (this.tool === 'select') {
        this.activity = { kind: 'selection', id: this.ports.id(), pointerId: e.pointerId, sequenceId: ++this.sequence, pane, press: [e.x, e.y], current: [e.x, e.y], target, shift: e.shift, moved: false, selectionRevision: this.selection.revision, cameraRevision: this.ports.cameraRevision(), epoch: this.document.epoch };
      }
      if (this.activity && !this.ports.capture(e.pointerId)) { this.cancel(); throw new Error('Pointer capture was unavailable; the gesture was canceled.'); }
    });
  }
  resolve(x, y, pane, bypass = false, excluded = []) { return this.ports.resolve ? this.ports.resolve(x, y, pane, { bypass, excluded }) : this.ports.surface(x, y, pane); }
  findClosure(x, y, pane) {
    this.closureSnap = null;
    const c = this.construction, a = this.activity;
    const points = c && c.type !== 'circle' ? c.points.map(p => p.position) : a?.kind === 'freehand' && !a.parts.length ? a.current : [];
    const ownerPane = c?.pane ?? a?.pane;
    if (pane !== ownerPane || points.length < 3) return null;
    const p = this.ports.project(points[0], ownerPane);
    if (this.ports.closureVisible && !this.ports.closureVisible(points[0], ownerPane)) return null;
    const owner = c || a, pixels = Math.hypot(x - p.x, y - p.y);
    if (pixels > 5) owner.closureArmed = true;
    if (owner.closureArmed && pixels <= 5) this.closureSnap = { pane: ownerPane, position: [...points[0]] };
    return this.closureSnap;
  }
  sampleFreehand(e) {
    const a = this.activity, dx = e.x - a.previous[0], dy = e.y - a.previous[1], steps = Math.min(200, Math.ceil(Math.hypot(dx, dy) / 2));
    for (let i = 1; i <= steps; i++) {
      const point = this.resolve(a.previous[0] + dx * i / steps, a.previous[1] + dy * i / steps, a.pane, e.alt);
      if (!point) { if (a.current.length > 1) a.parts.push(a.current); a.current = []; continue; }
      if (!a.current.length || distance(point, a.current.at(-1)) > .001) a.current.push(point);
      if (a.current.length >= 2046) { a.parts.push(a.current); a.current = []; }
    }
    a.previous = [e.x, e.y];
    if (this.findClosure(e.x, e.y, this.ports.pane(e.x))) {
      if (a.current.length > 1 && distance(a.current.at(-1), a.current[0]) < .001) a.current.pop();
      a.current.push([...a.current[0]]);
    }
  }
  startEdit(a) {
    const target = a.target, s = this.selection;
    if (!this.document.get(target.guideId)) return; // Mesh parts have no move-on-surface edit role.
    if (a.shift) return;
    if (target.pointId) this.select(s.model === 'direct' && s.activeEntityId === target.guideId ? s.entityIds : [target.guideId], 'direct', target.pointId, target.guideId);
    else if (!s.entityIds.includes(target.guideId)) this.select([target.guideId], this.document.get(target.guideId)?.type === 'circle' ? 'direct' : 'object');
    const direct = this.selection.model === 'direct' && this.selection.activeEntityId === target.guideId && target.pointId;
    const ids = direct ? [target.guideId] : this.selection.entityIds.filter(id => this.document.get(id));
    a.kind = 'edit'; a.pointId = direct ? target.pointId : null;
    a.baselines = ids.map(id => this.document.get(id)); a.expected = ids.map(id => ({ id, revision: this.document.revision(id) }));
    a.candidates = a.baselines; a.moved = true;
  }
  update(e) {
    const a = this.activity;
    if (!a || a.pointerId !== e.pointerId) {
      const c = this.construction;
      if (c && !this.temporary) {
        if (c.type === 'circle') {
          if (this.ports.pane(e.x) !== c.pane) return;
          try { c.preview = this.ports.circlePreview(c, e.x, e.y); this.ports.curve(c.preview); if (!c.frame) c.frame = { center: [...c.preview.points[0].position], normal: [...c.preview.normal] }; c.invalid = null; }
          catch (error) { c.invalid = error.message; c.preview = null; }
        } else {
          this.hover = this.findClosure(e.x, e.y, this.ports.pane(e.x))?.position || this.resolve(e.x, e.y, c.pane, e.alt);
        }
      }
      return;
    }
    if (a.epoch !== this.document.epoch) return this.cancel();
    if (a.kind === 'freehand') return this.sampleFreehand(e);
    if (a.cameraRevision !== this.ports.cameraRevision()) return this.cancel();
    a.current = [e.x, e.y];
    const delta = [e.x - a.press[0], e.y - a.press[1]];
    if (!a.moved && Math.hypot(...delta) > 4) {
      this.lastClick = null;
      a.moved = true;
      if (a.target) this.startEdit(a); else a.kind = 'marquee';
    }
    if (a.kind !== 'edit') return;
    try {
      a.candidates = a.baselines.map(g => g.type === 'circle' ? (Math.hypot(...delta) === 0 ? g : this.ports.circleEdit(g, a.pointId, delta, a.pane)) : makeGuide({ ...g, points: g.points.map(p => {
        if (a.pointId && p.id !== a.pointId) return p;
        // Offset from the painted point, not the press hit-region edge.
        if (Math.hypot(...delta) === 0) return p;
        const screen = this.ports.project(p.position, a.pane);
        const position = this.resolve(screen.x + delta[0], screen.y + delta[1], a.pane, e.alt, a.baselines.map(g => g.id));
        if (!position) throw new Error('Keep every edited point on the visible source surface.');
        return { ...p, position };
      }) }));
      for (const g of a.candidates) this.ports.curve(g);
      a.invalid = null;
    } catch (error) { a.invalid = error.message; a.candidates = []; }
  }
  move(e) { return this.run(() => this.update(e)); }
  up(e) {
    return this.run(() => {
      const a = this.activity;
      if (!a || a.pointerId !== e.pointerId) return;
      this.update(e);
      if (this.activity !== a) return;
      const proximityClosed = !!this.closureSnap; this.activity = null; this.closureSnap = null; this.ports.release(a.pointerId);
      if (a.kind === 'freehand') {
        const parts = [...a.parts, a.current].filter(p => p.length > 1);
        const guides = parts.map(p => {
          const closed = p.length >= 3 && (proximityClosed || a.closed && this.ports.screenDistance(p[0], p.at(-1), a.pane) <= 5);
          return fromPositions(p, 'polyline', closed, this.ports.id);
        });
        this.accept('Draw guides', [...this.document.guides, ...guides], [], a.epoch); return;
      }
      if (a.kind === 'edit') {
        if (a.invalid) throw new Error(a.invalid);
        const byId = new Map(a.candidates.map(g => [g.id, g]));
        this.accept(a.pointId ? 'Move guide point' : 'Move guides on surface', this.document.guides.map(g => byId.get(g.id) || g), a.expected, a.epoch); return;
      }
      if (a.selectionRevision !== this.selection.revision) return;
      if (a.kind === 'marquee') {
        const ids = this.ports.contained(a.press, a.current, a.pane);
        if (a.shift) this.select([...this.selection.entityIds, ...ids], this.selection.model, this.selection.pointId, this.selection.activeEntityId);
        else this.select(ids);
        return;
      }
      if (a.shift) { this.lastClick = null; if (a.target) this.toggle(a.target.guideId); return; }
      if (!a.target) { this.select([]); this.lastClick = null; return; }
      const double = this.lastClick && this.lastClick.id === a.target.guideId && this.lastClick.pointerType === e.pointerType && e.time - this.lastClick.time <= 400 && Math.hypot(e.x - this.lastClick.x, e.y - this.lastClick.y) <= 6;
      const ownPoint = a.target.pointId && this.selection.model === 'direct' && this.selection.activeEntityId === a.target.guideId;
      this.select(ownPoint ? this.selection.entityIds : [a.target.guideId], a.target.pointId || double || this.document.get(a.target.guideId)?.type === 'circle' ? 'direct' : 'object', a.target.pointId || null, a.target.guideId);
      this.lastClick = { id: a.target.guideId, pointerType: e.pointerType, time: e.time, x: e.x, y: e.y };
    });
  }
  accept(label, guides, expected = [], epoch = this.document.epoch) {
    // Derived geometry, including every spline projection, validates before mutation.
    let count = 0;
    for (const g of guides) count += this.ports.curve(g).length;
    if (count > 8192) throw new Error('Use at most 8192 derived surface samples.');
    return this.document.execute(label, guides, expected, epoch);
  }
  finishConstruction(closed = false) {
    return this.run(() => this.finishCurrentConstruction(closed));
  }
  finishCurrentConstruction(closed = false) {
      const c = this.construction; if (!c) return;
      try {
        if (c.type === 'circle' && !c.preview) throw new Error(c.invalid || 'Choose a positive radius on the source surface.');
        const positions = c.type === 'circle' ? c.preview : fromPositions(c.points.map(p => p.position), c.type, closed || c.closed, this.ports.id);
        const g = c.type === 'circle' ? positions : makeGuide({ ...positions, points: c.points.slice(0, positions.points.length) });
        this.accept('Create ' + c.type + ' guide', [...this.document.guides, g], [], c.epoch);
        this.construction = null; this.hover = null; this.closureSnap = null; // repeat construction remains ready
      } catch (error) { this.report(error.message); } // repairable accepted clicks survive
  }
  backspace() { return this.run(() => { if (this.construction) { this.construction.points.pop(); if (!this.construction.points.length) this.construction = null; } }); }
  removeIds(ids) {
    ids = ids.filter(id => this.document.get(id));
    if (!ids.length) return;
    this.accept('Delete guides', this.document.guides.filter(g => !ids.includes(g.id)), ids.map(id => ({ id, revision: this.document.revision(id) })));
  }
  remove() {
    return this.run(() => {
      this.cancel(); const s = this.selection;
      if (s.model === 'direct' && s.pointId && this.document.get(s.activeEntityId)?.type !== 'circle') {
        const g = this.document.get(s.activeEntityId), after = makeGuide({ ...g, points: g.points.filter(p => p.id !== s.pointId) });
        this.accept('Delete guide point', this.document.guides.map(v => v.id === g.id ? after : v), [{ id: g.id, revision: this.document.revision(g.id) }]);
      } else this.removeIds(s.entityIds);
    });
  }
  radius(value) {
    return this.run(() => {
      const g = this.document.get(this.selection.activeEntityId);
      if (g?.type !== 'circle') return;
      this.cancel(); this.accept('Set Circle radius', this.document.guides.map(v => v.id === g.id ? makeGuide({ ...g, radius: value }) : v), [{ id: g.id, revision: this.document.revision(g.id) }]);
    });
  }
  reverse() {
    return this.run(() => {
      this.cancel(); const ids = this.selection.entityIds.filter(id => this.document.get(id));
      this.accept('Reverse guides', this.document.guides.map(g => ids.includes(g.id) && g.type !== 'circle' ? makeGuide({ ...g, points: [...g.points].reverse() }) : g), ids.filter(id => this.document.get(id)?.type !== 'circle').map(id => ({ id, revision: this.document.revision(id) })));
    });
  }
  history(delta) { return this.run(() => { this.cancel(); this.document.moveHistory(delta); }); }
  replace(guides, label = 'Replace guides') { return this.run(() => { this.cancel(); this.accept(label, guides); }); }
  cancelPointer(pointerId) { return this.run(() => { if (this.activity?.pointerId === pointerId) { const a = this.activity; this.activity = null; this.closureSnap = null; this.ports.release(a.pointerId); } }); }
}
