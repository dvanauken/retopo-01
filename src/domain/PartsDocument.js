// A persistent tree of source partitions; accepted outputs belong to one leaf.
export class PartsDocument {
  constructor(mesh, saved = null, idFactory = null) {
    this.source = mesh; this.idFactory = idFactory;
    this.data = saved || { version: 1, sourceSha256: mesh.sourceSha256, meshId: mesh.id, root: 'original', nodes: { original: { id: 'original', name: mesh.title, partSource: null, excluded: false } }, history: [] };
    if (!saved && mesh.initialParts?.length) {
      this.data.nodes.original.children = mesh.initialParts.map(p => p.id);
      for (const part of mesh.initialParts) this.data.nodes[part.id] = { ...part };
    }
    this.validate();
    this.edits = []; this.editIndex = 0;
  }
  validate() {
    const d = this.data;
    if (d.version !== 1 || d.sourceSha256 !== this.source.sourceSha256 || d.meshId !== this.source.id || d.root !== 'original' || !d.nodes || Object.keys(d.nodes).length > 1000 || !Array.isArray(d.history)) throw new Error('This parts project belongs to a different source.');
    const seen = new Set();
    const walk = id => {
      const n = d.nodes[id];
      if (seen.has(id) || !n || n.id !== id || typeof n.name !== 'string' || n.name.length > 80 || typeof n.excluded !== 'boolean' || (n.partSource !== null && !/^[a-f0-9]{64}$/.test(n.partSource))) throw new Error('Invalid parts tree.');
      seen.add(id);
      if (n.children) {
        const imported = id === 'original' && this.source.initialParts?.length;
        if (!Array.isArray(n.children) || (imported ? JSON.stringify(n.children) !== JSON.stringify(this.source.initialParts.map(p => p.id)) : n.children.length !== 2)) throw new Error('Invalid split.');
        n.children.forEach(walk);
      }
    };
    walk(d.root);
    const parents = [...seen].filter(id => d.nodes[id].children && !(id === 'original' && this.source.initialParts?.length));
    if (d.history.length !== parents.length || new Set(d.history).size !== parents.length || d.history.some(id => !parents.includes(id))) throw new Error('Invalid split history.');
    for (const id of parents) for (const child of d.nodes[id].children) if (d.nodes[child].children && d.history.indexOf(child) < d.history.indexOf(id)) throw new Error('Invalid split order.');
  }
  leaves(id = this.data.root) { const n = this.data.nodes[id]; return n.children ? n.children.flatMap(i => this.leaves(i)) : [n]; }
  split(id, selected, remainder, name, exclude) {
    const node = this.data.nodes[id];
    if (!node || node.children) throw new Error('Select a current part before splitting.');
    if (this.leaves().length >= 32) throw new Error('Use at most 32 working parts.');
    if (!this.idFactory) throw new Error('Part creation requires an ID factory.');
    const make = (model, title, excluded) => ({ id: this.idFactory(), name: title.trim().slice(0, 80), partSource: model.partSource, excluded, closed: model.repair.closed });
    const a = make(selected, name || 'Selected part', exclude), b = make(remainder, node.name.endsWith(' remainder') ? node.name : node.name + ' remainder', false);
    node.children = [a.id, b.id]; this.data.nodes[a.id] = a; this.data.nodes[b.id] = b; this.data.history.push(id);
    return exclude ? b : a;
  }
  undoSplit() {
    const id = this.data.history.pop(); if (!id) return null;
    const node = this.data.nodes[id]; delete node.children; return node;
  }
  rename(id, name) { if (!name.trim()) throw new Error('Enter a part name.'); this.data.nodes[id].name = name.trim().slice(0, 80); }
  edit(label, operation) {
    const before = JSON.parse(JSON.stringify(this.data));
    try { operation(); this.validate(); }
    catch (error) { this.data = before; throw error; }
    const changes = [];
    // Inclusion/name commands deliberately leave later accepted output untouched.
    for (const [id, node] of Object.entries(this.data.nodes)) for (const key of ['name', 'excluded']) {
      if (before.nodes[id]?.[key] !== node[key]) changes.push({ id, key, before: before.nodes[id]?.[key], after: node[key] });
    }
    if (changes.length) { this.edits.splice(this.editIndex); this.edits.push({ label, changes }); this.editIndex++; }
  }
  moveEdit(delta) {
    const index = delta < 0 ? this.editIndex - 1 : this.editIndex, edit = this.edits[index];
    if (!edit) return false;
    for (const change of edit.changes) this.data.nodes[change.id][change.key] = change[delta < 0 ? 'before' : 'after'];
    this.editIndex += delta < 0 ? -1 : 1; return true;
  }
  exclude(id) {
    const n = this.data.nodes[id];
    if (n.excluded && n.closed === false && !this.source.initialParts?.some(p => p.id === id && p.partSource === n.partSource)) throw new Error('This excluded region is open. Use Undo split to restore its original attachment.');
    n.excluded = !n.excluded;
  }
}

export function assemblyOBJ(parts) {
  let offset = 1; const lines = ['# Retopo assembly: separate objects in original source coordinates.', '# Repair caps are retained. Objects are not welded.'];
  for (const { name, mesh, generated } of parts) {
    lines.push('o ' + name.replace(/[^\p{L}\p{N}_-]/gu, '_') + (generated ? '_retopo' : '_working_source'));
    for (const point of mesh.vertices) lines.push('v ' + point.join(' '));
    for (const face of mesh.faces) lines.push('f ' + face.map(i => i + offset).join(' '));
    offset += mesh.vertices.length;
  }
  return lines.join('\n') + '\n';
}
