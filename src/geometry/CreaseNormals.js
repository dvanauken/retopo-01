// Smooth only across shared edges below the crease angle. Coordinates and
// triangle order are unchanged, so source picking keeps its original meaning.
export function creaseNormals(vertices, indices, angleDegrees = 45) {
  const count = indices.length, parent = Int32Array.from({ length: count }, (_, i) => i);
  const positions = new Float32Array(count * 3), normals = new Float32Array(count * 3);
  const areaNormals = [], unitNormals = [], edges = new Map();
  const root = i => { while (parent[i] !== i) { parent[i] = parent[parent[i]]; i = parent[i]; } return i; };
  const join = (a, b) => { parent[root(a)] = root(b); };
  for (let i = 0; i < count; i += 3) {
    const p = indices.slice(i, i + 3).map(id => vertices[id]);
    const a = p[1].map((x, k) => x - p[0][k]), b = p[2].map((x, k) => x - p[0][k]);
    const n = [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]];
    const length = Math.hypot(...n); areaNormals.push(n); unitNormals.push(n.map(x => length ? x / length : 0));
    for (let j = 0; j < 3; j++) {
      positions.set(p[j], (i + j) * 3);
      const a = indices[i + j], b = indices[i + (j + 1) % 3], key = a < b ? `${a}:${b}` : `${b}:${a}`;
      if (!edges.has(key)) edges.set(key, []);
      edges.get(key).push([i + j, i + (j + 1) % 3]);
    }
  }
  const cosine = Math.cos(angleDegrees * Math.PI / 180);
  for (const pair of edges.values()) {
    if (pair.length !== 2) continue;
    const [a, b] = pair, na = unitNormals[Math.floor(a[0] / 3)], nb = unitNormals[Math.floor(b[0] / 3)];
    if (na.reduce((sum, x, k) => sum + x * nb[k], 0) <= cosine) continue;
    for (const corner of a) join(corner, indices[corner] === indices[b[0]] ? b[0] : b[1]);
  }
  const sums = new Float64Array(count * 3);
  for (let i = 0; i < count; i++) {
    const k = root(i) * 3, n = areaNormals[Math.floor(i / 3)];
    for (let j = 0; j < 3; j++) sums[k + j] += n[j];
  }
  for (let i = 0; i < count; i++) {
    const k = root(i) * 3, length = Math.hypot(sums[k], sums[k + 1], sums[k + 2]);
    for (let j = 0; j < 3; j++) normals[i * 3 + j] = length ? sums[k + j] / length : 0;
  }
  return { positions, normals };
}
