// One in-flight projection and one latest request: camera motion cannot flood the worker.
export class VertexSnapIndex {
  constructor(changed = () => {}, createWorker = () => new Worker(new URL('./VertexIndexWorker.js', import.meta.url), { type: 'module' })) {
    this.changed = changed; this.sequence = 0; this.pending = false; this.latest = null; this.cache = null; this.sourceKey = null; this.completed = 0;
    try {
      this.worker = createWorker();
      this.worker.onmessage = ({ data }) => {
        this.pending = false;
        if (!data.error && data.key === this.latest?.key && data.sourceKey === this.sourceKey) {
          this.cache = data; this.completed++; this.changed();
        }
        if (data.error) { this.worker.terminate(); this.worker = null; }
        else this.send();
      };
      this.worker.onerror = () => { this.worker.terminate(); this.worker = null; this.pending = false; this.cache = null; this.changed(); };
    } catch { this.worker = null; }
  }
  setSource(vertices, key) {
    this.sourceKey = key; this.latest = null; this.cache = null;
    if (this.worker) { const copy = Float64Array.from(vertices.flat()); this.worker.postMessage({ type: 'source', vertices: copy, sourceKey: key }, [copy.buffer]); }
  }
  update(snapshot) {
    this.latest = { ...snapshot, sourceKey: this.sourceKey };
    this.send();
  }
  send() {
    if (!this.worker || this.pending || !this.latest || this.cache?.key === this.latest.key) return;
    this.pending = true; this.worker.postMessage({ type: 'project', id: ++this.sequence, ...this.latest });
  }
  nearby(x, y, radius = 12) {
    const cache = this.cache;
    if (!cache || cache.key !== this.latest?.key || cache.sourceKey !== this.sourceKey) return [];
    const candidates = [];
    for (let ix = Math.floor((x - radius) / cache.cellSize); ix <= Math.floor((x + radius) / cache.cellSize); ix++) {
      for (let iy = Math.floor((y - radius) / cache.cellSize); iy <= Math.floor((y + radius) / cache.cellSize); iy++) {
        for (const id of cache.bins.get(`${ix},${iy}`) || []) {
          const distance = Math.hypot(cache.screen[id * 3] - x, cache.screen[id * 3 + 1] - y);
          if (distance <= radius) candidates.push({ vertexId: id, distance });
        }
      }
    }
    return candidates.sort((a, b) => a.distance - b.distance || a.vertexId - b.vertexId);
  }
  get ready() { return !!this.cache && this.cache.key === this.latest?.key && this.cache.sourceKey === this.sourceKey; }
}
