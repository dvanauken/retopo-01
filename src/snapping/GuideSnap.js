// Screen-space soft point snapping. Source attachment is resolved by the caller.
export class GuideSnap {
  constructor(ports) { this.ports = ports; this.prior = null; this.marker = null; }
  clear() { this.prior = null; this.marker = null; }
  resolve(x, y, pane, { excluded = [], bypass = false } = {}) {
    const raw = this.ports.surface(x, y, pane);
    const stamp = this.ports.stamp();
    if (!raw || bypass || (!this.ports.enabled() && !this.ports.verticesEnabled?.())) { this.clear(); return raw; }
    const candidates = [];
    if (this.ports.enabled()) for (const guide of this.ports.guides()) if (!excluded.includes(guide.id)) for (const point of guide.points) {
      const p = this.ports.project(point.position, pane), d = Math.hypot(p.x - x, p.y - y);
      if (d <= 12 && this.ports.visible(point.position, pane)) candidates.push({ kind: 'guide', key: `guide:${guide.id}:${point.id}`, guideId: guide.id, pointId: point.id, position: point.position, distance: d });
    }
    if (this.ports.verticesEnabled?.()) for (const vertex of this.ports.vertices(x, y, pane, this.prior)) {
      if (vertex.distance <= 12) candidates.push({ ...vertex, kind: 'vertex', key: `vertex:${vertex.vertexId}` });
    }
    const retained = this.prior?.stamp === stamp && this.prior.pane === pane && candidates.find(c => c.key === this.prior.key);
    candidates.sort((a, b) => a.distance - b.distance || a.key.localeCompare(b.key));
    const chosen = retained || candidates.find(c => c.distance <= 8);
    if (!chosen) { this.clear(); return raw; }
    this.prior = { ...chosen, pane, stamp }; this.marker = { ...chosen, pane };
    return [...chosen.position];
  }
}
