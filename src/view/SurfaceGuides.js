import * as THREE from 'three';
import { flatten, distance } from '../geometry/GuideCurve.js';

export class SurfaceGuides {
  constructor(ports) { this.ports = ports; this.cache = new WeakMap(); this.triangles = []; }
  setSource(mesh) {
    this.cache = new WeakMap(); this.triangles = [];
    const points = mesh.vertices.map(p => new THREE.Vector3(...p));
    for (const face of mesh.faces) for (let i = 1; i < face.length - 1; i++) this.triangles.push(new THREE.Triangle(points[face[0]], points[face[i]], points[face[i + 1]]));
  }
  nearest(position) {
    const point = new THREE.Vector3(...position), candidate = new THREE.Vector3();
    let best = Infinity, result;
    for (const triangle of this.triangles) {
      triangle.closestPointToPoint(point, candidate); const d = candidate.distanceToSquared(point);
      if (d < best) { best = d; result = candidate.toArray(); }
    }
    if (!result || best > .05 ** 2) throw new Error('The curve leaves the source surface. Move its points closer together.');
    return best < 1e-14 ? [...position] : result;
  }
  curve(guide) {
    if (this.cache.has(guide)) return this.cache.get(guide);
    let samples = flatten(guide);
    if (guide.type === 'polyline') {
      const dense = [samples[0]];
      for (let i = 1; i < samples.length; i++) {
        const a = samples[i - 1], b = samples[i], count = Math.max(1, Math.ceil(distance(a, b) / .04));
        if (dense.length + count > 2048) throw new Error('sample-budget-exceeded');
        for (let j = 1; j <= count; j++) dense.push(j === count ? b : a.map((v, k) => v + (b[k] - v) * j / count));
      }
      samples = dense;
    }
    const result = samples.map(p => this.nearest(p));
    this.cache.set(guide, result); return result;
  }
  visible(position, pane) {
    const p = this.ports.project(position, pane);
    if (p.z < -1 || p.z > 1 || !this.ports.inside(p.x, p.y, pane)) return false;
    const hit = this.ports.surface(p.x, p.y, pane);
    return hit && distance(hit, position) < .025;
  }
  handles(selection, pane) {
    if (!this.ports.shown() || selection.model !== 'direct') return [];
    const guide = this.ports.guides().find(g => g.id === selection.activeEntityId);
    if (!guide) return [];
    return guide.points.filter(p => this.visible(p.position, pane)).map(p => ({ guideId: guide.id, pointId: p.id, position: p.position, ...this.ports.project(p.position, pane) }));
  }
  hit(x, y, pane, selection) {
    if (!this.ports.shown()) return null;
    const handles = this.handles(selection, pane);
    for (const h of [...handles].reverse()) if (Math.hypot(h.x - x, h.y - y) <= 8) return h;
    const guides = [...this.ports.guides()].reverse();
    for (const guide of guides) {
      // These endpoints are also painted; hidden points never become hit targets.
      if (!guide.closed) for (const point of [guide.points[0], guide.points.at(-1)]) {
        const p = this.ports.project(point.position, pane);
        if (Math.hypot(p.x - x, p.y - y) <= 8 && this.visible(point.position, pane)) return { guideId: guide.id, pointId: point.id };
      }
      const curve = this.curve(guide);
      for (let i = 1; i < curve.length; i++) {
        const a = this.ports.project(curve[i - 1], pane), b = this.ports.project(curve[i], pane), dx = b.x - a.x, dy = b.y - a.y;
        const u = Math.max(0, Math.min(1, ((x - a.x) * dx + (y - a.y) * dy) / (dx * dx + dy * dy || 1)));
        if (Math.hypot(x - a.x - u * dx, y - a.y - u * dy) > 8) continue;
        const position = curve[i - 1].map((v, k) => v + (curve[i][k] - v) * u);
        if (this.visible(position, pane)) return { guideId: guide.id, pointId: null };
      }
    }
    return null;
  }
  bounds(guide, pane) {
    const p = this.curve(guide).map(v => this.ports.project(v, pane));
    return { left: Math.min(...p.map(v => v.x)), right: Math.max(...p.map(v => v.x)), top: Math.min(...p.map(v => v.y)), bottom: Math.max(...p.map(v => v.y)) };
  }
  contained(a, b, pane) {
    const left = Math.min(a[0], b[0]), right = Math.max(a[0], b[0]), top = Math.min(a[1], b[1]), bottom = Math.max(a[1], b[1]);
    return this.ports.shown() ? this.ports.guides().filter(g => {
      const box = this.bounds(g, pane);
      return box.left >= left && box.right <= right && box.top >= top && box.bottom <= bottom && this.curve(g).some(p => this.visible(p, pane));
    }).map(g => g.id) : [];
  }
}
