import { freeze } from '../contracts/GuideData.js';
import { makeGuide, LIMITS } from '../geometry/GuideCurve.js';

export class GuideDocument {
  #guides = Object.freeze([]); #history = []; #cursor = 0; #counters = new Map(); #listeners = new Set(); #gate = false;
  constructor(idFactory) { if (typeof idFactory !== 'function') throw new Error('An ID factory is required.'); this.idFactory = idFactory; this.epoch = idFactory(); }
  generation = 0;
  get guides() { return this.#guides; }
  get history() { return freeze({ index: this.#cursor, length: this.#history.length, undo: this.#history.slice(0, this.#cursor).map(c => c.label), redo: this.#history.slice(this.#cursor).map(c => c.label) }); }
  get(id) { return this.#guides.find(g => g.id === id); }
  revision(id) { return this.#counters.get(id) ?? 0; }
  subscribe(fn) { this.#listeners.add(fn); return () => this.#listeners.delete(fn); }
  #validate(values) {
    if (!Array.isArray(values) || values.length > LIMITS.guides) throw new Error('Use at most 48 guides.');
    const guides = values.map(makeGuide), ids = guides.map(g => g.id);
    if (new Set(ids).size !== ids.length || guides.reduce((n, g) => n + g.points.length, 0) > LIMITS.samples) throw new Error('Duplicate guide identity or too many guide points.');
    return Object.freeze(guides);
  }
  load(values) {
    if (this.#gate) throw new Error('command-stack-busy');
    const candidate = this.#validate(values);
    this.#guides = candidate; this.#history = []; this.#cursor = 0; this.#counters = new Map(); this.epoch = this.idFactory(); this.generation = 0;
    this.#publish('load');
  }
  execute(label, values, expected = [], epoch = this.epoch) {
    if (this.#gate) throw new Error('command-stack-busy');
    this.#gate = true;
    let changed = false;
    try {
      if (epoch !== this.epoch) throw new Error('The source document changed.');
      for (const { id, revision } of expected) if (!this.get(id) || this.revision(id) !== revision) throw new Error('This guide changed during the edit. Start the edit again.');
      const candidate = this.#validate(values);
      if (JSON.stringify(candidate) === JSON.stringify(this.#guides)) return false;
      const command = freeze({ id: this.idFactory(), label, before: this.#guides, after: candidate });
      this.#install(candidate); this.#history = this.#history.slice(0, this.#cursor); this.#history.push(command); this.#cursor++; changed = true;
    } finally { this.#gate = false; }
    if (changed) this.#publish(label);
    return changed;
  }
  #install(candidate) {
    const ids = new Set([...this.#guides, ...candidate].map(g => g.id)), increments = [];
    for (const id of ids) if (JSON.stringify(this.get(id)) !== JSON.stringify(candidate.find(g => g.id === id))) {
      const next = this.revision(id) + 1;
      if (!Number.isSafeInteger(next)) throw new Error('Guide revision exhausted.');
      increments.push([id, next]);
    }
    if (!Number.isSafeInteger(this.generation + 1)) throw new Error('Document generation exhausted.');
    for (const [id, next] of increments) this.#counters.set(id, next);
    this.#guides = candidate; this.generation++;
  }
  moveHistory(delta) {
    if (this.#gate) throw new Error('command-stack-busy');
    if (![-1, 1].includes(delta) || this.#cursor + delta < 0 || this.#cursor + delta > this.#history.length) return false;
    const c = this.#history[delta < 0 ? this.#cursor - 1 : this.#cursor];
    this.#gate = true;
    try { this.#install(delta < 0 ? c.before : c.after); this.#cursor += delta; } finally { this.#gate = false; }
    this.#publish(delta < 0 ? 'Undo ' + c.label : 'Redo ' + c.label); return true;
  }
  #publish(label) { for (const fn of this.#listeners) fn(freeze({ label, generation: this.generation, epoch: this.epoch })); }
}
